"""Build and statically clearance-check M5/M6 internal rope-guide spiders.

This is an experimental concept: one thin cross-guide per station, clipped to four existing inner flexure webs.
The guided model places four guides at z=-36,-12,+12,+36 mm in each 96 mm M module. The check measures intersections with the
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
ROOT_INNER_R_MM = 8.8
ROOT_OUTER_R_MM = 10.2
WEB_CENTER_R_MM = 6.9
WEB_ANGLES_DEG = (-22.5, 67.5, 157.5, 247.5)
WEB_CLIP_OUTER_D_MM = 6.4
WEB_CLIP_INNER_D_MM = 5.2
WEB_CLIP_GAP_MM = 1.2
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
    bar_length = ARM_TIP_R_MM - ROOT_INNER_R_MM
    bar_center = (ARM_TIP_R_MM + ROOT_INNER_R_MM) / 2.0
    ring = cylinder(2.0 * ROOT_OUTER_R_MM, THICKNESS_MM)
    ring_hole = cylinder(2.0 * ROOT_INNER_R_MM, THICKNESS_MM + 1.0)
    root_ring = trimesh.boolean.difference([ring, ring_hole], engine='manifold')
    solids = [root_ring]
    for angle in WEB_ANGLES_DEG:
        center = np.array([WEB_CENTER_R_MM * np.cos(np.radians(angle)),
                           WEB_CENTER_R_MM * np.sin(np.radians(angle)), 0.0])
        outer = cylinder(WEB_CLIP_OUTER_D_MM, THICKNESS_MM)
        inner = cylinder(WEB_CLIP_INNER_D_MM, THICKNESS_MM + 1.0)
        clip = trimesh.boolean.difference([outer, inner], engine="manifold")
        slot = trimesh.creation.box([WEB_CLIP_OUTER_D_MM, WEB_CLIP_GAP_MM, THICKNESS_MM + 1.0])
        slot.apply_translation([-WEB_CLIP_OUTER_D_MM / 2.0, 0.0, 0.0])
        clip = trimesh.boolean.difference([clip, slot], engine="manifold")
        clip.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle), [0, 0, 1]))
        clip.apply_translation(center)
        solids.append(clip)
    for angle in (0.0, 90.0, 180.0, 270.0):
        bar = trimesh.creation.box([bar_length, ARM_WIDTH_MM, THICKNESS_MM])
        bar.apply_translation([bar_center, 0.0, 0.0])
        bar.apply_transform(trimesh.transformations.rotation_matrix(np.radians(angle), [0, 0, 1]))
        solids.append(bar)
    solid = trimesh.boolean.union(solids, engine="manifold")
    cutters = []
    for angle in (0.0, 90.0, 180.0, 270.0):
        a = np.radians(angle)
        for radius in LANE_RADII_MM[kind]:
            cutters.append(cylinder(ROPE_HOLE_D_MM, THICKNESS_MM + 1.0,
                                    (radius * np.cos(a), radius * np.sin(a), 0.0), sections=48))
    return trimesh.boolean.difference([solid] + cutters, engine="manifold")



def body_cross_sections(mesh, z_values=GUIDE_Z_MM):
    """Summarize section contours to expose internal structure where guides collide."""
    summary = {}
    for z in z_values:
        section = mesh.section(plane_origin=[0.0, 0.0, z], plane_normal=[0.0, 0.0, 1.0])
        paths = [] if section is None else section.discrete
        contours = []
        for points in paths:
            xy = points[:, :2]
            radius = np.linalg.norm(xy, axis=1)
            contours.append({
                "points": int(len(points)),
                "closed": bool(np.linalg.norm(points[0] - points[-1]) < 1e-5),
                "min_radius_mm": round(float(radius.min()), 3),
                "max_radius_mm": round(float(radius.max()), 3),
                "bounds_xy_mm": np.round(np.c_[xy.min(axis=0), xy.max(axis=0)], 3).tolist(),
            })
        summary[str(z)] = contours
    return summary

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
                     "straight_pose_clear": volume <= 0.05,
                     "overlap_bounds_mm": None if overlap.is_empty else np.round(overlap.bounds, 3).tolist()})
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
        "body_cross_sections": body_cross_sections(body),
        "straight_pose_intersections": rows,
        "all_straight_pose_positions_clear": all(row["straight_pose_clear"] for row in rows),
        "limitations": [
            "checks straight-pose body clearance at the modeled guide stations only",
            "does not check deformed-body collision",
            "does not measure rope friction or wear",
            "flexure-web clip retention and assembly force are not tested",
            "guide stiffness and added mass are not included in the steering model",
        ],
    }


def main():
    report = {
        "status": "experimental, not print-approved",
        "concept": "open-centre cross-guide ring with four snap clips around M flexure webs",
        "dimensions_mm": {
            "plate_thickness": THICKNESS_MM,
            "root_inner_radius": ROOT_INNER_R_MM,
            "root_outer_radius": ROOT_OUTER_R_MM,
            "web_center_radius": WEB_CENTER_R_MM,
            "web_clip_outer_diameter": WEB_CLIP_OUTER_D_MM,
            "web_clip_inner_diameter": WEB_CLIP_INNER_D_MM,
            "web_clip_gap": WEB_CLIP_GAP_MM,
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
