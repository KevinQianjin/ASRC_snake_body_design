"""Rigid angular-misalignment sensitivity of M6 outer-station guide variants.

The guide, caps and wire envelope rotate together about the station origin (local
CAD axes) relative to the already deformed M6 body at one motion step. Gaps are exact
triangle distances. This complements the rigid-translation bracket of round 1; it is
not a model of bond compliance or of the guide's own deformation.
"""

import argparse
import time
from pathlib import Path

import fcl
import numpy as np
import trimesh

from m6_socket_screen import CAD, PARTS, deformed_body, gap, load_motion, load_variant, mesh_model, save


def rotation(axis, deg):
    return trimesh.transformations.rotation_matrix(np.radians(deg), np.eye(3)[axis])[:3, :3]


def run(a):
    t0 = time.time()
    rod, states, _ = load_motion()
    module = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    variants = {k: Path(v).resolve() for k, v in (s.split("=", 1) for s in a.variant)}
    meshes = {k: load_variant(v, a.station) for k, v in variants.items()}
    bounds = trimesh.util.concatenate([m for p in meshes.values() for m in p.values()]).bounds
    # pad the crop by the largest rotated displacement of the guide envelope
    reach = np.radians(max(a.angles)) * np.linalg.norm(np.abs(bounds).max(0))
    bounds = (bounds[0] - reach, bounds[1] + reach)
    detail = rod.evaluate(states[a.step], detail=True)[2]
    body, _, kept = deformed_body(module, a.station, bounds, a.spacing, rod, detail)
    rows = []
    for k, parts in meshes.items():
        objs = {p: fcl.CollisionObject(mesh_model(m.vertices, m.faces)) for p, m in parts.items()}
        for axis in range(3):
            for deg in sorted({0.0, *a.angles, *(-x for x in a.angles)}):
                R = rotation(axis, deg)
                row = dict(variant=k, axis="CAD_" + "xyz"[axis], angle_deg=deg)
                for p, o in objs.items():
                    o.setTransform(fcl.Transform(R, np.zeros(3)))
                    d, hit, _ = gap(body, o)
                    row[f"{p}_gap_mm"], row[f"{p}_contact"] = d, hit
                rows.append(row)
        print(k, min(r["guide_gap_mm"] for r in rows if r["variant"] == k), f"{time.time()-t0:.0f}s", flush=True)
    save(a.out, dict(script="m6_tilt.py", step=a.step, station_mm=a.station, spacing_mm=a.spacing,
                     crop_extra_mm=reach, kept_triangles=kept, rows=rows))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--variant", nargs="+", required=True)
    p.add_argument("--station", type=int, default=-12)
    p.add_argument("--step", type=int, default=1710)
    p.add_argument("--spacing", type=float, default=0.25)
    p.add_argument("--angles", nargs="+", type=float, default=[0.05, 0.1, 0.2, 0.3])
    a = p.parse_args()
    run(a)
