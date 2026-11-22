"""Full-mission exact M6 guide/body clearance for any outer-socket CAD folder.

Reuses the Round 2 (19-20 November) all-step method unchanged
(`extreme_tests/round2_20261119/m6_full.py`): the actual M6 body is axially refined
to 0.5 mm, cropped once with certified swept boxes over every archived strain state,
mapped affinely per exactly-unique final-module strain, and checked with exact FCL
triangle collision/distance against guide, caps and wire envelope. Only the CAD
folder and the output location are parameters here, so the archived Round 2 result
(uncrowned 0.25 mm candidate) can be reproduced and the 0.06 mm crowned land
(20 November evening) certified on the same 3,405 steps at both stations.
It reads the published mission and never writes into archived folders.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import fcl
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2))
import m6_full as R  # noqa: E402
from common import CAD, load_motion, motion_rows, write_table, save  # noqa: E402


def run(candidate, out, name, spacing, stations):
    t0 = time.time()
    rod, z, _ = load_motion()
    rows = motion_rows()
    _, representatives, inverse = np.unique(
        z[:, -32:], axis=0, return_index=True, return_inverse=True
    )
    inv = inverse.ravel()
    details = [rod.kinematic_metrics(z[i])[1] for i in representatives]
    mesh = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    fine = trimesh.util.concatenate(
        [
            R.refine_axial(R.patch(mesh.vertices, mesh.faces[i : i + 256]), spacing)
            for i in range(0, len(mesh.faces), 256)
        ]
    )
    records, summary = [], {}
    for st in stations:
        parts = R.load_variant(candidate, st)
        targets = {
            p: fcl.CollisionObject(R.mesh_model(m.vertices, m.faces))
            for p, m in parts.items()
        }
        body = R.swept_crop(fine, parts, st, rod, details)
        v = np.asarray(body.vertices)
        heights, ix = np.unique(v[:, 2], return_inverse=True)
        print(name, st, len(body.faces), "retained of", len(fine.faces), flush=True)
        solutions = []
        for j, detail in enumerate(details):
            a = R.coefficients(heights, st, rod, detail)[ix]
            mapped = a[:, 0] + v[:, :1] * a[:, 1] + v[:, 1:2] * a[:, 2]
            solid = fcl.CollisionObject(R.mesh_model(mapped, body.faces))
            result = {}
            for p in R.PARTS:
                distance, hit, pts = R.gap(solid, targets[p])
                result[p + "_gap_mm"] = distance
                if p == "guide":
                    direction = np.zeros(3) if hit else (pts[0] - pts[1]) / distance
                    for axis, witness, normal in zip(
                        "xyz", np.zeros(3) if hit else pts[1], direction
                    ):
                        result["guide_" + axis + "_mm"] = witness
                        result["toward_web_" + axis] = normal
            solutions.append(result)
            if (j + 1) % 500 == 0:
                print(name, st, j + 1, "of", len(details), f"{time.time()-t0:.0f}s", flush=True)
        local = [
            dict(step=i, phase=rows[i]["phase"], station_mm=st,
                 representative_step=int(representatives[j]), **solutions[j])
            for i, j in enumerate(inv)
        ]
        records.extend(local)
        summary[str(st)] = dict(
            steps=len(local),
            exact_unique_shapes=len(details),
            body_faces=len(fine.faces),
            swept_crop_faces=len(body.faces),
            phase_count=len({r["phase"] for r in local}),
            minima={p: min((r[p + "_gap_mm"], r["step"]) for r in local) for p in R.PARTS},
            contacts=sum(min(r[p + "_gap_mm"] for p in R.PARTS) <= 0 for r in local),
        )
    out.mkdir(parents=True, exist_ok=True)
    tag = "_".join(f"{s:+d}" for s in stations)
    write_table(out / f"{name}_all_steps_{tag}.csv.gz", records)
    save(out / f"{name}_full_{tag}.json",
         dict(candidate=os.path.relpath(candidate, HERE.parents[3]), spacing_mm=spacing,
              certified_query_radius_mm=R.WINDOW, stations=summary,
              wall_time_s=round(time.time() - t0, 1)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--out", type=Path, default=HERE / "results/full")
    p.add_argument("--spacing", type=float, default=0.5)
    p.add_argument("--stations", type=int, nargs="+", default=[-12, 12])
    a = p.parse_args()
    run(a.candidate.resolve(), a.out, a.name, a.spacing, a.stations)
