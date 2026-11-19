"""Check the actual six-millimetre M6 head adapter against the complete triangulated tank on every motion step."""

import argparse
import csv
import gzip
import json
from pathlib import Path

import fcl
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from replay import ROOT, plant, digest, as_relative
from length_cycle import FastTank, to_tank


def mesh_model(v, faces):
    bvh = fcl.BVHModel()
    bvh.beginModel(len(faces), len(v))
    bvh.addSubModel(np.ascontiguousarray(v), np.ascontiguousarray(faces))
    bvh.endModel()
    return bvh


def run(src):
    part = ROOT / "cad/lanes_u4m2/guides_v2/head_adapter.stl"
    tri = trimesh.load_mesh(part)
    if not tri.is_volume or np.max(abs(tri.bounds[:, 2] - [0.0, 6.0])) > 1.0e-5:
        raise ValueError("Adapter must register on the M6 end plane")
    # CAD (left, up, along) -> rod (along, up, right). This is a proper rotation.
    mat = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    verts = tri.vertices @ mat.T
    rad = np.linalg.norm(verts, axis=1).max()
    adapter = fcl.CollisionObject(mesh_model(verts, tri.faces))
    tank = FastTank()
    hull = fcl.CollisionObject(mesh_model(tank.mesh.vertices, tank.F))
    rod, _ = plant()
    with np.load(src / "controller_states.npz") as d:
        zs = d["motion_z"]
    with gzip.open(src / "motion_trace.json.gz", "rt") as f:
        trace = json.load(f)
    if len(trace) != len(zs):
        raise ValueError("Trace and adapter pose counts differ")
    table = []
    previous = None
    for i, (r, z) in enumerate(zip(trace, zs)):
        frame = rod.base.kinematic_metrics(z)[1]
        turn = rod.R0 @ frame["frames"][-1]
        ori = Rotation.from_matrix(turn)
        centre = to_tank(
            (rod.R0 @ (frame["points"][-1] + [0.02, 0.0, 0.0]))[None, :] * 1000.0,
            20,
            r["clamp_s_mm"],
            tank.entry_h,
        )[0]
        if np.linalg.norm(centre - r["head_tank_mm"]) > 1.0e-6:
            raise ValueError("Adapter datum disagrees with controller tip")
        adapter.setTransform(fcl.Transform(turn, centre))
        gap = max(
            0.0,
            fcl.distance(adapter, hull, fcl.DistanceRequest(), fcl.DistanceResult()),
        )
        face = centre + 6.0 * turn[:, 0]
        face_gap = tank.query.on_surface(np.array([face]))[1][0]
        bound = gap
        if previous is not None:
            p0, o0, d0 = previous
            displacement = (
                np.linalg.norm(centre - p0) + rad * (o0.inv() * ori).magnitude()
            )
            bound = min(d0, gap) - 0.5 * displacement
        previous = centre, ori, gap
        table.append(
            dict(
                step=i,
                phase=r["phase"],
                adapter_triangle_gap_mm=float(gap),
                interpolated_segment_lower_bound_mm=float(bound),
                mounting_face_centre_to_wall_mm=float(face_gap),
            )
        )
    with gzip.open(src / "adapter_clearance.csv.gz", "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(table)
    result = dict(
        adapter=as_relative(part),
        adapter_sha256=digest(part),
        tank_step_sha256=tank.sha,
        tank_triangulation_deflection_mm=0.5,
        adapter_triangles=len(tri.faces),
        tank_triangles=len(tank.F),
        motion_states=len(trace),
        minimum_sample=min(table, key=lambda x: x["adapter_triangle_gap_mm"]),
        minimum_between_pose_bound=min(
            table, key=lambda x: x["interpolated_segment_lower_bound_mm"]
        ),
        minimum_distance_from_mounting_face_centre=min(
            table, key=lambda x: x["mounting_face_centre_to_wall_mm"]
        ),
        threshold_after_standard_1p5_mm_allowance_mm=5.0,
        failed_interpolated_bounds=sum(
            r["interpolated_segment_lower_bound_mm"] - 1.5 < 5 for r in table
        ),
        scope="Actual rigid M6 adapter plate only. The sweep bound assumes linear position and shortest-arc rotation between successive simulated poses, on the stated tank mesh. The inspection-head housing, harness and rear support require their measured shapes.",
    )
    (src / "adapter_clearance.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    print(run(p.parse_args().source)["minimum_sample"])
