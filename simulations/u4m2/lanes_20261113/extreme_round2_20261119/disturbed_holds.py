"""Re-equilibrate selected real holds with displaced M6 bores and controlled load/fault sensitivities."""

import argparse
from pathlib import Path
import numpy as np
from scipy.optimize import root, minimize
from scipy.spatial.transform import Rotation
from common import OUT, NAMES, motion_rows, trajectory, save, read
from replay import plant
from sliding import material_gradient
from closed_loop_cycle import FeedbackDrive
from pitch_reference import pointing, angle_between
from pose_map import centreline, axis, tangent
from length_cycle import FastTank, to_tank
from u_springs import CAD_TO_ROD


def displaced_paths(rod, d, poses):
    nodes = np.array([42, 43, 45, 46])
    L = np.zeros(4)
    sides = []
    for k in range(4):
        ref = np.broadcast_to(rod.offsets3[2, k], (4, 3)).copy()
        cad = CAD_TO_ROD.T @ ref[0] * 1000
        new = ref.copy()
        for j in (1, 2):
            u = poses[j - 1]
            new[j] = (
                CAD_TO_ROD @ (u[:3] + Rotation.from_rotvec(u[3:]).apply(cad)) / 1000
            )
        for sign, off in ((-1, ref), (1, new)):
            pos = d["points"][nodes] + np.einsum("nij,nj->ni", d["frames"][nodes], off)
            seg = np.diff(pos, axis=0)
            length = np.linalg.norm(seg, axis=1)
            v = seg / length[:, None]
            L[k] += sign * length.sum()
            traction = sign * np.vstack((-v[0], v[:-1] - v[1:], v[-1]))
            sides.append((k, nodes, off, traction))
    return L, sides


