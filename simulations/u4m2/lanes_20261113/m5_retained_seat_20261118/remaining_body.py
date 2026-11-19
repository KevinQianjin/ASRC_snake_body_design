"""Check the remainder of the M5 CAD and guide-to-guide separation outside the detailed web windows."""

import argparse
import json
from pathlib import Path

from clearance import (
    CASES,
    CAD,
    b,
    collider,
    fcl,
    j,
    md,
    np,
    read_parts,
    station_parts,
    transfer_weights,
)
from shell import master_tags, RING_WINDOWS


def rigid_poses(mesh, fields):
    r, z = mesh["x"].T
    group = master_tags(mesh["x"])
    theta = np.radians(mesh["theta"])
    radial = np.c_[np.cos(theta), np.sin(theta), np.zeros(8)]
    xyz = radial[:, None, :] * r[None, :, None] + np.array([0, 0, 1]) * z[None, :, None]
    out = {}
    for name in ("D0", "D1", "R0", "R1", "R2", "R3"):
        x = xyz[:, group == name].reshape(-1, 3)
        y = fields[:, group == name, :3].reshape(-1, 3)
        u, _, v = np.linalg.svd((x - x.mean(0)).T @ (y - y.mean(0)))
        S = np.eye(3)
        S[-1, -1] = np.sign(np.linalg.det(u @ v))
        T = u @ S @ v
        offset = y.mean(0) - x.mean(0) @ T
        error = np.linalg.norm(x @ T + offset - y, axis=1).max()
        if error > 2e-6:
            raise ValueError(f"Rigid subbody {name} displacement mismatch {error}")
        out[name] = (T, offset, float(error))
    return out


def slab(lo, hi):
    return b.box((-35, -35, lo), (35, 35, hi))


def partition(mesh, edge):
    # Uncut source conservatively fills the other guide's eight counterbores/holes.
    body = b.load(b.BODY)
    stem = b.cyl(3.4, -48, 48)
    rc = b.cyl(8.62, -48, 48)
    blocks = {
        "D0": slab(-49, -45) + (stem ^ slab(-49, -30)),
        "D1": slab(45, 49) + (stem ^ slab(30, 49)),
    }
    for i, (lo, hi) in enumerate(RING_WINDOWS):
        blocks[f"R{i}"] = rc ^ slab(lo, hi)
    windows = {z: slab(z - 4.85, z + 4.85) for z in j.STATIONS}
    bits = []
    remaining = body
    for name, cut in blocks.items():
        part, remaining = remaining.split(cut)
        bits.append((None, name, part))
    for station, cut in windows.items():
        part, remaining = remaining.split(cut)
        bits.extend((station, None, component) for component in part.decompose())
    bits.extend((None, None, component) for component in remaining.decompose())
    output = []
    total = 0.0
    for window, tag, obj in bits:
        total += obj.volume()
        m = obj.to_mesh64()
        v = m.vert_properties[:, :3]
        a = np.arctan2(v[:, 1].mean(), v[:, 0].mean()) * 180 / np.pi
        i = int(np.argmin(abs((a - mesh["theta"] + 180) % 360 - 180)))
        A = np.radians(mesh["theta"][i])
        er = np.array([np.cos(A), np.sin(A), 0])
        n = np.cross(er, [0, 0, 1])
        if tag is None and np.max(abs(v @ n)) > 1.51:
            if v[:, 2].min() < 40.99:
                raise ValueError("Found an unclassified non-planar component")
            tag = "D1"  # Four actual rope-anchor lugs integral to the distal disk.
        if tag:
            output.append((window, tag, v, m.tri_verts, None))
        else:
            m = obj.simplify(0.001).refine_to_length(edge).to_mesh64()
            v = m.vert_properties[:, :3]
            corners, w, _ = transfer_weights(
                mesh["x"], mesh["t"], np.c_[v @ er, v[:, 2]]
            )
            output.append((window, f"rib_{i}", v, m.tri_verts, (i, corners, w, v @ n)))
    if abs(total - body.volume()) > 0.01:
        raise ValueError(
            f"CAD partition mass discrepancy {total - body.volume():.9f} mm3 over {body.volume():.6f}"
        )
    return output


