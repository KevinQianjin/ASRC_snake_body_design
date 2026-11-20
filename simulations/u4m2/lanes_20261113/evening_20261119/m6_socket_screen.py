"""Full-triangle M6 guide/web clearance for several outer-socket CAD variants.

For each requested motion step and M6 outer station (z = -12 or +12 mm) the actual
M6 body STL is axially refined, deformed with the archived 500 g mission state and
cropped once. Every guide variant (guide, caps, wire envelope) is then checked against
the same deformed body with exact triangle distance (python-fcl). The method is the
round-1 `m6_clearance.py` method generalised to several steps, both stations and
several CAD folders. It reads the published mission and never writes into it.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import fcl
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROUND1 = HERE.parent / "extreme_round1_20261119"
sys.path.insert(0, str(ROUND1))
from study_inputs import CAD, load_motion, save  # noqa: E402
from adapter import mesh_model  # noqa: E402
from cad_surface_refinement import refine_axial  # noqa: E402
from guide_web_compatibility import to_station  # noqa: E402

WINDOW = 0.6  # mm crop pad around the union of all variant component AABBs
PARTS = ("guide", "caps", "wire_envelope")


def patch(vertices, faces):
    ids, local = np.unique(faces.ravel(), return_inverse=True)
    return trimesh.Trimesh(vertices[ids], local.reshape(-1, 3), process=False)


def deformed_body(module, station, bounds, spacing, rod, detail):
    low, high = bounds
    near, total = [], 0
    for start in range(0, len(module.faces), 256):
        fine = refine_axial(patch(module.vertices, module.faces[start : start + 256]), spacing)
        total += len(fine.faces)
        mapped = to_station(fine.vertices, 5, station, rod, detail)
        tri = mapped[fine.faces]
        keep = np.all((tri.max(1) >= low - WINDOW) & (tri.min(1) <= high + WINDOW), axis=1)
        if keep.any():
            near.append(patch(mapped, fine.faces[keep]))
    body = trimesh.util.concatenate(near)
    return fcl.CollisionObject(mesh_model(body.vertices, body.faces)), total, len(body.faces)


def gap(body, part):
    if fcl.collide(body, part, fcl.CollisionRequest(), fcl.CollisionResult()):
        return 0.0, True, None
    res = fcl.DistanceResult()
    d = fcl.distance(body, part, fcl.DistanceRequest(enable_nearest_points=True), res)
    if not 0 < d < WINDOW:
        raise ValueError("crop does not certify this distance")
    return float(d), False, np.array(res.nearest_points)


def load_variant(folder, station):
    meshes = {p: trimesh.load_mesh(folder / f"M6_z{station:+d}_{p}.stl") for p in PARTS}
    for p, m in meshes.items():
        if not m.is_volume:
            raise ValueError(f"{folder.name} {p} is not a closed volume")
    return meshes


def run(args):
    t0 = time.time()
    rod, states, _ = load_motion()
    module = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    variants = dict(v.split("=", 1) for v in args.variant)
    variants = {k: Path(v).resolve() for k, v in variants.items()}
    rows, straight = [], []
    for station, steps in ((-12, args.steps_minus), (12, args.steps_plus)):
        if not steps:
            continue
        meshes = {k: load_variant(v, station) for k, v in variants.items()}
        bounds = trimesh.util.concatenate(
            [m for parts in meshes.values() for m in parts.values()]
        ).bounds
        objects = {
            k: {p: fcl.CollisionObject(mesh_model(m.vertices, m.faces)) for p, m in parts.items()}
            for k, parts in meshes.items()
        }
        flat = fcl.CollisionObject(mesh_model(module.vertices - [0, 0, station], module.faces))
        for k, parts in objects.items():
            straight.append(
                dict(variant=k, station_mm=station,
                     **{f"{p}_gap_mm": gap(flat, o)[0] for p, o in parts.items()})
            )
        for step in steps:
            detail = rod.evaluate(states[step], detail=True)[2]
            body, full, kept = deformed_body(module, station, bounds, args.spacing, rod, detail)
            for k, parts in objects.items():
                row = dict(step=step, station_mm=station, variant=k, axial_span_mm=args.spacing,
                           body_triangles=full, kept_triangles=kept)
                for p, o in parts.items():
                    d, hit, pts = gap(body, o)
                    row[f"{p}_gap_mm"] = d
                    row[f"{p}_contact"] = hit
                    if p == "guide" and pts is not None:
                        row["guide_witness_CAD_mm"] = pts[1].round(4).tolist()
                        row["closure_dir_CAD"] = ((pts[0] - pts[1]) / d).round(4).tolist()
                rows.append(row)
            print(station, step, kept, {r["variant"]: round(r["guide_gap_mm"], 5) for r in rows[-len(objects):]},
                  f"{time.time() - t0:.0f}s", flush=True)
            save(args.out, dict(script="m6_socket_screen.py", window_mm=WINDOW,
                                variants={k: str(v) for k, v in variants.items()},
                                straight=straight, rows=rows, elapsed_s=time.time() - t0))
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True, help="JSON file to write")
    p.add_argument("--variant", nargs="+", required=True, help="name=CAD folder")
    p.add_argument("--steps-minus", nargs="*", type=int, default=[])
    p.add_argument("--steps-plus", nargs="*", type=int, default=[])
    p.add_argument("--spacing", type=float, default=0.5)
    a = p.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    run(a)
