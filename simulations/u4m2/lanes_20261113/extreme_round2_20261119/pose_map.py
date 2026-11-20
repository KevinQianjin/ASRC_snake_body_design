"""Follow combined yaw/elevation slices and reverse the computed winch commands with a 500 g head."""

import argparse
from pathlib import Path
import numpy as np
from scipy.linalg import solve, eigvalsh
from scipy.optimize import minimize, root
from common import (
    OUT,
    NAMES,
    motion_rows,
    trajectory,
    write_table,
    save,
    read,
    read_csv,
)
from replay import plant
from closed_loop_cycle import FeedbackDrive
from length_cycle import FastTank, to_tank
from pitch_reference import pointing, angle_between

DEPTHS = (-15, 15, 45)
YAWS = (0, 45, -45, 90, -90, 135, -135, 160, -160, 175, -175)


def axis(yaw, pitch):
    y, p = np.radians([yaw, pitch])
    return np.array([np.cos(p) * np.cos(y), np.sin(p), np.cos(p) * np.sin(y)])


def tangent(rod, drive, z, R):
    T = drive.force(z, R).ravel()
    J = rod.control_jacobian(z)
    H = drive.tangent(z, R, T.reshape(3, 4))
    drive._last_hessian = H
    dz = solve(H, J.T * ((drive.ea + T) / R.ravel()), assume_a="sym") / 1000
    h = 1e-4
    A = np.column_stack(
        [(pointing(rod, z + h * v) - pointing(rod, z - h * v)) / (2 * h) for v in dz.T]
    )
    C = (drive.ea / R.ravel())[:, None] * (J @ dz) - np.diag(
        (drive.ea + T) / R.ravel()
    ) / 1000
    return A, C, float(eigvalsh(H, subset_by_index=(0, 0))[0])


def correct(rod, drive, z, R, target):
    A, C, e = tangent(rod, drive, z, R)
    for i in range(18):
        actual = pointing(rod, z)
        T = drive.force(z, R).ravel()
        if angle_between(actual, target) < 0.13 and min(T) > 2.68:
            return z, R, None
        if i and i % 4 == 0:
            A, C, e = tangent(rod, drive, z, R)
        miss = (target - actual) * 180 / np.pi
        B = A * 180 / np.pi

        def cost(x):
            d = B @ x - miss
            return 0.5 * (d @ d + 0.006 * x @ x)

        def jac(x):
            return B.T @ (B @ x - miss) + 0.006 * x

        res = minimize(
            cost,
            np.zeros(12),
            jac=jac,
            bounds=[(-1.1, 1.1)] * 12,
            constraints=[
                dict(type="ineq", fun=lambda x: T + C @ x - 2.85, jac=lambda _: C),
                dict(type="ineq", fun=lambda x: 250 - T - C @ x, jac=lambda _: -C),
            ],
            method="SLSQP",
            options=dict(ftol=1e-10, maxiter=85),
        )
        if not res.success and max(abs(res.x)) < 1e-6:
            return z, R, "winch allocation"
        diagnostics = {}
        for scale in (1.0, 0.5, 0.25, 0.125):
            trial = R + scale * res.x.reshape(3, 4) / 1000
            zn = equilibrate(rod, drive, z, trial, diagnostics)
            if zn is not None:
                break
        if zn is None:
            return z, R, diagnostics.get("reason", "equilibrium convergence")
        z, R = zn, trial
    return z, R, "pointing corrector iterations"


def is_rope_domain_error(exc):
    return str(exc) in {
        "Guide lies outside the supported bellmouth tangent domain",
        "End guide must lie in front of its rigid end interface",
    }