def mapped_points(vertices, web, tag, fields, poses):
    if web is None:
        rotation, translation, _ = poses[tag]
        return vertices @ rotation + translation
    rib, corners, weights, offset = web
    nodes = np.einsum("ij,ijk->ik", weights, fields[rib, corners])
    directors = nodes[:, 3:]
    directors /= np.linalg.norm(directors, axis=1)[:, None]
    return nodes[:, :3] + offset[:, None] * directors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    ap.add_argument("--out-name", default="remaining_body.json")
    ap.add_argument(
        "--intersections",
        type=Path,
        help="Optional local STL checkpoints in moving guide coordinates",
    )
    ap.add_argument("--edge", type=float, default=0.45)
    ap.add_argument("--tag", default="0p025")
    a = ap.parse_args()
    mesh = np.load(a.cache / f"mesh_{a.tag}.npz")
    bits = partition(mesh, a.edge)
    parts = read_parts(CAD / "parts")
    rows = []
    previous = []
    hw = {z: list(station_parts(parts, z)) for z in j.STATIONS}
    coll = {
        z: [fcl.CollisionObject(collider(p)) for _, _, p in hs] for z, hs in hw.items()
    }
    # The disk is deliberately outside every station part, including screw heads and the four fingers.
    envelope = b.cyl(31, -2.05, 2.05, 192)
    for hs in hw.values():
        if any((p - envelope).volume() > 1e-7 for _, _, p in hs):
            raise ValueError("Station envelope too small")
    for case in a.cases:
        s = dict(np.load(a.cache / f"{case}_{a.tag}.npz"))
        poses = rigid_poses(mesh, s["fields"])
        mapped = []
        for win, tag, v, faces, free in bits:
            world = mapped_points(v, free, tag, s["fields"], poses)
            mapped.append((win, tag, world, faces))
        for z in j.STATIONS:
            distances = []
            near = []
            for win, tag, v, faces in mapped:
                if win == z:
                    continue
                q = (v - s[f"C{z}"]) @ s[f"R{z}"]
                lo = q[:, 2].min()
                hi = q[:, 2].max()
                bound = max(lo - 2.05, -2.05 - hi, 0.0)
                if bound < 1:
                    qmesh = fcl.BVHModel()
                    qmesh.beginModel(len(faces), len(q))
                    qmesh.addSubModel(q, faces)
                    qmesh.endModel()
                    qo = fcl.CollisionObject(qmesh)
                    gaps = [
                        fcl.distance(
                            qo, obj, fcl.DistanceRequest(), fcl.DistanceResult()
                        )
                        for obj in coll[z]
                    ]
                    k = int(np.argmin(gaps))
                    bound = float(gaps[k])
                    partname, _, placed = hw[z][k]
                    res = fcl.DistanceResult()
                    fcl.distance(
                        qo,
                        coll[z][k],
                        fcl.DistanceRequest(enable_nearest_points=True),
                        res,
                    )
                    info = dict(
                        body=tag, part=partname, gap_mm=bound, intersection_mm3=0.0
                    )
                    if bound <= 1e-6:
                        solid = md.Manifold(
                            md.Mesh64(
                                np.array(q, order="C"),
                                np.array(faces, dtype=np.uint64, order="C", copy=True),
                            )
                        )
                        hit = solid ^ placed
                        info.update(
                            intersection_mm3=max(0.0, hit.volume()),
                            intersection_bounds_mm=list(hit.bounding_box()),
                        )
                        if a.intersections and hit.volume() > 0:
                            a.intersections.mkdir(parents=True, exist_ok=True)
                            b.trimesh_of(hit).export(
                                a.intersections / f"{case}_{z}_{tag}_{partname}.stl"
                            )
                            b.trimesh_of(solid).export(
                                a.intersections
                                / f"{case}_{z}_{tag}_{partname}_obstacle.stl"
                            )
                    else:
                        info["nearest_xyz_mm"] = np.mean(
                            res.nearest_points, axis=0
                        ).tolist()
                    near.append(info)
                    if case == "bend67.5" and tag == "rib_7":
                        solid = md.Manifold(
                            md.Mesh64(
                                np.array(q, order="C"),
                                np.array(faces, dtype=np.uint64, order="C", copy=True),
                            )
                        )
                        old = b.place(b.saddle(z, radial_limit=None)[0], j.ANGLES[0])
                        oldhit = old ^ solid
                        if oldhit.volume() > 1e-7:
                            final = next(h[2] for h in hw[z] if h[0] == "fork_0")
                            previous.append(
                                dict(
                                    case=case,
                                    station=z,
                                    rib_deg=337.5,
                                    part="fork_0",
                                    old_intersection_mm3=oldhit.volume(),
                                    old_overlap_bounds_station_xyz_mm=list(
                                        oldhit.bounding_box()
                                    ),
                                    revised_intersection_mm3=max(
                                        0.0, (solid ^ final).volume()
                                    ),
                                    revised_pair_gap_mm=solid.min_gap(final, 2.0),
                                )
                            )
                distances.append([tag, float(bound)])
            other = -z
            R = s[f"R{z}"].T @ s[f"R{other}"]
            C = (s[f"C{other}"] - s[f"C{z}"]) @ s[f"R{z}"]
            disk_gap = envelope.min_gap(
                envelope.transform(np.column_stack((R, C))), 50.0
            )
            rows.append(
                dict(
                    case=case,
                    station=z,
                    remaining_components=len(distances),
                    closest_lower_bound=min(distances, key=lambda d: d[1]),
                    direct_surface_checks=near,
                    guide_envelope_distance_mm=disk_gap,
                    rigid_fit_max_error_mm=max(p[2] for p in poses.values()),
                )
            )
            print(case, z, rows[-1]["closest_lower_bound"], disk_gap, flush=True)
    a.out.mkdir(exist_ok=True, parents=True)
    (a.out / a.out_name).write_text(
        json.dumps(
            dict(
                shell_mesh=a.tag,
                web_surface_edge_mm=a.edge,
                free_web_simplification_mm=0.001,
                previous_tip_comparison=previous,
                rows=rows,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
