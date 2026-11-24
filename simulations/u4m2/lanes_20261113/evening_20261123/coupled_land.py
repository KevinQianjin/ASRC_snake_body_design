"""Coupled local model of one M6 guide station: four solid CAD struts, a distributed crowned
adhesive layer and one rigid guide.

Second stage of handoff item 2 (22 November 2026 evening run). ``solid_bond.py`` showed that the
free strut (no guide) deforms MORE over the 0.5 mm land than the homogenised rod map. That
free-web field neglects the stiffening of the strut by the bonded guide. Here the guide is coupled:

* each of the four bonded struts (67.5, 157.5, 247.5, 337.5 deg) is the actual CAD strut, cropped
  between its nodes, meshed with graded P2 tetrahedra (fine in the land band) and driven at its
  two cut faces by the homogenised rod map, exactly as in ``solid_bond.py``;
* the adhesive is a distributed elastic layer on the actual inclined CAD side walls inside the
  land band |z - station| <= 0.25 mm: tangential stiffness G/t(z), normal stiffness
  2(1+nu)G/t(z), with the crowned thickness t(z) = 0.25 + crown (zh/0.25)^2 mm;
* one rigid guide per station is bonded to all four lands and carries the archived station
  wrench, as in the Round 2 / 22 November bond model.

The guide, the four struts and the layer are solved together (linear, small displacement).
G is ASSUMED (500 or 1,500 MPa); PA12 E = 1,530 MPa, nu = 0.4.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261122"))
import crowned_bond as CB  # noqa: E402
import strut_fe as FE  # noqa: E402
from solid_bond import CUTS, BODY  # noqa: E402

NU_ADH = 0.35
HALF = 0.25


def prism_mesh(solid, st, h_sec, dz_band, growth=1.3, h_max=0.6, band=0.6):
    """Structured graded mesh of the straight CAD strut prism.

    The cropped strut is an exact prism (a convex 10-vertex section translated along the strut
    axis). Its bottom cap polygon is triangulated (Triangle, max edge ~h_sec) and extruded
    through z layers that are dz_band thick within |z-st| < band and grow geometrically
    (factor ``growth``, capped at h_max) towards both cut faces. Each prism is split into
    three tetrahedra with the minimum-index diagonal rule, so the mesh is conforming.
    """
    import triangle
    z_lo, z_hi = solid.bounds[:, 2]
    v = solid.vertices
    bot, top = v[np.abs(v[:, 2] - z_lo) < 1e-6], v[np.abs(v[:, 2] - z_hi) < 1e-6]
    def centroid(zz):
        sec = solid.section(plane_origin=[0, 0, zz], plane_normal=[0, 0, 1])
        pth, T = sec.to_2D()
        return trimesh.transform_points([[*pth.polygons_full[0].centroid.coords[0], 0]], T)[0][:2]

    za, zb = z_lo + 0.5, z_hi - 0.5
    shift = (centroid(zb) - centroid(za)) / (zb - za)  # section drift per mm z (area centroids)
    c = bot[:, :2].mean(0)
    order = np.argsort(np.arctan2(*(bot[:, :2] - c).T[::-1]))
    poly = bot[order, :2]
    keep = np.r_[True, np.linalg.norm(np.diff(poly, axis=0), axis=1) > 1e-6]
    poly = poly[keep]
    n = len(poly)
    tri = triangle.triangulate(dict(vertices=poly, segments=np.c_[np.arange(n), (np.arange(n) + 1) % n]),
                               f"pq30a{0.433 * h_sec ** 2:.6f}Q")
    P2d, T2d = tri["vertices"], tri["triangles"]
    # graded z levels
    lo_b, hi_b = max(z_lo, st - band), min(z_hi, st + band)
    zs = list(np.linspace(lo_b, hi_b, int(np.ceil((hi_b - lo_b) / dz_band)) + 1))
    for direction, end in ((-1, z_lo), (1, z_hi)):
        z, dz = (zs[0] if direction < 0 else zs[-1]), dz_band
        while True:
            dz = min(dz * growth, h_max)
            z = z + direction * dz
            if (direction < 0 and z <= end + 0.3 * dz) or (direction > 0 and z >= end - 0.3 * dz):
                zs.append(end) if direction > 0 else zs.insert(0, end)
                break
            zs.append(z) if direction > 0 else zs.insert(0, z)
    zs = np.array(zs)
    m = len(P2d)
    nodes = np.vstack([np.c_[P2d + (zz - z_lo) * shift, np.full(m, zz)] for zz in zs])
    tets = []
    T = np.sort(T2d, axis=1)
    for k in range(len(zs) - 1):
        a0, b0, c0 = (T + k * m).T
        a1, b1, c1 = (T + (k + 1) * m).T
        tets += [np.c_[a0, b0, c0, c1], np.c_[a0, b0, b1, c1], np.c_[a0, a1, b1, c1]]
    tets = np.vstack(tets)
    _, vol = FE.bary_grad(nodes[tets])
    neg = vol < 0
    tets[neg] = tets[neg][:, [0, 2, 1, 3]]
    return nodes, tets


def land_samples(solid, st, max_edge):
    """Quadrature points on the bonded CAD side walls inside the land band (area-weighted)."""
    s = trimesh.intersections.slice_mesh_plane(solid, [0, 0, 1], [0, 0, st - HALF], cap=False)
    s = trimesh.intersections.slice_mesh_plane(s, [0, 0, -1], [0, 0, st + HALF], cap=False)
    v, f = trimesh.remesh.subdivide_to_size(s.vertices, s.faces, max_edge=max_edge)
    m = trimesh.Trimesh(v, f, process=False)
    keep = np.abs(m.face_normals[:, 2]) < 0.95  # side walls only (no end faces in the band)
    return m.triangles_center[keep], m.area_faces[keep], m.face_normals[keep]


def arm(x):
    return np.column_stack((np.eye(3), -CB.S.skew(x)))


class StrutLand:
    def __init__(self, module, theta, st, h_sec, dz_band, max_edge):
        self.theta, self.st = theta, st
        self.solid = FE.crop_strut(module, theta, *CUTS[st])
        v, t = prism_mesh(self.solid, st, h_sec, dz_band)
        self.X, self.conn = FE.p2(v, t)
        self.K, self.volume = FE.stiffness(self.X, self.conn)
        z = self.X[:, 2]
        b = np.flatnonzero((np.abs(z - CUTS[st][0]) < 1e-6) | (np.abs(z - CUTS[st][1]) < 1e-6))
        self.bnodes = b
        self.bd = (3 * b[:, None] + np.arange(3)).ravel()
        self.fd = np.setdiff1d(np.arange(3 * len(self.X)), self.bd)
        self.xs, self.ws, self.ns = land_samples(self.solid, st, max_edge)
        self.M, self.min_bary = FE.locate(self.X, self.conn, self.xs, k_near=400)
        self.n_tets = len(self.conn)

    def layer(self, G, crown):
        zh = self.xs[:, 2] - self.st
        t = 0.25 + crown * (zh / HALF) ** 2
        k = (self.ws / t * G)[:, None, None]
        D = k * (np.eye(3) + (2 * (1 + NU_ADH) - 1) * np.einsum("ni,nj->nij", self.ns, self.ns))
        return D, t

    def factor(self, G, crown):
        D, t = self.layer(G, crown)
        Dbig = sp.block_diag(list(D), format="csr")
        Ms = self.M
        Kl = (Ms.T @ Dbig @ Ms).tocsc()
        A = np.vstack([arm(x - [0, 0, self.st]) for x in self.xs])  # guide motion at samples (station frame)
        Kaug = (self.K + Kl).tocsc()
        fd, bd = self.fd, self.bd
        lu = spl.splu(Kaug[fd][:, fd].tocsc(), permc_spec="MMD_AT_PLUS_A")
        Kfq = -(Ms[:, fd].T @ Dbig @ A)  # (nf, 6)
        Bq = -lu.solve(np.asarray(Kfq))  # u_f = a + Bq q
        self._c = dict(D=D, Dbig=Dbig, A=A, lu=lu, Kfb=Kaug[fd][:, bd], Kfq=np.asarray(Kfq),
                       Bq=Bq, Kqq=A.T @ Dbig @ A, t=t)

    def condensed(self, ub):
        c = self._c
        a = -c["lu"].solve(c["Kfb"] @ ub)
        # guide eqn contribution: Kqq q + Kfq^T u_f
        Kg = c["Kqq"] + c["Kfq"].T @ c["Bq"]
        rg = -(c["Kfq"].T @ a)
        return Kg, rg, a

    def tractions(self, ub, a, q):
        c = self._c
        u = np.zeros(3 * len(self.X))
        u[self.bd] = ub
        u[self.fd] = a + c["Bq"] @ q
        us = (self.M @ u).reshape(-1, 3)
        slip = (c["A"] @ q).reshape(-1, 3) - us
        f = np.einsum("nij,nj->ni", c["D"], slip)
        tr = f / self.ws[:, None]
        ez = np.array([0, 0, 1.0])
        normal = np.einsum("ni,ni->n", tr, self.ns)
        ax_dir = ez - self.ns * self.ns[:, 2:3]
        ax_dir /= np.linalg.norm(ax_dir, axis=1, keepdims=True)
        axial = np.einsum("ni,ni->n", tr, ax_dir)
        cross = np.einsum("ni,ni->n", tr, np.cross(self.ns, ax_dir))
        return dict(f=f, normal=normal, axial=axial, cross=cross, slip=slip)


def solve_station(lands, st, rod, det, W):
    Kg = np.zeros((6, 6))
    rg = W.copy()
    parts = []
    for L in lands:
        P = L.X[L.bnodes]
        ub = (CB.to_station(P, 5, st, rod, det) - (P - [0, 0, st])).ravel()
        k, r, a = L.condensed(ub)
        Kg += k
        rg += r
        parts.append((L, ub, a))
    q = np.linalg.solve(Kg, rg)
    out, bal = [], np.zeros(6)
    for L, ub, a in parts:
        T = L.tractions(ub, a, q)
        x = L.xs - [0, 0, st]
        bal += np.r_[T["f"].sum(0), np.cross(x, T["f"]).sum(0)]
        out.append((L, T))
    return q, out, bal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mesh", nargs="+", default=["0.5:0.1", "0.35:0.06", "0.25:0.04"],
                   help="section edge h_sec : axial layer dz_band in the land band (mm)")
    p.add_argument("--max-edge", type=float, default=0.04)
    p.add_argument("--stations", type=int, nargs="+", default=[-12, 12])
    p.add_argument("--steps", type=int, nargs="+", default=list(CB.STEPS))
    p.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    p.add_argument("--G", type=float, nargs="+", default=[500.0, 1500.0])
    p.add_argument("--out", type=Path, default=HERE / "results")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rod, z, _ = CB.load_motion()
    module = trimesh.load_mesh(BODY)
    dets = {s: rod.kinematic_metrics(z[s])[1] for s in a.steps}
    rows = []
    t0 = time.time()
    for spec in a.mesh:
        hs, hb = map(float, spec.split(":"))
        for st in a.stations:
            lands = []
            for th in CB.S.MOUNT:
                t1 = time.time()
                L = StrutLand(module, th, st, hs, hb, a.max_edge)
                lands.append(L)
                print(f"mesh {hs}:{hb} strut {th}@{st}: {L.n_tets} tets, {3 * len(L.X)} dof, "
                      f"{len(L.xs)} layer pts, band area {L.ws.sum():.3f} mm2, "
                      f"min bary {L.min_bary:.3f}, {time.time() - t1:.1f} s", flush=True)
            W = CB.station_wrenches("M6", st)
            for crown in a.crown:
                for G in a.G:
                    for L in lands:
                        L.factor(G, crown)
                    for step in a.steps:
                        q, out, bal = solve_station(lands, st, rod, dets[step], W[step])
                        err = float(np.linalg.norm(bal - W[step]))
                        row = dict(h_sec_mm=hs, dz_band_mm=hb, station_mm=st, crown_mm=crown, G_MPa=G,
                                   step=step, guide_q=q.tolist(), wrench_closure=err, lands={})
                        for L, T in out:
                            area = L.ws
                            row["lands"][f"{L.theta}"] = dict(
                                n_tets=L.n_tets, band_area_mm2=float(area.sum()),
                                peak_abs_MPa={k: float(np.abs(T[k]).max()) for k in ("normal", "axial", "cross")},
                                mean_abs_MPa={k: float((np.abs(T[k]) * area).sum() / area.sum())
                                              for k in ("normal", "axial", "cross")},
                                peak_site_zh_mm=float(L.xs[np.argmax(np.abs(T["axial"])), 2] - st),
                                force_N=T["f"].sum(0).tolist(),
                                max_slip_mm=float(np.linalg.norm(T["slip"], axis=1).max()))
                        rows.append(row)
                        pk = max(v["peak_abs_MPa"]["axial"] for v in row["lands"].values())
                        pn = max(v["peak_abs_MPa"]["normal"] for v in row["lands"].values())
                        print(f"  mesh {hs}:{hb} st {st} crown {crown} G {G} step {step}: peak axial {pk:.2f}"
                              f" normal {pn:.2f} MPa, closure {err:.1e}", flush=True)
            del lands
            (a.out / "coupled_land.json").write_text(json.dumps(dict(rows=rows, elapsed_s=time.time() - t0), indent=1))
    print("done", time.time() - t0, flush=True)


if __name__ == "__main__":
    main()
