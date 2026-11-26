"""Geometric-nonlinearity check of the whole-body solid M6 model under the rod's end rotation.

The linear model (``body_bond.py``) imposes the ~47 deg D0 -> D1 rotation at step 1,709 as a
linearised rotation; ``strain_check.py`` found linearised rotations up to 0.85 rad and peak
strains of 3.7% in the hub/arm region. This script repeats the END-ROTATION case (no guides,
no wrench) with a total-Lagrangian St Venant-Kirchhoff P2 model:

  * D0 cut face clamped; every D1 node follows x = c + t + R(s*Omega)(X - c), with the
    finite rotation R applied exactly and the D1 translation t free (3 unknowns, zero force);
  * load factor s = 0 -> 1 in equal increments, full Newton with the consistent tangent;
  * same mesh, same PA12 constants as the linear run (SVK reduces to it for small strain).

It compares, at s = 1 and for the linear solution with the same Omega:
  the end moment, peak Green / linear principal strain (body and land bands), and the
  non-rigid deformation of the bonded arms in the land bands relative to their own rigid fit.
SVK is not a validated PA12 constitutive law at 3-4% strain; this is a kinematic validity check.
Writes results/nonlinear_check.json.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.spatial.transform import Rotation as Rot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import body_bond as BB  # noqa: E402
BS, F = BB.BS, BB.F

E, NU = F.E_PA12, F.NU_PA12
LAM = E * NU / ((1 + NU) * (1 - 2 * NU)); MU = E / (2 * (1 + NU))


class Model:
    def __init__(self, X, conn):
        self.X, self.conn = X, conn
        g, vol = F.bary_grad(X[conn[:, :4]])
        _, dNq = F.shape(F.QP)
        self.G = [np.einsum("nk,ekx->enx", dNq[q], g) for q in range(4)]  # (ne,10,3) reference gradients
        self.w = vol / 4
        ne = len(conn)
        self.dof = (3 * conn[:, :, None] + np.arange(3)).reshape(ne, 30)
        self.rows = np.repeat(self.dof, 30, axis=1).ravel(); self.cols = np.tile(self.dof, (1, 30)).ravel()

    def assemble(self, u, tangent=True):
        ue = u[self.conn]  # (ne,10,3)
        ne = len(self.conn)
        fe = np.zeros((ne, 30)); Ke = np.zeros((ne, 30, 30)) if tangent else None
        I = np.eye(3)
        for G in self.G:
            H = np.einsum("eai,eaj->eij", ue, G)
            Fd = I + H
            Eg = 0.5 * (np.einsum("eki,ekj->eij", Fd, Fd) - I)
            S = LAM * np.trace(Eg, axis1=1, axis2=2)[:, None, None] * I + 2 * MU * Eg
            P = np.einsum("eik,ekj->eij", Fd, S)  # first PK
            fe += np.einsum("eij,eaj->eai", P, G).reshape(ne, 30) * self.w[:, None]
            if tangent:
                # material part: dE = sym(F^T grad(du)); B (ne,6,30)
                B = np.zeros((ne, 6, 30))
                for a in range(10):
                    for i in range(3):
                        gi = G[:, a, :]  # (ne,3)
                        Fi = Fd[:, i, :]  # row i of F: dE_jk from du_i = 0.5(F_ij g_k + F_ik g_j)
                        c = 3 * a + i
                        B[:, 0, c] = Fi[:, 0] * gi[:, 0]; B[:, 1, c] = Fi[:, 1] * gi[:, 1]; B[:, 2, c] = Fi[:, 2] * gi[:, 2]
                        B[:, 3, c] = Fi[:, 1] * gi[:, 2] + Fi[:, 2] * gi[:, 1]
                        B[:, 4, c] = Fi[:, 0] * gi[:, 2] + Fi[:, 2] * gi[:, 0]
                        B[:, 5, c] = Fi[:, 0] * gi[:, 1] + Fi[:, 1] * gi[:, 0]
                C = np.zeros((6, 6)); C[:3, :3] = LAM; C[range(3), range(3)] += 2 * MU; C[range(3, 6), range(3, 6)] = MU
                Ke += np.einsum("eki,kl,elj->eij", B, C, B) * self.w[:, None, None]
                geo = np.einsum("eai,eij,ebj->eab", G, S, G) * self.w[:, None, None]  # (ne,10,10)
                Kg = np.zeros((ne, 30, 30))
                for d in range(3):
                    Kg[:, d::3, d::3] = geo
                Ke += Kg
        n = 3 * len(self.X)
        f = np.bincount(self.dof.ravel(), fe.ravel(), minlength=n)
        K = sp.csr_matrix((Ke.ravel(), (self.rows, self.cols)), shape=(n, n)) if tangent else None
        return f, K

    def strains(self, u, linear=False):
        ue = u[self.conn]; I = np.eye(3)
        _, dN = F.shape(np.full((1, 4), 0.25))
        g, _ = F.bary_grad(self.X[self.conn[:, :4]])
        Gc = np.einsum("nk,ekx->enx", dN[0], g)
        H = np.einsum("eai,eaj->eij", ue, Gc)
        Eg = 0.5 * (H + H.transpose(0, 2, 1)) if linear else 0.5 * (np.einsum("eki,ekj->eij", I + H, I + H) - I)
        return np.abs(np.linalg.eigvalsh(Eg)).max(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=float, default=10.0)
    ap.add_argument("--max-vol", type=float, default=2.0)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--step-id", type=int, default=1709)
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--max-seconds", type=float, default=1800)
    a = ap.parse_args()
    import pypardiso
    t0 = time.monotonic()
    rod, zs, _ = BB.CB.load_motion()
    Om = BB.rod_rotations(rod, rod.kinematic_metrics(zs[a.step_id])[1])["end_rotvec"]
    solid, _ = BS.lattice()
    v, t = BS.tet_mesh(solid, a.quality, a.max_vol)
    X, conn = F.p2(v, t)
    Mdl = Model(X, conn)
    z = X[:, 2]; tol = 1e-6
    d0 = np.flatnonzero(np.abs(z - BS.Z_LO) < tol); d1 = np.flatnonzero(np.abs(z - BS.Z_HI) < tol)
    c = np.r_[0.0, 0.0, BS.Z_HI]
    n = len(X); owner = np.zeros(n, int); owner[d0] = -1; owner[d1] = 1
    free = np.flatnonzero(owner == 0)
    nf = 3 * len(free)
    rows = list((3 * free[:, None] + np.arange(3)).ravel()); cols = list(range(nf)); vals = [1.0] * nf
    for i in d1:
        for k in range(3):
            rows.append(3 * i + k); cols.append(nf + k); vals.append(1.0)
    T = sp.csr_matrix((vals, (rows, cols)), shape=(3 * n, nf + 3))

    def u0(s):
        R = Rot.from_rotvec(s * Om).as_matrix()
        u = np.zeros((n, 3)); u[d1] = (X[d1] - c) @ R.T - (X[d1] - c)
        return u.ravel()

    # linear reference with the same Omega (prescribed linearised rotation, free translation)
    f0, K0 = Mdl.assemble(np.zeros((n, 3)))
    ulin0 = np.zeros((n, 3)); ulin0[d1] = np.cross(Om, X[d1] - c); ulin0 = ulin0.ravel()
    Kr = (T.T @ K0 @ T).tocsr()
    def solve(Kred, rhs):
        # a fresh PARDISO instance per factorisation (re-using one instance stalled Newton)
        solver = pypardiso.PyPardisoSolver(mtype=-2)
        Ku = sp.triu(0.5 * (Kred + Kred.T), format="csr"); Ku.eliminate_zeros(); Ku.sort_indices()
        x = solver.solve(Ku, rhs); solver.free_memory(everything=True); return x
    al = solve(Kr, -(T.T @ (K0 @ ulin0)))
    ulin = (T @ al + ulin0)
    flin = K0 @ ulin
    Mlin = np.cross(X[d1] - c, flin.reshape(-1, 3)[d1]).sum(0)
    # nonlinear continuation
    aN = np.zeros(nf + 3); hist = []
    for k in range(1, a.steps + 1):
        s = k / a.steps
        ub_prev = u0((k - 1) / a.steps); ub = u0(s)
        # consistent predictor: tangent at the last converged state, prescribed increment as load
        f, K = Mdl.assemble((T @ aN + ub_prev).reshape(-1, 3))
        aN -= solve((T.T @ K @ T).tocsr(), T.T @ (f + K @ (ub - ub_prev)))
        for it in range(25):
            u = T @ aN + ub
            f, K = Mdl.assemble(u.reshape(-1, 3))
            r = T.T @ f
            nr = float(np.linalg.norm(r)); ref = float(np.linalg.norm(f)) + 1e-30
            hist.append(dict(load=s, it=it, res_rel=nr / ref))
            print(f"s {s:.3f} it {it} |r|/|f| {nr / ref:.2e} {time.monotonic() - t0:.0f}s", flush=True)
            if nr / ref < a.tol: break
            aN -= solve((T.T @ K @ T).tocsr(), r)
            if time.monotonic() - t0 > a.max_seconds: break
        if time.monotonic() - t0 > a.max_seconds or nr / ref > 1e-3:
            break
    converged = (s == 1.0) and nr / ref < a.tol
    u = (T @ aN + ub).reshape(-1, 3)
    f, _ = Mdl.assemble(u, tangent=False)
    xd = X + u
    cdef = xd[d1].mean(0) - (X[d1].mean(0) - c) @ Rot.from_rotvec(s * Om).as_matrix().T
    Mnl = np.cross(xd[d1] - cdef, f.reshape(-1, 3)[d1]).sum(0)
    # strains and land-band arm deformation (relative to each land's own rigid fit)
    epsN = Mdl.strains(u); epsL = Mdl.strains(ulin.reshape(-1, 3), linear=True)
    cen = X[conn[:, :4]].mean(1); rr = np.hypot(cen[:, 0], cen[:, 1])
    band = (np.abs(np.abs(cen[:, 2]) - 12) < 0.6) & (rr > 15) & (rr < 24)
    def arm_nonrigid(U):
        out = {}
        r = np.hypot(X[:, 0], X[:, 1]); ang = np.degrees(np.arctan2(X[:, 1], X[:, 0]))
        for st in (-12, 12):
            for th in BB.MOUNT:
                near = np.abs((ang - th + 180) % 360 - 180) < 20
                sock = np.flatnonzero(near & (np.abs(z - st) <= BB.SOCKET_HALF) & (r > 13) & (r < 26))
                P = X[sock]; Y = P + U[sock]
                R_, t_ = BB.kabsch(P, Y)
                out[f"{st:+d}@{th}"] = float(np.linalg.norm(Y - (P @ R_.T + t_), axis=1).max())
        return out
    doc = dict(scope=__doc__, step=a.step_id, end_rotvec_deg=np.degrees(Om).tolist(), load_reached=s, converged=bool(converged),
               mesh=dict(quality=a.quality, max_tet_volume_mm3=a.max_vol, tets=len(conn), dofs=3 * n), newton=hist,
               end_moment_linear_Nmm=Mlin.tolist(), end_moment_nonlinear_Nmm=Mnl.tolist(),
               moment_ratio_nl_over_lin=float(np.linalg.norm(Mnl) / np.linalg.norm(Mlin) / s),
               peak_strain=dict(nonlinear_green=float(epsN.max()), linear=float(epsL.max()),
                                land_bands_nonlinear=float(epsN[band].max()), land_bands_linear=float(epsL[band].max()),
                                p99_nonlinear=float(np.percentile(epsN, 99)), p99_linear=float(np.percentile(epsL, 99))),
               socket_nonrigid_max_mm=dict(nonlinear=arm_nonrigid(u), linear_small_rotation=arm_nonrigid(ulin.reshape(-1, 3))),
               note="linear socket value uses an exact Kabsch fit on a linearised field, so it includes the "
                    "spurious stretch of a linearised 24-34 deg rotation; compare with body_bond (small-rotation fit)",
               elapsed_s=time.monotonic() - t0)
    (HERE / "results" / "nonlinear_check.json").write_text(json.dumps(doc, indent=1, default=float))
    print(json.dumps({k: doc[k] for k in ("load_reached", "converged", "moment_ratio_nl_over_lin", "peak_strain")}, indent=1))
    print(doc["socket_nonrigid_max_mm"])


if __name__ == "__main__":
    main()
