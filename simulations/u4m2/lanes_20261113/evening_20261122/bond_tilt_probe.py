"""Exact M6 CAD gap with the bonded-support guide motion AND a 0.2 deg rigid assembly tilt.

The 21 November evening run certified the crowned land against rigid tilt alone, with the
guide at its ideal rod position. Here the guide motion relative to its witness web from
the variable-thickness bond model (``crowned_bond.py cases``) is applied first, exactly as
the Round 2 local probe did (`m6_support.py`: R = Rw^T Rg, t = Rw^T (tg - tw - c + Rw c)),
and then the guide, caps and wire envelope are tilted together by +/- angle about the
same 26 axes as `evening_20261121/tilt_mission.py` (12 in-plane axes every 15 deg, CAD z).
Body: actual M6 STL, 0.5 mm axial refinement, certified swept crop over every transformed
part, affine rod map of the step's shape, exact FCL distance (Round 2 `m6_full.py`).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import fcl
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2))
sys.path.insert(0, str(HERE.parent / "evening_20261121"))
import m6_full as R  # noqa: E402
from common import CAD, load_motion  # noqa: E402
from tilt_mission import tilts  # noqa: E402

FOLDERS = {0.0: CAD / "m6_bond_gap_20261119", 0.06: CAD / "m6_crowned_land_20261120"}


def relative(row):
    qg, qw = np.array(row["guide_increment_mm_rad"]), np.array(row["web_increment_mm_rad"])
    c = np.array(row["witness_web_centre_mm"])
    Rw = Rotation.from_rotvec(qw[3:]).as_matrix()
    Rg = Rotation.from_rotvec(qg[3:]).as_matrix()
    return Rw.T @ Rg, Rw.T @ (qg[:3] - qw[:3] - c + Rw @ c)


def run(a):
    t0 = time.time()
    rows = json.loads((HERE / "results/bond_cases.json").read_text())["rows"]
    sel = [r for r in rows if r["nh"] == a.nh and r["station_mm"] == a.station
           and r["crown_mm"] in FOLDERS]
    rod, z, _ = load_motion()
    steps = sorted({r["step"] for r in sel})
    details = {s: rod.kinematic_metrics(z[s])[1] for s in steps}
    mesh = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    fine = trimesh.util.concatenate(
        [R.refine_axial(R.patch(mesh.vertices, mesh.faces[i:i + 256]), a.spacing)
         for i in range(0, len(mesh.faces), 256)])
    T = [("none", 0, np.eye(4))] + tilts(a.angle)
    out = []
    for crown, folder in FOLDERS.items():
        parts = R.load_variant(folder, a.station)
        cases = [r for r in sel if r["crown_mm"] == crown]
        specs = {}
        for r in cases:
            Rp, tp = relative(r)
            for k, (name, sign, M) in enumerate(T):
                H = np.eye(4)
                H[:3, :3] = M[:3, :3] @ Rp
                H[:3, 3] = M[:3, :3] @ tp
                specs[(id(r), k)] = H
        for k, (name, sign, M) in enumerate(T):  # ideal-position tilt reference
            specs[("ideal", k)] = M
        moved = {(key, p): m.copy().apply_transform(H)
                 for key, H in specs.items() for p, m in parts.items()}
        crop = dict(parts)
        crop.update({f"{p}_{i}": m for i, ((key, p), m) in enumerate(moved.items())})
        body = R.swept_crop(fine, crop, a.station, rod, [details[s] for s in steps])
        v = np.asarray(body.vertices)
        heights, ix = np.unique(v[:, 2], return_inverse=True)
        for s in steps:
            coef = R.coefficients(heights, a.station, rod, details[s])[ix]
            mapped = coef[:, 0] + v[:, :1] * coef[:, 1] + v[:, 1:2] * coef[:, 2]
            solid = fcl.CollisionObject(R.mesh_model(mapped, body.faces))
            groups = [("ideal position", dict(G_MPa=None, mismatch=None), "ideal")]
            groups += [(f"bond {r['mismatch']} G{r['G_MPa']:.0f}", r, id(r))
                       for r in cases if r["step"] == s]
            for label, r, key in groups:
                gaps = {}
                for k, (name, sign, _) in enumerate(T):
                    g = min(R.gap(solid, fcl.CollisionObject(R.mesh_model(m.vertices, m.faces)))[0]
                            for p in R.PARTS for m in [moved[((key, k), p)]])
                    gaps[name + ("" if sign == 0 else "+" if sign > 0 else "-")] = g
                tilted = {n: g for n, g in gaps.items() if n != "none"}
                worst = min(tilted, key=tilted.get)
                out.append(dict(step=s, station_mm=a.station, crown_mm=crown, case=label,
                                G_MPa=r["G_MPa"], mismatch=r["mismatch"],
                                gap_no_tilt_mm=gaps["none"], min_gap_tilted_mm=tilted[worst],
                                worst_tilt=worst, gaps_mm=gaps))
                print(a.station, crown, s, label, f"{gaps['none']:.5f} {tilted[worst]:.5f} {worst}",
                      flush=True)
    res = dict(script="bond_tilt_probe.py", station_mm=a.station, nh=a.nh, angle_deg=a.angle,
               spacing_mm=a.spacing, rows=out, elapsed_s=round(time.time() - t0, 1))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--station", type=int, required=True)
    p.add_argument("--nh", type=int, default=8)
    p.add_argument("--angle", type=float, default=0.2)
    p.add_argument("--spacing", type=float, default=0.5)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())
