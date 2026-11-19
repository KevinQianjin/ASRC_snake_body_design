"""Compare inside-rim relief sizes at each M5 rib-to-hub near approach on the two complete pure-bend poses."""

import argparse
import json
from pathlib import Path
import sys

from bench_inputs import CAD

sys.path.insert(0, str(CAD.parent / "m5_hub_relief_20261119"))
import relief
from clearance import b, fcl, collider, j, np
from remaining_body import partition, rigid_poses, mapped_points


def run(mesh, states, edge):
    rows = []
    bits = partition(mesh, edge)
    variants = {d: relief.sectors(d) for d in relief.SIZES}
    hubs = {
        d: [b.place(o[relief.FAMILIES[k % 2]], 45 * k) for k in range(8)]
        for d, o in variants.items()
    }
    obs = {
        d: [fcl.CollisionObject(collider(o)) for o in objs] for d, objs in hubs.items()
    }
    for name, state in states.items():
        poses = rigid_poses(mesh, state["fields"])
        for z in j.STATIONS:
            minima = {d: {"gap_mm": float("inf")} for d in variants}
            checked = 0
            for win, tag, v, faces, free in bits:
                if win == z:
                    continue
                v = (
                    mapped_points(v, free, tag, state["fields"], poses) - state[f"C{z}"]
                ) @ state[f"R{z}"]
                if v[:, 2].min() > 2.2 or v[:, 2].max() < -2.2:
                    continue
                model = fcl.BVHModel()
                model.beginModel(len(faces), len(v))
                model.addSubModel(v, faces)
                model.endModel()
                body = fcl.CollisionObject(model)
                for d, objs in obs.items():
                    for k, obj in enumerate(objs):
                        result = fcl.DistanceResult()
                        gap = max(
                            0.0,
                            float(
                                fcl.distance(
                                    body,
                                    obj,
                                    fcl.DistanceRequest(enable_nearest_points=True),
                                    result,
                                )
                            ),
                        )
                        if gap < minima[d]["gap_mm"]:
                            minima[d] = dict(
                                gap_mm=gap,
                                tag=tag,
                                sector=k,
                                nearest_pair_xyz_mm=np.asarray(
                                    result.nearest_points
                                ).tolist()
                                if gap > 0
                                else None,
                            )
                checked += 1
            if max(x["gap_mm"] for x in minima.values()) > 0.59:
                raise ValueError("Axial pruning cannot certify these minima")
            rows.append(
                dict(
                    case=name,
                    station=z,
                    near_body_components=checked,
                    hub_variants={f"{d:.2f}": v for d, v in minima.items()},
                )
            )
            print(
                name,
                z,
                [(d, round(v["gap_mm"], 5)) for d, v in minima.items()],
                flush=True,
            )
    return dict(
        edge_mm=edge,
        coverage="All remaining-body partitions except the station-local web window; all eight hub sectors. Other station hardware is scored separately.",
        rows=rows,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--coupled", action="store_true")
    p.add_argument("--cases", nargs="+", default=["bend67.5", "bend0"])
    p.add_argument("--edge", type=float, default=0.25)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    mesh = np.load(a.cache / ("shell_mesh.npz" if a.coupled else "mesh_0p025.npz"))
    states = {
        n: dict(
            np.load(a.cache / (f"{n}/shell.npz" if a.coupled else f"{n}_0p025.npz"))
        )
        for n in a.cases
    }
    a.out.write_text(json.dumps(run(mesh, states, a.edge), indent=2) + "\n")
