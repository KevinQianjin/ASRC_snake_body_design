"""Re-equilibrate selected 500 g fixed-winch poses with directional sliding on one real rope route."""

import argparse
import json
from pathlib import Path

import numpy as np
from numba import njit
from scipy.optimize import brentq, root

from replay import SHARED, NAMES, plant
from transmission import material_path
from spatial_model import rotation
from length_cycle import LengthDrive
from closed_loop_cycle import FeedbackDrive
from solve_bellmouth_holds import damped_stationary
from rebalance import metrics


@njit(cache=True)
def material_gradient(z, scale, L, gu, gw, F, ap, af):
    """Apply nodal virtual forces and frame gradients through the rod's finite-rotation kinematics."""
    q = (z / scale).reshape(-1, 4)
    grad = np.zeros_like(q)
    mapping = (0, 2, 1)
    signs = (1.0, 1.0, -1.0)
    for i in range(len(q) - 1, -1, -1):
        phi = np.array([q[i, 0], -q[i, 2], q[i, 1]])
        R, DR = rotation(phi)
        vec = np.zeros(3)
        der = np.zeros((3, 3))
        for j in range(len(gu)):
            v, dd = rotation(gu[j] * phi)
            vec += gw[j] * v[:, 0]
            for k in range(3):
                der[k] += gw[j] * gu[j] * signs[k] * dd[mapping[k], :, 0]
        v = L * (1.0 + q[i, 3]) * vec
        prox = F[i].T @ ap[i + 1]
        frm = F[i].T @ af[i + 1]
        for k in range(3):
            grad[i, k] = np.sum(frm * DR[mapping[k]]) * signs[k] + prox @ (
                L * (1.0 + q[i, 3]) * der[k]
            )
        grad[i, 3] = prox @ (L * vec)
        af[i] += af[i + 1] @ R.T + np.outer(ap[i + 1], v)
        ap[i] += ap[i + 1]
    return grad.ravel() / scale


def elastic_tensions(lengths, cumulative, mu, sign, rest, ea, free):
    scaling = np.exp(sign * mu * cumulative)
    deformed = free + lengths.sum()
    if deformed <= rest:
        return 0.0, np.zeros_like(lengths)

    def defect(t):
        return free / (1 + t / ea) + np.sum(lengths / (1 + t * scaling / ea)) - rest

    hi = ea * (deformed / rest - 1.0) / min(1.0, scaling.min()) * 1.01 + 1.0e-8
    first = brentq(defect, 0.0, hi, xtol=1.0e-12)
    return first, first * scaling


def on_material(rod, z, rest, drive, channel, mu, sign, common=None):
    if common is None:
        common = (
            rod.base.evaluate(z, detail=True)[2],
            rod.endpoints(z[rod.local]),
            drive.force(z, rest),
        )
    detail, endpoints, T = common
    p, F = detail["points"], detail["frames"]
    ray = channel % 4
    lane = channel // 4
    points, nodes, closure, _ = material_path(rod, detail, endpoints, lane, ray)
    # Discard duplicate analytic tangencies before constructing directions.
    keep = np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 1.0e-8]
    x = points[keep] / 1000.0
    nodes = nodes[keep]
    delta = np.diff(x, axis=0)
    ll = np.linalg.norm(delta, axis=1)
    u = delta / ll[:, None]
    angles = np.arctan2(
        np.linalg.norm(np.cross(u[:-1], u[1:]), axis=1), np.sum(u[:-1] * u[1:], axis=1)
    )
    wrap = np.r_[0.0, np.cumsum(angles)]
    winch, Ts = elastic_tensions(
        ll, wrap, mu, sign, rest.flat[channel], drive.ea, drive.free
    )
    # Add only the difference to the exact frictionless rod and shared-bore forces.
    # This preserves its analytic endpoint loads at mu=0, up to the disclosed arc quadrature.
    point = np.zeros_like(x)
    tension_difference = Ts - T.flat[channel]
    traction = tension_difference[:, None] * u
    point[:-1] -= traction
    point[1:] += traction
    local = np.einsum("nji,nj->ni", F[nodes], x - p[nodes])
    ap = np.zeros_like(p)
    af = np.zeros_like(F)
    np.add.at(ap, nodes, point)
    np.add.at(af, nodes, point[:, :, None] * local[:, None, :])
    g = material_gradient(
        z, rod.scale, rod.l, rod.planar.u, rod.planar.w, F, ap.copy(), af.copy()
    )
    defect = (
        drive.free / (1 + winch / drive.ea)
        + np.sum(ll / (1 + Ts / drive.ea))
        - rest.flat[channel]
    )
    return (
        g,
        dict(
            winch_N=winch,
            distal_N=float(Ts[-1]),
            wrap_deg=float(np.degrees(wrap[-1])),
            rope_unstretched_closure_mm=float(1000 * defect),
            piece_closure_mm=closure,
            other_minimum_N=float(np.delete(T.ravel(), channel).min()),
            point_force_closure_N=float(np.linalg.norm(point.sum(0))),
            point_moment_closure_Nmm=float(
                np.linalg.norm(np.cross(x, point).sum(0)) * 1000
            ),
        ),
        nodes,
        local,
        point,
    )


