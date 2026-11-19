"""Run the proposed M5 bending and installed-load cases. Units are N, mm, radians."""

import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.spatial.transform import Rotation

from continuation import Checkpoints, interpolate
from shell import Mesh, Model, rotation, spin_map

HERE = Path(__file__).resolve().parent
LANES = HERE.parent
SAVED = LANES / "morning_20261116"
ARCHIVE = SAVED / "fixed_winch_holds/equilibria_states.npz"
HOLES = SAVED / "rigid_end_audit/guide_holes.csv"
STATIONS_CSV = SAVED / "rigid_end_audit/guide_stations.csv"
KAPPA = 0.01748791036298669
LENGTH = 96.0
TOL = 3.0e-5
CAD_TO_ROD = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
CASES = (146, 141, 47, 64)


def rotpar(R):
    quat = Rotation.from_matrix(R).as_quat()
    if abs(quat[3]) < 1.0e-5:
        raise ValueError("Orientation is outside the Gibbs chart")
    return quat[:3] / quat[3]


def archive_loads():
    import lanes
    from bellmouth_model import apply_bellmouth
    from state_archives import load_states

    mass = json.loads((ARCHIVE.parent / "mass_model.json").read_text())
    lanes.install((21.0, 24.0, 28.0), 24.0, mass)
    design = json.loads((LANES / "../../../cad/lanes_u4m2/end_bellmouth_v1/design.json").read_text())
    rod = apply_bellmouth(lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8), design)
    states, _ = load_states(ARCHIVE)
    with HOLES.open() as f:
        holes = list(csv.DictReader(f))
    with STATIONS_CSV.open() as f:
        stations = list(csv.DictReader(f))
    archive = {}
    for record in CASES:
        label, z, t, _ = states[record]
        if int(label) != record:
            raise ValueError("Archive state ID mismatch")
        _, _, detail = rod.evaluate(z, t, detail=True)
        frame = detail["frames"][32] @ CAD_TO_ROD
        pos = detail["points"]
        R1 = frame.T @ detail["frames"][40] @ CAD_TO_ROD
        disp = frame.T @ (1000.0 * (pos[40] - pos[32])) - [0.0, 0.0, 96.0]
        loads, checks, stations_detail = [], [], []
        for st, node in ((-12, 35), (12, 37)):
            match = lambda row: (
                row["module"] == "M5" and int(row["state"]) == record and float(row["station_z_mm"]) == st
            )
            rows = [r for r in holes if match(r)]
            if len(rows) != 8 or len({(r["set"], r["ray"]) for r in rows}) != 8:
                raise ValueError("Incomplete per-hole load frame")
            F = np.array([frame.T @ json.loads(r["force_base_n"]) for r in rows])
            offsets = np.array(
                [
                    1000.0
                    * CAD_TO_ROD.T
                    @ rod.offsets3["ABC".index(r["set"]), ("up", "right", "down", "left").index(r["ray"])]
                    for r in rows
                ]
            )
            Rg = frame.T @ detail["frames"][node] @ CAD_TO_ROD
            moments = np.cross(offsets @ Rg.T, F)
            row = next(r for r in stations if match(r))
            ferr = np.linalg.norm(F.sum(0) - frame.T @ json.loads(row["force_base_n"]))
            merr = np.linalg.norm(moments.sum(0) - frame.T @ json.loads(row["moment_base_nmm"]))
            hole_err = max(
                np.linalg.norm(v - frame.T @ json.loads(h["moment_base_nmm"]))
                for v, h in zip(moments, rows)
            )
            if max(ferr, merr, hole_err) > 1.0e-8:
                raise ValueError("Archived bore load transformation failed")
            checks.append(
                dict(
                    station_mm=st,
                    holes=len(rows),
                    force_error_N=ferr,
                    moment_error_Nmm=merr,
                    per_hole_moment_error_Nmm=hole_err,
                    force_N=F.sum(0),
                    moment_Nmm=moments.sum(0),
                )
            )
            stations_detail.append(
                dict(
                    station_mm=st,
                    centre_in_proximal_axes_mm=frame.T @ (1000.0 * (pos[node] - pos[32]))
                    + [0.0, 0.0, -48.0],
                    guide_frame_in_proximal_axes=Rg,
                    holes=[
                        dict(
                            rope_set=r["set"],
                            ray=r["ray"],
                            offset_in_guide_mm=off,
                            force_in_proximal_axes_N=force,
                            moment_at_archived_guide_centre_Nmm=torque,
                        )
                        for r, off, force, torque in zip(rows, offsets, F, moments)
                    ],
                )
            )
            loads.append((f"G{st:+}", offsets, F))
        cells = detail["q"][32:40].copy()
        target = dict(
            displacement_mm=disp,
            rotation=R1,
            cells=cells,
            loads=loads,
            checks=checks,
            stations_detail=stations_detail,
            source_frame=frame,
        )
        if np.max(np.abs(end_pose(target, 1.0) - np.r_[disp, rotpar(R1)])) > 1.0e-7:
            raise ValueError("Continuation endpoint differs from archived disk pose")
        archive[record] = target
    return archive


