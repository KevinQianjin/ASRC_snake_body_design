"""Force-controlled P3 coupon on the elastic production pin and cap in a bench fixture."""

import argparse
import json
from pathlib import Path

import numpy as np
from cvxopt import matrix, solvers, spmatrix

from inputs import p3_input
from contact import LEVELS, Patch, shoulder_distance
from steel import SHAFT, Steel


class Interface:
    def __init__(self, web, steel, rotation, facets):
        self.web = web
        self.steel = steel
        self.rotation = rotation
        x = web.x[web.ids]
        self.groups = [
            np.flatnonzero(web.bore),
            np.flatnonzero(web.shoulder & (x[:, 2] < 0)),
            np.flatnonzero(web.shoulder & (x[:, 2] > 0)),
        ]
        self.idx = np.concatenate(self.groups)
        self.bound, self.inside, self.bore_z, self.bore_norm = steel.counterbore(facets)

    def rows(self, u, t, q):
        x = (self.web.x[self.web.ids] + u) @ self.rotation.T + t
        gaps, normals, metal = [], [], []
        for k, ids in enumerate(self.groups):
            p = x[ids]
            if k == 0:
                name = "pin"
                z = p[:, 2]
                v, _, dv, _, _ = self.steel.components(q, name, z)
                xy = p[:, :2] - v
                radius = np.linalg.norm(xy, axis=1)
                normal0 = np.c_[xy / radius[:, None], np.zeros(len(p))]
                normal = normal0.copy()
                normal[:, 2] = -np.sum(normal0[:, :2] * dv, axis=1)
                gap = radius - SHAFT
            else:
                sign = -1 if k == 1 else 1
                name = "cap" if k == 1 else "pin"
                z = np.full(len(p), sign * 1.52)
                v, theta, _, _, w = self.steel.components(q, name, z)
                local = p.copy()
                local[:, :2] -= v + (p[:, 2] - z)[:, None] * theta
                local[:, 2] += np.sum(p[:, :2] * theta, axis=1) - w
                gap, normal0 = shoulder_distance(local, sign)
                normal = normal0.copy()
                normal[:, :2] += normal0[:, 2, None] * theta
                normal[:, 2] -= np.sum(normal0[:, :2] * theta, axis=1)
            gaps.append(gap)
            normals.append(normal)
            metal.append(
                self.steel.normal_rows(p, name, z, normal0)[:, self.steel.free]
            )
        nw = np.vstack(normals)
        return (
            np.r_[np.concatenate(gaps), self.bound - self.inside @ q],
            np.vstack((nw, np.zeros((len(self.bound), 3)))),
            nw @ self.rotation,
            np.vstack((*metal, self.inside)),
        )


def contact_step(interface, u, t, q, force, seed):
    web, steel, idx = interface.web, interface.steel, interface.idx
    g, n, local, A = interface.rows(u, t, q)
    g0 = g - n @ t + A @ q
    g0[: len(idx)] -= np.einsum("ij,ij->i", local, u[idx])
    nw = n[: len(idx)]
    bins = np.rint(np.arctan2(nw[:, 1], nw[:, 0]) * 4 / np.pi).astype(int) + 5
    bins += 11 * np.where(nw[:, 2] > 0.45, 1, np.where(nw[:, 2] < -0.45, 2, 0))
    selected = set(seed)
    for label in np.unique(bins):
        group = np.flatnonzero(bins == label)
        selected.update(group[np.argsort(g0[group])[:3]].tolist())
    for _ in range(45):
        s = np.array(sorted(selected))
        # All web rows precede steel-to-steel constraints.
        w = s[s < len(idx)]
        d = 3 * idx[w, None] + np.arange(3)
        web.ensure(idx[w])
        compliance = A[s] @ steel.solve(A[s].T)
        block = web.comp[d[:, None, :, None], d[None, :, None, :]]
        compliance[: len(w), : len(w)] += np.einsum(
            "ia,ijab,jb->ij", local[w], block, local[w], optimize=True
        )
        compliance = (compliance + compliance.T) / 2 + 1e-9 * np.eye(len(s))
        neg = spmatrix(-1.0, list(range(len(s))), list(range(len(s))))
        result = solvers.qp(
            matrix(compliance),
            matrix(g0[s]),
            neg,
            matrix(0.0, (len(s), 1)),
            matrix(n[s].T),
            matrix(force),
        )
        if result["status"] != "optimal":
            raise ValueError("Contact QP " + result["status"])
        lam = np.maximum(0.0, np.asarray(result["x"]).ravel())
        tn = np.asarray(result["y"]).ravel()
        nodal = local[w] * lam[: len(w), None]
        un = (web.comp[:, d.ravel()] @ nodal.ravel()).reshape(-1, 3)
        qn = -steel.solve(A[s].T @ lam)
        predicted = g0 + n @ tn - A @ qn
        predicted[: len(idx)] += np.einsum("ij,ij->i", local, un[idx])
        missed = np.flatnonzero(predicted < -2e-6)
        new = set(missed[np.argsort(predicted[missed])[:30]].tolist()) - selected
        if not new:
            loads = np.zeros(len(web.fdof))
            np.add.at(loads, d, nodal)
            return un, tn, qn, s, lam, loads
        selected.update(new)
    raise ValueError("Active constraints did not settle")


