"""Checks for the 23 November 2026 evening study. Writes results/validation.json.

1. P2 patch test on both meshers (TetGen strut, structured prism strut): uniaxial stress along
   the strut axis plus a rigid motion must be reproduced at interior and interpolated points.
2. Regression: the `rod` and `rigidland` rows of solid_bond_cases.json must equal the archived
   22 November bond_cases.json rows.
3. Mesh convergence of the free-strut (solid) bond-point field, h = 0.6 vs 0.45 mm.
4. Coupled over-constrained case: station wrench closure.
5. Boundary-condition consistency (expected to FAIL; it is the finding): moment carried by the
   eight rigid-ring-driven solid struts vs the rod model's own cell moment.
"""

import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse.linalg as spl
import trimesh

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
sys.path.insert(0, str(HERE))
import strut_fe as FE  # noqa: E402

CAD = HERE.parents[3] / "cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl"


def patch(X, conn, cuts, axis):
    K, _ = FE.stiffness(X, conn)
    z = X[:, 2]
    b = np.flatnonzero((np.abs(z - cuts[0]) < 1e-6) | (np.abs(z - cuts[1]) < 1e-6))
    bd = (3 * b[:, None] + np.arange(3)).ravel()
    fd = np.setdiff1d(np.arange(3 * len(X)), bd)
    eps = (np.outer(axis, axis) - FE.NU_PA12 * (np.eye(3) - np.outer(axis, axis))) / FE.E_PA12
    W = np.array([[0, -1, 2], [1, 0, -3], [-2, 3, 0]]) * 1e-4
    ex = (X @ (eps + W).T + [1e-2, -2e-2, 3e-3]).ravel()
    u = ex.copy()
    u[fd] = spl.spsolve(K[fd][:, fd].tocsc(), -K[fd][:, bd] @ ex[bd])
    return float(np.abs(u - ex).max() / np.abs(ex).max())


def main():
    checks = {}
    module = trimesh.load_mesh(CAD)
    cuts = (-16.5, -6.75)
    solid = FE.crop_strut(module, 247.5, *cuts)
    def centroid(zz):
        sec = solid.section(plane_origin=[0, 0, zz], plane_normal=[0, 0, 1])
        pth, T = sec.to_2D()
        return trimesh.transform_points([[*pth.polygons_full[0].centroid.coords[0], 0]], T)[0]

    a = centroid(cuts[1] - 0.5) - centroid(cuts[0] + 0.5)  # strut axis from section area centroids
    a /= np.linalg.norm(a)
    from coupled_land import prism_mesh

    nodes, tets = prism_mesh(solid, -12, 0.5, 0.1)
    X, conn = FE.p2(nodes, tets)
    e_prism = patch(X, conn, cuts, a)
    nodes, tets = FE.mesh(solid, 0.8)
    X, conn = FE.p2(nodes, tets)
    e_tet = patch(X, conn, cuts, a)
    checks["patch_test"] = dict(prism_rel_err=e_prism, tetgen_rel_err=e_tet,
                                
                                passed=bool(e_prism < 1e-4 and e_tet < 1e-4))

    old = json.loads((HERE.parent / "evening_20261122/results/bond_cases.json").read_text())["rows"]
    new = json.loads((RES / "solid_bond_cases.json").read_text())["rows"]
    key = lambda r: (r["step"], r["station_mm"], r["nh"], r["crown_mm"], r["G_MPa"], r["mismatch"])  # noqa: E731
    A = {key(r): r for r in old}
    diffs = [abs(r["peak_abs_traction_MPa"][c] - A[key(r)]["peak_abs_traction_MPa"][c])
             for r in new if key(r) in A for c in r["peak_abs_traction_MPa"]]
    checks["regression_22nov"] = dict(rows=len(diffs) // 3, max_abs_diff_MPa=max(diffs),
                                      passed=bool(len(diffs) >= 48 * 3 and max(diffs) < 1e-9))

    conv = json.loads((RES / "solid_convergence.json").read_text())["rows"]
    idx = {(r["h_mm"], r["cuts"], r["step"], r["rib_deg"], r["station_mm"]): r for r in conv}
    rel = []
    for (h, c, s, th, st), r in idx.items():
        if h == 0.6 and c == "full":
            f = idx[0.45, "full", s, th, st]
            rel.append(abs(r["solid"]["max_nonrigid_mm"] - f["solid"]["max_nonrigid_mm"])
                       / f["solid"]["max_nonrigid_mm"])
    short = [abs(r["solid"]["max_nonrigid_mm"] - idx[0.6, "full", r["step"], r["rib_deg"], r["station_mm"]]["solid"]["max_nonrigid_mm"])
             / idx[0.6, "full", r["step"], r["rib_deg"], r["station_mm"]]["solid"]["max_nonrigid_mm"]
             for r in conv if r["cuts"] == "short"]
    checks["free_strut_convergence"] = dict(max_rel_change_h06_vs_h045=max(rel),
                                            max_rel_change_short_cut=max(short),
                                            passed=bool(max(rel) < 0.01))

    cp = json.loads((RES / "overconstrained_rigid_ring/coupled_land_step1709_zm12_crown006_G500.json").read_text())
    clos = max(r["wrench_closure"] for r in cp["rows"])
    checks["coupled_wrench_closure"] = dict(max=clos, passed=bool(clos < 1e-6))

    cm = json.loads((RES / "cell_moment.json").read_text())["rows"]
    ratio = [r["solid_bending_moment_Nmm"] / r["rod_bending_moment_Nmm"] for r in cm]
    checks["bc_consistency_cell_moment"] = dict(
        solid_over_rod_moment=ratio, min_ratio=min(ratio),
        passed=bool(max(ratio) < 2.0),
        note="Expected to fail: rigid-ring rod-map driving over-constrains the struts.")
    (RES / "validation.json").write_text(json.dumps(checks, indent=1))
    for k, v in checks.items():
        print(k, "PASS" if v["passed"] else "FAIL", {a: b for a, b in v.items() if a != "passed"})


if __name__ == "__main__":
    main()
