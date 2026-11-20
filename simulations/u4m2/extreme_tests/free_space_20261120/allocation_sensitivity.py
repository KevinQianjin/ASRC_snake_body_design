"""Replay the published two-degree mixed-down command allocations and compare their finite-exit limits."""

import argparse
from pathlib import Path
import numpy as np
from study_context import (
    RESULTS,
    ROUND2,
    NAMES,
    read_csv,
    trajectory,
    write_table,
    save,
)
from pose_map import axis, equilibrate, correct
from pitch_reference import angle_between, pointing
from replay import plant
from closed_loop_cycle import FeedbackDrive
from bellmouth_model import inspect_routing
from shared_bore import RAYS, solve
from cad_screen import Geometry, failed_part


def margins(rod, z, R):
    T = FeedbackDrive(rod).force(z, R)
    ends, _ = inspect_routing(rod.base, z, T)
    val = {
        f"{e['module']}_{e['end']}_{e['set']}_{e['ray']}": e["design_margin_deg"]
        for e in ends
        if not (
            e["set"] == "C"
            and (e["module"], e["end"]) in (("M5", "distal"), ("M6", "proximal"))
        )
    }
    for k, (left, right) in enumerate(rod.endpoints(z[rod.local])):
        _, meta = solve(left, right, rod.profiles, rod.step)
        for j, tag in enumerate(("M5_distal", "M6_proximal")):
            val[f"{tag}_C_{RAYS[k]}"] = (
                np.degrees(rod.profiles[j, 2]) - meta["exit_angles_deg"][j]
            )
    assert len(val) == 24
    n = min(val, key=val.get)
    return T, n, val[n]


def run(root):
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    states, rest, _ = trajectory()
    source = read_csv(ROUND2 / "motion_limits/pose_steps.csv.gz")
    route = []
    audited = []
    summaries = {}
    extra = []
    for yaw, seed in ((175, 913), (-175, 1796)):
        z, R = states[seed], rest[seed]
        drive.stability(z, R, drive.force(z, R))
        active = True
        for r in source:
            if (
                int(r["yaw_deg"]) != yaw
                or int(r["branch_end_deg"]) != -90
                or r["leg"] != "out"
                or r["free_pass"] != "True"
            ):
                continue
            p = float(r["target_pitch_deg"])
            R = (
                np.array([float(r[n + "_command_mm"]) for n in NAMES]).reshape(3, 4)
                / 1000
            )
            zn = equilibrate(rod, drive, z, R)
            if zn is None:
                drive.stability(z, R, drive.force(z, R))
                zn = equilibrate(rod, drive, z, R)
            if zn is None:
                raise ArithmeticError("Published winch command did not reproduce")
            z = zn
            T, tag, margin = margins(rod, z, R)
            tf = np.array([float(r[n + "_N"]) for n in NAMES])
            delta = max(abs(tf - T.ravel()))
            if delta > 1e-4:
                raise ValueError(f"Archived tension mismatch {delta}")
            rec = dict(
                yaw_deg=yaw,
                pitch_deg=p,
                axis_error_deg=angle_between(pointing(rod, z), axis(yaw, p)),
                critical_exit=tag,
                minimum_wrap_reserve_deg=margin,
                archive_tension_difference_N=delta,
            )
            rec.update(
                {n + "_N": float(t) for n, t in zip(NAMES, T.ravel(), strict=True)}
            )
            route.append(rec)
            if active:
                audited.append((yaw, p, z.copy(), R.copy(), T.copy(), rec))
            if margin < 1:
                active = False
    g = Geometry(rod, 0.5)
    details = [rod.base.kinematic_metrics(z)[1] for _, _, z, _, _, _ in audited]
    g.prepare(details)
    checked = []
    for (yaw, p, z, R, T, rec), d in zip(audited, details, strict=True):
        gaps = g.query(d, z, T)
        checked.append(
            dict(**rec, first_failed_geometry=failed_part(gaps) or "", **gaps)
        )
    for yaw in (175, -175):
        seq = [
            (v, raw)
            for v, raw in zip(checked, audited, strict=True)
            if v["yaw_deg"] == yaw
        ]
        fail = next(
            (j for j, (v, raw) in enumerate(seq) if v["first_failed_geometry"]), None
        )
        if fail == 0:
            raise ValueError("Published branch has an obstructed seed")
        idx = len(seq) - 1 if fail is None else fail - 1
        lo = seq[idx][0]["pitch_deg"]
        high = None if fail is None else seq[fail][0]["pitch_deg"]
        why = None if fail is None else seq[fail][0]["first_failed_geometry"]
        _, _, z, R, _, _ = seq[idx][1]
        retrace = [(v[0]["pitch_deg"], v[1][2], v[1][3]) for v in seq[: idx + 1]]
        while high is not None and abs(high - lo) > 1:
            mid = (high + lo) / 2
            zn, rn, reason = correct(rod, drive, z, R, axis(yaw, mid))
            d = rod.base.kinematic_metrics(zn)[1]
            g.prepare([d])
            T, n, m = margins(rod, zn, rn)
            gaps = g.query(d, zn, T)
            cause = reason or failed_part(gaps)
            extra.append(
                dict(
                    yaw_deg=yaw,
                    pitch_deg=mid,
                    reason=cause or "",
                    critical_exit=n,
                    minimum_wrap_reserve_deg=m,
                    **{
                        name + "_N": t for name, t in zip(NAMES, T.ravel(), strict=True)
                    },
                    **gaps,
                )
            )
            if cause:
                high = mid
                why = cause
            else:
                lo = mid
                z, R = zn, rn
                retrace.append((lo, z, R))
        dmax = 0.0
        emin = np.inf
        tmin = np.inf
        for p, expected, cmd in reversed(retrace):
            drive.stability(z, R, drive.force(z, R))
            z = equilibrate(rod, drive, z, cmd)
            R = cmd
            if z is None:
                raise ArithmeticError("Alternative reverse solve failed")
            dmax = max(dmax, float(np.max(abs(z - expected))))
            T = drive.force(z, R)
            emin = min(emin, drive.stability(z, R, T))
            tmin = min(tmin, T.min())
        summaries[str(yaw)] = dict(
            last_screened_pitch_deg=lo,
            first_failed_pitch_deg=high,
            reason=why,
            reverse_commands=len(retrace),
            max_return_state_difference=dmax,
            min_return_tangent=emin,
            min_return_tension_N=tmin,
            recovered_seed=bool(dmax < 1e-7 and emin > 0 and tmin >= 2.5),
        )
        print(yaw, lo, high, why, flush=True)
    out = root / "allocation"
    write_table(out / "archived_replay.csv.gz", route)
    write_table(out / "geometry_prefix.csv.gz", checked)
    if extra:
        write_table(out / "boundary_probes.csv.gz", extra)
    save(
        out / "allocation.json",
        dict(
            source_command_grid_deg=2,
            archived_ideal_last_deg=-87,
            archived_ideal_stop_deg=-88,
            re_equilibrated_saved_out_rows=len(route),
            all_geometry_prefix_states=len(checked),
            paths=summaries,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