def virtual_work(rod, z, nodes, local, point, gradient):
    d = np.random.default_rng(34).normal(size=len(z))
    d /= np.linalg.norm(d)
    h = 4.0e-6

    def xyz(zz):
        det = rod.base.evaluate(zz, detail=True)[2]
        return det["points"][nodes] + np.einsum(
            "nij,nj->ni", det["frames"][nodes], local
        )

    fd = np.sum(point * (xyz(z + h * d) - xyz(z - h * d))) / (2 * h)
    return float(abs(fd - d @ gradient))


def run(a):
    rod, mass = plant()
    drive = LengthDrive(rod)
    feedback = FeedbackDrive(rod)
    with np.load(SHARED / "results/rebalanced_states.npz") as f:
        labels = f["hold_id"].astype(int).tolist()
        zs = f["z"]
        rests = f["winch_rest_lengths_mm"] / 1000.0
        tens = f["tensions_n"]
    report = dict(
        model="One rope in steady sliding. All other ropes keep their frictionless equilibrium laws. Negative sign pulls towards the winch. Global shape, effective elongation and all twelve tensions re-equilibrate at the same command.",
        cells_per_module=8,
        source_channel=NAMES[a.channel],
        mass=mass,
        holds=[],
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for label in a.holds:
        i = labels.index(label)
        rest = rests[i].reshape(3, 4)
        z, trace, status = damped_stationary(
            rod, tens[i].reshape(3, 4), zs[i], drive=drive, rest=rest, max_seconds=120
        )
        if z is None:
            raise ValueError(status)
        head, yaw = metrics(rod, z)
        T0 = drive.force(z, rest)
        H = feedback.tangent(z, rest, T0)
        rows = []
        states = []
        zero, _, _, _, _ = on_material(rod, z, rest, drive, a.channel, 0.0, 1)
        for sign in (-1, 1):
            seed = z.copy()
            for mu in a.mu:

                def residual(zz):
                    delta, *_ = on_material(rod, zz, rest, drive, a.channel, mu, sign)
                    return drive.energy(zz, rest)[1] + delta

                root_result = root(
                    residual,
                    seed,
                    jac=lambda _: H,
                    method="hybr",
                    options=dict(xtol=2e-9, maxfev=110),
                )
                result = root_result.x
                rr = rod.residual(residual(result))
                q = (result / rod.scale).reshape(-1, 4)
                ok = (
                    rr < 2.0e-6
                    and np.max(abs(q[:, 3])) <= 0.0475
                    and np.max(abs(q[:, :3])) <= 1.5
                )
                row = dict(
                    mu=mu,
                    sign=sign,
                    converged=bool(ok),
                    residual=float(rr),
                    function_evaluations=int(root_result.nfev),
                )
                if ok:
                    seed = result
                    g, m, nodes, local, point = on_material(
                        rod, result, rest, drive, a.channel, mu, sign
                    )
                    p1, a1 = metrics(rod, result)
                    row.update(
                        m,
                        virtual_work_error=float(
                            virtual_work(rod, result, nodes, local, point, g)
                        ),
                        head_change_from_updated_frictionless_mm=float(
                            np.linalg.norm(p1 - head)
                        ),
                        yaw_change_deg=float((a1[0] - yaw[0] + 180) % 360 - 180),
                        elevation_change_deg=float(a1[2] - yaw[2]),
                        rigid_rod_geometry_pass=bool(
                            np.all(rod.geometry_constraints(result) >= 0)
                        ),
                    )
                    states.append((mu, sign, result.copy()))
                else:
                    row["solver_message"] = str(root_result.message)
                rows.append(row)
        report["holds"].append(
            dict(
                hold=label,
                nominal_head_mm=head.tolist(),
                nominal_angles_deg=yaw.tolist(),
                nominal_tensions_N=T0.tolist(),
                zero_mu_virtual_force_max=float(np.max(abs(zero))),
                cases=rows,
            )
        )
        if states:
            np.savez_compressed(
                a.out.parent / f"sliding_hold_{label}.npz",
                mu=np.array([v[0] for v in states]),
                sign=np.array([v[1] for v in states]),
                z=np.stack([v[2] for v in states]),
                rest_m=rest,
            )
        a.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            label,
            [(r["mu"], r["sign"], r.get("distal_N"), r["residual"]) for r in rows],
            flush=True,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--channel", type=int, default=10, choices=range(12))
    p.add_argument("--holds", nargs="+", type=int, default=[52, 63, 146])
    p.add_argument("--mu", nargs="+", type=float, default=[0.05, 0.15, 0.30])
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
