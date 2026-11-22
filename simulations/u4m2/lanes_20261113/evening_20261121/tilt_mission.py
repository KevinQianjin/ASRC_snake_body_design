"""Full-mission rigid-tilt clearance of an M6 outer-socket guide variant (evening, 21 Nov 2026).

The 20 November evening study bisected the first-contact rigid tilt of the crowned
M6 land only at the governing left-yaw steps (z = -12 mm step 1,710; z = +12 mm step
1,709). This script checks the same rigid-tilt question at every exactly-unique final-
module strain of the archived 3,405-step 500 g mission, using the Round 2 all-step
method (`extreme_tests/round2_20261119/m6_full.py`: 0.5 mm axial refinement of the
actual M6 body, certified swept crop, affine per-shape map, exact FCL distances).

For each shape, guide + caps + wire envelope rotate together about the station origin
by +/- `--angle` (default 0.2 deg) about 12 in-plane axes (every 15 deg from CAD x
toward CAD y, i.e. 0 = CAD x, 90 = CAD y) and about CAD z (26 tilts). The exact gap at
each tilt equals the largest rigid translation, in any direction, that stays contact-
free at that tilt. Parts are pruned with the rigorous bound
gap_tilted >= gap_nominal - r_max * angle; pruned parts cannot be the minimum.
The crop is built from the union of all tilted parts, so it remains certified.
Rigid-body sensitivity only: no bond compliance, guide bending or as-printed form error.
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
from common import CAD, load_motion, save  # noqa: E402

INPLANE = [float(t) for t in range(0, 180, 15)]


def tilts(angle):
    out = []
    for t in INPLANE:
        ax = [np.cos(np.radians(t)), np.sin(np.radians(t)), 0.0]
        for s in (-1, 1):
            out.append((f"inplane_{t:g}deg", s, ax))
    for s in (-1, 1):
        out.append(("CAD_z", s, [0.0, 0.0, 1.0]))
    return [(n, s, trimesh.transformations.rotation_matrix(np.radians(s * angle), ax))
            for n, s, ax in out]


def run(a):
    t0 = time.time()
    rod, z, _ = load_motion()
    _, representatives, inverse = np.unique(z[:, -32:], axis=0, return_index=True, return_inverse=True)
    inv = inverse.ravel()
    if a.steps:
        shape_ids = sorted({int(inv[s]) for s in a.steps})
    else:
        shape_ids = list(range(a.shard, len(representatives), a.nshards))
    details_all = [rod.kinematic_metrics(z[i])[1] for i in representatives]  # crop over the whole mission
    mesh = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    fine = trimesh.util.concatenate(
        [R.refine_axial(R.patch(mesh.vertices, mesh.faces[i:i + 256]), a.spacing)
         for i in range(0, len(mesh.faces), 256)])
    parts = R.load_variant(a.candidate.resolve(), a.station)
    rmax = {p: float(np.linalg.norm(m.vertices, axis=1).max()) for p, m in parts.items()}
    reach = {p: r * np.radians(a.angle) for p, r in rmax.items()}
    T = tilts(a.angle)
    tilted = {(k, p): m.copy().apply_transform(M) for k, (_, _, M) in enumerate(T) for p, m in parts.items()}
    crop_parts = dict(parts)
    crop_parts.update({f"{p}_{k}": m for (k, p), m in tilted.items()})
    body = R.swept_crop(fine, crop_parts, a.station, rod, details_all)
    v = np.asarray(body.vertices)
    heights, ix = np.unique(v[:, 2], return_inverse=True)
    objs = {p: fcl.CollisionObject(R.mesh_model(m.vertices, m.faces)) for p, m in parts.items()}
    tobjs = {key: fcl.CollisionObject(R.mesh_model(m.vertices, m.faces)) for key, m in tilted.items()}
    print(a.name, a.station, "crop", len(body.faces), "shapes", len(shape_ids), flush=True)
    rows, queries, pruned = [], 0, 0
    for n, j in enumerate(shape_ids):
        coef = R.coefficients(heights, a.station, rod, details_all[j])[ix]
        mapped = coef[:, 0] + v[:, :1] * coef[:, 1] + v[:, 1:2] * coef[:, 2]
        solid = fcl.CollisionObject(R.mesh_model(mapped, body.faces))
        nominal = {p: R.gap(solid, objs[p])[0] for p in R.PARTS}
        row = dict(shape=j, representative_step=int(representatives[j]),
                   **{f"nominal_{p}_gap_mm": g for p, g in nominal.items()})
        worst = (np.inf, None, None, None)
        for k, (name, sign, _) in enumerate(T):
            best, bpart = np.inf, None
            for p in sorted(R.PARTS, key=lambda p: nominal[p] - reach[p]):
                if nominal[p] - reach[p] >= best:
                    pruned += 1
                    continue
                g = R.gap(solid, tobjs[(k, p)])[0]
                queries += 1
                if g < best:
                    best, bpart = g, p
            row[f"{name}{'+' if sign > 0 else '-'}"] = best
            if best < worst[0]:
                worst = (best, name, sign, bpart)
        row.update(min_tilted_gap_mm=worst[0], min_axis=worst[1], min_sign=worst[2], min_part=worst[3])
        rows.append(row)
        if (n + 1) % 100 == 0:
            print(a.name, a.station, n + 1, "of", len(shape_ids), f"{time.time()-t0:.0f}s", flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    save(a.out, dict(script="tilt_mission.py", candidate=os.path.relpath(a.candidate.resolve(), HERE.parents[3]),
                     station_mm=a.station, angle_deg=a.angle, spacing_mm=a.spacing,
                     shard=a.shard, nshards=a.nshards, steps=a.steps, unique_shapes_total=len(representatives),
                     tilts=[f"{n}{'+' if s > 0 else '-'}" for n, s, _ in T], rmax_mm=rmax,
                     crop_faces=len(body.faces), exact_queries=queries, pruned_queries=pruned,
                     step_to_shape=inv.tolist() if a.shard == 0 else None,
                     rows=rows, elapsed_s=round(time.time() - t0, 1)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--station", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--angle", type=float, default=0.2)
    p.add_argument("--spacing", type=float, default=0.5)
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--nshards", type=int, default=1)
    p.add_argument("--steps", type=int, nargs="*", default=[], help="evaluate only these steps' shapes")
    run(p.parse_args())