def end_pose(data, fraction):
    """Ramp each archived intrinsic cell strain and integrate the resulting SE(3) pose."""
    p = np.zeros(3)
    R = np.eye(3)
    nodes, weights = np.polynomial.legendre.leggauss(4)
    for cell in fraction * data["cells"]:
        phi = np.array([cell[0], -cell[2], cell[1]])
        direction = (weights / 2) @ Rotation.from_rotvec((nodes + 1.0)[:, None] * phi / 2).as_matrix()[
            :, :, 0
        ]
        p += 12.0 * (1.0 + cell[3]) * (R @ direction)
        R = R @ Rotation.from_rotvec(phi).as_matrix()
    return np.r_[CAD_TO_ROD.T @ p - [0.0, 0.0, 96.0], rotpar(CAD_TO_ROD.T @ R @ CAD_TO_ROD)]


class Factor:
    """Sparse symmetric LDL for the internal shell coordinates."""

    def __init__(self, A):
        try:
            from cvxopt import cholmod, matrix, spmatrix
        except ImportError:
            self.lu = splu(A, permc_spec="MMD_AT_PLUS_A")
            self.solve = self.lu.solve
            return
        lower = sparse.tril(A, format="coo")
        mat = spmatrix(lower.data, lower.row, lower.col, size=A.shape)
        cholmod.options["supernodal"] = 0
        try:
            self.fact = cholmod.symbolic(mat)
            cholmod.numeric(mat, self.fact)
        except ArithmeticError:
            self.lu = splu(A, permc_spec="MMD_AT_PLUS_A")
            self.solve = self.lu.solve
            return
        self.matrix = matrix
        self.chol = cholmod

    def solve(self, b):
        rhs = self.matrix(np.asfortranarray(b))
        self.chol.solve(self.fact, rhs)
        sol = np.asarray(rhs)
        return sol.ravel() if b.ndim == 1 else sol


def end_work(qend, axis):
    L, dL = spin_map(qend[-3:])
    Q = np.r_[np.zeros(3), L.T @ axis]
    deriv = np.zeros((6, 6))
    deriv[3:, 3:] = np.einsum("i,aij->ja", axis, dL)
    return Q, deriv


