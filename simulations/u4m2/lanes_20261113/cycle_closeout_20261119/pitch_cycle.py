"""Continue the same closed loop through vertical-up and vertical-down sweeps and withdrawal."""

import argparse
import gzip
import json
from pathlib import Path
import tempfile

import numpy as np

from replay import BASE, Runner, pack, plant, digest, controller_settings
from pitch_reference import (
    angle_between,
    angular_error,
    pitch_axes,
    pointing,
    target_axis,
)

PITCH = ("pitch_up", "pitch_up_return", "pitch_down", "pitch_down_return")


class PointingRunner(Runner):
    def measured_angles(self, z, phase):
        if phase in PITCH:
            return pitch_axes(pointing(self.r, z))
        return super().measured_angles(z, phase)

    def check(self, z, R, s, target, kind, index, phase):
        if phase not in PITCH:
            return super().check(z, R, s, target, kind, index, phase)
        axis = pointing(self.r, z)
        measured = pitch_axes(axis)
        # Score the inherited mechanical checks separately. The directional test below supplies the angle gate.
        d = np.degrees(self.r.kinematic_metrics(z)[0])
        row, P = super().check(z, R, s, [d[0], d[2]], kind, index, phase)
        errors = angular_error(target, measured)
        direction_error = angle_between(axis, target_axis(target[1]))
        row.update(
            checked_angle_coordinates="out_of_plane_and_signed_pitch",
            yaw_error_deg=None,
            elevation_error_deg=float(target[1] - row["elevation_deg"]),
            target_signed_pitch_deg=float(target[1]),
            out_of_plane_deg=float(measured[0]),
            signed_pitch_deg=float(measured[1]),
            head_direction_xyz=axis.tolist(),
            pointing_error_deg=direction_error,
            controlled_errors_deg=errors.tolist(),
            checks_pass=bool(row["checks_pass"] and direction_error <= 1.0),
        )
        return row, P


def plan(prefix, work):
    ref = json.loads((BASE / "reference/nominal.json").read_text())
    split = next(i for i, r in enumerate(ref) if r["phase"] == "exit")
    with np.load(BASE / "closed_loop/nominal_gains.npz") as f:
        B = f["B"]
        R = f["R"]
        angles = f["target"]
    with np.load(BASE / "reference/nominal_states.npz") as f:
        seeds = f["z"]
    with np.load(prefix / "pitch_neutral.npz") as f:
        neutral = (f["z"], f["rest_m"], f["B"], 20.0)
    entries = []
    attempts = []
    for name, phase, goal in (("up", "pitch_up", 90.0), ("down", "pitch_down", -90.0)):
        rows = json.loads((prefix / f"pitch_{name}.json").read_text())
        with np.load(prefix / f"pitch_{name}.npz") as f:
            by = {
                float(a): (z, r, b, float(a))
                for a, z, r, b in zip(f["pitch_deg"], f["z"], f["rest_m"], f["B"])
            }
        # Execute every geometry-qualified contiguous reference until the first failed preflight.
        safe = []
        for row in rows:
            a = row["target_deg"]
            if not row["envelope_pass"] or a not in by:
                break
            safe.append(by[a])
        attempts.append(
            dict(
                requested_target_deg=goal,
                terminal_qualified_reference_deg=safe[-1][3] if safe else 20.0,
                first_rejected_preflight=next(
                    (r for r in rows if not r["envelope_pass"]), None
                ),
                preflight_reached_target=bool(
                    safe and abs(safe[-1][3] - goal) < 1.0e-9
                ),
            )
        )
        if safe:
            entries.extend((phase, v) for v in safe)
            entries.extend(
                (phase + "_return", v) for v in [*reversed(safe[:-1]), neutral]
            )
    rows = [
        *ref[:split],
        *[
            dict(
                phase=ph,
                clamp_s_mm=15.0,
                target_yaw_deg=0.0,
                target_signed_pitch_deg=v[3],
            )
            for ph, v in entries
        ],
        *ref[split:],
    ]
    for ix, r in enumerate(rows):
        r["index"] = ix
    start = split
    n = len(entries)
    rr = np.concatenate(
        [R[:start], np.array([v[1] for _, v in entries]).reshape(n, 3, 4), R[start:]]
    )
    bb = np.concatenate(
        [B[:start], np.array([v[2] for _, v in entries]).reshape(n, 14, 12), B[start:]]
    )
    aa = np.concatenate(
        [
            angles[:start],
            np.array([(0.0, v[3]) for _, v in entries]).reshape(n, 2),
            angles[start:],
        ]
    )
    gg = work / "gains.npz"
    np.savez_compressed(gg, R=rr, B=bb, target=aa)
    np.savez_compressed(
        work / "nominal_states.npz",
        z=np.concatenate(
            [
                seeds[:start],
                np.array([v[0] for _, v in entries]).reshape(n, -1) if n else seeds[:0],
                seeds[start:],
            ]
        ),
    )
    (work / "nominal.json").write_text(json.dumps(rows))
    return rows, aa, split, gg, attempts


