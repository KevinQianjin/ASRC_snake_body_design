"""Verify handovers for withdrawal, add one-degree free-space probes and one-mm installed depth brackets."""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import fcl
import trimesh
from common import CAD, OUT, NAMES, trajectory, motion_rows, read, read_csv, save
from pose_map import axis, centreline, clearance, correct, equilibrate
from replay import plant
from closed_loop_cycle import FeedbackDrive
from pitch_reference import angle_between, pointing
from length_cycle import FastTank, to_tank
from adapter import mesh_model
from u_springs import CAD_TO_ROD


def run(out, resume=False):
    tracked = read(out / "pose_paths.json")
    table = read_csv(out / "pose_steps.csv.gz")
    z0, rest0, T0 = trajectory()
    archive = motion_rows()
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    tank = FastTank()
    part = trimesh.load_mesh(CAD / "guides_v2/head_adapter.stl")
    adapter = fcl.CollisionObject(mesh_model(part.vertices @ CAD_TO_ROD.T, part.faces))
    hull = fcl.CollisionObject(mesh_model(tank.mesh.vertices, tank.F))

    def state_for(record, z):
        R = np.array([float(record[n + "_command_mm"]) / 1000 for n in NAMES]).reshape(
            3, 4
        )
        zz = equilibrate(rod, drive, z, R)
        return zz, R

    output = out / "pose_boundary_checks.json"
    previous = read(output) if resume and output.exists() else {}
    boundaries = previous.get("brackets", [])
    returns = previous.get("withdrawal_connections", [])
    completed = previous.get("source_slices", {})
    for path in tracked:
        y = path["yaw_deg"]
        end = path["end_deg"]
        i = path["start_step"]
        part_rows = [
            r
            for r in table
            if int(r["yaw_deg"]) == y and int(r["branch_end_deg"]) == end
        ]
        key = f"{y:+d}/{end:+d}"
        fingerprint = hashlib.sha256(
            json.dumps([path, part_rows], sort_keys=True).encode()
        ).hexdigest()
        if key in completed:
            if completed[key] != fingerprint:
                raise ValueError("Saved slice differs from the current pose study")
            continue
        forward = [
            r for r in part_rows if r["leg"] == "out" and r["free_pass"] == "True"
        ]
        retreat = [r for r in part_rows if r["leg"] == "return"]
        if not forward:
            continue
        cache = {20: z0[i]}
        drive.stability(z0[i], rest0[i], T0[i].reshape(3, 4))

        def get(row):
            p = float(row["target_pitch_deg"])
            R = np.array([float(row[n + "_command_mm"]) / 1000 for n in NAMES]).reshape(
                3, 4
            )
            if p not in cache:
                # Continue along previously archived, solved winch points to get a local converged seed.
                for v in forward:
                    a = float(v["target_pitch_deg"])
                    if (a - 20) * np.sign(end - 20) > (p - 20) * np.sign(end - 20):
                        break
                    if a not in cache:
                        near = min(cache, key=lambda n: abs(a - n))
                        z, _ = state_for(v, cache[near])
                        if z is None:
                            drive.stability(cache[near], R, drive.force(cache[near], R))
                            z, _ = state_for(v, cache[near])
                        if z is None:
                            raise RuntimeError(
                                "Archived forward pose did not reproduce"
                            )
                        cache[a] = z
            return cache[p], R

        last = retreat[-1] if retreat else None
        if last and float(last["target_pitch_deg"]) == 20:
            z, R = state_for(last, z0[i])
            if z is None:
                raise RuntimeError("No neutral connection")
            # Reversing the accepted archive prefix recovers the original withdrawn clamp datum.
            prefix = archive[: i + 1]
            returns.append(
                dict(
                    yaw_deg=y,
                    end_deg=end,
                    source_step=i,
                    command_closure_mm=float(np.max(abs(R - rest0[i])) * 1000),
                    scaled_state_closure=np.max(abs(z - z0[i])),
                    tension_closure_N=np.max(abs(drive.force(z, R).ravel() - T0[i])),
                    reverse_prefix_states=len(prefix),
                    withdrawn_clamp_mm=float(prefix[0]["clamp_s_mm"]),
                    minimum_archived_prefix_gap_mm=min(
                        float(r["tank_clearance_after_allowance_mm"]) for r in prefix
                    ),
                    maximum_archived_prefix_error_deg=max(
                        float(r["pointing_error_deg"]) for r in prefix
                    ),
                )
            )
        else:
            returns.append(
                dict(
                    yaw_deg=y,
                    end_deg=end,
                    source_step=i,
                    connected=False,
                    last_return_pitch_deg=float(last["target_pitch_deg"])
                    if last
                    else None,
                    reason="The solved reverse path did not reconnect to the archived +20 degree hold",
                )
            )
        failed = path["first_free_failure"]
        if failed:
            current = forward[-1]
            lo = float(current["target_pitch_deg"])
            hi = failed["pitch_deg"]
            if abs(hi - lo) > 1:
                z, R = get(current)
                m = (lo + hi) / 2
                zz, rr, why = correct(rod, drive, z, R, axis(y, m))
                T = drive.force(zz, rr)
                e = angle_between(pointing(rod, zz), axis(y, m))
                passed = bool(
                    why is None
                    and e <= 1
                    and T.min() >= 2.5
                    and T.max() <= 250
                    and rod.geometry_constraints(zz).min() >= -1e-7
                    and drive.stability(zz, rr, T) > 0
                    and max(abs((zz / rod.scale).reshape(-1, 4)[:, 3])) <= 0.0475
                )
                if passed:
                    lo = m
                else:
                    hi = m
            boundaries.append(
                dict(
                    kind="free_pitch",
                    yaw_deg=y,
                    branch_end_deg=end,
                    last_pass_deg=lo,
                    first_fail_deg=hi,
                )
            )
        # Depth slices at the most constrained installed pose and the furthest accepted orientation.
        loc = [min(forward, key=lambda r: float(r["gap_depth_15_mm"])), forward[-1]]
        for row in {r["target_pitch_deg"]: r for r in loc}.values():
            z, R = get(row)
            line = centreline(rod, z)
            det = rod.kinematic_metrics(z)[1]
            frame = rod.R0 @ det["frames"][-1]
            depths = []
            for s in range(-15, 46):
                x = to_tank(line[-1:], 20, s, tank.entry_h)[0]
                adapter.setTransform(fcl.Transform(frame, x))
                ag = (
                    max(
                        0.0,
                        fcl.distance(
                            adapter, hull, fcl.DistanceRequest(), fcl.DistanceResult()
                        ),
                    )
                    - 1.5
                )
                g = clearance(tank, line, s)
                depths.append((s, g, ag))
            cross = [
                dict(
                    from_mm=a[0],
                    to_mm=b[0],
                    from_min_gap_mm=min(a[1:]),
                    to_min_gap_mm=min(b[1:]),
                )
                for a, b in zip(depths, depths[1:])
                if (min(a[1:]) >= 5) != (min(b[1:]) >= 5)
            ]
            boundaries.append(
                dict(
                    kind="depth",
                    yaw_deg=y,
                    branch_end_deg=end,
                    pitch_deg=float(row["target_pitch_deg"]),
                    depth_step_mm=1,
                    interval_mm=[-15, 45],
                    brackets=cross,
                    minimum_body_gap_mm=min(v[1] for v in depths),
                    minimum_adapter_gap_mm=min(v[2] for v in depths),
                    samples=depths,
                )
            )
        completed[key] = fingerprint
        save(
            output,
            dict(
                withdrawal_connections=returns,
                brackets=boundaries,
                source_slices=completed,
            ),
        )
        print("boundary check", key, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    run(a.out, a.resume)