def equilibrate(rod, drive, z, R, diagnostics=None):
    def gradient(x):
        return drive.energy(x, R)[1]

    try:
        fit = root(
            gradient,
            z,
            jac=lambda _: drive._last_hessian,
            method="hybr",
            options=dict(xtol=2e-9, maxfev=55),
        )
        if rod.residual(gradient(fit.x)) < 2e-6:
            return fit.x
    except ValueError as exc:
        if not is_rope_domain_error(exc):
            raise
        if diagnostics is not None:
            diagnostics["reason"] = (
                "equilibrium trial exceeded the finite rope routing domain"
            )
    # Retry from the last admissible configuration. Each accepted Newton step must
    # decrease the residual and stay inside the existing physical bellmouth model.
    zz = z.copy()
    for iteration in range(16):
        g = gradient(zz)
        residual = rod.residual(g)
        if residual < 2e-6:
            return zz
        try:
            if iteration % 4 == 0:
                H = drive.tangent(zz, R, drive.force(zz, R))
            delta = solve(H, -g, assume_a="sym")
        except np.linalg.LinAlgError:
            return None
        except ValueError as exc:
            if is_rope_domain_error(exc):
                return None
            raise
        for divisor in (1, 2, 4, 8, 16, 32, 64, 128):
            candidate = zz + delta / divisor
            try:
                after = rod.residual(gradient(candidate))
            except ValueError as exc:
                if not is_rope_domain_error(exc):
                    raise
                continue
            if after < residual:
                zz = candidate
                break
        else:
            return None
    return zz if rod.residual(gradient(zz)) < 2e-6 else None


def centreline(rod, z):
    d = rod.kinematic_metrics(z)[1]
    return np.vstack([np.zeros(3), d["points"] + [0.02, 0, 0]]) @ rod.R0.T * 1000


def clearance(tank, line, depth):
    return float(tank.clearance(to_tank(line, 20.0, depth, tank.entry_h))[0] - 1.5)


