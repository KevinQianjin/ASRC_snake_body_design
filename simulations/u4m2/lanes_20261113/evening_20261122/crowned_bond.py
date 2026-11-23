"""Bonded-support model of the M6 outer sockets with an axially varying (crowned) adhesive layer.

Extends the Round 2 bonded-land model (`extreme_tests/round2_20261119/m6_support.py`)
without changing its structure model, loads or fit mismatch:

* the eight condensed CAD rib plates, the two rigid guide plates and the four bonded
  side-wall pads per seat are reused unchanged (``S.build``);
* each pad keeps two in-plane Gauss points; the axial direction over the 0.5 mm land
  uses ``nh`` Gauss-Legendre points (Round 2 used nh = 2);
* the layer thickness at each point follows the crowned CAD,
  t(z) = t0 + crown * (z / 0.25 mm)^2 (t0 = 0.25 mm; crown 0 = uncrowned candidate);
* both station wrenches and the rod-mapped fit mismatch act simultaneously; the
  incremental disk motion stays fixed, as in Round 2.

The adhesive moduli are assumed (500 / 1,500 MPa shear, nu = 0.35), not measured.
Outputs are written only under this run's ``results/`` folder.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve

HERE = Path(__file__).resolve().parent
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2))
import m6_support as S  # noqa: E402
from common import load_motion, station_wrenches, input_file, read_csv  # noqa: E402
from common import OUT as R2OUT  # noqa: E402
from m6_socket_screen import to_station  # noqa: E402

T0 = 0.25  # mid-land bond gap (mm), both candidates
HALF = 0.25  # half land length (mm)
NU = 0.35
STEPS = (1709, 1710, 1885)


def mismatch(xyz, st, rod, det, mode):
    """Rod-mapped fit mismatch of land points (station frame, mm).

    mode 'rod'      : Round 2 map, the homogenised rod strain is applied inside the land;
    mode 'midplane' : the axial component is taken at the land mid-plane (zh = 0), i.e. the
                      PA12 web is axially inextensible over the 0.5 mm land; transverse
                      components (section rotation, land-to-land incompatibility) are kept.
    mode 'rigidland': the 'rod' field is replaced, land by land, by its least-squares rigid
                      motion (applied by the callers through ``rigid_fit``): each web moves
                      rigidly over its bond footprint, and only land-to-land incompatibility
                      and the station wrenches load the bond.
    """
    xyz = np.atleast_2d(xyz)
    d = to_station(xyz + [0, 0, st], 5, st, rod, det) - xyz
    if mode == "midplane":
        mid = xyz.copy()
        mid[:, 2] = 0.0
        d[:, 2] = (to_station(mid + [0, 0, st], 5, st, rod, det) - mid)[:, 2]
    return d


def rigid_fit(xyz, d):
    """Least-squares rigid-body part of a displacement field (used per land footprint)."""
    M = np.vstack([np.column_stack((np.eye(3), -S.skew(x))) for x in xyz])
    sol = np.linalg.lstsq(M, d.ravel(), rcond=None)[0]
    return (M @ sol).reshape(-1, 3)


def land_groups(blocks):
    groups = {}
    for i, b in enumerate(blocks):
        groups.setdefault((b[0], b[1]), []).append(i)
    return groups.values()


def material_points(angle, radius, nh=2, crown=0.0):
    """Same pads as Round 2; axial Gauss order nh and per-point layer thickness."""
    t = np.radians(angle)
    er = np.array([np.cos(t), np.sin(t), 0])
    et = np.array([-np.sin(t), np.cos(t), 0])
    ez = np.array([0, 0, 1])
    xh, wh = np.polynomial.legendre.leggauss(nh)
    pts = []
    for normal, tangent, a, b in ((er, et, 1.335, 1.5), (et, er, 1.5, 1.335)):
        for side in (-1, 1):
            for u in (-1, 1):
                for x, w in zip(xh, wh):
                    zh = x * HALF
                    rel = side * a * normal + u * b / np.sqrt(3) * tangent + zh * ez
                    area = b * (HALF * w)  # (2b/2 in-plane) x (0.5*w/2 axial)
                    thick = T0 + crown * (zh / HALF) ** 2
                    pts.append(
                        dict(centre=radius * er, rel=rel, normal=side * normal,
                             area=area, thick=thick, zh=zh)
                    )
    return pts


def interfaces(K, maps, G, nh, crown):
    blocks = []
    total = K.copy()
    for (theta, st), (web, guide, r) in maps.items():
        if theta not in S.MOUNT:
            continue
        for p in material_points(theta, r, nh, crown):
            B = np.zeros((3, len(K)))
            B[:, guide] = S.arm(p["centre"] + p["rel"])
            B[:, web] = -S.arm(p["rel"])
            D = p["area"] / p["thick"] * G * (
                np.eye(3) + (2 * (1 + NU) - 1) * np.outer(p["normal"], p["normal"])
            )
            total += B.T @ D @ B
            blocks.append((theta, st, p, B, D))
    return total, blocks


def components(stress, normal):
    ez = np.array([0.0, 0.0, 1.0])
    return dict(
        normal=stress @ normal,
        axial_shear=stress @ ez,
        cross_shear=stress @ np.cross(normal, ez),
    )


def cases(out, nh_list, crowns, moduli, modes=("rod",)):
    rod, z, _ = load_motion()
    K, maps, _ = S.build(0.09)
    free = np.arange(12, len(K))
    loads = {st: station_wrenches("M6", st) for st in S.STATIONS}
    full = read_csv(input_file(R2OUT, "m6_guides", "m6_all_steps.csv.gz"))
    witness = {(int(r["step"]), int(r["station_mm"])): r for r in full}
    rows = []
    for step in STEPS:
        det = rod.kinematic_metrics(z[step])[1]
        for nh, crown, G, mode in [(a, b, c, d) for a in nh_list for b in crowns
                                   for c in moduli for d in modes]:
                if True:  # one solve per (nh, crown, G, mismatch) combination
                    A, blocks = interfaces(K, maps, G, nh, crown)
                    F = np.zeros(len(K))
                    for j, st in enumerate(S.STATIONS):
                        F[36 + 6 * j: 42 + 6 * j] = loads[st][step]
                    mism = []
                    for theta, st, p, B, D in blocks:
                        xyz = p["centre"] + p["rel"]
                        mism.append(mismatch(xyz, st, rod, det, mode)[0])
                    if mode == "rigidland":
                        for ids in land_groups(blocks):
                            X = np.array([blocks[i][2]["centre"] + blocks[i][2]["rel"] for i in ids])
                            fit = rigid_fit(X, np.array([mism[i] for i in ids]))
                            for i, v in zip(ids, fit):
                                mism[i] = v
                    for i, (theta, st, p, B, D) in enumerate(blocks):
                        F += B.T @ D @ mism[i]
                    q = np.zeros(len(K))
                    q[free] = solve(A[np.ix_(free, free)], F[free], assume_a="sym")
                    lands, bal = {}, {st: np.zeros(6) for st in S.STATIONS}
                    for (theta, st, p, B, D), delta in zip(blocks, mism):
                        f = D @ (B @ q - delta)
                        s = components(f / p["area"], p["normal"])
                        L = lands.setdefault((theta, st), dict(w=np.zeros(6), pts=[]))
                        L["w"][:3] += f
                        L["w"][3:] += np.cross(p["rel"], f)
                        L["pts"].append((p, s, f))
                        bal[st] += np.r_[f, np.cross(p["centre"] + p["rel"], f)]
                    for j, st in enumerate(S.STATIONS):
                        err = float(np.linalg.norm(bal[st] - loads[st][step]))
                        if err > 2e-5:
                            raise ValueError(f"land reaction closure {err}")
                        sl = slice(36 + 6 * j, 42 + 6 * j)
                        w = witness[step, st]
                        ref = np.array([float(w["guide_" + a + "_mm"]) for a in "xyz"])
                        nrm = np.array([float(w["toward_web_" + a]) for a in "xyz"])
                        theta = min(S.ANGLES, key=lambda th: abs(
                            (th - np.degrees(np.arctan2(ref[1], ref[0])) + 180) % 360 - 180))
                        web, _, r = maps[theta, st]
                        centre = material_points(theta, r)[0]["centre"]
                        gd = S.rigid(ref, q[sl]) - ref
                        wd = S.rigid(ref - centre, q[web]) - (ref - centre)
                        rel = gd - wd
                        rot = np.degrees(np.linalg.norm(q[sl][3:] - q[web][3:]))
                        allpts = [x for (th, s2), L in lands.items() if s2 == st for x in L["pts"]]
                        area = sum(p["area"] for p, _, _ in allpts)
                        peak = {k: float(max(abs(s[k]) for _, s, _ in allpts))
                                for k in ("normal", "axial_shear", "cross_shear")}
                        mean = {k: float(sum(abs(s[k]) * p["area"] for p, s, _ in allpts) / area)
                                for k in ("normal", "axial_shear", "cross_shear")}
                        land_f = {f"{int(th * 10)}": float(np.linalg.norm(L["w"][:3]))
                                  for (th, s2), L in lands.items() if s2 == st}
                        land_m = {f"{int(th * 10)}": float(np.linalg.norm(L["w"][3:]))
                                  for (th, s2), L in lands.items() if s2 == st}
                        rows.append(dict(
                            step=step, station_mm=st, nh=nh, crown_mm=crown, G_MPa=G, mismatch=mode,
                            mean_layer_mm=float(sum(p["thick"] * p["area"] for p, _, _ in allpts) / area),
                            witness_rib_deg=float(theta),
                            witness_relative_motion_mm=float(np.linalg.norm(rel)),
                            witness_normal_closure_mm=float(rel @ nrm),
                            guide_minus_web_rotation_deg=rot,
                            peak_abs_traction_MPa=peak,
                            area_mean_abs_traction_MPa=mean,
                            land_force_N_by_rib_deg_x10=land_f,
                            land_moment_Nmm_by_rib_deg_x10=land_m,
                            land_wrench_closure_residual=err,
                            guide_increment_mm_rad=q[sl].tolist(),
                            web_increment_mm_rad=q[web].tolist(),
                            witness_web_centre_mm=centre.tolist(),
                        ))
        print("cases step", step, "done", flush=True)
    return rows


def duty(nh, crown, G, every=1, mode="rod"):
    """Mission envelope of pad tractions (Round 2 `duty.bond_duty`, generalised)."""
    rod, z, _ = load_motion()
    steps = np.arange(0, len(z), every)
    hist = [rod.kinematic_metrics(z[i])[1] for i in steps]
    K, maps, _ = S.build(0.09)
    A, blocks = interfaces(K, maps, G, nh, crown)
    n, m = len(steps), len(blocks)
    F = np.zeros((n, len(K)))
    for j, st in enumerate(S.STATIONS):
        F[:, 36 + 6 * j: 42 + 6 * j] = station_wrenches("M6", st)[steps]
    deltas = np.zeros((n, m, 3))
    for st in S.STATIONS:
        ids = [i for i, v in enumerate(blocks) if v[1] == st]
        xyz = np.array([blocks[i][2]["centre"] + blocks[i][2]["rel"] for i in ids])
        for j, d in enumerate(hist):
            deltas[j, ids] = mismatch(xyz, st, rod, d, mode)
    if mode == "rigidland":
        for ids in land_groups(blocks):
            X = np.array([blocks[i][2]["centre"] + blocks[i][2]["rel"] for i in ids])
            M = np.vstack([np.column_stack((np.eye(3), -S.skew(x))) for x in X])
            P = M @ np.linalg.pinv(M)  # projector onto rigid fields of this land
            for j in range(n):
                deltas[j, ids] = (P @ deltas[j, ids].ravel()).reshape(-1, 3)
    B = np.array([v[3] for v in blocks])
    D = np.array([v[4] for v in blocks])
    F += np.einsum("gak,gab,sgb->sk", B, D, deltas, optimize=True)
    q = np.zeros_like(F)
    q[:, 12:] = cho_solve(cho_factor(A[12:, 12:]), F[:, 12:].T).T
    slip = np.einsum("gak,sk->sga", B, q, optimize=True) - deltas
    res = {}
    for k in ("normal", "axial_shear", "cross_shear"):
        res[k] = dict(max=-np.inf, min=np.inf)
    ez = np.array([0.0, 0.0, 1.0])
    env = []
    for i, (theta, st, p, _, d) in enumerate(blocks):
        stress = slip[:, i] @ d.T / p["area"]
        for k, along in (("normal", p["normal"]), ("axial_shear", ez),
                         ("cross_shear", np.cross(p["normal"], ez))):
            v = stress @ along
            for fn, key in ((np.argmax, "max"), (np.argmin, "min")):
                j = fn(v)
                better = v[j] > res[k]["max"] if key == "max" else v[j] < res[k]["min"]
                if better:
                    res[k][key] = float(v[j])
                    res[k][key + "_site"] = dict(step=int(steps[j]), station_mm=st,
                                                 rib_deg=float(theta), zh_mm=float(p["zh"]),
                                                 thick_mm=float(p["thick"]))
            env.append((k, float(np.ptp(v))))
    for k in res:
        res[k]["largest_point_range"] = max(r for kk, r in env if kk == k)
    return dict(nh=nh, crown_mm=crown, G_MPa=G, mismatch=mode, steps=int(n), every=every,
                envelope=res)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("cases", "duty"))
    p.add_argument("--nh", type=int, nargs="+", default=[2, 4, 8])
    p.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    p.add_argument("--G", type=float, nargs="+", default=[500.0, 1500.0])
    p.add_argument("--every", type=int, default=1)
    p.add_argument("--mismatch", nargs="+", default=["rod", "midplane", "rigidland"], choices=("rod", "midplane", "rigidland"))
    p.add_argument("--out", type=Path, default=HERE / "results")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.mode == "cases":
        rows = cases(a.out, a.nh, a.crown, a.G, a.mismatch)
        data = dict(rows=rows)
        name = "bond_cases.json"
    else:
        data = dict(runs=[duty(nh, c, G, a.every, m) for nh in a.nh for c in a.crown
                          for G in a.G for m in a.mismatch])
        name = f"bond_duty_nh{'-'.join(map(str, a.nh))}.json"
    data["elapsed_s"] = time.time() - t0
    (a.out / name).write_text(json.dumps(data, indent=1))
    print("wrote", a.out / name, f"{data['elapsed_s']:.0f} s", flush=True)


if __name__ == "__main__":
    main()
