"""Couple twelve directional sliding force laws to the rod at the four executed mission turns."""

import argparse
import csv
import json
import gzip
from pathlib import Path
import numpy as np
from scipy.optimize import root

from replay import plant
from pitch_reference import pointing, position, angle_between
from sliding import on_material, virtual_work
from closed_loop_cycle import FeedbackDrive
from tension_report import NAMES

TURNS = ("right_out", "left_out", "pitch_up", "pitch_down")


def command_signs(rest, rows, turn, side):
    """Use the simultaneous change in commanded length to the nearest different orientation target."""
    y0, p0 = rows[turn]["target_yaw_deg"], rows[turn]["target_elevation_deg"]
    for k in range(turn + side, len(rows) if side > 0 else -1, side):
        if (
            abs(rows[k]["target_yaw_deg"] - y0)
            + abs(rows[k]["target_elevation_deg"] - p0)
        ) > 1.0e-5:
            mm = side * (rest[k] - rest[turn]).ravel() * 1000
            return k, mm, np.where(abs(mm) < 0.001, 0, np.sign(mm)).astype(int)
    raise ValueError("No neighbouring distinct target")


def run(src, coefficients):
    with gzip.open(src / "controller_records.json.gz", "rt") as f:
        rows = json.load(f)
    with np.load(src / "controller_states.npz") as f:
        poses = f["settled_z"]
        rest = f["settled_rest_m"]
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    results = []
    fields = []
    field_ids = []
    for ph in TURNS:
        ii = [i for i, r in enumerate(rows) if r["phase"] == ph]
        if not ii:
            continue
        i = ii[-1]
        z0 = poses[i]
        R = rest[i]
        nominal = drive.force(z0, R)
        H = drive.tangent(z0, R, nominal)
        for direction, side in (("approach", -1), ("departure", 1)):
            neighbour, delta, signs = command_signs(rest, rows, i, side)
            seed = z0.copy()

            def evaluate(z, mu, details=False):
                T = drive.force(z, R)
                common = (
                    rod.base.evaluate(z, detail=True)[2],
                    rod.endpoints(z[rod.local]),
                    T,
                )
                g = drive.energy(z, R)[1].copy()
                info = []
                for k, sign in enumerate(signs):
                    force, report, nodes, local, point = on_material(
                        rod, z, R, drive, k, mu, int(sign), common
                    )
                    g += force
                    if details:
                        report.pop("other_minimum_N")
                        report.update(
                            rope=NAMES[k],
                            imposed_sign=int(sign),
                            virtual_work_error=virtual_work(
                                rod, z, nodes, local, point, force
                            ),
                        )
                        info.append(report)
                return g, info

            zero = rod.residual(evaluate(z0, 0.0)[0])
            for mu in coefficients:
                trial = root(
                    lambda z: evaluate(z, mu)[0],
                    seed,
                    jac=lambda _: H,
                    method="hybr",
                    options=dict(xtol=2e-9, maxfev=110),
                )
                z = trial.x
                g, records = evaluate(z, mu, True)
                res = rod.residual(g)
                q = (z / rod.scale).reshape(-1, 4)
                ok = bool(
                    res < 2.0e-6
                    and np.max(abs(q[:, 3])) <= 0.0475
                    and np.max(abs(q[:, :3])) <= 1.5
                )
                row = dict(
                    phase=ph,
                    target_index=i,
                    neighbour_target_index=neighbour,
                    command_direction=direction,
                    mu=mu,
                    delta_command_mm=delta.tolist(),
                    imposed_sliding_signs=signs.tolist(),
                    nominal_tensions_N=nominal.ravel().tolist(),
                    converged=ok,
                    force_residual=res,
                    zero_mu_at_archived_state_residual=zero,
                    function_evaluations=trial.nfev,
                )
                if ok:
                    seed = z.copy()
                    fields.append(seed)
                    field_ids.append(len(results))
                    row.update(
                        ropes=records,
                        pointing_change_deg=angle_between(
                            pointing(rod, z0), pointing(rod, z)
                        ),
                        tip_change_mm=np.linalg.norm(
                            position(rod, z) - position(rod, z0)
                        ),
                        min_distal_N=min(r["distal_N"] for r in records),
                        max_distal_N=max(r["distal_N"] for r in records),
                        minimum_winch_N=min(r["winch_N"] for r in records),
                        max_winch_N=max(r["winch_N"] for r in records),
                        below_operating_distal=[
                            r["rope"] for r in records if r["distal_N"] < 2.5
                        ],
                        rod_geometry_pass=bool(
                            rod.geometry_constraints(z).min() >= -1.0e-7
                        ),
                    )
                else:
                    row["solver_message"] = str(trial.message)
                results.append(row)
                print(ph, direction, mu, ok, res, row.get("min_distal_N"), flush=True)
        info = dict(
            rope_order=NAMES,
            mu_values=coefficients,
            channel_sign_deadband_mm=0.001,
            tests=len(results),
            converged=sum(r["converged"] for r in results),
            assumptions="Identical actual winch commands at the turning point. Signs follow commanded shortening/payout toward the neighbouring distinct angular target; below 0.001 mm use uniform tension. These are two steady sliding limits imposed at the same pose command. Stick, slip fronts and feedback response through the reversal are unmeasured.",
            cases=results,
        )
        (src / "sliding_turns.json").write_text(
            json.dumps(info, indent=2, allow_nan=False) + "\n"
        )
        np.savez_compressed(src / "sliding_turns.npz", case=field_ids, z=fields)
    channels = []
    for row in results:
        if not row["converged"]:
            continue
        for k, rope in enumerate(row["ropes"]):
            channels.append(
                dict(
                    phase=row["phase"],
                    target=row["target_index"],
                    direction=row["command_direction"],
                    mu=row["mu"],
                    rope=rope["rope"],
                    imposed_sign=rope["imposed_sign"],
                    neighbour_command_change_mm=row["delta_command_mm"][k],
                    nominal_uniform_N=row["nominal_tensions_N"][k],
                    winch_N=rope["winch_N"],
                    distal_N=rope["distal_N"],
                    total_turn_deg=rope["wrap_deg"],
                )
            )
    if channels:
        with (src / "sliding_turn_tensions.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=channels[0], lineterminator="\n")
            w.writeheader()
            w.writerows(channels)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--mu", type=float, nargs="+", default=[0.05, 0.15])
    a = p.parse_args()
    run(a.source, a.mu)