class Solver:
    def __init__(self, model):
        self.m = model
        self.inside = np.setdiff1d(np.arange(model.size), np.r_[model.clamp, model.end])

    def step(self, q, moment, pure, target, scale, max_iter=28):
        """Pure bend has a free end force and a spatial couple on the specified axis.

        Its amplitude is an unknown. The prescribed scalar twist about that axis is
        2 atan(axis dot Gibbs vector). Both orthogonal end moments vanish.
        A loaded step instead prescribes all six archived end-disk coordinates.
        """
        m, I, T = self.m, self.inside, self.m.end
        q = q.copy()

        def measure(q, M, g):
            if pure is None:
                mismatch = target - q[T]
                return np.max(abs(g[I])), np.max(abs(mismatch))
            Q, _ = end_work(q[T], pure)
            miss = target - pure @ q[T[3:]]
            return max(np.max(abs(g[I])), np.max(abs(g[T] - M * Q))), abs(miss)

        if m.mesh.minimum_orientation(m.mapping(q)[0]) <= 0.0:
            raise RuntimeError("Initial transferred configuration folds a shell triangle")
        for it in range(max_iter):
            energy, g, K, fields = m.assemble(q, scale)
            if m.mesh.minimum_orientation(fields[0]) <= 0.0:
                raise RuntimeError("Trial configuration folds a shell triangle")
            residual, miss = measure(q, moment, g)
            if residual < TOL and miss < 1.0e-9:
                return q, moment, it, residual
            fac = Factor(K[I][:, I])
            Kie = K[I][:, T].toarray()
            if pure is None:
                de = target - q[T]
                di = fac.solve(-g[I] - Kie @ de)
                dm = 0.0
            else:
                Q, dQ = end_work(q[T], pure)
                response = fac.solve(np.column_stack((-g[I], Kie)))
                zi, Y = response[:, 0], response[:, 1:]
                S = K[T][:, T].toarray() - Kie.T @ Y - moment * dQ
                A = np.zeros((7, 7))
                A[:6, :6] = S
                A[:6, -1] = -Q
                A[-1, 3:6] = pure
                rhs = np.r_[moment * Q - g[T] - Kie.T @ zi, target - pure @ q[T[3:]]]
                sol = np.linalg.solve(A, rhs)
                de, dm = sol[:6], sol[6]
                di = zi - Y @ de
            del fac, K
            dq = np.zeros_like(q)
            dq[I] = di
            dq[T] = de
            # The initial predictor enforces a changed displacement or bending target.
            # Once it is satisfied, backtrack Newton on the free equilibrium residual.
            step = 1.0
            proposal = m.increment(q, dq)
            if miss < 1.0e-8:
                while step >= 1.0 / 128:
                    proposal = m.increment(q, step * dq)
                    vtrial, trial, _, trial_fields = m.assemble(proposal, scale, False)
                    new, trial_miss = measure(proposal, moment + step * dm, trial)
                    work = 0.0 if pure is None else moment * (end_work(q[T], pure)[0] @ de)
                    slope = g @ dq - work
                    descent = slope < 0 and vtrial - step * work <= energy + 1.0e-4 * step * slope
                    if (
                        np.isfinite(new)
                        and m.mesh.minimum_orientation(trial_fields[0]) > 0.0
                        and (descent or new < residual * (1.0 - 1.0e-4 * step) or new < TOL)
                    ):
                        if new < TOL and trial_miss < 1.0e-9:
                            return proposal, moment + step * dm, it + 1, new
                        break
                    step /= 2
                if step < 1.0 / 128:
                    raise RuntimeError(f"Newton line search stalled at residual {residual:.6g}")
            q = proposal
            moment += step * dm
            if not np.all(np.isfinite(q)):
                raise RuntimeError("Nonfinite configuration")
        raise RuntimeError(f"Newton iteration limit, residual {residual:.6g}, boundary error {miss:.4g}")

    def condensed(self, K):
        I, T = self.inside, self.m.end
        Kie = K[I][:, T].toarray()
        return K[T][:, T].toarray() - Kie.T @ Factor(K[I][:, I]).solve(Kie)


def physical_reaction(q, body, g):
    L, _ = spin_map(q[body.rot])
    return g[body.pos], np.linalg.solve(L.T, g[body.rot])