def run(out):
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    tank = FastTank()
    states, rest, nom = trajectory()
    rows = motion_rows()
    R0 = rod.R0.copy()
    gw = rod.gw.copy()
    info = read(out / "m6_support.json")["cases"]
    cases = []
    for step in (1709, 1710, 1885, 1843, 2059, 2348, 2432):
        z = states[step]
        R = rest[step]
        H = drive.tangent(z, R, nom[step].reshape(3, 4))
        yaw = float(rows[step]["target_yaw_deg"])
        pitch = float(rows[step]["target_elevation_deg"])
        scenarios = [("control", np.zeros((2, 6)), 0.0, 0.0, 0.0, None)]
        if step in (1709, 1710, 1885):
            for G in (500.0, 1500.0):
                shifts = np.array(
                    [
                        next(
                            v["guide_increment_mm_rad"]
                            for v in info
                            if (v["step"], v["station_mm"], v["gap_mm"], v["G_MPa"])
                            == (step, st, 0.25, G)
                        )
                        for st in (-12, 12)
                    ]
                )
                scenarios.append(
                    (f"displaced_M6_G{int(G)}", shifts, 0.0, 0.0, 0.0, None)
                )
        if step in (1709, 2432):
            for delta in (-2.0, 2.0):
                scenarios.append(
                    ("fixture_tilt", np.zeros((2, 6)), delta, 0.0, 0.0, None)
                )
                scenarios.append(
                    ("side_harness_N", np.zeros((2, 6)), 0.0, delta, 0.0, None)
                )
                scenarios.append(
                    ("head_CG_lateral_mm", np.zeros((2, 6)), 0.0, 0.0, delta * 5, None)
                )
            scenarios.append(
                (
                    "one_rope_released",
                    np.zeros((2, 6)),
                    0.0,
                    0.0,
                    0.0,
                    int(nom[step].argmax()),
                )
            )
        for scenario, offset, tilt, harness, cg, released in scenarios:
            R = rest[step].copy()
            theta = np.radians(20 + tilt)
            rod.base.R0 = Rotation.from_rotvec([0, 0, theta]).as_matrix()
            rod.base.gw = rod.base.R0[1].copy()

            def calc(x, report=False):
                _, _, d = rod.evaluate(x, detail=True)
                # No additional head weight. Gravity at an eccentric centre adds only a moment.
                e = np.zeros_like(d["points"])
                g = np.zeros_like(d["frames"])
                e[-1] = -rod.R0.T @ np.array([0.0, 0.0, harness])
                g[-1] = -np.outer(
                    rod.R0.T @ [0.0, -rod.payload * 9.81, 0.0],
                    np.array([0, 0, cg]) / 1000,
                )
                lengths = d["rope_lengths"].copy()
                paths = []
                if offset.any():
                    change, paths = displaced_paths(rod, d, offset)
                    lengths[2] += change
                T = drive.ea * np.maximum(0, lengths + drive.free - R) / R
                if released is not None:
                    T.flat[released] = 0
                for k, nodes, off, unit in paths:
                    f = T[2, k] * unit
                    e[nodes] += f
                    g[nodes] += f[:, :, None] * off[:, None, :]
                potential_grad = rod.evaluate(x, T)[1] + material_gradient(
                    x, rod.scale, rod.l, rod.planar.u, rod.planar.w, d["frames"], e, g
                )
                return (T, potential_grad) if report else potential_grad

            fit = root(
                calc,
                z,
                jac=lambda _: H,
                method="hybr",
                options=dict(xtol=1e-9, maxfev=130),
            )
            T, grad = calc(fit.x, True)
            res = rod.residual(grad)
            row = dict(
                step=step,
                scenario=scenario,
                tilt_deg=tilt,
                harness_N=harness,
                cg_lateral_mm=cg,
                released=None if released is None else NAMES[released],
                residual=res,
                converged=bool(res < 2e-6),
            )
            if row["converged"]:
                tip = pointing(rod, fit.x)
                gap = (
                    tank.clearance(
                        to_tank(
                            centreline(rod, fit.x),
                            20 + tilt,
                            float(rows[step]["clamp_s_mm"]),
                            tank.entry_h,
                        )
                    )[0]
                    - 1.5
                )
                row.update(
                    tension_N=T.ravel(),
                    pointing_error_deg=angle_between(tip, axis(yaw, pitch)),
                    tank_gap_mm=gap,
                    geometry_margin=rod.geometry_constraints(fit.x).min(),
                    peak_strain=np.max(abs((fit.x / rod.scale).reshape(-1, 4)[:, 3])),
                )
            if offset.any() and row["converged"]:
                x = fit.x
                log = []
                for it in range(17):
                    Tc, grad = calc(x, True)
                    miss = axis(yaw, pitch) - pointing(rod, x)
                    error = angle_between(pointing(rod, x), axis(yaw, pitch))
                    log.append(
                        dict(
                            iteration=it,
                            pointing_error_deg=error,
                            minimum_N=Tc.min(),
                            maximum_N=Tc.max(),
                            rest_change_mm=(R - rest[step]).ravel() * 1000,
                            residual=rod.residual(grad),
                            gap_mm=tank.clearance(
                                to_tank(
                                    centreline(rod, x),
                                    20,
                                    float(rows[step]["clamp_s_mm"]),
                                    tank.entry_h,
                                )
                            )[0]
                            - 1.5,
                        )
                    )
                    if error <= 0.2 and Tc.min() >= 2.5:
                        break
                    J, C, _ = tangent(rod, drive, x, R)
                    A = J * 180 / np.pi
                    goal = miss * 180 / np.pi
                    solve_qp = minimize(
                        lambda u: 0.5 * (np.sum((A @ u - goal) ** 2) + 0.002 * u @ u),
                        np.zeros(12),
                        jac=lambda u: A.T @ (A @ u - goal) + 0.002 * u,
                        bounds=[(-0.25, 0.25)] * 12,
                        constraints=[
                            dict(
                                type="ineq",
                                fun=lambda u: Tc.ravel() + C @ u - 2.8,
                                jac=lambda _: C,
                            )
                        ],
                        method="SLSQP",
                        options=dict(ftol=1e-10, maxiter=100),
                    )
                    if not solve_qp.success:
                        break
                    R = R + solve_qp.x.reshape(3, 4) / 1000
                    trial = root(
                        calc,
                        x,
                        jac=lambda _: H,
                        method="hybr",
                        options=dict(xtol=1e-9, maxfev=70),
                    )
                    if rod.residual(calc(trial.x)) >= 2e-6:
                        break
                    x = trial.x
                row["local_feedback"] = log
            cases.append(row)
        rod.base.R0 = R0.copy()
        rod.base.gw = gw.copy()
        save(out / "disturbed_holds.json", cases)
    print("held-command perturbations", len(cases), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
