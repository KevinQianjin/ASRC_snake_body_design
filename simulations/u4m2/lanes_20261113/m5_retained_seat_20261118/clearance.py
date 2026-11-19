"""Map the machined M5 CAD webs into the moving guide frame and test the actual solids."""

import argparse
import csv
import hashlib
import fcl
import json
from pathlib import Path
import sys

import manifold3d as md
import numpy as np

HERE = Path(__file__).resolve().parent
CAD = HERE.parents[3] / "cad/lanes_u4m2/retained_seat_20261118"
sys.path.insert(0, str(CAD))
sys.path.insert(0, str(HERE.parent / "m5_large_rotation_20261118"))
import build as b
import joint as j
from continuation import transfer_weights

CASES = ("bend67.5", "bend0", "146", "141", "47", "64")
CARDINAL = (0, 90, 180, 270)


def collider(solid):
    mesh = solid.to_mesh64()
    model = fcl.BVHModel()
    model.beginModel(len(mesh.tri_verts), len(mesh.vert_properties))
    model.addSubModel(mesh.vert_properties[:, :3], mesh.tri_verts)
    model.endModel()
    return model


def read_parts(directory):
    return {
        p.stem: b.load(p)
        for p in directory.glob("*.stl")
        if not p.name.startswith("M5_")
    }


def station_parts(parts, z):
    for i in range(8):
        a = 45 * i
        name = "hub_upper_sector" if i % 2 == 0 else "hub_lower_sector"
        yield f"hub_{i}", name, b.place(parts[name], a)
        yield (
            f"lap_screw_{i}",
            "lap_screw",
            b.place(parts["lap_screw"].translate((9.60, 0, 0)), a + 22.5),
        )
    for i, a in enumerate(j.ANGLES):
        for name in ("fork", "gate", "shoulder_pin", "threaded_cap"):
            obj = parts[f"{name}_{z:+d}"] if name in ("fork", "gate") else parts[name]
            yield f"{name}_{i}", name, b.place(obj, a)
        lock = parts["hub_screw"].translate((j.HUB_FASTENER_X, j.FORK_Y, 0))
        yield f"fork_screw_{i}", "hub_screw", b.place(lock, a)
    for i, a in enumerate(CARDINAL):
        yield f"arm_{i}", "rope_arm", b.place(parts["rope_arm"], a)
        lock = parts["hub_screw"].translate((j.HUB_FASTENER_X, 0, 0))
        yield f"arm_screw_{i}", "hub_screw", b.place(lock, a)


def prepared_webs(body, z, edge, mesh):
    """Both extremes of this slab lie beyond the 3.2 mm fork plate."""
    half = 4.85
    obj = body.trim_by_plane((0, 0, 1), z - half).trim_by_plane((0, 0, -1), -z - half)
    shapes = obj.decompose()
    if len(shapes) != 8:
        raise ValueError(f"Expected eight separate CAD webs, got {len(shapes)}")
    out = []
    for solid in shapes:
        q = solid.simplify(0.0005).refine_to_length(edge).to_mesh64()
        verts = q.vert_properties[:, :3]
        faces = q.tri_verts
        centroid = verts.mean(0)
        angle = np.degrees(np.arctan2(centroid[1], centroid[0]))
        i = int(np.argmin(np.abs((mesh["theta"] - angle + 180) % 360 - 180)))
        a = np.radians(mesh["theta"][i])
        er = np.array([np.cos(a), np.sin(a), 0])
        n = np.cross(er, [0, 0, 1])
        sample = np.c_[verts @ er, verts[:, 2]]
        corners, weights, outside = transfer_weights(mesh["x"], mesh["t"], sample)
        reconstructed = (sample[:, 0, None] * er + sample[:, 1, None] * [0, 0, 1]) + (
            verts @ n
        )[:, None] * n
        if np.linalg.norm(reconstructed - verts, axis=1).max() > 1e-10:
            raise ValueError("Invalid web frame")
        ends = np.isclose(abs(verts[:, 2] - z), half, atol=1e-6)
        out.append(
            (
                i,
                mesh["theta"][i],
                corners,
                weights,
                verts @ n,
                faces,
                ends,
                verts,
                outside,
            )
        )
    return sorted(out, key=lambda x: x[0])


def map_vertices(field, pose, z, web):
    i, angle, corners, w, off, faces, ends, verts, outside = web
    nodal = field[i, corners]
    at = np.einsum("ij,ijk->ik", w, nodal)
    d = at[:, 3:]
    d /= np.linalg.norm(d, axis=1)[:, None]
    mapped = (at[:, :3] + off[:, None] * d - pose[f"C{z}"]) @ pose[f"R{z}"]
    return mapped


def map_web(field, pose, z, web):
    mapped = map_vertices(field, pose, z, web)
    faces, ends = web[5:7]
    solid = md.Manifold(
        md.Mesh64(
            np.array(mapped, dtype=np.float64, order="C", copy=True),
            np.array(faces, dtype=np.uint64, order="C", copy=True),
        )
    )
    if solid.status() != md.Error.NoError or solid.volume() <= 0:
        raise ValueError("Invalid deformed solid")
    return solid, mapped[ends]


