"""Check axial sight lines to the two split flange rims and non-bearing carriage clearance at P3 poses."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from inputs import p3_input
from fixture_check import MotionCheck, fixture


def inspect_view(metal, obstacles, side):
    """A sampled annular edge has front-face metal inside the rim and clear foreground outside."""
    sign = 1 if side == "head" else -1
    face = 4.17 if sign == 1 else -4.59
    visible = []
    blocked = []
    relief = []
    for angle in np.arange(0.0, 360.0, 5.0) + 0.73:
        ray = np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
        inside = ray * 1.02
        outside = ray * 1.06
        origin = (*inside, face + sign * 30.0)
        face_hits = metal.ray_cast(origin, (*inside, face - sign * 0.10))
        if not face_hits or abs(face_hits[0].position[2] - face) > 0.005:
            relief.append(angle)
            continue
        # At the outside point, require a clear foreground to 0.10 mm behind the rim.
        # Other geometry deeper in the scene can affect contrast, which requires calibration.
        if metal.ray_cast(
            (*outside, face + sign * 30.0), (*outside, face - sign * 0.10)
        ):
            raise ValueError("Unexpected target metal beyond the nominal flange rim")
        if any(
            part.ray_cast((*pt, face + sign * 30.0), (*pt, face - sign * 0.10))
            for pt in (inside, outside)
            for part in obstacles.values()
        ):
            blocked.append(angle)
        else:
            visible.append(angle)
    quadrants = np.bincount(
        (np.array(visible, dtype=float) // 90).astype(int), minlength=4
    )
    return dict(
        sampled_azimuths=72,
        clear_edge_samples=len(visible),
        clear_samples_by_quadrant=quadrants.tolist(),
        driver_slot_or_missing_front_face=len(relief),
        obstructed_samples=len(blocked),
        obstructed_angles_deg=blocked,
    )


def run(results, carriage):
    moving, fixed = fixture(carriage)
    R = Rotation.from_matrix(p3_input()[2])
    check = MotionCheck(moving, fixed)
    rows = []
    for support in ("clamped", "hinged"):
        data = json.loads((results / f"fine_{support}.json").read_text())
        t = {
            v["factor"]: np.array(v["coupon_carriage_spn_mm"])
            for v in data["states"]
            if v["converged"]
        }
        if len(t) != 9:
            raise ValueError("Both complete nine-state fine results are required")
        ref = next(f for f in t if 0 < f < 0.25)
        check.segment(Rotation.identity(), np.zeros(3), R, t[ref])
        for sign in (1, -1):
            steps = [
                ref,
                0,
                0.25 * sign,
                0.5 * sign,
                0.75 * sign,
                sign,
                0.75 * sign,
                0.5 * sign,
                0.25 * sign,
                0,
                ref,
            ]
            for a, b in zip(steps, steps[1:]):
                check.segment(R, t.get(a, np.zeros(3)), R, t.get(b, np.zeros(3)))
        for f, pos in t.items():
            obs = {
                name: obj.transform(np.column_stack((R.as_matrix(), pos)))
                for name, obj in moving.items()
            }
            obs["pin_carriage"] = fixed["pin_carriage"]
            row = dict(
                support=support,
                factor=f,
                unintended_rigid_pair_gap_mm=check.measure(R, pos)[0],
            )
            for side, n, other in (
                ("head", "shoulder_pin", "threaded_cap"),
                ("cap", "threaded_cap", "shoulder_pin"),
            ):
                row[side] = inspect_view(fixed[n], obs | {other: fixed[other]}, side)
            rows.append(row)
    return dict(
        views=rows,
        interpolated_segments=check.segments,
        unique_rigid_carriage_poses=check.counter,
        pairs_per_pose=len(check.mob) * len(check.fix) - len(check.intent),
        uncertified_subintervals=check.unresolved,
        minimum_sampled_rigid_gap_mm=check.best[0],
        closest_pair=check.best[1:3],
        lower_bound_rigid_prescribed_path_mm=check.lower_bound,
        rigid_path_surface_exclusions=[list(k) for k in sorted(check.intent)],
        ray_length_mm=30.0,
        inside_outside_probe_radii_mm=[1.02, 1.06],
        interpretation="Rigid nominal sight lines. Cameras, lighting, actual seating, rim finish, optical precision, local coupon deformation and rotating optical frames require bench measurement.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--carriage", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    data = run(a.results, a.carriage)
    a.out.write_text(json.dumps(data, indent=2) + "\n")
    print(len(data["views"]), data["minimum_sampled_rigid_gap_mm"])
