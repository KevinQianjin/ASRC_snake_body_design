"""Bond tractions of the crowned M6 lands with the fit mismatch taken from a local solid strut model.

Adds a fourth mismatch model, ``solid``, to the 22 November bonded-land model
(``../evening_20261122/crowned_bond.py``): the displacement of every bond point is the
P2-tetrahedron solution of its own CAD strut (``strut_fe.py``), driven at the two strut cut
faces by the same homogenised rod map. Everything else (rib plates, guide plates, pads,
crowned layer, station wrenches, assumed adhesive moduli) is unchanged.

Sub-commands
  convergence : mesh / cut-plane study of the bond-point field at the governing steps
  cases       : crowned_bond ``cases`` with mismatch rod, rigidland, solid
  duty        : crowned_bond mission envelope with mismatch solid
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261122"))
import crowned_bond as CB  # noqa: E402
import strut_fe as FE  # noqa: E402

BODY = CB.S.BODY
CUTS = {-12: (-16.5, -6.75), 12: (6.75, 16.5)}  # isolated strut span (CAD sections)
SHORT_CUTS = {-12: (-15.75, -7.5), 12: (7.5, 15.75)}
STEPS = CB.STEPS
_original_mismatch = CB.mismatch


def strut_axis(module, angle, st):
    """CAD strut centre radius and radial slope dr/dz at the station (from two sections)."""
    out = []
    want = np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
    for z in (st - 0.5, st + 0.5):
        s = module.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        p, T = s.to_2D()
        cs = [trimesh.transform_points([[*P.centroid.coords[0], 0]], T)[0][:2] for P in p.polygons_full]
        c = max(cs, key=lambda c: c @ want / np.linalg.norm(c))
        out.append(np.linalg.norm(c))
    return 0.5 * (out[0] + out[1]), out[1] - out[0]


def land_points(theta, r_map, nh):
    """Round 2 / 22 Nov pad points of one land (station frame), crown-independent positions."""
    return np.array([p["centre"] + p["rel"] for p in CB.material_points(theta, r_map, nh, 0.0)])


class SolidField:
    """Per-land strut models and the patched ``mismatch`` used by crowned_bond."""

    def __init__(self, h, nh_list, cuts=CUTS, lands=None):
        module = trimesh.load_mesh(BODY)
        _, maps, _ = CB.S.build(0.09)
        self.lands = {}
        self.cuts = cuts
        for (theta, st), (_, _, r_map) in maps.items():
            if theta not in CB.S.MOUNT or (lands and (theta, st) not in lands):
                continue
            r_cad, slope = strut_axis(module, theta, st)
            er = np.array([np.cos(np.radians(theta)), np.sin(np.radians(theta)), 0])
            pts = np.vstack([land_points(theta, r_map, nh) for nh in nh_list])
            # Evaluate on the actual inclined strut wall: shift each pad radially to the CAD
            # strut centre at its own height (map radius -> CAD radius, plus slope * zh).
            body = pts + [0, 0, st] + np.outer((r_cad - r_map) + slope * pts[:, 2], er)
            t0 = time.time()
            strut = FE.Strut(module, theta, *cuts[st], h, body)
            self.lands[theta, st] = dict(
                strut=strut, pts=pts, tree=cKDTree(pts), r_cad=r_cad, slope=slope,
                r_map=r_map, build_s=time.time() - t0)
            print(f"strut {theta} @ {st}: {strut.n_tets} tets, {strut.max_dofs} dof, "
                  f"min bary {strut.locate_min_bary:.3f}, {time.time() - t0:.1f} s", flush=True)
        self._cache = {}

    def boundary_disp(self, key, rod, det):
        L = self.lands[key]
        cache_key = (key, id(det))
        if cache_key not in self._cache:
            st = key[1]
            P = L["strut"].boundary_points()
            self._cache = {k: v for k, v in self._cache.items() if k[1] == id(det)}
            self._cache[cache_key] = (CB.to_station(P, 5, st, rod, det) - (P - [0, 0, st])).ravel()
        return self._cache[cache_key]

    def field(self, key, rod, det):
        L = self.lands[key]
        return (L["strut"].H @ self.boundary_disp(key, rod, det)).reshape(-1, 3)

    def mismatch(self, xyz, st, rod, det, mode):
        if mode != "solid":
            return _original_mismatch(xyz, st, rod, det, mode)
        xyz = np.atleast_2d(xyz)
        out = np.empty_like(xyz)
        ang = np.degrees(np.arctan2(xyz[:, 1], xyz[:, 0])) % 360
        for theta in CB.S.MOUNT:
            sel = np.abs((ang - theta + 180) % 360 - 180) < 22.5
            if not sel.any():
                continue
            key = (theta, st)
            d, idx = self.lands[key]["tree"].query(xyz[sel])
            if d.max() > 1e-9:
                raise ValueError("bond point not in the precomputed land set")
            out[sel] = self.field(key, rod, det)[idx]
        return out


def residual(X, d):
    return d - CB.rigid_fit(X, d)


def convergence(out, hs):
    rod, z, _ = CB.load_motion()
    rows = []
    variants = [(h, "full", CUTS) for h in hs] + [(hs[1], "short", SHORT_CUTS)]
    for h, label, cuts in variants:
        F = SolidField(h, [8], cuts)
        for step in STEPS:
            det = rod.kinematic_metrics(z[step])[1]
            for key, L in F.lands.items():
                X = L["pts"]
                d_rod = _original_mismatch(X, key[1], rod, det, "rod")
                d_sol = F.field(key, rod, det)
                zh = X[:, 2]
                row = dict(h_mm=h, cuts=label, cut_z_mm=list(cuts[key[1]]), step=step,
                           rib_deg=float(key[0]), station_mm=key[1],
                           n_tets=L["strut"].n_tets, dof=L["strut"].max_dofs,
                           r_cad_mm=L["r_cad"], r_map_mm=L["r_map"], dr_dz=L["slope"])
                for name, d in (("rod", d_rod), ("solid", d_sol)):
                    res = residual(X, d)
                    # Axial strain over the land: slope of u_z with zh, least squares over all pads.
                    eps = np.polyfit(zh, d[:, 2] - CB.rigid_fit(X, d)[:, 2], 1)[0]
                    row[name] = dict(
                        max_abs_mismatch_mm=float(np.abs(d).max()),
                        max_nonrigid_mm=float(np.linalg.norm(res, axis=1).max()),
                        rms_nonrigid_mm=float(np.sqrt((res ** 2).sum(1).mean())),
                        axial_strain_over_land=float(eps),
                    )
                row["solid_minus_rod_rms_mm"] = float(np.sqrt(((d_sol - d_rod) ** 2).sum(1).mean()))
                rows.append(row)
            print("convergence", h, label, step, flush=True)
    (out / "solid_convergence.json").write_text(json.dumps(dict(rows=rows), indent=1))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("convergence", "cases", "duty"))
    p.add_argument("--h", type=float, nargs="+", default=[0.8, 0.6, 0.45])
    p.add_argument("--nh", type=int, nargs="+", default=[2, 8])
    p.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    p.add_argument("--G", type=float, nargs="+", default=[500.0, 1500.0])
    p.add_argument("--mismatch", nargs="+", default=["rod", "rigidland", "solid"])
    p.add_argument("--every", type=int, default=1)
    p.add_argument("--out", type=Path, default=HERE / "results")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.mode == "convergence":
        convergence(a.out, a.h)
        print("wrote convergence", f"{time.time() - t0:.0f} s")
        return
    F = SolidField(a.h[0], a.nh)
    CB.mismatch = F.mismatch
    meta = dict(h_mm=a.h[0], cuts={str(k): v for k, v in CUTS.items()},
                strut_tets={f"{k[0]}@{k[1]}": v["strut"].n_tets for k, v in F.lands.items()})
    if a.mode == "cases":
        data = dict(meta=meta, rows=CB.cases(a.out, a.nh, a.crown, a.G, a.mismatch))
        name = "solid_bond_cases.json"
    else:
        data = dict(meta=meta, runs=[CB.duty(nh, c, G, a.every, m) for nh in a.nh for c in a.crown
                                     for G in a.G for m in a.mismatch])
        name = f"solid_bond_duty_nh{'-'.join(map(str, a.nh))}_every{a.every}.json"
    data["elapsed_s"] = time.time() - t0
    (a.out / name).write_text(json.dumps(data, indent=1))
    print("wrote", a.out / name, f"{data['elapsed_s']:.0f} s", flush=True)


if __name__ == "__main__":
    main()
