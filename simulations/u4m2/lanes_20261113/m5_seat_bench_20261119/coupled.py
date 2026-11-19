"""Match the two M5 guides, eight bearing submodels and the loaded nonlinear M5 shell."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from cvxopt import solvers
from scipy import sparse
from scipy.spatial.transform import Rotation

from bench_inputs import COMPONENTS, LANES
from contact import Patch, evaluate
from clearance import CASES, j

sys.path.insert(0, str(LANES / "evening_20261118"))
import pin_seat
from shell import Mesh, Model, SPINS, rotation, skew
from study import (
    CAD_TO_ROD,
    Checkpoints,
    KAPPA,
    LENGTH,
    Solver,
    archive_loads,
    end_pose,
    rotpar,
)
from continuation import transfer_weights

POS_TOL = 0.001
COUPLE_TOL = 0.02
THRUST_SCALE = 0.02  # numerical preconditioner in mm/N for mixed normal equilibrium
TORQUE_SCALE = 0.03  # numerical mixing scale, mm per N mm


def rotation_fit(reference, current):
    ref = reference - reference.mean(0)
    cur = current - current.mean(0)
    u, _, vt = np.linalg.svd(ref.T @ cur)
    correct = np.eye(3)
    correct[2, 2] = np.linalg.det(vt.T @ u.T)
    R = vt.T @ correct @ u.T
    return R, current.mean(0) - R @ reference.mean(0)


def couple_potential(guide, land, coefficient, hessian):
    """Objective equal-and-opposite moments derived from one local relative-rotation potential."""
    G, dG, ddG = guide
    L, dL, ddL = land
    A = coefficient
    energy = -np.sum(A * (G.T @ L))
    grad = -np.r_[
        np.einsum("ij,khi,hj->k", A, dG, L), np.einsum("ij,hi,khj->k", A, G, dL)
    ]
    if not hessian:
        return energy, grad, None
    gg = -np.einsum("ij,abhi,hj->ab", A, ddG, L)
    ll = -np.einsum("ij,hi,abhj->ab", A, G, ddL)
    gl = -np.einsum("ij,ahi,bhj->ab", A, dG, dL)
    return energy, grad, np.block([[gg, gl], [gl.T, ll]])


class SharedGuideModel(Model):
    def __init__(self, mesh):
        super().__init__(mesh, "point")
        self.sites = [
            (i, z) for (i, z), (_, _, mounted) in self.rib_lands.items() if mounted
        ]
        self.nominal_turn = {z: self.turns[f"G{z:+}"][1].copy() for z in j.STATIONS}
        self.which = {}
        self.offsets = np.zeros((len(self.sites), 3))
        self.moments = np.zeros((len(self.sites), 3, 3))
        for i, z in self.sites:
            nodes = self.rib_lands[i, z][0]
            self.which[i, z] = np.isin(self.turns[f"G{z:+}"][0], 6 * nodes)

    def set_interface(self, q, offsets, torques, relatives):
        """Offsets and target moments are expressed in the moving common guide frame."""
        q = q.copy()
        m = self.mesh
        nf = len(self.free) // 8
        for k, (i, z) in enumerate(self.sites):
            tag = f"G{z:+}"
            R = rotation(q[self.bodies[tag].rot])[0]
            nodes = self.rib_lands[i, z][0]
            mask = self.which[i, z]
            self.ref[nodes, :3] = m.xyz[nodes] + offsets[k]
            self.turns[tag][1][mask] = self.nominal_turn[z][mask] + offsets[k]
            weight = m.weights[:, np.flatnonzero(m.patch_names == tag)[0]]
            ids = self.free[i * nf : (i + 1) * nf, :3]
            q[ids] += weight[:, None] * (R @ (offsets[k] - self.offsets[k]))
            self.moments[k] = 0.5 * skew(torques[k]) @ relatives[k]
        self.offsets = offsets.copy()
        return q

    def assemble(self, q, scale=0.0, hessian=True):
        energy, g, K, fields = super().assemble(q, scale, hessian)
        rows = []
        cols = []
        values = []
        for (i, z), A in zip(self.sites, self.moments):
            if not np.any(A):
                continue
            gids = self.bodies[f"G{z:+}"].rot
            lids = self.bodies[f"L{i}_{z}"].rot
            ids = np.r_[gids, lids]
            v, d, H = couple_potential(rotation(q[gids]), rotation(q[lids]), A, hessian)
            energy += v
            g[ids] += d
            if hessian:
                rows.extend(np.repeat(ids, 6))
                cols.extend(np.tile(ids, 6))
                values.extend(H.ravel())
        if hessian and rows:
            K += sparse.coo_matrix((values, (rows, cols)), shape=K.shape).tocsc()
        return energy, g, K, fields


class Interface:
    def __init__(self, model, patch, case, mixed_thrust=False):
        self.mixed_thrust = mixed_thrust
        self.model = model
        self.patch = patch
        self.case = case
        mesh = model.mesh
        self.reference = patch.x[patch.fixed_nodes]
        self.maps = []
        for i, z in model.sites:
            _, centre, _ = model.rib_lands[i, z]
            angle = mesh.theta[i]
            B = Rotation.from_euler("z", angle, degrees=True).as_matrix() @ j.web_axes(
                z
            )
            world = centre + self.reference @ B.T
            nodes, weights, _ = transfer_weights(
                mesh.x, mesh.t, np.c_[world @ mesh.radial[i], world[:, 2]]
            )
            self.maps.append((B, nodes, weights))

    def sample(self, q, scale, *, write_fields=None, strain=False):
        m = self.model
        patch = self.patch
        _, _, _, (x, f, _) = m.assemble(q, scale, False)
        field = x.reshape(8, m.mesh.n, 6)
        answers = []
        errors = []
        torques = []
        rels = []
        for k, ((i, z), (B, nodes, w)) in enumerate(zip(m.sites, self.maps)):
            ids, centre, _ = m.rib_lands[i, z]
            g = m.bodies[f"G{z:+}"]
            G = rotation(q[g.rot])[0]
            L = rotation(q[m.bodies[f"L{i}_{z}"].rot])[0]
            rel = G.T @ L
            pin = g.centre + q[g.pos] + G @ (centre - g.centre)
            world_axes = G @ B
            ends = np.einsum("ij,ijk->ik", w, field[i, nodes])
            normal = ends[:, 3:]
            normal /= np.linalg.norm(normal, axis=1)[:, None]
            placed = (
                ends[:, :3] + normal * self.reference[:, 2, None] - pin
            ) @ world_axes
            R, cut_origin = rotation_fit(self.reference, placed)
            prescribed = (placed - cut_origin) @ R - self.reference
            lift = patch.lift_ends(prescribed)
            F = f[ids, :3].sum(0)
            Flocal = world_axes.T @ F
            inputs = dict(
                station_mm=z,
                rib_deg=float(m.mesh.theta[i]),
                **dict(zip(COMPONENTS, Flocal)),
            )
            out = (
                None
                if write_fields is None
                else write_fields / f"site_{z}_{m.mesh.theta[i]:g}.npz"
            )
            # Reflection in the bend plane fixes the through-thickness translation of an in-plane rib.
            # Recover its normal reaction from contact, and compare all three forces with the shell.
            symmetric = (
                self.case == "bend67.5"
                and abs(np.cos(np.radians(m.mesh.theta[i] - 67.5))) < 1e-8
            )
            sim = evaluate(
                patch,
                inputs,
                out,
                relative_matrix=R,
                background=lift,
                recover_strain=strain,
                normal_translation=float(cut_origin[2])
                if symmetric or self.mixed_thrust
                else None,
            )
            sim["mirror_plane_normal_translation_prescribed"] = bool(symmetric)
            sim["mixed_thrust_equilibrium"] = self.mixed_thrust
            reaction = np.sum(
                [v["resultant_spn_N"] for v in sim["contact_components"].values()],
                axis=0,
            )
            mismatch = reaction - Flocal
            prescribed_error = (
                np.linalg.norm(mismatch[:2])
                if self.mixed_thrust
                else sim["force_residual_N"]
            )
            if not sim["converged"] or prescribed_error > 0.005:
                raise ValueError(
                    f"Local contact failed at {i}, {z}: residual {sim['force_residual_N']}"
                )
            t = np.array(sim["relative_translation_spn_mm"])
            diff = B @ (t - cut_origin)
            # Translate the bearing moment from the nominal pin to the shell's displaced ring centre.
            target = B @ sim["contact_moment_about_pivot_spn_Nmm"] - np.cross(
                m.offsets[k], G.T @ F
            )
            used = np.einsum("ij,kij->k", m.moments[k], SPINS @ rel)
            ring = pin + G @ m.offsets[k]
            actual_tau = (
                np.cross(x[ids, :3] - ring, f[ids, :3])
                + np.cross(x[ids, 3:], f[ids, 3:])
            ).sum(0)
            # In mixed control the cut's normal coordinate is prescribed on the solid.
            # Match its recovered normal reaction to the shell by adjusting the shell ring offset.
            update = t - cut_origin
            if self.mixed_thrust:
                update[2] = THRUST_SCALE * mismatch[2]
            errors.append(B @ update)
            torques.append((used, target))
            rels.append(rel)
            answers.append(
                dict(
                    station=z,
                    rib_deg=float(m.mesh.theta[i]),
                    force_world_N=F.tolist(),
                    offset_guide_mm=m.offsets[k].tolist(),
                    cut_frame_in_pin_mm=cut_origin.tolist(),
                    fit_rotation_xyzw=Rotation.from_matrix(R).as_quat().tolist(),
                    cut_face_nonrigid_max_mm=float(
                        np.linalg.norm(prescribed, axis=1).max()
                    ),
                    translation_residual_mm=float(np.linalg.norm(diff)),
                    moment_residual_Nmm=float(np.linalg.norm(target - used)),
                    shell_ring_moment_balance_Nmm=float(
                        np.linalg.norm(G.T @ actual_tau - used)
                    ),
                    contact=sim,
                )
            )
        return np.array(errors), np.array(torques), np.array(rels), answers


def write_json(path, data):
    temp = path.with_suffix(".part")
    temp.write_text(json.dumps(data, indent=2) + "\n")
    temp.replace(path)


def shared_rod_loads(folder, record, previous):
    """Transfer both M5 guide loads and the end-disk pose from one rebalanced eight-cell state."""
    import hashlib

    sys.path.insert(0, str(LANES / "shared_bore_20261119"))
    from shared_bore import RAYS, load_rod

    _, rod, _ = load_rod()
    fields = folder / "rebalanced_states.npz"
    holes = folder / "guide_hole_loads.npz"
    with (
        np.load(fields, allow_pickle=False) as st,
        np.load(holes, allow_pickle=False) as data,
    ):
        i = int(np.flatnonzero(st["hold_id"] == record).item())
        jh = int(np.flatnonzero(data["hold"] == record).item())
        _, _, detail = rod.evaluate(st["z"][i], st["tensions_n"][i], detail=True)
        f = detail["frames"]
        base_frame = f[32] @ CAD_TO_ROD
        entries = []
        summary = []
        for old, node, station in zip(
            previous["loads"], (35, 37), (-12, 12), strict=True
        ):
            ids = np.flatnonzero(
                (data["hole_module"] == "M5") & (data["station_mm"] == station)
            )
            if len(ids) != 8:
                raise ValueError("Expected the eight B/C holes on each M5 inner guide")
            offsets = np.array(
                [
                    1000 * CAD_TO_ROD.T @ rod.offsets3["ABC".index(k), RAYS.index(ray)]
                    for k, ray in zip(data["family"][ids], data["ray"][ids])
                ]
            )
            if not np.allclose(offsets, old[1], atol=1e-9, rtol=0):
                raise ValueError(
                    "Hole labels or positions differ from the archived guide"
                )
            R = base_frame.T @ f[node] @ CAD_TO_ROD
            fm = data["hole_wrench_CAD"][jh, ids] @ R.T
            if not np.allclose(
                np.cross(offsets @ R.T, fm[:, 0]), fm[:, 1], atol=1e-8, rtol=0
            ):
                raise ValueError("Station load transformation changes a bore moment")
            entries.append((old[0], offsets, fm[:, 0]))
            summary.append(
                dict(
                    station=station,
                    eight_forces_in_M5_base_N=fm[:, 0].tolist(),
                    total_force_N=fm[:, 0].sum(axis=0).tolist(),
                    total_moment_Nmm=fm[:, 1].sum(axis=0).tolist(),
                    maximum_per_hole_force_change_N=float(
                        np.linalg.norm(fm[:, 0] - old[2], axis=1).max()
                    ),
                )
            )
        target = end_pose({"cells": detail["q"][32:40]}, 1.0)
        direct_R = base_frame.T @ f[40] @ CAD_TO_ROD
        delta = base_frame.T @ (
            1000 * (detail["points"][40] - detail["points"][32])
        ) - [0, 0, 96]
        if not np.allclose(target, np.r_[delta, rotpar(direct_R)], atol=1e-7, rtol=0):
            raise ValueError("Disk pose reconstruction differs from the rebalanced rod")
        evidence = dict(
            method="One-way transfer from solved shared-bore state",
            state=record,
            SHA256={
                v.name: hashlib.sha256(v.read_bytes()).hexdigest()
                for v in (fields, holes)
            },
            disk_translation_change_mm=float(
                np.linalg.norm(delta - previous["displacement_mm"])
            ),
            disk_rotation_change_deg=float(
                np.degrees(
                    Rotation.from_matrix(direct_R @ previous["rotation"].T).magnitude()
                )
            ),
            stations=summary,
        )
        return target, entries, evidence


def solve_case(mesh, patch, case, seed, args, records):
    m = SharedGuideModel(mesh)
    S = Solver(m)
    cp = Checkpoints(m, case, None, seed)
    q, M = cp.load(1.0)
    if case.isdecimal():
        pure = None
        scale = 1.0
        m.external = records[int(case)]["loads"]
        target = end_pose(records[int(case)], 1.0)
    else:
        a = np.radians(float(case[4:]))
        pure = np.array([np.cos(a), np.sin(a), 0])
        target = np.tan(KAPPA * LENGTH / 2)
        scale = 0.0
    q, M, _, _ = S.step(q, M, pure, target, scale)
    base_q = q.copy()
    base_M = M
    source = (
        LANES
        / "evening_20261118/pin_seat/pin_r0p30"
        / f"results_{args.tag}"
        / f"point_{case}.json"
    )
    baseline = json.loads(source.read_text())["samples"][-1]
    base_forces = {
        (v["station_mm"], v["rib_deg"]): np.array(v["force_N"])
        for v in baseline["lands"]
    }
    _, _, _, (_, base_nodal_forces, _) = m.assemble(base_q, scale, False)
    source_error = max(
        np.linalg.norm(
            base_nodal_forces[m.rib_lands[i, z][0], :3].sum(0)
            - base_forces[z, float(mesh.theta[i])]
        )
        for i, z in m.sites
    )
    if source_error > 0.005:
        raise ValueError(f"Inconsistent source reaction {source_error:g} N")
    boundary_evidence = None
    if args.shared_results is not None:
        if not case.isdecimal():
            raise ValueError(
                "A shared-bore boundary condition requires a saved winch state"
            )
        target, m.external, boundary_evidence = shared_rod_loads(
            args.shared_results, int(case), records[int(case)]
        )
        q, M, _, _ = S.step(q, M, pure, target, scale)
        base_q, base_M = q.copy(), M
        _, _, _, (_, updated, _) = m.assemble(base_q, scale, False)
        base_forces = {
            (z, float(mesh.theta[i])): updated[m.rib_lands[i, z][0], :3].sum(axis=0)
            for i, z in m.sites
        }
    interface = Interface(m, patch, case, args.mixed_thrust)
    out = args.out / f"{case}.json"
    hist = []
    xs = []
    fs = []
    summary = dict(
        case=case,
        shell_area_mm2=args.area,
        solid_mesh=args.level,
        angular_and_cut_face_boundary_coupled=True,
        maximum_reconstructed_force_error_N=float(source_error),
        reference_pin_reactions="evening_20261118/pin_seat/pin_r0p30",
        criteria=dict(translation_mm=POS_TOL, moment_Nmm=COUPLE_TOL, force_N=0.005),
        thrust_equilibrium="prescribed axial displacement with reaction matching"
        if args.mixed_thrust
        else "force with reflection-plane exception",
        status="running",
        history=hist,
    )
    if boundary_evidence is not None:
        summary["shared_rod_boundary"] = boundary_evidence
        summary["reference_pin_reactions"] = (
            "Ideal pin model recalculated at the transferred disk pose and per-hole forces"
        )
    state = np.zeros((2, len(m.sites), 3))
    work = args.fields / case
    work.mkdir(parents=True, exist_ok=True)
    start = args.restart / case / "restart.npz" if args.restart else None
    if args.restart and not start.is_file():
        raise FileNotFoundError(start)
    if start and start.exists():
        with np.load(start) as d:
            if (
                str(d["solid_mesh"]) != args.level
                or float(d["shell_area"]) != args.area
            ):
                raise ValueError("Restart mesh differs")
            m.set_interface(q, d["offsets"], d["moments"], d["relatives"])
            q = d["q"]
            M = float(d["M"])
    elif args.warm_interfaces:
        with np.load(args.warm_interfaces / case / "restart.npz") as d:
            q = m.set_interface(q, d["offsets"], d["moments"], d["relatives"])
    it = 0
    try:
        for it in range(args.iterations + 1):
            q, M, nsteps, res = S.step(q, M, pure, target, scale)
            dt, tm, rel, sites = interface.sample(q, scale)
            state = np.stack((m.offsets, tm[:, 0] * TORQUE_SCALE))
            resid = np.stack((dt, (tm[:, 1] - tm[:, 0]) * TORQUE_SCALE))
            pt = max(site["translation_residual_mm"] for site in sites)
            ft = max(site["contact"]["force_residual_N"] for site in sites)
            mt = float(np.linalg.norm(tm[:, 1] - tm[:, 0], axis=1).max())
            hist.append(
                dict(
                    iteration=it,
                    shell_iterations=nsteps,
                    shell_equilibrium_residual=float(res),
                    maximum_translation_mismatch_mm=pt,
                    maximum_contact_force_mismatch_N=ft,
                    maximum_moment_mismatch_Nmm=mt,
                )
            )
            summary.update(last_sites=sites, iterations=it)
            write_json(out, summary)
            np.savez_compressed(
                work / "restart.npz",
                q=q,
                M=M,
                offsets=m.offsets,
                moments=tm[:, 0],
                relatives=rel,
                shell_area=args.area,
                solid_mesh=args.level,
            )
            print(
                case,
                it,
                "mm",
                round(pt, 6),
                "N mm",
                round(mt, 6),
                "shell",
                round(res, 8),
                flush=True,
            )
            if pt < POS_TOL and mt < COUPLE_TOL and ft < 0.005:
                break
            # Damped multi-secant mixing of the eight positions and reaction couples.
            x = state.ravel()
            f = resid.ravel()
            xs.append(x.copy())
            fs.append(f.copy())
            step = 0.65 * f
            if len(xs) > 1:
                DX = np.diff(np.stack(xs[-6:]), axis=0).T
                DF = np.diff(np.stack(fs[-6:]), axis=0).T
                coeff = np.linalg.lstsq(DF, f, rcond=0.002)[0]
                step -= (DX + 0.65 * DF) @ coeff
            delta = step.reshape(state.shape)
            max_step = np.max(np.linalg.norm(delta, axis=2))
            delta *= min(1.0, 0.12 / max(max_step, 1e-12))
            new = state + delta
            q = m.set_interface(q, new[0], new[1] / TORQUE_SCALE, rel)
        else:
            summary["status"] = "iteration limit"
            write_json(out, summary)
            return False
        dt, tm, rel, sites = interface.sample(q, scale, write_fields=work, strain=True)
        x = m.mapping(q)[0].reshape(8, mesh.n, 6)
        poses = {}
        shifts = {}
        for z in j.STATIONS:
            b = m.bodies[f"G{z:+}"]
            G = rotation(q[b.rot])[0]
            G0 = rotation(base_q[b.rot])[0]
            poses[f"R{z}"] = G
            poses[f"C{z}"] = b.centre + q[b.pos]
            holes = np.array(
                [
                    [r * np.cos(a), r * np.sin(a), 0]
                    for r in (24, 28)
                    for a in np.radians([0, 90, 180, 270])
                ]
            )
            d = q[b.pos] - base_q[b.pos]
            u = (G - G0) @ holes.T + d[:, None]
            shifts[str(z)] = dict(
                translation_world_mm=d.tolist(),
                rotation_deg=float(
                    np.degrees(Rotation.from_matrix(G @ G0.T).magnitude())
                ),
                maximum_bore_shift_mm=float(np.linalg.norm(u, axis=0).max()),
            )
        endpoint_error = (
            float(np.max(np.abs(target - q[m.end])))
            if pure is None
            else float(abs(target - pure @ q[m.end[3:]]))
        )
        np.savez_compressed(
            work / "shell.npz",
            fields=x,
            **poses,
            residual=res,
            endpoint_constraint_residual=endpoint_error,
        )
        summary["endpoint_constraint_residual"] = endpoint_error
        summary.update(
            status="converged",
            last_sites=sites,
            guide_changes_from_ideal=shifts,
            maximum_site_force_change_N=float(
                max(
                    np.linalg.norm(
                        np.array(v["force_world_N"])
                        - base_forces[v["station"], v["rib_deg"]]
                    )
                    for v in sites
                )
            ),
            end_translation_change_mm=float(
                np.linalg.norm(q[m.bodies["D1"].pos] - base_q[m.bodies["D1"].pos])
            ),
            baseline_fixture_couple_Nmm=float(base_M),
            fixture_couple_Nmm=float(M),
        )
        write_json(out, summary)
        return True
    except (ArithmeticError, RuntimeError, ValueError) as err:
        summary.update(status="failed", error=str(err))
        write_json(out, summary)
        print(case, "FAILED", err, flush=True)
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--area", type=float, choices=(0.055, 0.025), default=0.055)
    p.add_argument("--level", choices=("middle", "fine"), default="middle")
    p.add_argument("--cases", nargs="+", choices=CASES, required=True)
    p.add_argument("--seed", type=Path, required=True)
    p.add_argument("--fields", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--shared-results",
        type=Path,
        help="Use the rebalanced eight-cell disk pose and per-hole loads for saved winch cases.",
    )
    p.add_argument("--iterations", type=int, default=20)
    p.add_argument(
        "--mixed-thrust",
        action="store_true",
        help="Match recovered normal force while the solid follows the shell cut in the pin direction.",
    )
    seed_mode = p.add_mutually_exclusive_group()
    seed_mode.add_argument("--restart", type=Path)
    seed_mode.add_argument("--warm-interfaces", type=Path)
    a = p.parse_args()
    a.tag = str(a.area).replace(".", "p")
    a.out.mkdir(parents=True, exist_ok=True)
    a.fields.mkdir(parents=True, exist_ok=True)
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    pin_seat.install(0.30)
    mesh = Mesh(a.area)
    patch = Patch(a.level, 2.7, fit_relief=True, prescribed_ends=True)
    np.savez_compressed(
        a.fields / "patch_mesh.npz",
        x=patch.x,
        q=patch.hex,
        level=a.level,
        length=2.7,
        crown=j.CROWN_RADIUS,
        fit_relief=True,
    )
    np.savez_compressed(
        a.fields / "shell_mesh.npz", x=mesh.x, t=mesh.t, theta=mesh.theta
    )
    records = archive_loads() if any(c.isdecimal() for c in a.cases) else {}
    ok = [solve_case(mesh, patch, c, a.seed, a, records) for c in a.cases]
    if not all(ok):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