def run(out, yaws, resume=False):
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    tank = FastTank()
    zr, rr, _ = trajectory()
    motion = motion_rows()
    archive_yaw = np.array([float(r["target_yaw_deg"]) for r in motion])
    phase = np.array([r["phase"] for r in motion])
    records = []
    paths = []
    if resume and (out / "pose_paths.json").exists():
        paths = read(out / "pose_paths.json")
        records = read_csv(out / "pose_steps.csv.gz")
        existing = {(v["yaw_deg"], v["end_deg"]) for v in paths}
        # The CSV is installed before its summary. Recover only committed slice pairs after interruption.
        records = [
            r
            for r in records
            if (int(r["yaw_deg"]), int(r["branch_end_deg"])) in existing
        ]
    finished = {(r["yaw_deg"], r["end_deg"]) for r in paths}
    for yaw in yaws:
        if all((yaw, end) in finished for end in (-90, 90)):
            continue
        ids = np.flatnonzero(phase == ("right_out" if yaw >= 0 else "left_out"))
        start = int(
            ids[
                np.argmin(
                    abs(archive_yaw[ids] - yaw)
                    + 0.001
                    * np.array([float(motion[i]["pointing_error_deg"]) for i in ids])
                )
            ]
        )
        line = centreline(rod, zr[start])
        connector = {
            d: min(clearance(tank, line, s) for s in range(min(d, 15), max(d, 15) + 1))
            for d in DEPTHS
        }
        for direction, end in ((1, 90), (-1, -90)):
            if (yaw, end) in finished:
                continue
            z, R = zr[start].copy(), rr[start].copy()
            outward = []
            failure = None

            def record(leg, p, z, R, why):
                T = drive.force(z, R).ravel()
                err = angle_between(pointing(rod, z), axis(yaw, p))
                eig = drive.stability(z, R, T.reshape(3, 4))
                line = centreline(rod, z)
                geo = rod.geometry_constraints(z).min()
                axial = np.max(abs((z / rod.scale).reshape(-1, 4)[:, 3]))
                row = dict(
                    yaw_deg=yaw,
                    branch_end_deg=end,
                    leg=leg,
                    target_pitch_deg=p,
                    source_step=start,
                    axis_error_deg=err,
                    tangent_min=eig,
                    geometry_margin=geo,
                    axial_strain_max=axial,
                    residual=rod.residual(drive.energy(z, R)[1]),
                    minimum_N=min(T),
                    maximum_N=max(T),
                    free_pass=bool(
                        why is None
                        and err <= 1
                        and eig > 0
                        and geo >= -1e-7
                        and axial <= 0.0475
                        and min(T) >= 2.5
                        and max(T) <= 250
                    ),
                    reason=why or "",
                    **{f"gap_depth_{d}_mm": clearance(tank, line, d) for d in DEPTHS},
                )
                for n, t, h in zip(NAMES, T, R.flat):
                    row[n + "_N"] = t
                    row[n + "_command_mm"] = h * 1000
                records.append(row)
                return row

            outward.append((20, z.copy(), R.copy(), record("out", 20, z, R, None)))
            # All named plan elevations, with a maximum two-degree spacing in between.
            pitches = sorted(
                set(
                    list(range(20 + 2 * direction, end + direction, 2 * direction))
                    + [
                        p
                        for p in (-60, -30, 0, 45, 69, 90, -90)
                        if (p - 20) * direction > 0 and (end - p) * direction >= 0
                    ]
                ),
                reverse=direction < 0,
            )
            for p in pitches:
                z0, r0 = z, R
                z, R, why = correct(rod, drive, z, R, axis(yaw, p))
                row = record("out", p, z, R, why)
                if row["free_pass"]:
                    # Locate the first 5 mm tank gap crossing to within one degree on this slice.
                    last_p, _, _, prev = outward[-1]
                    if abs(last_p - p) > 1 and any(
                        (prev[f"gap_depth_{d}_mm"] >= 5)
                        != (row[f"gap_depth_{d}_mm"] >= 5)
                        for d in DEPTHS
                    ):
                        mid = (last_p + p) / 2
                        zm, rm, reason = correct(rod, drive, z0, r0, axis(yaw, mid))
                        record("boundary_probe", mid, zm, rm, reason)
                    outward.append((p, z.copy(), R.copy(), row))
                else:
                    failure = dict(
                        pitch_deg=p,
                        reason=why or "mechanical acceptance",
                        error_deg=row["axis_error_deg"],
                    )
                    # Resolve the last accepted command before beginning the return.
                    z = equilibrate(rod, drive, z, outward[-1][2])
                    if z is None:
                        failure["recovery"] = "equilibrium convergence"
                        break
                    break
            reverse = []
            if z is not None:
                for p, zref, cmd, _ in reversed(outward):
                    zn = equilibrate(rod, drive, z, cmd)
                    if zn is None:
                        reverse.append(
                            record(
                                "return", p, z, cmd, "reverse equilibrium convergence"
                            )
                        )
                        break
                    z = zn
                    reverse.append(record("return", p, z, cmd, None))
            by_depth = {}
            for d in DEPTHS:
                key = f"gap_depth_{d}_mm"
                through = connector[d] >= 5
                safe = []
                for p, _, _, row in outward:
                    through = through and row[key] >= 5
                    if through:
                        safe.append(p)
                reverse_ok = len(reverse) == len(outward) and all(
                    v["free_pass"] for v in reverse
                )
                returned = {v["target_pitch_deg"]: v for v in reverse}
                recoverable = []
                for p in safe:
                    r = returned.get(p)
                    if not r or not r["free_pass"] or r[key] < 5:
                        break
                    recoverable.append(p)
                by_depth[d] = dict(
                    connector_min_mm=connector[d],
                    last_contiguous_out_deg=safe[-1] if safe else None,
                    last_retraceable_deg=recoverable[-1] if recoverable else None,
                    full_slice_return=bool(
                        reverse_ok
                        and len(safe) == len(outward)
                        and len(recoverable) == len(outward)
                        and failure is None
                    ),
                )
            paths.append(
                dict(
                    yaw_deg=yaw,
                    end_deg=end,
                    start_step=start,
                    forward_samples=len(outward),
                    reverse_samples=len(reverse),
                    first_free_failure=failure,
                    depths=by_depth,
                )
            )
            print(
                yaw,
                end,
                len(outward),
                failure,
                {d: v["last_retraceable_deg"] for d, v in by_depth.items()},
                flush=True,
            )
            write_table(out / "pose_steps.csv.gz", records)
            save(out / "pose_paths.json", paths)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--yaw", nargs="+", type=int, default=YAWS)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out, a.yaw, a.resume)
