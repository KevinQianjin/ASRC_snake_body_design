"""How much of the clearance margin is the homogenised rod map's own distortion of the arm?

For each bonded arm (four MOUNT ribs, both stations) and the governing steps, CAD wall points of
the arm inside the guide socket (|z - station| <= 1.62 mm, the Round 2 socket half-length) are
mapped with the rod map (``to_station``). The guide is bonded to the 0.5 mm land, so it follows
the land's least-squares rigid motion. The deviation of the socket-wall points from that rigid
motion is the non-rigid distortion that the rod map writes into the arm geometry around the guide,
which the 19-22 November clearance studies compared against margins of about 0.03-0.04 mm.
The free-strut solid field of ``solid_bond.py`` is NOT used here (it is over-constrained).
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261122"))
import crowned_bond as CB  # noqa: E402
import strut_fe as FE  # noqa: E402
from solid_bond import CUTS  # noqa: E402

SOCKET_HALF, LAND_HALF = 1.62, 0.25


def wall_points(solid, st, half, edge=0.05):
    s = trimesh.intersections.slice_mesh_plane(solid, [0, 0, 1], [0, 0, st - half], cap=False)
    s = trimesh.intersections.slice_mesh_plane(s, [0, 0, -1], [0, 0, st + half], cap=False)
    v, f = trimesh.remesh.subdivide_to_size(s.vertices, s.faces, max_edge=edge)
    m = trimesh.Trimesh(v, f, process=False)
    keep = np.abs(m.face_normals[:, 2]) < 0.95
    return m.triangles_center[keep]


def main():
    rod, z, _ = CB.load_motion()
    module = trimesh.load_mesh(CB.S.BODY)
    rows = []
    geo = {}
    for st in CUTS:
        for th in CB.S.MOUNT:
            solid = FE.crop_strut(module, th, *CUTS[st])
            geo[th, st] = (wall_points(solid, st, LAND_HALF), wall_points(solid, st, SOCKET_HALF))
    for step in CB.STEPS:
        det = rod.kinematic_metrics(z[step])[1]
        for (th, st), (land, sock) in geo.items():
            loc = lambda P: P - [0, 0, st]  # noqa: E731
            dl = CB.to_station(land, 5, st, rod, det) - loc(land)
            ds = CB.to_station(sock, 5, st, rod, det) - loc(sock)
            M = np.vstack([np.column_stack((np.eye(3), -CB.S.skew(x))) for x in loc(land)])
            q = np.linalg.lstsq(M, dl.ravel(), rcond=None)[0]
            Ms = np.vstack([np.column_stack((np.eye(3), -CB.S.skew(x))) for x in loc(sock)])
            dev = ds - (Ms @ q).reshape(-1, 3)
            n = np.linalg.norm(dev, axis=1)
            zz = sock[:, 2] - st
            rows.append(dict(step=step, station_mm=st, rib_deg=th,
                             land_rigid_rotation_deg=float(np.degrees(np.linalg.norm(q[3:]))),
                             max_socket_wall_deviation_mm=float(n.max()),
                             at_zh_mm=float(zz[np.argmax(n)]),
                             max_dev_within_land_mm=float(n[np.abs(zz) <= LAND_HALF].max()),
                             max_dev_at_socket_ends_mm=float(n[np.abs(zz) >= SOCKET_HALF - 0.1].max())))
            print(rows[-1], flush=True)
    (HERE / "results" / "socket_distortion.json").write_text(json.dumps(dict(rows=rows), indent=1))


if __name__ == "__main__":
    main()