def evaluate(interface, force):
    web, steel = interface.web, interface.steel
    u = np.zeros((len(web.ids), 3))
    t = np.zeros(3)
    q = np.zeros(len(steel.free))
    seed = []
    for it in range(54):
        un, tn, qn, s, lam, loads = contact_step(interface, u, t, q, force, seed)
        # Beam DOFs combine mm and radians; the slope metric uses a 1 mm lever.
        step = max(
            np.linalg.norm(un - u, axis=1).max(),
            np.linalg.norm(tn - t),
            np.max(abs(qn - q)),
        )
        seed = s[lam > 2e-4].tolist()
        if step < 3e-6:
            break
        weight = 1.0 if it == 0 else 0.65
        u += weight * (un - u)
        t += weight * (tn - t)
        q += weight * (qn - q)
    rhs = np.zeros(len(web.free))
    np.add.at(rhs, web.fdof, loads)
    full = np.zeros(web.x.size)
    full[web.free] = web.lu.solve(rhs)
    disp = full.reshape(-1, 3)
    g, n, _, A = interface.rows(disp[web.ids], tn, qn)
    w = s < len(interface.idx)
    steel_residual = steel.K[np.ix_(steel.free, steel.free)] @ qn + A[s].T @ lam
    energy = float(0.5 * qn @ (steel.K[np.ix_(steel.free, steel.free)] @ qn))
    return dict(
        converged=bool(step < 3e-6),
        iterations=it + 1,
        last_step_mm_or_rad=float(step),
        coupon_carriage_spn_mm=tn.tolist(),
        pin_on_web_spn_N=force.tolist(),
        contact_force_residual_N=float(np.linalg.norm(n[s].T @ lam - force)),
        free_steel_force_or_moment_residual_max=float(np.max(abs(steel_residual))),
        minimum_web_contact_gap_mm=float(g[: len(interface.idx)].min()),
        minimum_polygonal_counterbore_gap_mm=float(g[len(interface.idx) :].min()),
        summed_counterbore_normal_load_N=float(lam[~w].sum()),
        peak_nodal_pressure_MPa=float((lam[w] / web.area[interface.idx[s[w]]]).max()),
        steel_strain_energy_Nmm=energy,
        **steel.recover(qn),
        **web.stress(disp),
    )


def run(args):
    _, force, rotation = p3_input()
    web = Patch(args.mesh, 2.7, fit_relief=True)
    steel = Steel(args.spacing, args.support, args.young, args.thread_limit)
    interface = Interface(web, steel, rotation, args.facets)
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    data = dict(
        mesh=args.mesh,
        web_elements=len(web.hex),
        web_nodes=len(web.x),
        beam_free_dofs=len(steel.free),
        spacing_mm=args.spacing,
        facets=args.facets,
        support=args.support,
        steel_modulus_MPa=args.young,
        thread_tie_end_n_mm=args.thread_limit,
        web_modulus_MPa=1530.0,
        web_poisson=0.4,
        rotation_coupon_to_pin=rotation.tolist(),
        source_force_spn_N=force.tolist(),
        states=[],
    )
    if args.resume and args.out.exists():
        saved = json.loads(args.out.read_text())
        if {k: v for k, v in data.items() if k != "states"} != {
            k: v for k, v in saved.items() if k != "states"
        }:
            raise ValueError(
                "Cannot reuse results from another mesh, material, restraint or orientation"
            )
        data["states"] = [v for v in saved["states"] if v["converged"]]
    for label in args.levels:
        factor = 1.0 / np.linalg.norm(force) if label == "ref" else float(label)
        if any(v["factor"] == factor for v in data["states"]):
            continue
        if factor == 0 or abs(factor) > 1:
            raise ValueError("Provide a signed nonzero factor, or ref for +1 N")
        try:
            state = evaluate(interface, force * factor)
        except (ArithmeticError, ValueError) as e:
            state = dict(converged=False, error=str(e))
        data["states"].append(dict(factor=factor, **state))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.out.with_suffix(".partial")
        tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
        tmp.replace(args.out)
        print(
            label,
            state.get("converged"),
            state.get("shaft_centre_sp_mm"),
            state.get("error", ""),
            flush=True,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mesh", choices=LEVELS, default="fine")
    p.add_argument("--spacing", type=float, default=0.15)
    p.add_argument("--facets", type=int, default=24)
    p.add_argument("--support", choices=("clamped", "hinged"), default="clamped")
    p.add_argument("--young", type=float, default=200000.0)
    p.add_argument("--thread-limit", type=float, choices=(-3.125, -2.57), default=-2.57)
    p.add_argument("--levels", nargs="+", default=["1", "-1"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    run(p.parse_args())
