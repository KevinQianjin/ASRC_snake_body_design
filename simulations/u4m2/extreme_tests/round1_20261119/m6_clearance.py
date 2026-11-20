"""Translate the as-designed M6 guide assembly at motion step 1710 and recheck its CAD surfaces."""

import argparse
from pathlib import Path

import fcl
import numpy as np
import trimesh

from study_inputs import CAD, load_motion, save
from adapter import mesh_model
from cad_surface_refinement import refine_axial
from guide_web_compatibility import to_station

STATION = -12
STEP = 1710
WINDOW = 0.6  # mm around all unshifted component AABBs


def patch(vertices, faces):
    ids, faces_local = np.unique(faces.ravel(), return_inverse=True)
    return trimesh.Trimesh(vertices[ids], faces_local.reshape(-1, 3), process=False)


def body_near(module, guide_bounds, spacing, rod, detail):
    """Refine every source face before trimming by its deformed, station-frame AABB."""
    near = []
    total = 0
    low, high = guide_bounds
    for start in range(0, len(module.faces), 256):
        block = patch(module.vertices, module.faces[start : start + 256])
        fine = refine_axial(block, spacing)
        total += len(fine.faces)
        mapped = to_station(fine.vertices, 5, STATION, rod, detail)
        triangles = mapped[fine.faces]
        keep = np.all(
            (triangles.max(axis=1) >= low - WINDOW)
            & (triangles.min(axis=1) <= high + WINDOW),
            axis=1,
        )
        if keep.any():
            near.append(patch(mapped, fine.faces[keep]))
    combined = trimesh.util.concatenate(near)
    return (
        fcl.CollisionObject(mesh_model(combined.vertices, combined.faces)),
        total,
        len(combined.faces),
    )


def proximity(body, part, shift):
    part.setTransform(fcl.Transform(np.eye(3), shift))
    touching = bool(
        fcl.collide(body, part, fcl.CollisionRequest(), fcl.CollisionResult())
    )
    result = fcl.DistanceResult()
    gap = fcl.distance(
        body, part, fcl.DistanceRequest(enable_nearest_points=True), result
    )
    if touching:
        return 0.0, True, None
    if not gap > 0 or gap >= WINDOW - np.max(np.abs(shift)):
        raise ValueError("The cropped AABB does not certify this nearest distance")
    points = np.array(result.nearest_points)
    np.testing.assert_allclose(np.linalg.norm(points[0] - points[1]), gap, atol=2e-7)
    return float(gap), False, points


def run(out, resolutions):
    rod, states, _ = load_motion()
    detail = rod.evaluate(states[STEP], detail=True)[2]
    module = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    meshes = {
        part: trimesh.load_mesh(CAD / f"guides_v3/M6_z-12_{part}.stl")
        for part in ("guide", "caps", "wire_envelope")
    }
    if not all(m.is_volume for m in (module, *meshes.values())):
        raise ValueError("Expected closed CAD inputs")
    bounds = trimesh.util.concatenate(list(meshes.values())).bounds
    objects = {
        p: fcl.CollisionObject(mesh_model(m.vertices, m.faces))
        for p, m in meshes.items()
    }
    straight_body = fcl.CollisionObject(
        mesh_model(module.vertices - [0, 0, STATION], module.faces)
    )
    straight_gaps = {
        p: proximity(straight_body, part, np.zeros(3))[0] for p, part in objects.items()
    }
    results = []
    for spacing in resolutions:
        body, full, kept = body_near(module, bounds, spacing, rod, detail)
        nominal = {p: proximity(body, obj, np.zeros(3)) for p, obj in objects.items()}
        ref_gap, _, points = nominal["guide"]
        direction = (points[0] - points[1]) / ref_gap
        directions = {
            "toward_web": direction,
            "CAD_x": np.eye(3)[0],
            "CAD_y": np.eye(3)[1],
            "CAD_z": np.eye(3)[2],
        }
        rows = []
        for label, axis in directions.items():
            offsets = [-0.05, -0.025, 0.0, 0.010, 0.020, 0.025, 0.050]
            if label == "toward_web":
                offsets += [ref_gap - 0.0001, ref_gap + 0.0001]
            for mm in sorted(offsets):
                for part, obj in objects.items():
                    gap, hit, _ = proximity(body, obj, mm * axis)
                    rows.append(
                        dict(
                            axis=label,
                            translation_mm=mm,
                            part=part,
                            gap_mm=gap,
                            intersects=hit,
                        )
                    )
        check = [v for v in rows if v["axis"] == "toward_web" and v["part"] == "guide"]
        positive = [v for v in check if v["translation_mm"] >= 0]
        lower = max(
            v["translation_mm"]
            for v in positive
            if not v["intersects"] and v["translation_mm"] <= ref_gap
        )
        upper = min(v["translation_mm"] for v in positive if v["intersects"])
        if not lower <= ref_gap <= upper or upper - lower > 0.000201:
            raise ValueError("Offset contact did not bracket the witness")
        summary = dict(
            axial_mesh_span_mm=spacing,
            full_body_triangles=full,
            retained_triangles=kept,
            nominal_gaps_mm={p: v[0] for p, v in nominal.items()},
            nominal_body_guide_witness_CAD_mm=points,
            closure_direction_CAD=direction,
            clear_to_contact_bracket_mm=[lower, upper],
            cases=rows,
        )
        results.append(summary)
        save(
            out / "m6_clearance.json",
            dict(
                step=STEP,
                station_mm=STATION,
                aabb_pad_mm=WINDOW,
                straight_gaps_mm=straight_gaps,
                resolution=results,
            ),
        )
        print(spacing, full, kept, summary["nominal_gaps_mm"], lower, upper, flush=True)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resolution", nargs="+", type=float, default=[0.5, 0.25, 0.125])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out, a.resolution)
