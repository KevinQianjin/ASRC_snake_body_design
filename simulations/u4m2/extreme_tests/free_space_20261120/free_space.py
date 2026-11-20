"""Continue actual 12-winch equilibria in free space and replay the accepted commands in reverse."""

import argparse
import numpy as np
from study_context import (
    MODULES,
    NAMES,
    RESULTS,
    motion_rows,
    read_csv,
    save,
    trajectory,
    write_table,
)
from closed_loop_cycle import FeedbackDrive
from guide_loads import record as guide_record
from pitch_reference import pointing, angle_between
from pose_map import axis, correct, equilibrate, is_rope_domain_error
from replay import plant

# Coordinate, fixed other coordinate, seed phase, finite search cap.
PATHS = {
    "right": ("yaw", 20, "right_out", 540),
    "left": ("yaw", 20, "left_out", -540),
    "up": ("pitch", 0, "pitch_up", 360),
    "down": ("pitch", 0, "pitch_down", -360),
    "right_up": ("pitch", 175, "right_out", 200),
    "right_down": ("pitch", 175, "right_out", -200),
    "left_up": ("pitch", -175, "left_out", 200),
    "left_down": ("pitch", -175, "left_out", -200),
    "antipode": ("pitch", 180, "right_out", -20),
}


def coordinates(mode, fixed, value):
    return (value, fixed) if mode == "yaw" else (fixed, value)


def metrics(rod, drive, z, R, yaw, pitch, failure):
    actual = pointing(rod, z)
    error = angle_between(actual, axis(yaw, pitch))
    _, _, d = rod.evaluate(z, detail=True)
    q = d["q"]
    cell_mm = rod.l * 1000
    curvature = np.linalg.norm(q[:, 1:3], axis=1) / (cell_mm * (1 + q[:, 3]))
    geo = rod.geometry_constraints(z, d)
    idx = int(np.argmin(geo[len(q) :]))
    gap = rod.diameter * 1000 * (np.sqrt(max(0.0, 1 + geo[len(q) + idx])) - 1)
    tensions = drive.force(z, R)
    try:
        eig = drive.stability(z, R, tensions)
    except ValueError as exc:
        if not is_rope_domain_error(exc):
            raise
        eig = None
        failure = failure or "finite-difference tangent outside rope routing domain"
    residual = rod.residual(drive.energy(z, R)[1])
    axial = float(max(abs(q[:, 3])))
    j = int(np.argmax(curvature))
    location = f"{MODULES[j // rod.sub]} cell {1 + j % rod.sub}"
    lim = failure or next(
        (
            label
            for bad, label in (
                (residual >= 2e-6, "equilibrium residual"),
                (error > 1.0, "pointing error"),
                (np.min(geo[: len(q)]) < -1e-7, "local curvature clearance"),
                (gap < -1e-5, "nonlocal body capsules"),
                (axial > 0.0475, "axial rod screen"),
                (np.min(tensions) < 2.5, "distal tension floor"),
                (np.max(tensions) > 250, "solver tension ceiling"),
                (eig is None or eig <= 0, "fixed-winch tangent"),
            )
            if bad
        ),
        "",
    )
    out = dict(
        yaw_deg=yaw,
        pitch_deg=pitch,
        pass_ideal=not lim,
        reason=lim,
        axis_error_deg=error,
        head_x=actual[0],
        head_y=actual[1],
        head_z=actual[2],
        residual=residual,
        tangent_min=eig,
        body_capsule_gap_mm=gap,
        capsule_segment_i=int(rod.ii[idx]),
        capsule_segment_j=int(rod.jj[idx]),
        local_radius_mm=1 / curvature[j],
        curvature_location=location,
        axial_strain_max=axial,
        min_N=tensions.min(),
        max_N=tensions.max(),
    )
    for i, m in enumerate(MODULES):
        s = slice(i * rod.sub, (i + 1) * rod.sub)
        a, b = d["frames"][i * rod.sub, :, 0], d["frames"][(i + 1) * rod.sub, :, 0]
        out[m + "_end_tangent_deg"] = angle_between(a, b)
        out[m + "_accum_bend_deg"] = np.degrees(np.linalg.norm(q[s, 1:3], axis=1).sum())
        out[m + "_signed_twist_deg"] = np.degrees(q[s, 0].sum())
        out[m + "_min_radius_mm"] = 1 / max(curvature[s])
        if m.startswith("M"):
            # Signed section demand envelope on a 1.8 mm circular backbone, reference curvature.
            bending = 0.9 * np.linalg.norm(q[s, 1:3], axis=1) / cell_mm
            out[m + "_fibre_tensile_strain"] = max(q[s, 3] + bending)
            out[m + "_fibre_compressive_strain"] = min(q[s, 3] - bending)
    for n, t, h, length in zip(
        NAMES, tensions.flat, R.flat, d["rope_lengths"].flat, strict=True
    ):
        out[n + "_N"], out[n + "_command_mm"], out[n + "_internal_mm"] = (
            t,
            h * 1000,
            length * 1000,
        )
    tags, loads, *_ = guide_record(rod.base, rod.profiles, z, tensions, True)
    for mod in ("M5", "M6"):
        for st in (-24, -12, 12, 24):
            ids = [i for i, v in enumerate(tags) if v[:2] == (mod, st)]
            if ids:
                force, moment = loads[ids].sum(0)
                for k, v in zip(
                    ("Fx_N", "Fy_N", "Fz_N", "Mx_Nmm", "My_Nmm", "Mz_Nmm"),
                    np.r_[force, moment],
                    strict=True,
                ):
                    out[f"{mod}_{st:+}_{k}"] = v
    return out


