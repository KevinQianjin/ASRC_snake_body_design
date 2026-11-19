"""Check the complete deformed CAD mesh against the three guide component families at controlling states."""

import argparse
import json
from pathlib import Path

import fcl
import numpy as np
import trimesh

from stations import BODIES, GUIDES, archive
from replay import plant
from cad_surface_refinement import refine_axial
from guide_web_compatibility import to_station
from adapter import mesh_model
from mesh_boolean64 import to_manifold


def run(source, kind, out, resolution):
    zs, ids, _ = archive(source, kind)
    data = json.loads((out / f"station_{kind}.json").read_text())
    rod = plant()[0].base
    result = []
    for name, path in BODIES.items():
        mesh = refine_axial(trimesh.load_mesh(path), resolution)
        if not mesh.is_watertight or not mesh.is_winding_consistent:
            raise ValueError("Refinement opened the body surface")
        for tag, r in data["parts"].items():
            if not tag.startswith(name):
                continue
            x = r["worst"]
            st = x["station_mm"]
            i = int(np.flatnonzero(ids == x["state"])[0])
            m = int(name[1:]) - 1
            detail = rod.evaluate(zs[i], detail=True)[2]
            vert = to_station(mesh.vertices, m, st, rod, detail)
            model = fcl.CollisionObject(mesh_model(vert, mesh.faces))
            for part in ("guide", "caps", "wire_envelope"):
                gg = trimesh.load_mesh(GUIDES / f"{tag}_{part}.stl")
                g = fcl.CollisionObject(mesh_model(gg.vertices, gg.faces))
                distance = max(
                    0.0,
                    fcl.distance(model, g, fcl.DistanceRequest(), fcl.DistanceResult()),
                )
                ov = 0.0
                if distance < 1e-7:
                    solid = to_manifold(
                        trimesh.Trimesh(vert, mesh.faces, process=False)
                    )
                    ov = max(0.0, float((solid ^ to_manifold(gg)).volume()))
                result.append(
                    dict(
                        tag=tag,
                        station_mm=st,
                        part=part,
                        state=int(ids[i]),
                        phase=x["phase"],
                        body_triangles=len(mesh.faces),
                        guide_triangles=len(gg.faces),
                        complete_mesh_distance_mm=float(distance),
                        overlap_mm3=ov,
                    )
                )
            print(
                kind,
                tag,
                min(x["complete_mesh_distance_mm"] for x in result[-3:]),
                flush=True,
            )
    summary = dict(
        resolution_mm=resolution,
        checks=len(result),
        rows=result,
        min_gap=min(x["complete_mesh_distance_mm"] for x in result),
        max_overlap=max(x["overlap_mm3"] for x in result),
    )
    (out / f"solid_{kind}_{str(resolution).replace('.', 'p')}.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--kind", choices=("holds", "motion"), required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resolution", type=float, default=0.5)
    a = p.parse_args()
    run(a.source, a.kind, a.out, a.resolution)
