"""Screen the six current guide assemblies outside the two retained M5 stations against their actual bodies."""

import argparse
import csv
import gzip
import json
from pathlib import Path

import numpy as np
import trimesh

from replay import ROOT, SHARED, plant, as_relative, digest
from guide_web_compatibility import sample_patch, SignedDistance, to_station

CAD = ROOT / "cad/lanes_u4m2"
GUIDES = CAD / "guides_v3"
BODIES = {
    "M5": CAD / "retained_seat_20261118/parts/M5_machined_body.stl",
    "M6": CAD / "end_bellmouth_v1/M6_lane_anchorC.stl",
}
STATIONS = {"M5": (-24, 24), "M6": (-24, -12, 12, 24)}


def archive(source, kind):
    if kind == "holds":
        with (SHARED / "results/rebalanced_holds.csv").open() as f:
            phases = [r["phase"] for r in csv.DictReader(f)]
        with np.load(source) as f:
            return f["z"], f["hold_id"], phases
    with gzip.open(source.parent / "motion_trace.json.gz", "rt") as f:
        phases = [r["phase"] for r in json.load(f)]
    with np.load(source) as f:
        zs = f["motion_z"]
    return zs, np.arange(len(zs)), phases


def movement_bound(q, others, distance, radius, cell):
    """Largest relative material-point motion in either adjacent constant-strain cell, measured from their common guide node."""
    d = np.abs(q[None, :, :] - others)
    angle = np.linalg.norm(d[:, :, :3], axis=2)
    scale = 1.0 + np.maximum(abs(q[None, :, 3]), abs(others[:, :, 3]))
    return np.max(
        distance * d[:, :, 3]
        + (radius * distance / cell + scale * distance**2 / (2 * cell)) * angle,
        axis=1,
    )