def surface_extremes(mesh, strains):
    """Two shell faces, in-plane principal strains and strain along the build Z axis."""
    thickness = np.tile(mesh.thick, 8)
    membrane, curvature = strains[:, :3], strains[:, 3:6]
    records = {}

    def location(index, side, value, angle):
        rib, elem = divmod(int(index), len(mesh.t))
        return dict(
            strain=value,
            rib_deg=mesh.theta[rib],
            reference_r_z_through_mm=np.r_[mesh.centres[elem], side * thickness[index] / 2.0],
            direction_to_build_Z_deg=angle,
        )

    for side in (-1.0, 1.0):
        e = membrane + side * 0.5 * thickness[:, None] * curvature
        mean = 0.5 * (e[:, 0] + e[:, 1])
        delta = 0.5 * np.hypot(e[:, 0] - e[:, 1], e[:, 2])
        # The positive principal direction makes this angle with the local radial axis.
        phi = 0.5 * np.arctan2(e[:, 2], e[:, 0] - e[:, 1])
        for key, vector, comp, func in (
            ("principal_tensile", mean + delta, np.sin(phi), np.argmax),
            ("principal_compressive", mean - delta, np.cos(phi), np.argmin),
            ("build_Z_tensile", e[:, 1], np.ones_like(mean), np.argmax),
            ("build_Z_compressive", e[:, 1], np.ones_like(mean), np.argmin),
        ):
            i = func(vector)
            current = records.get(key)
            if current is None or func([current["strain"], vector[i]]) == 1:
                angle = np.degrees(np.arccos(np.clip(abs(comp[i]), 0.0, 1.0)))
                records[key] = location(i, side, vector[i], angle)
    return records


def land_reactions(m, q, x, f):
    """Forces and couples exerted by the guide on each moving rib land."""
    mesh = m.mesh
    lands = []
    for (i, s), (ids, centre, mounted) in m.rib_lands.items():
        if not mounted:
            continue
        guide = m.bodies[f"G{s:+}"]
        Rg = rotation(q[guide.rot])[0]
        guide_origin = guide.centre + q[guide.pos]
        pivot = guide_origin + Rg @ (centre - guide.centre)
        force = f[ids, :3].sum(0)
        torque = (np.cross(x[ids, :3] - pivot, f[ids, :3]) + np.cross(x[ids, 3:], f[ids, 3:])).sum(0)
        Rland = Rg if m.variant == "bond" else rotation(q[m.bodies[f"L{i}_{s}"].rot])[0]
        rv = Rotation.from_matrix(Rg.T @ Rland).as_rotvec()
        mask = (abs(mesh.x[:, 1] - s) <= 1.62 + 2.0e-6) & (mesh.x[:, 0] > 13) & (mesh.x[:, 0] < 26)
        ids2 = np.flatnonzero(mask) + i * mesh.n
        delta = (x[ids2, :3] - guide_origin) @ Rg - (mesh.xyz[ids2] - guide.centre)
        er, n = mesh.radial[i], mesh.normals[i]
        lands.append(
            dict(
                station_mm=s,
                rib_deg=mesh.theta[i],
                force_N=force,
                land_moment_Nmm=torque,
                relative_rotation_deg=np.degrees(np.linalg.norm(rv)),
                inplane_rotation_deg=np.degrees(rv @ n),
                socket_travel_3d_mm=np.linalg.norm(delta, axis=1).max(),
                socket_travel_inplane_mm=np.hypot(delta @ er, delta[:, 2]).max(),
                socket_travel_normal_mm=np.abs(delta @ n).max(),
            )
        )
    return lands


