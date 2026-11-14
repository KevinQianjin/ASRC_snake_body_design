"""Build and statically clearance-check M5/M6 internal rope-guide spiders.

This is an experimental concept: one thin cross-spider per station, with an 8 mm
sleeve bonded to the central 1.8 mm backbone. Guides are positioned at z=-24,0,
+24 mm in each 96 mm M module. The check measures intersections with the
straight-pose printable M5/M6 bodies; it does not prove bent-state contact,
fatigue, rope friction, adhesive retention, or stiffness.

Run from this folder:
    python build_rope_guides.py
Requires trimesh and manifold3d.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
GUIDE_Z_MM = (-36.0, -12.0, 12.0, 36.0)
THICKNESS_MM = 1.2
HUB_LENGTH_MM = 8.0
HUB_D_MM = 6.0
BACKBONE_HOLE_D_MM = 2.1
ROPE_HOLE_D_MM = 2.6
ARM_WIDTH_MM = 4.0
ARM_TIP_R_MM = 28.7
LANE_RADII_MM = {"M5": (24.0, 27.0), "M6": (27.0,)}
BODY_FILES = {"M5": "M5_lane_anchorB.stl", "M6": "M6_lane_anchorC.stl"}


def cylinder(diameter, height, center=(0.0, 0.0, 0.0), sections=64):
    mesh = trimesh.creation.cylinder(radius=diameter / 2.0, height=height, sections=sections)
    mesh.apply_translation(center)
    return mesh


def guide_mesh(kind):
    if kind not in LANE_RADII_MM:
        raise ValueError(f"unknown guide kind: {kind}")
    bar_length = ARM_TIP_R_MM - HUB_D_MM / 2.0
    bar_center = (ARM_TIP_R_MM + HUB_D_MM / 2.0) / 2.0
    solids = [cylinder(HUB_D_MM, HUB_LENGTH_MM)]
    for angle in (0.0, 90.0, 180.0, 270.0):
        bar = trimesh.creation.box([bar_length, ARM_WIDTH_MM, THICKNESS_MM])
        bar.apply_translation([bar_center, 0.0, 0.0])
        bar.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle), [0, 0, 1]))
        solids.append(bar)
    solid = trimesh.boolean.union(solids, engine="manifold")
    cutters = [cylinder(BACKBONE_HOLE_D_MM, HUB_LENGTH_MM + 1.0)]
    for angle in (0.0, 90.0, 180.0, 270.0):
        a = np.radians(angle)
        for radius in LANE_RADII_MM[kind]:
            cutters.append(cylinder(ROPE_HOLE_D_MM, THICKNESS_MM + 1.0,
                                    (radius * np.cos(a), radius * np.sin(a), 0.0), sections=48))
    return trimesh.boolean.difference([solid] + cutters, engine="manifold")


def check_kind(kind):
    part = guide_mesh(kind)
    if not part.is_watertight:
        raise RuntimeError(f"{kind} guide mesh is not watertight")
    body_path = HERE / BODY_FILES[kind]
    body = trimesh.load_mesh(body_path, force="mesh")
    rows = []
    for z in GUIDE_Z_MM:
        placed = part.copy()
        placed.apply_translation([0.0, 0.0, z])
        overlap = trimesh.boolean.intersection([body, placed], engine="manifold")
        volume = 0.0 if overlap.is_empty else float(overlap.volume)
        rows.append({"center_z_mm": z, "intersection_volume_mm3": round(volume, 6),
                     "straight_pose_clear": volume <= 0.05})
    return {
        "kind": kind,
        "guide_count_per_module": len(GUIDE_Z_MM),
        "rope_lanes_mm": list(LANE_RADII_MM[kind]),
        "part": {
            "watertight": bool(part.is_watertight),
            "volume_mm3": round(float(part.volume), 3),
            "bounds_mm": np.round(part.bounds, 3).tolist(),
        },
        "body_file": body_path.name,
        "straight_pose_intersections": rows,
        "all_straight_pose_positions_clear": all(row["straight_pose_clear"] for row in rows),
        "limitations": [
            "does not check deformed-body collision",
            "does not measure rope friction or wear",
            "backbone bond and axial retention are not tested",
            "guide stiffness and added mass are not included in the steering model",
        ],
    }


def main():
    report = {
        "status": "experimental, not print-approved",
        "concept": "rod-mounted cross-spider; guide stations with a maximum 24 mm pitch in M5 and M6",
        "dimensions_mm": {
            "plate_thickness": THICKNESS_MM,
            "hub_length": HUB_LENGTH_MM,
            "hub_diameter": HUB_D_MM,
            "backbone_hole_diameter": BACKBONE_HOLE_D_MM,
            "rope_hole_diameter": ROPE_HOLE_D_MM,
            "arm_width": ARM_WIDTH_MM,
            "arm_tip_radius": ARM_TIP_R_MM,
        },
        "modules": {kind: check_kind(kind) for kind in ("M5", "M6")},
    }
    report["all_straight_pose_positions_clear"] = all(
        module["all_straight_pose_positions_clear"] for module in report["modules"].values()
    )
    out = HERE / "rope_guide_geometry_check.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved {out.name}")
    if not report["all_straight_pose_positions_clear"]:
        raise SystemExit("guide collision in straight-pose body mesh; revise geometry before proceeding")


if __name__ == "__main__":
    main()
