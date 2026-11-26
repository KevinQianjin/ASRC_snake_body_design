"""Whole-body solid M6 module with both rigid guides bonded through the distributed crowned
adhesive layer — evening, 24 November 2026 (stage 2 of handoff item 1, 23 Nov evening run).

Why: the 23 November local strut model drove each bonded strut at its own cut faces with the
homogenised rod map and was over-constrained (30-35x the rod cell moment). Here the rod map is
applied only where it is a rigid-section statement, at the two module end masters, and the whole
CAD lattice (``body_solid.lattice``, verified against the plate model in ``body_solid.py``)
deforms freely in between, with the guides bonded to their real lands.

Model (linear, small strain, P2 tetrahedra; PA12 E = 1,530 MPa, nu = 0.4):
  * D0 (z = -44.9 mm cut face) clamped; D1 (z = +40.9 mm) one rigid body whose ROTATION is
    prescribed and whose translations are free (zero force) -> pure end moment ("kinematic" case);
  * the prescribed rotation is the rod model's relative rotation of the two end faces at the
    step (Kabsch fits of the rod-mapped faces, log map) -- about 47 deg at steps 1,709 / 1,885;
    it is applied as a linearised rotation, i.e. the linear-elastic moment that produces it;
  * each guide (stations z = -12 / +12 mm) is a rigid body bonded to its four lands
    (67.5, 157.5, 247.5, 337.5 deg) by the distributed layer of ``coupled_land.py``: area-weighted
    points on the actual inclined CAD side walls inside |z - st| <= 0.25 mm, tangential stiffness
    G/t, normal 2(1+nu_a)G/t, t(z) = 0.25 + crown (zh/0.25)^2 mm; G is ASSUMED;
  * the archived station wrench (Round 2 ``guide_hole_loads.npz``) is applied to each guide
    ("wrench" case); total = kinematic + wrench (superposition is exact in this linear model).
The body's own bending is uniform under an end moment, while the rod's cell rotations vary along
the module (8.0 -> 4.65 deg per cell at step 1,709). Each station's kinematic part is therefore
also reported rescaled by the ratio of the rod's local rotation over the two cells adjoining the
station to the rod's mean rotation over 24 mm, i.e. the rod's local-to-mean MOMENT ratio
("local" scaling; the solid's own non-uniform compliance along z is kept).

The NiTi backbone (rod EI 64,730 = PA12 body 44,118 + backbone 20,612 N mm^2) is not part of
this CAD body. Ropes, rope contact, friction, adhesive failure and geometric nonlinearity are not
modelled. Outputs go only under ``results/``.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "evening_20261123"))
sys.path.insert(0, str(HERE.parent / "evening_20261122"))
import body_solid as BS  # noqa: E402
import strut_fe as F  # noqa: E402
import crowned_bond as CB  # noqa: E402
from coupled_land import land_samples, arm, HALF, NU_ADH  # noqa: E402
from solid_bond import CUTS  # noqa: E402

MOUNT = CB.S.MOUNT
STATIONS = (-12, 12)
SOCKET_HALF = 1.62


def locate(X, conn, pts, k=48):
    """Vectorised P2 interpolation matrix (3m x 3n) at points; nearest containing tetrahedron."""
    Xv = X[conn[:, :4]]
    tree = cKDTree(Xv.mean(1))
    _, cand = tree.query(pts, k=k)
    J = (Xv[cand, 1:] - Xv[cand, :1]).transpose(0, 1, 3, 2)
    l123 = np.linalg.solve(J, (pts[:, None] - Xv[cand, 0])[..., None])[..., 0]
    L = np.concatenate([1 - l123.sum(-1, keepdims=True), l123], -1)
    best = np.argmax(L.min(-1), 1)
    Lb = L[np.arange(len(pts)), best]; tet = cand[np.arange(len(pts)), best]
    N, _ = F.shape(Lb)
    nodes = conn[tet]
    rows = (3 * np.arange(len(pts))[:, None, None] + np.arange(3)[None, None, :]) + np.zeros((1, 10, 1), int)
    cols = 3 * nodes[:, :, None] + np.arange(3)[None, None, :]
    vals = np.repeat(N[:, :, None], 3, axis=2)
    M = sp.csr_matrix((vals.ravel(), (rows.ravel(), cols.ravel())), shape=(3 * len(pts), 3 * len(X)))
    return M, float(Lb.min(1).min())


def rigid_fit(P, U):
    """Least-squares linearised rigid motion (U0 at origin, omega) of displacements U at points P."""
    A = np.zeros((3 * len(P), 6))
    A[:, :3] = np.tile(np.eye(3), (len(P), 1))
    A[:, 3:] = -np.vstack([CB.S.skew(p) for p in P])
    sol, *_ = np.linalg.lstsq(A, U.ravel(), rcond=None)
    return sol, (U.ravel() - A @ sol).reshape(-1, 3)


def kabsch(P, Y):
    pc, yc = P.mean(0), Y.mean(0)
    H = (P - pc).T @ (Y - yc); Uu, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ Uu.T))
    R = Vt.T @ np.diag([1, 1, d]) @ Uu.T
    return R, yc - R @ pc


def rod_rotations(rod, det):
    """Rod relative end rotation (D0 -> D1) and local rotations over [st-12, st+12], in the D0 frame."""
    ang = np.radians(np.arange(0, 360, 30))
    face = lambda zz: np.c_[20 * np.cos(ang), 20 * np.sin(ang), np.full(len(ang), zz)]
    fits = {}
    for zz in (BS.Z_LO, BS.Z_HI, -24.0, 0.0, 24.0):
        P = face(zz)
        fits[zz] = kabsch(P - [0, 0, -12], CB.to_station(P, 5, -12, rod, det))
    R0 = fits[BS.Z_LO][0]
    rel = lambda a, b: Rot.from_matrix(fits[a][0].T @ fits[b][0]).as_rotvec()
    return dict(end=R0.T @ fits[BS.Z_HI][0], end_rotvec=Rot.from_matrix(R0.T @ fits[BS.Z_HI][0]).as_rotvec(),
                local={-12: rel(-24.0, 0.0), 12: rel(0.0, 24.0)})


class Body:
    def __init__(self, quality, max_vol, max_edge):
        solid, self.crop = BS.lattice()
        module = trimesh.load_mesh(BS.BODY)
        t0 = time.monotonic()
        v, t = BS.tet_mesh(solid, quality, max_vol)
        self.X, self.conn = F.p2(v, t)
        self.K, self.vol = BS.assemble(self.X, self.conn)
        X = self.X; z = X[:, 2]; tol = 1e-6
        self.clamped = np.flatnonzero(np.abs(z - BS.Z_LO) < tol)
        self.d1 = np.flatnonzero(np.abs(z - BS.Z_HI) < tol)
        self.T, gcol = BS.transform(X, [self.d1], self.clamped)
        self.c1 = gcol[0]
        self.Kr = (self.T.T @ self.K @ self.T).tocsr()
        self.n = self.Kr.shape[0]
        # bond layer points on the actual land walls
        self.lands = []
        for st in STATIONS:
            for th in MOUNT:
                strut = F.crop_strut(module, th, *CUTS[st])
                xs, ws, ns = land_samples(strut, st, max_edge)
                self.lands.append(dict(st=st, th=th, xs=xs, ws=ws, ns=ns))
        allx = np.vstack([L["xs"] for L in self.lands])
        M, self.min_bary = locate(X, self.conn, allx)
        self.MT = (M @ self.T).tocsr()
        off = 0
        for L in self.lands:
            m = len(L["xs"]); L["rows"] = slice(3 * off, 3 * (off + m)); off += m
        # socket-wall nodes of each bonded strut (for the arm distortion check)
        r = np.hypot(X[:, 0], X[:, 1]); ang = np.degrees(np.arctan2(X[:, 1], X[:, 0]))
        for L in self.lands:
            near = np.abs((ang - L["th"] + 180) % 360 - 180) < 20
            L["sock"] = np.flatnonzero(near & (np.abs(z - L["st"]) <= SOCKET_HALF) & (r > 13) & (r < 26))
            L["band"] = np.flatnonzero(near & (np.abs(z - L["st"]) <= HALF + 1e-9) & (r > 13) & (r < 26))
        self.mesh = dict(quality=quality, max_tet_volume_mm3=max_vol, tets=len(self.conn), p2_nodes=len(X),
                         dofs=3 * len(X), reduced_dofs=self.n, layer_points=len(allx), layer_max_edge_mm=max_edge,
                         min_bary=self.min_bary, land_area_mm2=[float(L["ws"].sum()) for L in self.lands],
                         socket_nodes=[int(len(L["sock"])) for L in self.lands], build_s=time.monotonic() - t0)

    def system(self, G, crown):
        """Assemble [body reduced DOFs | guide -12 (6) | guide +12 (6)] with the bond layer."""
        n = self.n; Ntot = n + 12
        blocks = []
        Kb = self.Kr.copy().tocoo()
        rows, cols, vals = [Kb.row], [Kb.col], [Kb.data]
        for L in self.lands:
            zh = L["xs"][:, 2] - L["st"]
            t = 0.25 + crown * (zh / HALF) ** 2
            k = (L["ws"] / t * G)[:, None, None]
            D = k * (np.eye(3) + (2 * (1 + NU_ADH) - 1) * np.einsum("ni,nj->nij", L["ns"], L["ns"]))
            Dbig = sp.block_diag(list(D), format="csr")
            Mb = self.MT[L["rows"]]
            A = np.vstack([arm(x - [0, 0, L["st"]]) for x in L["xs"]])
            g = n + 6 * STATIONS.index(L["st"])
            Kbb = (Mb.T @ Dbig @ Mb).tocoo()
            Kbg = -(Mb.T @ (Dbig @ A))  # (n,6) dense
            Kgg = A.T @ (Dbig @ A)
            rows += [Kbb.row]; cols += [Kbb.col]; vals += [Kbb.data]
            Kbg = sp.coo_matrix(np.asarray(Kbg))
            rows += [Kbg.row, Kbg.col + g]; cols += [Kbg.col + g, Kbg.row]; vals += [Kbg.data, Kbg.data]
            gi, gj = np.meshgrid(np.arange(6) + g, np.arange(6) + g, indexing="ij")
            rows += [gi.ravel()]; cols += [gj.ravel()]; vals += [Kgg.ravel()]
            L["D"], L["A"], L["t"] = D, A, t
        Kt = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(Ntot, Ntot))
        return 0.5 * (Kt + Kt.T)

    def solve(self, Kt, rhs_list):
        """Prescribe D1 rotations (columns c1+3..c1+5); rhs_list: (omega(3), guide wrenches (12))."""
        import pypardiso
        Ntot = Kt.shape[0]
        pres = self.c1 + np.arange(3, 6)
        free = np.setdiff1d(np.arange(Ntot), pres)
        Kff = Kt[free][:, free].tocsr(); Kfp = Kt[free][:, pres]
        B = np.zeros((len(free), len(rhs_list))); Up = np.zeros((3, len(rhs_list)))
        for j, (om, W) in enumerate(rhs_list):
            Fv = np.zeros(Ntot); Fv[self.n:] = W
            B[:, j] = Fv[free] - Kfp @ om; Up[:, j] = om
        Ku = sp.triu(Kff, format="csr"); Ku.eliminate_zeros(); Ku.sort_indices()
        s = pypardiso.PyPardisoSolver(); s.set_matrix_type(2)
        Uf = s.solve(Ku, B); s.free_memory(everything=True)
        if Uf.ndim == 1: Uf = Uf[:, None]
        U = np.zeros((Ntot, len(rhs_list))); U[free] = Uf; U[pres] = Up
        resid = float(np.abs(Kff @ Uf - B).max() / max(np.abs(B).max(), 1e-30))
        return U, resid

    def post(self, U):
        """Per-land tractions, bond slip, guide motion relative to its land and socket distortion."""
        n = self.n
        ub = self.T @ U[:n]; ub = ub.reshape(-1, 3)
        out = {}
        for L in self.lands:
            q = U[n + 6 * STATIONS.index(L["st"]): n + 6 * STATIONS.index(L["st"]) + 6]
            us = (self.MT[L["rows"]] @ U[:n]).reshape(-1, 3)
            slip = (L["A"] @ q).reshape(-1, 3) - us
            f = np.einsum("nij,nj->ni", L["D"], slip)
            tr = f / L["ws"][:, None]
            ez = np.array([0, 0, 1.0]); ns = L["ns"]
            ax = ez - ns * ns[:, 2:3]; ax /= np.linalg.norm(ax, axis=1, keepdims=True)
            comp = dict(normal=np.einsum("ni,ni->n", tr, ns), axial=np.einsum("ni,ni->n", tr, ax),
                        cross=np.einsum("ni,ni->n", tr, np.cross(ns, ax)))
            # land rigid motion (fit over band nodes, about the station point) vs guide
            P = self.X[L["band"]] - [0, 0, L["st"]]
            land, _ = rigid_fit(P, ub[L["band"]])
            Ps = self.X[L["sock"]] - [0, 0, L["st"]]
            Us = ub[L["sock"]]
            rigid_part = land[:3] + np.cross(land[3:], Ps)
            dist = np.linalg.norm(Us - rigid_part, axis=1)
            zh = Ps[:, 2]
            w = L["ws"]
            out[f"{L['st']:+d}@{L['th']}"] = dict(
                peak_abs_MPa={k: float(np.abs(v).max()) for k, v in comp.items()},
                mean_abs_MPa={k: float((np.abs(v) * w).sum() / w.sum()) for k, v in comp.items()},
                force_N=f.sum(0).tolist(), max_slip_mm=float(np.linalg.norm(slip, axis=1).max()),
                guide_minus_land_rot_deg=float(np.degrees(np.linalg.norm(q[3:] - land[3:]))),
                land_rotation_deg=float(np.degrees(np.linalg.norm(land[3:]))),
                socket_nonrigid_max_mm=float(dist.max()),
                socket_nonrigid_in_land_mm=float(dist[np.abs(zh) <= HALF + 1e-9].max()),
                socket_nonrigid_at_ends_mm=float(dist[np.abs(zh) >= SOCKET_HALF - 0.3].max()))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=float, default=5.0)
    ap.add_argument("--max-vol", type=float, default=0.4)
    ap.add_argument("--max-edge", type=float, default=0.08)
    ap.add_argument("--steps", type=int, nargs="+", default=[1709, 1885])
    ap.add_argument("--G", type=float, nargs="+", default=[500.0, 1500.0])
    ap.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rod, zstates, _ = CB.load_motion()
    B = Body(a.quality, a.max_vol, a.max_edge)
    print("mesh", B.mesh, flush=True)
    rot = {}
    for s in a.steps:
        det = rod.kinematic_metrics(zstates[s])[1]
        rot[s] = rod_rotations(rod, det)
    W = {st: CB.station_wrenches("M6", st) for st in STATIONS}
    doc = dict(scope=__doc__, mesh=B.mesh, crop=B.crop, parameters=vars(a),
               rod_rotations={s: dict(end_rotvec_deg=np.degrees(r["end_rotvec"]).tolist(),
                                      local_rotvec_deg={st: np.degrees(v).tolist() for st, v in r["local"].items()})
                              for s, r in rot.items()},
               cases=[])
    for G in a.G:
        for crown in a.crown:
            t0 = time.monotonic()
            Kt = B.system(G, crown)
            rhs = []
            for s in a.steps:
                rhs.append((rot[s]["end_rotvec"], np.zeros(12)))
                rhs.append((np.zeros(3), np.r_[W[-12][s], W[12][s]]))
            U, resid = B.solve(Kt, rhs)
            for i, s in enumerate(a.steps):
                Uk, Uw = U[:, 2 * i], U[:, 2 * i + 1]
                # solid local rotation over [st-12, st+12] from the kinematic field (ring-to-ring sections)
                ub = (B.T @ Uk[:B.n]).reshape(-1, 3)
                zc = B.X[:, 2]; rr = np.hypot(B.X[:, 0], B.X[:, 1])
                def sec(zz):
                    m = (np.abs(zc - zz) < 0.6) & (rr < 8.6)
                    if m.sum() < 12: m = np.abs(zc - zz) < 0.6
                    return rigid_fit(B.X[m], ub[m])[0][3:]
                scale, solid_share = {}, {}
                uniform = np.linalg.norm(rot[s]["end_rotvec"]) * 24.0 / (BS.Z_HI - BS.Z_LO)
                for st in STATIONS:
                    lo, hi = st - 12.0, st + 12.0
                    solid_rot = sec(hi) - sec(lo)
                    rod_loc = rot[s]["local"][st]
                    # moment scaling: rod local curvature / rod mean curvature over the same 24 mm
                    scale[st] = float(np.linalg.norm(rod_loc) / uniform)
                    # diagnostic: solid local rotation under the end moment / uniform share
                    solid_share[st] = float(np.linalg.norm(solid_rot) / uniform)
                pk, pw = B.post(Uk), B.post(Uw)
                tot = {}
                for st in STATIONS:
                    Ul = scale[st] * Uk + Uw
                    tot[st] = B.post(Ul)
                row = dict(G_MPa=G, crown_mm=crown, step=s, residual=resid, local_moment_scale=scale,
                           solid_local_rotation_over_uniform=solid_share,
                           kinematic=pk, wrench=pw, total_end_moment=B.post(Uk + Uw),
                           total_local={k: v for st in STATIONS for k, v in tot[st].items() if k.startswith(f"{st:+d}")},
                           guide_q_kinematic=Uk[B.n:].tolist(), guide_q_wrench=Uw[B.n:].tolist(),
                           wrench_applied={st: W[st][s].tolist() for st in STATIONS})
                # wrench closure: sum of layer forces on the body from the wrench case equals the applied wrench
                for st in STATIONS:
                    fs = sum(np.array(pw[f"{st:+d}@{th}"]["force_N"]) for th in MOUNT)
                    row.setdefault("wrench_force_closure_N", {})[st] = float(np.linalg.norm(fs - W[st][s][:3]))
                doc["cases"].append(row)
                tl = row["total_local"]
                print(f"G {G} crown {crown} step {s} scale {scale} solid_share {solid_share} resid {resid:.1e} | " + " ".join(
                    f"{k}: ax {v['peak_abs_MPa']['axial']:.1f}/{v['mean_abs_MPa']['axial']:.1f} n {v['peak_abs_MPa']['normal']:.1f} "
                    f"sockL {v['socket_nonrigid_in_land_mm']:.4f} sockE {v['socket_nonrigid_at_ends_mm']:.3f}"
                    for k, v in tl.items()), flush=True)
            print(f"  system G {G} crown {crown}: {time.monotonic() - t0:.0f}s", flush=True)
            (out / "body_bond.json").write_text(json.dumps(doc, indent=1, default=float))


if __name__ == "__main__":
    main()