def summarize(solver, q, moment, axis, scale):
    m = solver.m
    mesh = m.mesh
    energy, g, K, (x, f, strains) = m.assemble(q, scale, hessian=axis is not None)
    tip = m.bodies["D1"]
    qtip = q[m.end]
    F1, M1 = physical_reaction(q, tip, g)
    F0, M0 = physical_reaction(q, m.bodies["D0"], g)
    R1 = rotation(q[tip.rot])[0]
    row = dict(
        elastic_potential_minus_load_work_Nmm=energy,
        tip_displacement_mm=q[tip.pos],
        tip_rotation=R1,
        distal_force_N=F1,
        distal_moment_Nmm=M1,
        proximal_force_N=F0,
        proximal_moment_Nmm=M0,
        free_residual_inf=np.max(abs(g[solver.inside])),
    )
    if axis is not None:
        Sout = solver.condensed(K)
        del K
        Q, dQ = end_work(qtip, axis)
        # Apply a small linearised twist about the bent distal axis while holding the bend coordinate.
        Qz, _ = end_work(qtip, R1[:, 2])
        L, _ = spin_map(qtip[3:])
        hc = np.r_[np.zeros(3), 2.0 * axis / (1.0 + (axis @ qtip[3:]) ** 2)]
        ht = np.r_[np.zeros(3), R1[:, 2] @ L]
        A = Sout - moment * dQ
        bend = np.linalg.solve(A, Q)
        P = np.column_stack((Q, Qz))
        comp = np.vstack((hc, ht)) @ np.linalg.solve(A, P)
        row.update(
            bend_angle_rad=2.0 * np.arctan(axis @ qtip[3:]),
            applied_couple_Nmm=moment,
            tangent_EI_Nmm2=LENGTH / (hc @ bend),
            tangent_GJ_Nmm2=LENGTH * np.linalg.inv(comp)[1, 1],
            orthogonal_moment_Nmm=np.linalg.norm(M1 - moment * axis),
        )
    faces = surface_extremes(mesh, strains)
    peak = max(
        (faces["principal_tensile"], faces["principal_compressive"]), key=lambda v: abs(v["strain"])
    )
    row.update(
        max_abs_surface_strain=abs(peak["strain"]),
        signed_peak_strain=peak["strain"],
        peak_rib_deg=peak["rib_deg"],
        peak_reference_r_z_through_mm=peak["reference_r_z_through_mm"],
        surface_extremes=faces,
    )
    row["minimum_oriented_area_ratio"] = mesh.minimum_orientation(x)
    row["lands"] = land_reactions(m, q, x, f)
    load_force = np.zeros(3)
    load_moment = np.zeros(3)
    for key, offsets, values in m.external:
        b = m.bodies[key]
        Rg = rotation(q[b.rot])[0]
        points = b.centre + q[b.pos] + offsets @ Rg.T
        load_force += scale * values.sum(0)
        load_moment += scale * np.cross(points, values).sum(0)
    force_error = F0 + F1 + load_force
    moment_error = (
        M0
        + M1
        + np.cross(m.bodies["D0"].centre, F0)
        + np.cross(tip.centre + q[tip.pos], F1)
        + load_moment
    )
    row.update(
        force_balance_N=np.linalg.norm(force_error), moment_balance_Nmm=np.linalg.norm(moment_error)
    )
    return row


