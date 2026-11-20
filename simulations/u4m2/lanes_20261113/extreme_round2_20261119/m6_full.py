"""Exact FCL triangle distances for both M6 candidate seats at all archived motion states."""

import argparse
import numpy as np
import fcl
import trimesh

from common import CAD, CANDIDATE, OUT, load_motion, motion_rows, write_table, save
from m6_socket_screen import (
    PARTS,
    WINDOW,
    load_variant,
    mesh_model,
    patch,
    gap,
    refine_axial,
    to_station,
)

GRID = np.linspace(-48, 48, 193)


def coefficients(heights, st, rod, detail):
    # The existing constant-strain CAD map is affine in x and y at each fixed z.
    n = len(heights)
    base = np.column_stack((np.zeros((n, 2)), heights))
    points = np.concatenate((base, base + [1, 0, 0], base + [0, 1, 0]))
    origin, x, y = np.split(to_station(points, 5, st, rod, detail), 3)
    return np.stack((origin, x - origin, y - origin), axis=1)


def leaves(triangles, n=32):
    if len(triangles) <= n:
        return [(triangles.min((0, 1)), triangles.max((0, 1)))]
    centres = triangles.mean(1)
    axis = np.ptp(centres, axis=0).argmax()
    half = len(centres) // 2
    idx = np.argpartition(centres[:, axis], half)
    return leaves(triangles[idx[:half]], n) + leaves(triangles[idx[half:]], n)


def swept_crop(mesh, parts, st, rod, details):
    """Exclude only faces whose swept boxes cannot reach any solid within WINDOW."""
    mins = np.full((len(GRID), 3, 3), np.inf)
    maxs = -mins.copy()
    stretch = curvature = 0.0
    for d in details:
        a = coefficients(GRID, st, rod, d)
        mins = np.minimum(mins, a)
        maxs = np.maximum(maxs, a)
        q = d["q"][-8:]
        stretch = max(stretch, np.max(np.abs(1 + q[:, 3])))
        curvature = max(
            curvature, np.max(np.linalg.norm(q[:, :3], axis=1)) / (rod.l * 1000)
        )
    v = np.asarray(mesh.vertices)
    ids = np.rint((v[:, 2] + 48) * 2).astype(int).clip(0, len(GRID) - 1)
    lo, hi = mins[ids, 0].copy(), maxs[ids, 0].copy()
    for axis in (0, 1):
        x = v[:, axis, None]
        a, b = mins[ids, axis + 1] * x, maxs[ids, axis + 1] * x
        lo += np.minimum(a, b)
        hi += np.maximum(a, b)
    # Speed along a material axial generator <= stretch + transverse radius * curvature.
    dist = np.abs(GRID[ids] - v[:, 2])
    error = dist * (stretch + curvature * np.linalg.norm(v[:, :2], axis=1)) + 1e-7
    lo = (lo - error[:, None])[mesh.faces].min(1)
    hi = (hi + error[:, None])[mesh.faces].max(1)
    bounds = trimesh.util.concatenate(list(parts.values())).bounds
    candidates = np.flatnonzero(
        np.all((lo <= bounds[1] + WINDOW) & (hi >= bounds[0] - WINDOW), axis=1)
    )
    lo, hi = lo[candidates], hi[candidates]
    keep = np.zeros(len(candidates), bool)
    for part in parts.values():
        for mn, mx in leaves(part.triangles):
            keep |= np.all((lo <= mx + WINDOW) & (hi >= mn - WINDOW), axis=1)
    return patch(v, mesh.faces[candidates[keep]])


def run(out, spacing):
    rod, z, _ = load_motion()
    rows = motion_rows()
    # Do not cluster approximately equal states. Local M6 strain uniquely sets geometry in its station frame.
    _, representatives, inverse = np.unique(
        z[:, -32:], axis=0, return_index=True, return_inverse=True
    )
    inv = inverse.ravel()
    details = [rod.kinematic_metrics(z[i])[1] for i in representatives]
    mesh = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    fine = trimesh.util.concatenate(
        [
            refine_axial(patch(mesh.vertices, mesh.faces[i : i + 256]), spacing)
            for i in range(0, len(mesh.faces), 256)
        ]
    )
    records = []
    summary = {}
    for st in (-12, 12):
        parts = load_variant(CANDIDATE, st)
        targets = {
            p: fcl.CollisionObject(mesh_model(m.vertices, m.faces))
            for p, m in parts.items()
        }
        body = swept_crop(fine, parts, st, rod, details)
        v = np.asarray(body.vertices)
        heights, ix = np.unique(v[:, 2], return_inverse=True)
        print(st, len(body.faces), "retained of", len(fine.faces), flush=True)
        solutions = []
        for j, detail in enumerate(details):
            a = coefficients(heights, st, rod, detail)[ix]
            mapped = a[:, 0] + v[:, :1] * a[:, 1] + v[:, 1:2] * a[:, 2]
            solid = fcl.CollisionObject(mesh_model(mapped, body.faces))
            result = {}
            for p in PARTS:
                distance, hit, pts = gap(solid, targets[p])
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
                print(st, j + 1, "of", len(details), flush=True)
        local = [
            dict(
                step=i,
                phase=rows[i]["phase"],
                station_mm=st,
                representative_step=int(representatives[j]),
                **solutions[j],
            )
            for i, j in enumerate(inv)
        ]
        records.extend(local)
        summary[str(st)] = dict(
            steps=len(local),
            exact_unique_shapes=len(details),
            body_faces=len(fine.faces),
            swept_crop_faces=len(body.faces),
            phase_count=len({r["phase"] for r in local}),
            minima={
                p: min(((r[p + "_gap_mm"], r["step"]) for r in local)) for p in PARTS
            },
            contacts=sum(min(r[p + "_gap_mm"] for p in PARTS) <= 0 for r in local),
        )
    write_table(out / "m6_all_steps.csv.gz", records)
    save(
        out / "m6_full.json",
        dict(spacing_mm=spacing, certified_query_radius_mm=WINDOW, stations=summary),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=type(OUT), default=OUT)
    p.add_argument("--spacing", type=float, default=0.5)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out, a.spacing)