def run(source, kind, out, spacing, reuse_bound=0.0):

    rod, _ = plant()
    base = rod.base
    zs, ids, phases = archive(source, kind)
    if len(zs) != len(ids) or len(zs) != len(phases):
        raise ValueError("Mismatched state and phase records")
    out.mkdir(parents=True, exist_ok=True)
    parts = {}
    results = []
    hashes = {}
    cols = (
        "state",
        "phase",
        "module",
        "station_mm",
        "minimum_sample_gap_mm",
        "negative_samples",
        "max_land_axial_movement_mm",
        "sample_x_mm",
        "sample_y_mm",
        "sample_z_mm",
        "representative_state",
        "sample_motion_bound_mm",
        "minimum_sample_lower_bound_mm",
        "minimum_sample_upper_bound_mm",
    )
    for module, source_cad in BODIES.items():
        body = trimesh.load_mesh(source_cad)
        if not body.is_volume:
            raise ValueError(f"Body is not a volume: {module}")
        hashes[as_relative(source_cad)] = digest(source_cad)
        j = int(module[1:]) - 1
        for st in STATIONS[module]:
            tag = f"{module}_z{st:+d}"
            files = [
                GUIDES / f"{tag}_{k}.stl" for k in ("guide", "caps", "wire_envelope")
            ]
            meshes = [trimesh.load_mesh(p) for p in files]
            if not all(m.is_volume for m in meshes):
                raise ValueError(f"Open guide component at {tag}")
            hashes.update({as_relative(p): digest(p) for p in files})
            pts, _ = sample_patch(body, meshes, st, spacing, 1.0, 7)
            f = SignedDistance(meshes)
            straight = pts.copy()
            straight[:, 2] -= st
            d0 = f(straight)
            land = (abs(straight[:, 2]) <= 0.25) & (d0 <= 0.25)
            cache = {}
            local = []
            representatives = []
            values_by_pose = []
            distance = np.max(abs(straight[:, 2]))
            radius = np.max(np.linalg.norm(straight[:, :2], axis=1))
            node = j * base.sub + round((st + 48) / (base.l * 1000))
            can_bound = bool(reuse_bound > 0 and distance <= base.l * 1000)

            for ix, z in enumerate(zs):
                key = z.tobytes()
                q = (z / base.scale).reshape(-1, 4)[node - 1 : node + 1]
                source_ix = ix
                movement = 0.0
                if key not in cache and can_bound and representatives:
                    bounds = movement_bound(
                        q, np.stack(representatives), distance, radius, base.l * 1000
                    )
                    near = int(bounds.argmin())
                    step = float(bounds[near])
                    ref_ix, reference = values_by_pose[near]
                    if step <= reuse_bound and reference[0] - step > 0:
                        cache[key] = (reference, ref_ix, step)
                if key not in cache:
                    detail = base.evaluate(z, detail=True)[2]
                    current = to_station(pts, j, st, base, detail)
                    dx = current - straight
                    lower = d0 - np.linalg.norm(dx, axis=1)
                    trial = int(lower.argmin())
                    best = f(current[trial : trial + 1])[0]
                    # A 1-Lipschitz distance field eliminates samples that cannot contain the minimum or a penetration.
                    cand = np.flatnonzero(lower <= max(0.0, best) + 1e-8)
                    values = f(current[cand])
                    k = cand[values.argmin()]
                    val = (
                        float(values.min()),
                        int((values < 0).sum()),
                        float(np.max(np.abs(dx[land, 2]))) if land.any() else None,
                        *pts[k].tolist(),
                    )
                    cache[key] = (val, ix, 0.0)
                    representatives.append(q.copy())
                    values_by_pose.append((ix, val))
                val, source_ix, movement = cache[key]
                # For a bound reuse, preserve the witness from the identified representative.
                local.append(
                    dict(
                        zip(
                            cols,
                            (
                                int(ids[ix]),
                                phases[ix],
                                module,
                                st,
                                *val,
                                int(ids[source_ix]),
                                movement,
                                val[0] - movement,
                                val[0] + movement,
                            ),
                        )
                    )
                )
            worst = min(local, key=lambda r: r["minimum_sample_lower_bound_mm"])
            parts[tag] = dict(
                representative_evaluations=len(representatives),
                bound_reuse_records=sum(r["sample_motion_bound_mm"] > 0 for r in local),
                max_land_axial_upper_bound_mm=max(
                    r["max_land_axial_movement_mm"] + r["sample_motion_bound_mm"]
                    for r in local
                ),
                samples=len(pts),
                land_samples=int(land.sum()),
                straight_minimum_mm=float(d0.min()),
                worst=worst,
                negative_records=sum(r["negative_samples"] > 0 for r in local),
                max_land_axial_movement_mm=max(
                    r["max_land_axial_movement_mm"] for r in local
                ),
            )
            results.extend(local)
            print(kind, tag, worst["state"], worst["minimum_sample_gap_mm"], flush=True)
    with gzip.open(out / f"station_{kind}.csv.gz", "wt", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(results)
    summary = dict(
        records=len(zs),
        unique_geometries=len(cache),
        station_records=len(results),
        spacing_mm=spacing,
        window_mm=1.0,
        seed=7,
        max_reuse_bound_mm=reuse_bound,
        sources=hashes,
        parts=parts,
        worst=min(results, key=lambda r: r["minimum_sample_lower_bound_mm"]),
        scope="Signed distances for sampled nearby actual body surfaces under the constant-strain rod deformation. Coordinates identify the undeformed CAD witness. The surfaces, adhesive and guide are not in coupled force equilibrium. Numerical and manufacturing uncertainty require separate evidence.",
    )
    (out / f"station_{kind}.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--kind", choices=("holds", "motion"), required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--spacing", type=float, default=0.15)
    p.add_argument("--reuse-bound", type=float, default=0.0)
    a = p.parse_args()
    run(a.source, a.kind, a.out, a.spacing, a.reuse_bound)