def serial(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    raise TypeError(type(obj))


def save(path, data):
    part = path.with_suffix(".tmp")
    part.write_text(json.dumps(data, default=serial, indent=1, allow_nan=False) + "\n")
    part.replace(path)


def run_case(model, archive, case, step, out, cache=None, seed=None, resume=False):
    solver = Solver(model)
    pure = case.startswith("bend")
    axis = (
        np.array([np.cos(np.radians(float(case[4:]))), np.sin(np.radians(float(case[4:]))), 0.0])
        if pure
        else None
    )
    data = None if pure else archive[int(case)]
    model.external = [] if pure else data["loads"]
    q = model.zero.copy()
    M = 0.0
    frac = 0.0
    output = dict(
        variant=model.variant,
        case=case,
        mesh=model.mesh.info,
        max_fraction_step=step,
        inputs=None if pure else dict(stations=data["checks"], target=end_pose(data, 1.0)),
        completed=False,
        steps=[],
        samples=[],
    )
    checkpoints = [0.0, 0.25, 0.5, 0.75, 1.0] if pure else [0.0, 1.0]
    cp = Checkpoints(model, case, cache, seed)
    history = [(0.0, np.r_[q, M])]
    if resume:
        previous = json.loads(out.read_text())
        if previous["completed"] or previous["variant"] != model.variant or previous["case"] != case:
            raise ValueError("Can only resume the matching unfinished case")
        if previous["mesh"] != output["mesh"]:
            raise ValueError("Cannot resume with a different mesh")
        output = previous
        accepted = [0.0] + [s["fraction"] for s in output["steps"] if s["accepted"]]
        recovery = Checkpoints(model, case, None, cache)
        if not recovery.same_mesh:
            raise ValueError("Resume requires the exact original mesh")
        history = []
        for f in accepted[-3:]:
            if round(f, 9) not in recovery.seeds:
                raise ValueError("Missing accepted state for the continuation restart")
            q, M = recovery.load(round(f, 9))
            history.append((f, np.r_[model.lift(q, -1.0), M]))
        frac = accepted[-1]
        if model.mesh.minimum_orientation(model.mapping(q)[0]) <= 0.0:
            raise ValueError("The last checkpoint contains a folded triangle")
        output.setdefault("resumes", []).append(dict(from_fraction=frac, max_fraction_step=step))
    else:
        cp.save(0.0, q, M)
    t = time.monotonic()
    for stop in checkpoints:
        if stop < frac - 1.0e-10 or any(abs(r["fraction"] - stop) < 1.0e-10 for r in output["samples"]):
            continue
        h = step
        while frac < stop - 1.0e-10:
            nextfrac = min(stop, frac + h)
            target = np.tan(nextfrac * KAPPA * LENGTH / 2.0) if pure else end_pose(data, nextfrac)
            start = time.monotonic()
            try:
                start_q, start_m = q, M
                guess = cp.load(nextfrac) if cp.seeds and nextfrac <= max(cp.seeds) else None
                if guess is not None:
                    start_q, start_m = guess
                elif len(history) >= 2:
                    val = interpolate(history[-3:], nextfrac)
                    start_q, start_m = model.lift(val[:-1], 1.0), val[-1]
                new, Mnew, it, res = solver.step(
                    start_q, start_m, axis, target, 0.0 if pure else nextfrac
                )
            except (RuntimeError, np.linalg.LinAlgError) as exc:
                output["steps"].append(dict(fraction=nextfrac, accepted=False, reason=str(exc)))
                h = (nextfrac - frac) / 2.0
                save(out, output)
                if h < 1.0 / 256:
                    return output
                continue
            q, M, frac = new, Mnew, nextfrac
            cp.save(frac, q, M)
            history.append((frac, np.r_[model.lift(q, -1.0), M]))
            history = history[-3:]
            output["steps"].append(
                dict(
                    fraction=frac,
                    accepted=True,
                    iterations=it,
                    residual=res,
                    seconds=time.monotonic() - start,
                )
            )
            print(
                case,
                model.variant,
                round(frac, 5),
                it,
                f"{res:.2g}",
                f"{time.monotonic() - t:.1f}s",
                flush=True,
            )
            save(out, output)
            h = min(step, h * 1.5)
        row = summarize(solver, q, M, axis, 0.0 if pure else frac)
        row["fraction"] = stop
        output["samples"].append(row)
        save(out, output)
    output["completed"] = True
    output["elapsed_s_after_restart" if resume else "elapsed_s"] = time.monotonic() - t
    save(out, output)
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", type=float, required=True)
    ap.add_argument("--step", type=float, default=0.125)
    ap.add_argument(
        "--variants", nargs="+", choices=["bare", "bond", "point"], default=["bare", "bond", "point"]
    )
    ap.add_argument(
        "--cases",
        nargs="+",
        choices=["bend0", "bend67.5", *map(str, CASES)],
        default=["bend0", "bend67.5", *map(str, CASES)],
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--seed", type=Path)
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Continue an unfinished case from its exact scratch mesh and last accepted states",
    )
    args = ap.parse_args()
    if not (0 < args.step <= 1.0 and args.area > 0):
        ap.error("positive mesh area and step in (0, 1] required")
    if args.resume and (args.cache is None or args.seed is not None):
        ap.error("--resume requires --cache and uses only that original trajectory")
    args.out.mkdir(parents=True, exist_ok=True)
    mesh = Mesh(args.area)
    print(mesh.info, flush=True)
    data = archive_loads() if any(not c.startswith("bend") for c in args.cases) else {}
    unfinished = []
    for variant in args.variants:
        model = Model(mesh, variant)
        for case in args.cases:
            if variant == "bare" and not case.startswith("bend"):
                continue
            out = args.out / f"{variant}_{case}.json"
            if out.exists() and not args.resume:
                raise FileExistsError(out)
            result = run_case(model, data, case, args.step, out, args.cache, args.seed, args.resume)
            if not result["completed"]:
                unfinished.append(out.name)
    if unfinished:
        raise SystemExit("Incomplete equilibria saved in " + ", ".join(unfinished))


if __name__ == "__main__":
    main()