def bounds_distance(a, bounds):
    a = np.array(a)
    bnd = np.array(bounds)
    return np.linalg.norm(np.maximum(np.maximum(a[:3] - bnd[3:], bnd[:3] - a[3:]), 0))


def run(args):
    def checksums():
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(args.parts.glob("*.stl"))
        }

    checked_parts = checksums()
    mesh = np.load(args.cache / f"mesh_{args.tag}.npz")
    parts = read_parts(args.parts)
    body = b.load(args.parts / "M5_machined_body.stl")
    rows = []
    geometry = []
    mesh_info = {}
    poses = {
        case: dict(np.load(args.cache / f"{case}_{args.tag}.npz"))
        for case in args.cases
    }
    for z in j.STATIONS:
        hardware = list(station_parts(parts, z))
        hardware_bvh = {
            label: fcl.CollisionObject(collider(obj)) for label, _, obj in hardware
        }
        request = fcl.DistanceRequest(enable_nearest_points=True)
        ws = prepared_webs(body, z, args.edge, mesh)
        mesh_info[str(z)] = {
            "web_count": len(ws),
            "vertices": sum(len(q[7]) for q in ws),
            "extrapolated_vertices": sum(q[-1] for q in ws),
            "faces": sum(len(q[5]) for q in ws),
        }
        for case, pose in poses.items():
            records = []
            solids = {}
            for web in ws:
                i, angle = web[:2]
                obj, ends = map_web(pose["fields"], pose, z, web)
                solids[round(float(angle), 1)] = obj
                query = fcl.CollisionObject(collider(obj))
                # Each row is a true minimum within the capped 1 mm search for this web and component.
                for label, family, part in hardware:
                    if bounds_distance(obj.bounding_box(), part.bounding_box()) > 1:
                        continue
                    dr = fcl.DistanceResult()
                    gap = float(
                        np.clip(
                            fcl.distance(query, hardware_bvh[label], request, dr), 0, 1
                        )
                    )
                    volume = max(0.0, (obj ^ part).volume()) if gap < 0.000001 else 0.0
                    pt = (
                        np.mean(dr.nearest_points, axis=0).tolist()
                        if 0 < gap < 1
                        else [None] * 3
                    )
                    end_bnd_min = float(
                        np.min(
                            np.maximum.reduce(
                                [
                                    np.zeros(len(ends)),
                                    ends[:, 2] - part.bounding_box()[5],
                                    part.bounding_box()[2] - ends[:, 2],
                                ]
                            )
                        )
                    )
                    records.append(
                        dict(
                            case=case,
                            station=z,
                            rib_deg=round(float(angle), 1),
                            part=label,
                            family=family,
                            clearance_mm=gap,
                            intersection_mm3=volume,
                            nearest_x_mm=pt[0],
                            nearest_y_mm=pt[1],
                            nearest_z_mm=pt[2],
                            slab_end_axial_lower_bound_mm=end_bnd_min,
                        )
                    )
            if not records:
                raise ValueError("No nearby hardware found")
            rows.extend(records)
            other = [
                r
                for r in records
                if r["family"] not in ("shoulder_pin", "threaded_cap")
            ]
            bearing = [
                r for r in records if r["family"] in ("shoulder_pin", "threaded_cap")
            ]

            def worst(rr):
                row = min(
                    rr, key=lambda x: (x["clearance_mm"], -x["intersection_mm3"])
                ).copy()
                source = solids[row["rib_deg"]]
                part = next(p for k, _, p in hardware if k == row["part"])
                row["independent_manifold_gap_mm"] = source.min_gap(part, 1.0)
                row["independent_intersection_mm3"] = max(0.0, (source ^ part).volume())
                return row

            geometry.append(
                dict(
                    case=case,
                    station=z,
                    unintended=worst(other),
                    bearing=worst(bearing),
                    pairs_in_broad_phase=len(records),
                    min_axial_distance_to_cut_faces_mm=min(
                        x["slab_end_axial_lower_bound_mm"] for x in records
                    ),
                )
            )
            print(args.tag, args.edge, z, case, geometry[-1]["unintended"], flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    tag = args.tag + "_edge" + str(args.edge).replace(".", "p")
    with (args.out / f"clearance_{tag}.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    if checked_parts != checksums():
        raise ValueError("CAD changed during the clearance study")
    result = dict(
        part_sha256=checked_parts,
        shell_triangle_area_mm2=float(args.tag.replace("p", ".")),
        surface_edge_target_mm=args.edge,
        surface_simplification_bound_mm=0.0005,
        slab_half_height_mm=4.85,
        search_limit_mm=1,
        web_mesh=mesh_info,
        recovery_errors={c: p["endpoint_errors"].tolist() for c, p in poses.items()},
        stations=geometry,
    )
    (args.out / f"clearance_{tag}.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--parts", type=Path, default=CAD / "parts")
    ap.add_argument("--tag", required=True, choices=("0p025", "0p055"))
    ap.add_argument("--edge", type=float, default=0.20)
    ap.add_argument("--cases", nargs="+", default=CASES, choices=CASES)
    ap.add_argument("--out", required=True, type=Path)
    run(ap.parse_args())
