"""Refine each achieved vertical pose with its actual twelve winch commands held fixed."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np

from replay import plant
from pitch_reference import angle_between, pointing, position, target_axis
from spatial_model import refine_seed
from closed_loop_cycle import FeedbackDrive
from solve_bellmouth_holds import damped_stationary


def run(source):
    coarse, _ = plant()
    fine, _ = plant(cells=16)
    with (source / "rope_tensions_at_events.csv").open() as stream:
        endpoints = {
            r["event"]: int(r["step"])
            for r in csv.DictReader(stream)
            if r["event"] in ("Pitch up", "Pitch down")
        }
    if set(endpoints) != {"Pitch up", "Pitch down"}:
        raise ValueError("Both executed pitch endpoints are required")
    rows = []
    with np.load(source / "controller_states.npz") as data:
        for label, step in endpoints.items():
            z = data["motion_z"][step]
            R = data["motion_rest_m"][step].reshape(3, 4)
            T = data["motion_tensions_N"][step].reshape(3, 4)
            goal = 90.0 if label == "Pitch up" else -90.0
            initial = refine_seed(z, coarse.base, fine.base)
            drive = FeedbackDrive(fine)
            drive.stability(initial, R, drive.force(initial, R))
            q = drive.solve(initial, R)
            method = "warm-start fixed-winch root"
            stop_reason = None
            if q is None:
                method = "damped fixed-winch equilibrium after warm-start failure"
                q, _, stop_reason = damped_stationary(
                    fine, T, initial, max_seconds=100, drive=drive, rest=R
                )
            r = dict(
                solver=method,
                solver_status=stop_reason,
                event=label,
                step=step,
                requested_pitch_deg=goal,
                rest_lengths_mm=(1000 * R).tolist(),
                converged=q is not None,
            )
            if q is not None:
                refined = drive.force(q, R)
                r.update(
                    coarse_axis=pointing(coarse, z).tolist(),
                    fine_axis=pointing(fine, q).tolist(),
                    change_in_pointing_deg=angle_between(
                        pointing(coarse, z), pointing(fine, q)
                    ),
                    refined_error_to_requested_deg=angle_between(
                        pointing(fine, q), target_axis(goal)
                    ),
                    change_in_head_position_mm=float(
                        np.linalg.norm(position(coarse, z) - position(fine, q))
                    ),
                    maximum_change_in_rope_tension_N=float(np.max(abs(T - refined))),
                    fine_tensions_N=refined.tolist(),
                    coarse_residual=coarse.residual(
                        FeedbackDrive(coarse).energy(z, R)[1]
                    ),
                    refined_residual=fine.residual(drive.energy(q, R)[1]),
                    fine_min_tangent=drive.stability(q, R, refined),
                )
                np.savez_compressed(
                    source / ("mesh_" + label.lower().replace(" ", "_") + ".npz"),
                    z8=z,
                    z16=q,
                    rest_m=R,
                    T8_N=T,
                    T16_N=refined,
                )
            rows.append(r)
    result = dict(
        boundary="Same 500 g mass and same actual unstretched winch lengths, with 8 and 16 cells per module. The feedback gains and 8-cell commanded path stay fixed.",
        rows=rows,
    )
    (source / "mesh_poles.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    print(run(p.parse_args().source))
