"""Register coupled M5 solid/shell fields to the actual assembly and compare both hub profiles."""

import argparse
import json
from pathlib import Path
import sys

from scipy.spatial.transform import Rotation
from bench_inputs import CAD

sys.path.insert(0, str(CAD.parent / "m5_hub_relief_20261119"))
import relief
from clearance import (
    CAD as RETAINED,
    CASES,
    b,
    bounds_distance,
    collider,
    fcl,
    j,
    map_vertices,
    md,
    np,
    prepared_webs,
    read_parts,
    station_parts,
)
from corrected import local_transfer
from remaining_body import mapped_points, partition, rigid_poses

NEAR = 0.7


def solid(vertices, faces):
    obj = md.Manifold(
        md.Mesh64(
            np.array(vertices, dtype=float, order="C", copy=True),
            np.array(faces, dtype=np.uint64, order="C", copy=True),
        )
    )
    if obj.status() != md.Error.NoError or obj.volume() <= 0.0:
        raise ValueError("Invalid deformed CAD surface")
    return obj


def append_distances(body, family, hardware, rows):
    query = fcl.CollisionObject(collider(body))
    bound = body.bounding_box()
    for label, kind, obj, obs, variant in hardware:
        if bounds_distance(bound, obj.bounding_box()) > NEAR:
            continue
        res = fcl.DistanceResult()
        d = max(
            0.0,
            float(
                fcl.distance(
                    query, obs, fcl.DistanceRequest(enable_nearest_points=True), res
                )
            ),
        )
        if d > NEAR:
            continue
        vol = max(0.0, (body ^ obj).volume()) if d < 1e-7 else 0.0
        rows.append(
            dict(
                body=family,
                part=label,
                kind=kind,
                variant=variant,
                gap_mm=d,
                overlap_mm3=vol,
                nearest_xyz_mm=np.mean(res.nearest_points, axis=0).tolist()
                if d > 1e-7
                else None,
            )
        )


def classify(rows, mask):
    subset = [r for r in rows if mask(r)]
    if not subset:
        return None
    return min(subset, key=lambda r: (r["gap_mm"], -r["overlap_mm3"]))


