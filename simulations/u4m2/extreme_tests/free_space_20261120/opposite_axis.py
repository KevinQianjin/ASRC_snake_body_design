"""Test whether the screened upward meridian can point directly opposite the clamp."""

import argparse
import gc
from pathlib import Path
import numpy as np
from study_context import NAMES, RESULTS, read, read_csv, save
from cad_screen import Geometry, failed_part
from free_space import metrics
from mesh_limits import candidate_mass, fixed
from pitch_reference import angle_between, pointing
from pose_map import axis, correct, equilibrate
from closed_loop_cycle import FeedbackDrive
from replay import plant
from spatial_model import refine_seed


def check(rod, original, commands, spacing, target):
    drive = FeedbackDrive(rod)
    q, cmd, reason = correct(rod, drive, original, commands, target, tol_deg=0.0001)
    q0 = equilibrate(rod, drive, q, commands)
    if q0 is None:
        raise ArithmeticError(
            "Opposite-axis command did not return to the original +200 degree state"
        )
    geo = Geometry(rod, spacing)
    pairs = ((original, commands), (q, cmd), (q0, commands))
    ds = [rod.base.kinematic_metrics(z)[1] for z, _ in pairs]
    geo.prepare(ds)
    records = []
    for stage, (z, r), d in zip(
        ("approach", "trimmed", "recovered"), pairs, ds, strict=True
    ):
        m = metrics(rod, drive, z, r, 0, 200, reason if stage == "trimmed" else None)
        gaps = geo.query(d, z, drive.force(z, r))
        failure = failed_part(gaps)
        records.append(
            dict(
                stage=stage,
                command_mm=r.ravel() * 1000,
                tensions_N=drive.force(z, r).ravel(),
                actual_head_axis=pointing(rod, z),
                physical_axis_separation_deg=angle_between(
                    pointing(rod, z), axis(0, 20)
                ),
                target_error_deg=m["axis_error_deg"],
                min_tangent=m["tangent_min"],
                residual=m["residual"],
                rod_pass=m["pass_ideal"],
                rod_failure=m["reason"],
                gaps=gaps,
                first_CAD_failure=failure,
                screened=bool(m["pass_ideal"] and failure is None),
            )
        )
    return dict(
        cells_per_module=rod.base.sub,
        axial_surface_spacing_mm=spacing,
        max_command_trim_mm=np.max(abs(cmd - commands)) * 1000,
        max_scaled_state_return_difference=np.max(abs(q0 - original)),
        rows=records,
    )


def run(root):
    prefix = read(root / "geometry/up.json")["paths"]["up"]
    if (
        prefix["last_contiguous_screened_deg"] < 200
        or not prefix["prefix_return_checked"]
    ):
        raise ValueError(
            "The upward meridian must already reach and reverse through +200 degrees"
        )
    raw = read_csv(root / "angles/up.csv.gz")
    a = next(
        r
        for r in raw
        if r["leg"] == "out"
        and float(r["command_deg"]) == 200
        and r["pass_ideal"] == "True"
    )
    with np.load(root / "angles/up_states.npz") as sf:
        original = sf["z"][int(a["index"])]
    commands = (
        np.array([float(a[n + "_command_mm"]) for n in NAMES]).reshape(3, 4) / 1000
    )
    coarse, _ = plant()
    fine, _ = plant(cells=16)
    change = candidate_mass(fine)
    target = axis(0, 200)
    fine_origin, f = fixed(
        fine,
        refine_seed(original, coarse.base, fine.base),
        commands,
        pointing(coarse, original),
        target,
    )
    if fine_origin is None:
        raise ArithmeticError(f["reason"])
    cases = []
    for r, z, h in ((coarse, original, 0.5), (fine, fine_origin, 0.25)):
        case = check(r, z, commands, h, target)
        cases.append(case)
        print(
            case["cells_per_module"],
            [(v["stage"], v["target_error_deg"], v["screened"]) for v in case["rows"]],
            flush=True,
        )
        gc.collect()
    save(
        root / "mesh/opposite_axis.json",
        dict(
            target_yaw_deg=0,
            target_pitch_deg=200,
            neutral_pitch_deg=20,
            mathematical_upper_bound_deg=180,
            rope_order=NAMES,
            target_tolerance_deg=0.0001,
            fine_candidate_mass_change_g=1000 * change,
            full_approach_and_return_resolution_cells=8,
            cases=cases,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
