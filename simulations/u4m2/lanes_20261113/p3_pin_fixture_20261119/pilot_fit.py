"""Measure free translation from two actual STL pilot sections; generate and check a bench-only candidate."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull

from inputs import CAD, p3_input
from bench_cad import RETAINED, b, on_pin_frame, pin_carriage

DEFAULT_CAD = CAD.parent / "p3_pin_fixture_20261119"
PILOTS = {
    "head": ("shoulder_pin", (2.12, 3.75)),
    "cap": ("threaded_cap", (-4.13, -2.12)),
}


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(solid, z, low, high):
    rings = []
    for p in solid.slice(z).to_polygons():
        p = np.asarray(p)
        r = np.linalg.norm(p, axis=1)
        if r.min() > low and r.max() < high:
            hull = ConvexHull(p)
            if hull.equations[:, -1].max() > 0:
                raise ValueError("Selected ring does not enclose the shaft axis")
            rings.append((p[hull.vertices], hull))
    if len(rings) != 1:
        raise ValueError(f"Expected one cylindrical ring at {z} mm, found {len(rings)}")
    return rings[0]


def axis_bounds(A, limit, direction):
    along = A @ direction
    return float(np.max(limit[along < -1e-8] / along[along < -1e-8])), float(
        np.min(limit[along > 1e-8] / along[along > 1e-8])
    )


def width(A, limit, direction):
    solutions = []
    for c in (direction, -direction):
        res = linprog(
            c, A_ub=A, b_ub=limit, bounds=[(None, None)] * len(c), method="highs"
        )
        if res.status == 2:
            return None
        if not res.success:
            raise ValueError(res.message)
        solutions.append(res.x)
    return float(direction @ (solutions[1] - solutions[0]))


def geometry(bore, metal, direction, delta_cases):
    planes = []
    gaps = []
    which = []
    sections = []
    for name, (_, (lo, hi)) in PILOTS.items():
        for z in np.linspace(lo + 0.001, hi - 0.001, 5):
            ring, h = section(bore, z, 0.69, 0.77)
            collar, _ = section(metal[name], z, 0.70, 0.74)
            A = h.equations[:, :2]
            clearance = -h.equations[:, 2] - (A @ collar.T).max(axis=1)
            planes.append(A)
            gaps.append(clearance)
            which.extend([name] * len(A))
            sections.append(
                dict(
                    name=name,
                    n_mm=float(z),
                    bore_outer_radius_mm=float(np.linalg.norm(ring, axis=1).max()),
                    collar_outer_radius_mm=float(np.linalg.norm(collar, axis=1).max()),
                    minimum_centred_normal_gap_mm=float(clearance.min()),
                )
            )
    A = np.vstack(planes)
    h = np.concatenate(gaps)
    caps = np.array(which) == "cap"
    lo, hi = axis_bounds(A, h, direction)
    vols = []
    for label, s in (
        ("negative_limit", lo),
        ("positive_limit", hi),
        ("negative_plus_5um", lo - 0.005),
        ("positive_plus_5um", hi + 0.005),
    ):
        shift = (*(s * direction), 0.0)
        vols.append(
            dict(
                pose=label,
                offset_along_P3_mm=s,
                overlap_by_part_mm3={
                    k: max(0.0, float((bore ^ v.translate(shift)).volume()))
                    for k, v in metal.items()
                },
            )
        )
    errors = []
    for delta in delta_cases:
        # Translate the cap-side bore centre relative to the head-side bore, with parallel axes.
        limit = h + caps * delta * (A @ direction)
        extent = width(A, limit, direction)
        errors.append(
            dict(
                cap_side_bore_offset_along_P3_mm=delta,
                parallel_assembly_fits=extent is not None,
                projected_free_width_mm=extent,
            )
        )
    return dict(
        sections=sections,
        P3_axis_limits_mm=[lo, hi],
        on_axis_full_reversal_mm=hi - lo,
        full_projected_width_mm=width(A, h, direction),
        centred_minimum_normal_gap_mm=float(h.min()),
        boolean_offsets=vols,
        parallel_bore_offset_sensitivity=errors,
    )


def run(cad_dir):
    cad_dir.mkdir(exist_ok=True, parents=True)
    _, force, _ = p3_input()
    d = force[:2] / np.linalg.norm(force[:2])
    actual = CAD / "parts/pin_carriage.stl"
    base = b.load(actual)
    metal = {
        name: on_pin_frame(b.load(RETAINED / f"parts/{part}.stl"))
        for name, (part, _) in PILOTS.items()
    }
    candidate = cad_dir / "pin_carriage_bore_1p46.stl"
    check = b.export(pin_carriage(0.73).simplify(1e-6), candidate)
    obj = b.load(candidate)
    rebuild = pin_carriage().simplify(1e-6)

    def vol(shape):
        return max(0.0, float(shape.volume()))

    exterior = b.box((-7, -18, -5), (7, 2, 5)) - b.cyl(0.751, -5, 5)
    result = dict(
        cad_frame="s, p, n; head on positive n",
        P3_transverse_unit_sp=d.tolist(),
        source_sha256={
            k: file_hash(p)
            for k, p in {
                "original_carriage": actual,
                **{a: RETAINED / f"parts/{n}.stl" for a, (n, _) in PILOTS.items()},
            }.items()
        },
        candidate=dict(filename=candidate.name, sha256=file_hash(candidate), **check),
        default_rebuild_difference_mm3=vol(base - rebuild) + vol(rebuild - base),
        candidate_removed_material_mm3=vol(base - obj),
        candidate_added_material_mm3=vol(obj - base),
        difference_outside_pilot_zone_mm3=vol((obj - base) ^ exterior)
        + vol((base - obj) ^ exterior),
        alternatives={},
    )
    for label, solid in (
        ("1.50", base),
        ("1.48", pin_carriage(0.74)),
        ("1.46", obj),
        ("1.45", pin_carriage(0.725)),
    ):
        result["alternatives"][label] = geometry(
            solid, metal, d, [0.0, 0.005, 0.010, 0.015, 0.020, 0.025, 0.030]
        )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cad-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = run(a.cad_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n")
    for k, v in report["alternatives"].items():
        print(
            k,
            v["on_axis_full_reversal_mm"],
            [
                x["parallel_assembly_fits"]
                for x in v["parallel_bore_offset_sensitivity"]
            ],
            flush=True,
        )