def run(name, out):
    mode, fixed, phase, cap = PATHS[name]
    zr, rr, tr = trajectory()
    motion = motion_rows()
    seed = max(i for i, r in enumerate(motion) if r["phase"] == phase)
    start = float(
        motion[seed]["target_yaw_deg" if mode == "yaw" else "target_elevation_deg"]
    )
    direction = np.sign(cap - start)
    z, R = zr[seed].copy(), rr[seed].copy()
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    np.testing.assert_allclose(drive.force(z, R).ravel(), tr[seed].ravel(), atol=2e-7)
    if name == "antipode":
        row = next(
            r
            for r in read_csv(out / "right.csv.gz")
            if r["leg"] == "out"
            and float(r["yaw_deg"]) == 180
            and r["pass_ideal"] == "True"
        )
        with np.load(out / "right_states.npz") as data:
            z = data["z"][int(row["index"])]
        R = (
            np.array([float(row[n + "_command_mm"]) for n in NAMES]).reshape(3, 4)
            / 1000
        )
    origin_state = z.copy()
    history, rows, states = [], [], []

    def record(leg, value, z, R, reason=None):
        yaw, pitch = coordinates(mode, fixed, value)
        r = dict(
            path=name,
            index=len(rows),
            leg=leg,
            command_deg=value,
            source_step=seed,
            **metrics(rod, drive, z, R, yaw, pitch, reason),
        )
        rows.append(r)
        states.append(z.copy())
        return r

    origin = record("seed", start, z, R)
    if not origin["pass_ideal"]:
        raise ValueError(f"Archived seed failed: {origin['reason']}")
    history.append((start, z.copy(), R.copy()))
    last = start
    rejected = None
    while direction * (cap - last) > 0:
        trial = last + direction * min(4, abs(cap - last))
        if rejected is None:
            landmarks = (180, -180, 360, -360) if mode == "yaw" else (-160, 200)
            ahead = [
                v for v in landmarks if 0 < direction * (v - last) < abs(trial - last)
            ]
            if ahead:
                trial = min(ahead, key=lambda v: abs(v - last))
        else:
            trial = (last + rejected) / 2
        try:
            zn, rn, why = correct(
                rod,
                drive,
                z,
                R,
                axis(*coordinates(mode, fixed, trial)),
                tol_deg=0.002 if name == "antipode" and trial == cap else 0.13,
            )
            row = record("out", trial, zn, rn, why)
        except ValueError as exc:
            if not is_rope_domain_error(exc):
                raise
            row = record(
                "out",
                trial,
                z,
                R,
                "corrector exceeded finite rope routing domain; recorded previous state",
            )
        if len(rows) % 16 == 0 or not row["pass_ideal"]:
            print(name, trial, row["reason"] or "accepted", flush=True)
        if row["pass_ideal"]:
            history.append((trial, zn.copy(), rn.copy()))
            last, z, R = trial, zn, rn
        else:
            rejected = trial
        if rejected is not None and abs(rejected - last) <= 1.0:
            break
    reverse = []
    for value, zref, command in reversed(history):
        state = equilibrate(rod, drive, z, command)
        row = record(
            "return",
            value,
            z if state is None else state,
            command,
            "reverse equilibrium convergence" if state is None else None,
        )
        reverse.append(row)
        if not row["pass_ideal"]:
            break
        z = state
    out.mkdir(parents=True, exist_ok=True)
    write_table(out / (name + ".csv.gz"), rows)
    np.savez_compressed(out / (name + "_states.npz"), z=np.array(states))
    failures = [r for r in rows if r["leg"] == "out" and not r["pass_ideal"]]
    limiting = next(
        (r for r in reversed(failures) if r["command_deg"] == rejected), None
    )
    forward = [r for r in rows if r["leg"] != "return" and r["pass_ideal"]]
    reverse_ok = len(reverse) == len(history) and all(r["pass_ideal"] for r in reverse)
    summary = dict(
        path=name,
        source_step=seed,
        source_phase=phase,
        connector="right to 180 deg"
        if name == "antipode"
        else "archived mission to seed",
        seed_deg=start,
        limit_deg=cap,
        last_pass_deg=last,
        first_rejected_deg=rejected,
        limiting_reason=limiting["reason"] if limiting else "search cap",
        return_to_seed=reverse_ok,
        closure_state_difference=float(np.max(abs(z - origin_state)))
        if reverse_ok
        else None,
        accepted_forward=len(history),
        attempted_forward=len(rows) - len(reverse),
        reverse_steps=len(reverse),
        max_pass_error_deg=max(r["axis_error_deg"] for r in forward),
        min_pass_tangent=min(r["tangent_min"] for r in forward),
        min_pass_tension_N=min(r["min_N"] for r in forward),
        max_pass_tension_N=max(r["max_N"] for r in forward),
        minima_self_gap_mm=min(r["body_capsule_gap_mm"] for r in forward),
    )
    save(out / (name + ".json"), summary)
    print(
        name,
        last,
        rejected,
        summary["limiting_reason"],
        "retrace",
        reverse_ok,
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="*", metavar="PATH")
    from pathlib import Path

    p.add_argument("--out", type=Path, default=RESULTS / "angles")
    a = p.parse_args()
    for path in a.paths or PATHS:
        if path not in PATHS:
            p.error(f"Unknown path {path}")
        run(path, a.out)