def audit_rows(records, trace, attempts, expected):
    def error(r):
        return max(
            abs(v)
            for v in r.get(
                "controlled_errors_deg", (r["yaw_error_deg"], r["elevation_error_deg"])
            )
        )

    m = [r for r in trace if r["kind"] != "start"]
    turns = []
    for ph, goal in (("pitch_up", 90.0), ("pitch_down", -90.0)):
        group = [r for r in records if r["phase"] == ph]
        r = group[-1] if group else None
        turns.append(
            dict(
                phase=ph,
                requested_deg=goal,
                actual_terminal_signed_pitch_deg=r["signed_pitch_deg"] if r else None,
                terminal_reference_deg=r["target_signed_pitch_deg"] if r else None,
                error_to_requested_direction_deg=angle_between(
                    r["head_direction_xyz"], target_axis(goal)
                )
                if r
                else None,
                index=r["index"] if r else None,
                tensions_N=r["tensions_n"] if r else None,
                terminal_after_allowance_mm=r["clearance_mm"] - 1.5 if r else None,
                endpoint_reached=bool(
                    r
                    and r["target_signed_pitch_deg"] == goal
                    and angle_between(r["head_direction_xyz"], target_axis(goal)) <= 0.2
                ),
            )
        )
    failures = [
        dict(
            index=r["index"],
            kind=r["kind"],
            phase=r["phase"],
            angular_error_deg=error(r),
            minimum_tension_N=r["minimum_tension_n"],
            tank_after_allowance_mm=r["clearance_mm"] - 1.5,
        )
        for r in m
        if not (
            r["checks_pass"]
            and r["residual"] < 2.0e-6
            and r["operating_tension_pass"]
            and r["node_move_mm"] <= 4.5 + 1e-8
        )
    ]
    unsettled = [
        r["index"]
        for r in records
        if error(r) > 0.2
        or not r["operating_tension_pass"]
        or not r["checks_pass"]
        or r["residual"] >= 2.0e-6
        or (r.get("pointing_error_deg", 0.0) > 0.2)
    ]
    return dict(
        requested_pitch_deg=[90, -90],
        base_working_pitch_deg=20.0,
        input_control="Yaw/elevation in yaw phases; out-of-plane angle and signed forward/up pitch for pitch phases. Direction-vector error also scores both vertical poles.",
        requested_cycle_pass=bool(
            len(records) == expected
            and all(t["endpoint_reached"] for t in turns)
            and not failures
            and not unsettled
        ),
        reference_completed=len(records) == expected,
        expected_executed_reference_count=expected,
        settled_targets=len(records),
        accepted_motion_states_including_start=len(trace),
        pitch_preflight=attempts,
        turning_points=turns,
        failed_motion_checks=failures,
        unsettled_or_failed_targets=unsettled,
        minimum_motion_tension_N=min(r["minimum_tension_n"] for r in m),
        peak_motion_tension_N=max(r["peak_tension_n"] for r in m),
        minimum_motion_tank_after_allowance_mm=min(r["clearance_mm"] for r in m) - 1.5,
        peak_motion_angle_coordinate_error_deg=max(error(r) for r in m),
        maximum_node_step_mm=max(r["node_move_mm"] for r in m),
        peak_pitch_direction_error_deg=max(
            (r.get("pointing_error_deg", 0.0) for r in m), default=None
        ),
        minimum_fixed_winch_eigenvalue=min(r["minimum_eigenvalue"] for r in m),
        peak_motion_equilibrium_residual=max(r["residual"] for r in m),
    )


def run(a):
    a.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as path:
        work = Path(path)
        ref, targets, split, g, attempts = plan(a.plan, work)
        a.ref = work
        a.gains = g
        a.limit = None
        controller_settings(a)
        model, mass = plant()
        run = PointingRunner("nominal", a, rod=model)
        with gzip.open(a.base / "controller_records.json.gz", "rt") as f:
            records = json.load(f)[:split]
        with gzip.open(a.base / "motion_trace.json.gz", "rt") as f:
            prefix = [r for r in json.load(f) if r["index"] < split]
        with np.load(a.base / "controller_states.npz") as b:
            zs = list(b["settled_z"][:split])
            rests = list(b["settled_rest_m"][:split])
            run.trace_states = list(b["motion_z"][: len(prefix)])
            run.trace_rest = list(b["motion_rest_m"][: len(prefix)])
        run.trace = list(prefix)
        run.max_move = max(r["node_move_mm"] for r in prefix)
        prev = records[-1]
        z = zs[-1]
        R = rests[-1]
        if prev["phase"] != "left_return" or (prev["index"], len(prefix)) != (
            split - 1,
            len(run.trace_states),
        ):
            raise ValueError("The prefix must end at the same neutral left return")
        continuation = dict(
            start_index=split,
            z=z,
            rest_m=R,
            clamp_s_mm=prev["clamp_s_mm"],
            target=targets[split - 1],
            offset_mm=np.asarray(prev["offset_mm"]),
            correction_scale=prev["correction_scale"],
            phase=prev["phase"],
        )

        def accept(index, r, z, rest, runner):
            records.append(r)
            zs.append(z.copy())
            rests.append(rest.copy())

        failure = None
        try:
            run.run(accept, continuation=continuation)
        except (ValueError, RuntimeError, ArithmeticError) as e:
            failure = str(e)
            print(failure, flush=True)
        pack(a.out, run, records, zs, rests)
        summary = audit_rows(records, run.trace, attempts, len(ref))
        summary.update(
            prefix_settled_targets=split,
            prefix_motion_samples=len(prefix),
            reference_input_archive_sha256=digest(a.base / "controller_states.npz"),
            continuation_solver_failure=failure,
            mass=mass,
        )
        (a.out / "summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n"
        )
        print(
            summary["settled_targets"],
            summary["turning_points"],
            summary["requested_cycle_pass"],
            flush=True,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