def run(a):
    mesh = dict(np.load(a.fields / "shell_mesh.npz"))
    pmesh = dict(np.load(a.fields / "patch_mesh.npz"))
    L = float(pmesh["length"])
    parts = read_parts(RETAINED / "parts")
    candidate = {k: b.load(a.hub_parts / f"{k}.stl") for k in relief.FAMILIES}
    data = {c: dict(np.load(a.fields / c / "shell.npz")) for c in a.cases}
    poses = {c: rigid_poses(mesh, s["fields"]) for c, s in data.items()}
    body = b.load(RETAINED / "parts/M5_machined_body.stl")
    bits = partition(mesh, a.outer_edge)
    env = b.cyl(31, -2.05, 2.05, 192)
    rows = []
    quality = []
    for z in j.STATIONS:
        hw = []
        for name, k, obj in station_parts(parts, z):
            if (obj - env).volume() > 1e-7:
                raise ValueError("Invalid station bounding envelope")
            hw.append(
                (
                    name,
                    k,
                    obj,
                    fcl.CollisionObject(collider(obj)),
                    "original" if k in candidate else "both",
                )
            )
            if k in candidate:
                other = b.place(candidate[k], 45 * int(name[4:]))
                hw.append(
                    (name, k, other, fcl.CollisionObject(collider(other)), "relieved")
                )
        hits = {c: [] for c in data}
        outer = {c: [] for c in data}
        for web in prepared_webs(body, z, a.inner_edge, mesh):
            i, angle = web[:2]
            az = np.radians(angle)
            W = Rotation.from_euler("z", angle, degrees=True).as_matrix() @ j.web_axes(
                z
            )
            pivot = j.R_PIVOT * np.array([np.cos(az), np.sin(az), 0.0])
            reference = (web[7] - pivot - [0, 0, z]) @ W
            if i % 2:
                sel, idx, weight, err = local_transfer(
                    reference, pmesh, str(pmesh["level"]), L, float(pmesh["crown"])
                )
                # Join onto the shell at the cut faces. No incremental displacement is added to the shell twice.
                fade = np.clip((L - abs(reference[sel, 0])) / 0.18, 0.0, 1.0)
            for c, s in data.items():
                q = map_vertices(s["fields"], s, z, web)
                if i % 2:
                    with np.load(a.fields / c / f"site_{z}_{angle:g}.npz") as pc:
                        deformed = (
                            reference[sel]
                            + np.einsum("ij,ijk->ik", weight, pc["u"][idx])
                        ) @ pc["R"].T + pc["translation"]
                    delta = deformed @ W.T + pivot - q[sel]
                    quality.append(
                        dict(
                            case=c,
                            station=z,
                            rib_deg=angle,
                            cad_to_hex_max_projection_mm=float(err.max()),
                            seam_blend_width_mm=0.18,
                            largest_difference_in_join_band_mm=float(
                                np.linalg.norm(delta[fade < 1], axis=1).max()
                            ),
                        )
                    )
                    q[sel] += fade[:, None] * delta
                append_distances(solid(q, web[5]), f"rib_{i}", hw, hits[c])
        for win, tag, v, faces, link in bits:
            if win == z:
                continue
            for c, s in data.items():
                q = (
                    mapped_points(v, link, tag, s["fields"], poses[c]) - s[f"C{z}"]
                ) @ s[f"R{z}"]
                if q[:, 2].min() > 2.05 + NEAR or q[:, 2].max() < -2.05 - NEAR:
                    continue
                append_distances(solid(q, faces), tag, hw, outer[c])
        for c, s in data.items():
            bearing = lambda r: r["kind"] in ("shoulder_pin", "threaded_cap")
            station = dict(
                case=c,
                station=z,
                near_local_pairs=hits[c],
                near_nonlocal_pairs=outer[c],
                intended_bearing=classify(hits[c], bearing),
            )
            other = -z
            R = s[f"R{z}"].T @ s[f"R{other}"]
            t = (s[f"C{other}"] - s[f"C{z}"]) @ s[f"R{z}"]
            station["station_envelope_gap_mm"] = env.min_gap(
                env.transform(np.column_stack((R, t))), 55.0
            )
            for variant in ("original", "relieved"):
                local = classify(
                    hits[c],
                    lambda r: r["variant"] in ("both", variant) and not bearing(r),
                )
                outside = classify(
                    outer[c], lambda r: r["variant"] in ("both", variant)
                )
                nearest = classify(
                    [r for r in (local, outside) if r is not None], lambda r: True
                )
                if nearest is None:
                    raise ValueError("No near pair: increase the reporting radius")
                station[variant] = dict(
                    local_unintended=local,
                    remaining_body=outside,
                    nearest_unintended=nearest,
                )
            rows.append(station)
            print(
                c,
                z,
                [
                    (
                        v,
                        station[v]["nearest_unintended"]["part"],
                        round(station[v]["nearest_unintended"]["gap_mm"], 5),
                    )
                    for v in ("original", "relieved")
                ],
                flush=True,
            )
    return dict(
        solid_level=str(pmesh["level"]),
        local_surface_edge_mm=a.inner_edge,
        other_body_surface_edge_mm=a.outer_edge,
        candidate_manifest=json.loads((a.hub_parts / "manifest.json").read_text())[
            "chamfer_radial_and_axial_mm"
        ],
        nearest_search_radius_mm=NEAR,
        stations=rows,
        join_checks=quality,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fields", type=Path, required=True)
    p.add_argument("--hub-parts", type=Path, required=True)
    p.add_argument("--cases", nargs="+", choices=CASES, required=True)
    p.add_argument("--inner-edge", type=float, default=0.15)
    p.add_argument("--outer-edge", type=float, default=0.25)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.write_text(json.dumps(run(a), indent=2) + "\n")
