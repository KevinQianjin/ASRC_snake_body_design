"""Conventional whole-body triangle refinement at the controlling M6 mission states."""

import argparse
from pathlib import Path
import fcl
import trimesh
from common import CAD, CANDIDATE, OUT, load_motion, save
from m6_socket_screen import deformed_body, load_variant, mesh_model, gap


def run(out):
    rod, z, _ = load_motion()
    body = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    rows = []
    for st in (-12, 12):
        parts = load_variant(CANDIDATE, st)
        bounds = trimesh.util.concatenate(list(parts.values())).bounds
        objects = {
            p: fcl.CollisionObject(mesh_model(m.vertices, m.faces))
            for p, m in parts.items()
        }
        for step in (1709, 1885):
            d = rod.evaluate(z[step], detail=True)[2]
            for spacing in (0.25, 0.125):
                solid, total, kept = deformed_body(body, st, bounds, spacing, rod, d)
                rows.append(
                    dict(
                        step=step,
                        station_mm=st,
                        axial_refinement_mm=spacing,
                        full_triangles=total,
                        kept_triangles=kept,
                        gaps_mm={p: gap(solid, o)[0] for p, o in objects.items()},
                    )
                )
                save(out / "m6_guides" / "m6_fine_exact.json", rows)
                print(st, step, spacing, rows[-1]["gaps_mm"]["guide"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
