"""Handoff item 2 (23 Nov evening run): exact M6 clearance at +/-0.2 deg tilt with the SOLID arm.

The archived crowned-land margins (0.0284 / 0.0424 mm at z = -12 / +12 mm) used a body deformed
by the homogenised rod map, and the 23 November bracket used an undeformed body (about 0.079 /
0.080 mm). Here the body around each guide is deformed by the whole-body solid field of
``body_bond.py`` (guide bonded with the crowned or uncrowned layer, G = 500 MPa by default,
"local" moment scaling + station wrench) expressed RELATIVE TO THE GUIDE:

    x_body_in_guide_frame = x + u_body(x) - (q_t + q_r x (x - station))

with the guide's own bonded motion q. Same parts, 26 tilts of the guide about the station origin,
0.5 mm axial refinement and exact FCL distance as ``evening_20261123/rigid_arm_probe.py``.
Linear field (small strain; the relative field is small, so linearised rotation is adequate).
Rigid-CAD clearance only; no contact mechanics.
"""
import argparse, json, sys, time
from pathlib import Path

import fcl
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import body_bond as BB  # noqa: E402  (sets up the evening_20261122/23 import paths)

ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2))
sys.path.insert(0, str(HERE.parent / "evening_20261121"))
import m6_full as R  # noqa: E402
from common import CAD  # noqa: E402
from tilt_mission import tilts  # noqa: E402

FOLDERS = {0.0: CAD / "m6_bond_gap_20261119", 0.06: CAD / "m6_crowned_land_20261120"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=float, default=5.0)
    ap.add_argument("--max-vol", type=float, default=0.4)
    ap.add_argument("--max-edge", type=float, default=0.08)
    ap.add_argument("--G", type=float, default=500.0)
    ap.add_argument("--steps", type=int, nargs="+", default=[1709, 1885])
    ap.add_argument("--angle", type=float, default=0.2)
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    t0 = time.monotonic()
    rod, zs, _ = BB.CB.load_motion()
    B = BB.Body(a.quality, a.max_vol, a.max_edge)
    W = {st: BB.CB.station_wrenches("M6", st) for st in BB.STATIONS}
    rot = {s: BB.rod_rotations(rod, rod.kinematic_metrics(zs[s])[1]) for s in a.steps}
    mesh = trimesh.load_mesh(BB.BS.BODY)
    T = [("none", 0, np.eye(4))] + tilts(a.angle)
    rows = []
    patches = {}
    for st in BB.STATIONS:
        tri = mesh.vertices[mesh.faces]
        keep = np.all(np.abs(tri[:, :, 2] - st) < 5, axis=1) | ((tri[:, :, 2].min(1) < st + 3) & (tri[:, :, 2].max(1) > st - 3))
        local = R.patch(mesh.vertices - [0, 0, st], mesh.faces[keep])
        fine = R.refine_axial(local, 0.5)
        M, mb = BB.locate(B.X, B.conn, np.asarray(fine.vertices) + [0, 0, st])
        patches[st] = (fine, (M @ B.T).tocsr(), mb)
    for crown, folder in FOLDERS.items():
        Kt = B.system(a.G, crown)
        rhs = []
        for s in a.steps:
            rhs += [(rot[s]["end_rotvec"], np.zeros(12)), (np.zeros(3), np.r_[W[-12][s], W[12][s]])]
        U, resid = B.solve(Kt, rhs)
        for i, s in enumerate(a.steps):
            uniform = np.linalg.norm(rot[s]["end_rotvec"]) * 24.0 / (BB.BS.Z_HI - BB.BS.Z_LO)
            for st in BB.STATIONS:
                scale = float(np.linalg.norm(rot[s]["local"][st]) / uniform)
                Ul = scale * U[:, 2 * i] + U[:, 2 * i + 1]
                fine, MT, mb = patches[st]
                ub = (MT @ Ul[:B.n]).reshape(-1, 3)
                q = Ul[B.n + 6 * BB.STATIONS.index(st): B.n + 6 * BB.STATIONS.index(st) + 6]
                x = np.asarray(fine.vertices)
                rel = ub - (q[:3] + np.cross(q[3:], x))
                body = fcl.CollisionObject(R.mesh_model(x + rel, fine.faces))
                parts = R.load_variant(folder, st)
                gaps, by_part = {}, {}
                for name, sign, Mt in T:
                    key = name + ("" if sign == 0 else "+" if sign > 0 else "-")
                    by_part[key] = {p: R.gap(body, fcl.CollisionObject(R.mesh_model(
                        m.copy().apply_transform(Mt).vertices, m.faces)))[0] for p, m in parts.items()}
                    gaps[key] = min(by_part[key].values())
                tilted = {n: g for n, g in gaps.items() if n != "none"}
                worst = min(tilted, key=tilted.get)
                rows.append(dict(step=s, station_mm=st, crown_mm=crown, G_MPa=a.G, local_moment_scale=scale,
                                 solve_residual=resid, locate_min_bary=mb,
                                 max_relative_body_motion_mm=float(np.linalg.norm(rel, axis=1).max()),
                                 gap_no_tilt_mm=gaps["none"], min_gap_tilted_mm=tilted[worst], worst_tilt=worst,
                                 governing_part=min(by_part[worst], key=by_part[worst].get),
                                 no_tilt_by_part_mm=by_part["none"], gaps_mm=gaps))
                print(s, st, crown, f"rel {rows[-1]['max_relative_body_motion_mm']:.4f} gap {gaps['none']:.5f} "
                      f"tilted {tilted[worst]:.5f} {worst} {rows[-1]['governing_part']}", flush=True)
                Path(a.out).mkdir(parents=True, exist_ok=True)
                (Path(a.out) / "solid_arm_probe.json").write_text(json.dumps(dict(
                    scope=__doc__, angle_deg=a.angle, spacing_mm=0.5, mesh=B.mesh, rows=rows,
                    elapsed_s=time.monotonic() - t0), indent=1, default=float))


if __name__ == "__main__":
    main()
