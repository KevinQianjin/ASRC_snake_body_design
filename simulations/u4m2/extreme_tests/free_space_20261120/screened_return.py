"""Start the return at the last screened state and reverse just that accepted command prefix."""

import argparse
from pathlib import Path
import numpy as np
from study_context import (
    RESULTS,
    NAMES,
    read,
    read_csv,
    save,
    write_table,
    motion_rows,
    trajectory,
)
from free_space import PATHS, coordinates
from mesh_limits import saved_state
from pose_map import axis, equilibrate
from replay import plant
from closed_loop_cycle import FeedbackDrive
from pitch_reference import pointing, angle_between


def run(root, names):
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    archive = motion_rows()
    zr, rest, _ = trajectory()
    for name in names:
        mode, fixed, phase, _ = PATHS[name]
        lo = read(root / "geometry" / (name + ".json"))["paths"][name][
            "last_contiguous_screened_deg"
        ]
        if lo is None:
            continue
        im = read(root / "angles" / (name + ".json"))
        start = im["seed_deg"]
        rows = read_csv(root / "angles" / (name + ".csv.gz"))
        front = [
            r
            for r in rows
            if r["leg"] != "return"
            and r["pass_ideal"] == "True"
            and abs(float(r["command_deg"]) - start) <= abs(lo - start) + 1e-7
        ]
        probes = root / "geometry" / (name + "_probes.csv.gz")
        if probes.exists():
            front.extend(
                r
                for r in read_csv(probes)
                if r["out_pass"] == "True"
                and abs(float(r["command_deg"]) - start) <= abs(lo - start) + 1e-7
            )
        front.sort(key=lambda r: abs(float(r["command_deg"]) - start), reverse=True)
        z, R = saved_state(name, lo, root / "angles", root / "geometry", rod, drive)
        data = []
        seq = [(name, float(r["command_deg"]), r) for r in front]
        if name == "antipode":
            parent = [
                r
                for r in read_csv(root / "angles/right.csv.gz")
                if r["pass_ideal"] == "True"
                and r["leg"] != "return"
                and float(r["command_deg"]) < 180
            ]
            seq.extend(("right", float(r["command_deg"]), r) for r in reversed(parent))
        for segment, a, r in seq:
            mode, fixed, _, _ = PATHS[segment]
            y, p = coordinates(mode, fixed, a)
            ref, cmd = saved_state(
                segment, a, root / "angles", root / "geometry", rod, drive
            )
            drive.stability(z, R, drive.force(z, R))
            state = equilibrate(rod, drive, z, cmd)
            if state is None:
                raise ArithmeticError(f"Return failed at {segment} {a}")
            z, R = state, cmd
            t = drive.force(z, R)
            err = angle_between(pointing(rod, z), axis(y, p))
            eig = drive.stability(z, R, t)
            residual = rod.residual(drive.energy(z, R)[1])
            delta = np.max(abs(z - ref))
            v = dict(
                segment=segment,
                command_deg=a,
                yaw_deg=y,
                pitch_deg=p,
                axis_error_deg=err,
                tangent_min=eig,
                residual=residual,
                scaled_state_difference_to_screened_forward=delta,
                max_force_difference_N=np.max(
                    abs(t.ravel() - np.array([float(r[n + "_N"]) for n in NAMES]))
                ),
                pass_return=bool(
                    err <= 1
                    and eig > 0
                    and residual < 2e-6
                    and t.min() >= 2.5
                    and t.max() <= 250
                    and delta < 1e-7
                ),
            )
            v.update({n + "_N": f for n, f in zip(NAMES, t.ravel(), strict=True)})
            data.append(v)
        step = im["source_step"]
        phases = {
            "right_out": "right_return",
            "left_out": "left_return",
            "pitch_up": "pitch_up_return",
            "pitch_down": "pitch_down_return",
        }
        handover = np.max(abs(z - zr[step]))
        if archive[step + 1]["phase"] != phases[phase]:
            raise ValueError("Archived neutral-return leg does not follow the seed")
        neutral = max(i for i, r in enumerate(archive) if r["phase"] == phases[phase])
        write_table(root / "return" / (name + ".csv.gz"), data)
        save(
            root / "return" / (name + ".json"),
            dict(
                path=name,
                turn_deg=lo,
                checked=len(data),
                all_pass=all(v["pass_return"] for v in data) and handover < 1e-7,
                maximum_forward_return_difference=max(
                    v["scaled_state_difference_to_screened_forward"] for v in data
                ),
                max_force_difference_N=max(v["max_force_difference_N"] for v in data),
                seed_step=step,
                seed_command_difference_mm=np.max(abs(R - rest[step])) * 1000,
                seed_state_difference=handover,
                archived_neutral_step=neutral,
                archived_neutral_yaw_deg=float(archive[neutral]["target_yaw_deg"]),
                archived_neutral_pitch_deg=float(
                    archive[neutral]["target_elevation_deg"]
                ),
            ),
        )
        print(name, lo, handover, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="*", metavar="PATH")
    p.add_argument("--results", type=Path, default=RESULTS)
    a = p.parse_args()
    run(a.results, a.paths or PATHS)
