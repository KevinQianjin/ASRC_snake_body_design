"""Prepare signed vertical pointing references with the fixed-centre 500 g design model."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import solve
from scipy.optimize import minimize

from replay import BASE
from shared_bore import load_rod
from closed_loop_cycle import FeedbackDrive
from length_cycle import FastTank, to_tank


def pointing(rod, z):
    _, d = rod.kinematic_metrics(z)
    return rod.R0 @ d["frames"][-1, :, 0]


def pitch_axes(axis):
    """Sideslip and signed elevation in the fixed forward/up plane, nonsingular at both vertical poles."""
    x, y, z = axis
    return np.degrees([np.arctan2(z, np.hypot(x, y)), np.arctan2(y, x)])


def angular_error(target, actual):
    return (np.asarray(target) - actual + 180.0) % 360.0 - 180.0


def target_axis(pitch):
    a = np.radians(pitch)
    return np.array([np.cos(a), np.sin(a), 0.0])


def angle_between(a, b):
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b))))


def position(rod, z):
    d = rod.kinematic_metrics(z)[1]
    return rod.R0 @ (d["points"][-1] + [0.02, 0, 0]) * 1000.0


def sensitivity(rod, drive, z, R):
    T = drive.force(z, R).ravel()
    J = rod.control_jacobian(z)
    H = drive.tangent(z, R, T.reshape(3, 4))
    drive._last_hessian = H
    deriv = solve(H, J.T * ((drive.ea + T) / R.ravel()), assume_a="sym") / 1000.0
    # Central differencing in just the twelve command-induced directions avoids a separate kinematic basis per DOF.
    A = []
    P = []
    for v in deriv.T:
        h = 2e-4
        a, pa = rod.kinematic_metrics(z + h * v)
        b, pb = rod.kinematic_metrics(z - h * v)
        da = pitch_axes(rod.R0 @ pa["frames"][-1, :, 0])
        db = pitch_axes(rod.R0 @ pb["frames"][-1, :, 0])
        A.append(angular_error(da, db) / (2 * h))
        P.append(rod.R0 @ (pa["points"][-1] - pb["points"][-1]) * 1000.0 / (2 * h))
    C = (drive.ea / R.ravel())[:, None] * (J @ deriv) - np.diag(
        (drive.ea + T) / R.ravel()
    ) / 1000.0
    return np.array(A).T, C, np.array(P).T


def update(A, C, P, T, miss, height_error, vertical_weight, lower_tension, allocation):
    # The primary target is angular. Vertical height is a soft secondary objective for the inspection pose.
    # Enforce symmetry of the side pair for each lane in this sagittal planning problem.
    sym = np.zeros((12, 9))
    for g in range(3):
        sym[4 * g, 3 * g] = 1
        sym[4 * g + 2, 3 * g + 1] = 1
        sym[[4 * g + 1, 4 * g + 3], 3 * g + 2] = 1
    ang = A @ sym
    ds = C @ sym
    vert = P[1] @ sym
    w = vertical_weight

    def fun(x):
        e = ang @ x - miss
        h = vert @ x - height_error
        return 0.5 * (e @ e + w * w * h * h + 2e-4 * (x @ x))

    def jac(x):
        return (
            ang.T @ (ang @ x - miss)
            + w * w * vert * (vert @ x - height_error)
            + 2e-4 * x
        )

    cons = [
        dict(type="ineq", fun=lambda x: T + ds @ x - lower_tension, jac=lambda x: ds),
        dict(type="ineq", fun=lambda x: 250.0 - T - ds @ x, jac=lambda x: -ds),
    ]
    r = minimize(
        fun,
        np.zeros(9),
        jac=jac,
        bounds=[(-0.85, 0.85)] * 9,
        constraints=cons,
        method="SLSQP",
        options=dict(maxiter=150, ftol=2e-12),
    )
    if (
        allocation == "minimum-tension"
        and r.success
        and np.linalg.norm(ang[1]) > 1.0e-8
    ):
        # Retain the first QP's reachable pitch increment. Use redundant winches to reduce antagonistic load.
        achieved = ang[1] @ r.x
        eq = dict(type="eq", fun=lambda x: ang[1] @ x - achieved, jac=lambda x: ang[1])

        def cost(x):
            load = (T + ds @ x - lower_tension) / 10.0
            h = vert @ x - height_error
            return 0.5 * (load @ load + 0.005 * (x @ x) + w * w * h * h)

        def grad(x):
            return (
                ds.T @ (T + ds @ x - lower_tension) / 100.0
                + 0.005 * x
                + w * w * vert * (vert @ x - height_error)
            )

        trial = minimize(
            cost,
            r.x,
            jac=grad,
            bounds=[(-0.85, 0.85)] * 9,
            constraints=[*cons, eq],
            method="SLSQP",
            options=dict(maxiter=150, ftol=1.0e-10),
        )
        if trial.success:
            r = trial
    return sym @ r.x, bool(r.success)


def solve_branch(
    rod,
    drive,
    tank,
    z_start,
    command,
    start_gain,
    sign,
    end,
    step,
    w,
    neutral_height,
    out,
    allocation,
):
    R = command.copy()
    z = z_start.copy()
    A, C, P = start_gain
    records = []
    fields = {}
    angles_target = np.r_[np.arange(20.0 + sign * step, end, sign * step), end]
    for pitch in angles_target:
        target = [0.0, pitch]
        accepted = True
        why = None
        for it in range(30):
            axis = pointing(rod, z)
            miss = angular_error(target, pitch_axes(axis))
            T = drive.force(z, R).ravel()
            if max(abs(miss)) < 0.025 and min(T) > 2.94:
                break
            if it == 0 or it % 3 == 0:
                A, C, P = sensitivity(rod, drive, z, R)
            x, ok = update(
                A,
                C,
                P,
                T,
                miss,
                np.clip(neutral_height - position(rod, z)[1], -3, 3),
                w,
                3.0,
                allocation,
            )
            if not ok and np.max(abs(x)) < 1e-6:
                accepted = False
                why = "No feasible winch increment"
                break
            rn = R + x.reshape(3, 4) / 1000.0
            zn = drive.solve(z, rn)
            if zn is None:
                accepted = False
                why = "Equilibrium did not converge"
                break
            z, R = zn, rn
        else:
            accepted = False
            why = "Reference corrector exceeded its iteration budget"
        d = rod.kinematic_metrics(z)[1]
        world = (
            np.vstack([np.zeros(3), d["points"] + [0.02, 0, 0]]) @ rod.R0.T
        ) * 1000.0
        gap = tank.clearance(to_tank(world, 20.0, 15.0, tank.entry_h))[0] - 1.5
        T = drive.force(z, R)
        axis = pointing(rod, z)
        residual = rod.residual(drive.energy(z, R)[1])
        geo = rod.geometry_constraints(z)
        eig = drive.stability(z, R, T)
        r = dict(
            allocation=allocation,
            target_deg=float(pitch),
            achieved_axes_deg=pitch_axes(axis).tolist(),
            axis_xyz=axis.tolist(),
            axis_error_deg=angle_between(axis, target_axis(pitch)),
            minimum_tension_N=float(T.min()),
            max_tension_N=float(T.max()),
            clearance_after_allowance_mm=float(gap),
            residual=residual,
            min_tangent_eigenvalue=eig,
            rod_geometry_pass=bool(geo.min() >= -1e-7),
            max_axial_strain=float(np.max(abs(d["q"][:, 3]))),
            planned_equilibrium=accepted,
            solver_reason=why,
            world_head_mm=position(rod, z).tolist(),
        )
        r["envelope_pass"] = bool(
            accepted
            and gap >= 5.0
            and geo.min() >= -1e-7
            and eig > 1e-7
            and T.min() >= 2.5
            and T.max() <= 250.0
            and r["max_axial_strain"] <= 0.05
            and r["axis_error_deg"] < 0.2
        )
        records.append(r)
        if accepted:
            A, C, P = sensitivity(rod, drive, z, R)
            fields[float(pitch)] = (z.copy(), R.copy(), np.vstack((A, C)), T.copy())
        if len(records) % 5 == 0 or not accepted or pitch == end:
            print(
                f"{pitch:+g} deg: error {r['axis_error_deg']:.4f} gap {gap:.2f} Tmin {T.min():.3f} {why}",
                flush=True,
            )
        save_branch(out, sign, records, fields)
        if not accepted:
            break
    return records, fields


def save_branch(out, sign, records, fields):
    suffix = "up" if sign > 0 else "down"
    (out / f"pitch_{suffix}.json").write_text(
        json.dumps(records, indent=2, allow_nan=False) + "\n"
    )
    if fields:
        np.savez_compressed(
            out / f"pitch_{suffix}.npz",
            pitch_deg=list(fields),
            z=[v[0] for v in fields.values()],
            rest_m=[v[1] for v in fields.values()],
            B=[v[2] for v in fields.values()],
            tension_N=[v[3] for v in fields.values()],
        )


def run(a):
    a.out.mkdir(parents=True, exist_ok=True)
    _, rod, _ = load_rod()
    drive = FeedbackDrive(rod)
    tank = FastTank()
    rows = json.loads((BASE / "reference/nominal.json").read_text())
    split = next(i for i, r in enumerate(rows) if r["phase"] == "exit")
    i = split - 1
    with np.load(BASE / "closed_loop/nominal_gains.npz") as g:
        R0 = g["R"][i]
    with np.load(BASE / "reference/nominal_states.npz") as f:
        z0 = f["z"][i]
    drive.stability(z0, R0, drive.force(z0, R0))
    z0 = drive.solve(z0, R0)
    if z0 is None:
        raise ValueError("Neutral planning equilibrium unavailable")
    A, C, P = sensitivity(rod, drive, z0, R0)
    h = position(rod, z0)[1]
    np.savez_compressed(
        a.out / "pitch_neutral.npz", z=z0, rest_m=R0, B=np.vstack((A, C))
    )
    for sign, end in ((1, 90.0), (-1, -90.0)):
        if a.direction == "up" and sign < 0 or a.direction == "down" and sign > 0:
            continue
        solve_branch(
            rod,
            drive,
            tank,
            z0,
            R0,
            (A, C, P),
            sign,
            end,
            a.step,
            a.height_weight,
            h,
            a.out,
            a.allocation,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--step", type=float, default=2.0)
    p.add_argument("--height-weight", type=float, default=0.035)
    p.add_argument("--direction", choices=("both", "up", "down"), default="both")
    p.add_argument(
        "--allocation",
        choices=("height-priority", "minimum-tension"),
        default="height-priority",
    )
    a = p.parse_args()
    run(a)
