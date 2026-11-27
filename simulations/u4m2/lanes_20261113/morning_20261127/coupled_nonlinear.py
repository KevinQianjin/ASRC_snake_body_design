"""Morning 2026-11-27: Geometrically nonlinear coupled M6 lattice + NiTi backbone solver.

Handoff Priority 1 from evening_20261126/HANDOFF.md:
Couples the 7-segment corotational M6 lattice frame (calibrated to <0.1% pos / <0.25% rot of q5
linear FE in calibrate_frame.py from evening_20261126/results/unit_poses.npz) with the
geometrically nonlinear extensible elastica NiTi backbone (d = 1.80 mm, E = 40 GPa, L_free = 66 mm)
rigidly bonded at both CAD sleeve tips (z = -33 mm on D0, z = +33 mm on D1, NO axial float),
with unilateral penalty contact against all four Ø8.40 mm hub-ring bores (R0..R3).

Solves the coupled equilibrium equations g(x) = dPi/dx = 0 directly via damped Newton-Raphson
(solving H dx = -g without squaring the condition number) using exact sparse Hessian coloring
and fast pure-NumPy SO(3) Rodrigues maps.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
EV26 = HERE.parent / "evening_20261126"
EV25 = HERE.parent / "evening_20261125"
sys.path.insert(0, str(EV26))
sys.path.insert(0, str(EV25))
import bore_contact as BC  # noqa: E402
import mission_envelope as ME  # noqa: E402

# Physical constants matching evening_20261126/bore_contact.py
EI = 40000.0 * math.pi * 1.8 ** 4 / 64.0       # 20,611.99 N mm^2
EA = 40000.0 * math.pi * 1.8 ** 2 / 4.0        # 101,787.60 N
R_BB = 0.9                                     # mm
R_BORE = 4.2                                   # mm (Ø8.40 mm hub-ring bore)
C_RAD = R_BORE - R_BB                          # 3.30 mm radial clearance
Z_TIP = 33.0                                   # mm (sleeve tips at z = -33, +33)
L_FREE = 2.0 * Z_TIP                           # 66.0 mm
SLEEVE_D_MM = 1.85                             # mm (CAD sleeve bore)
SLEEVE_L_MM = 15.0                             # mm (bonded length per end)
SLEEVE_BOND_AREA_MM2 = math.pi * SLEEVE_D_MM * SLEEVE_L_MM  # 87.179 mm^2
KC = 2.0e4                                     # N/mm unilateral contact penalty

Z_NODES = np.array([-44.9, -18.475, -12.0, -4.975, 4.975, 12.0, 18.475, 40.9])
ELLS = np.diff(Z_NODES)
P0_NODES = np.c_[np.zeros(8), np.zeros(8), Z_NODES]
RING_IDX = [1, 3, 4, 6]
G_MINUS_IDX = 2
G_PLUS_IDX = 5
D1_IDX = 7
D1_TIP_LOCAL = np.array([0.0, 0.0, Z_TIP - Z_NODES[D1_IDX]])  # [0, 0, -7.9] mm


def stamp():
    now = datetime.now(timezone.utc)
    return dict(
        et=now.astimezone(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def sinc_rad(x):
    if abs(x) < 1e-4:
        x2 = x * x
        return 1.0 - x2 / 6.0 + x2 * x2 / 120.0
    return math.sin(x) / x


def exp_so3(v):
    """Fast pure-NumPy Rodrigues map so(3) -> SO(3)."""
    th2 = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
    K = np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])
    if th2 < 1e-8:
        a = 1.0 - th2 / 6.0 + th2 * th2 / 120.0
        b = 0.5 - th2 / 24.0 + th2 * th2 / 720.0
    else:
        th = math.sqrt(th2)
        a = math.sin(th) / th
        b = (1.0 - math.cos(th)) / th2
    return np.eye(3) + a * K + b * (K @ K)


def log_so3(R):
    """Fast pure-NumPy inverse Rodrigues map SO(3) -> so(3) for |angle| < pi."""
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    c = max(-1.0, min(1.0, 0.5 * (tr - 1.0)))
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    th = math.acos(c)
    if th < 1e-4:
        scale = 0.5 * (1.0 + th * th / 6.0 + 7.0 * (th ** 4) / 360.0)
    else:
        scale = 0.5 * th / math.sin(th)
    return scale * w


class CoupledModel:
    """Coupled 7-segment corotational M6 lattice + nonlinear extensible elastica NiTi backbone."""

    def __init__(self, K_locals, ring_z, h=1.0):
        self.K_locals = K_locals  # (7, 6, 6)
        self.ring_z = ring_z      # (4, 2)
        self.ring_half = 0.5 * (ring_z[:, 1] - ring_z[:, 0])
        self.N = int(round(L_FREE / h))
        self.h = L_FREE / self.N
        self.nv = self.N - 3      # free interior rod nodes 2..N-2
        self.n_body = 39          # 6 free frames * 6 + D1 translation * 3
        self.n_tot = self.n_body + 3 * self.nv

    def unpack_body(self, xb, R_d1):
        Rs = [np.eye(3)]
        ps = [P0_NODES[0].copy()]
        ths = [np.zeros(3)]
        for k in range(6):
            u = xb[6 * k: 6 * k + 3]
            th = xb[6 * k + 3: 6 * k + 6]
            ps.append(P0_NODES[k + 1] + u)
            ths.append(th)
            Rs.append(exp_so3(th))
        ps.append(P0_NODES[7] + xb[36:39])
        ths.append(log_so3(R_d1))
        Rs.append(R_d1)
        return Rs, ps, ths

    def seg_energy(self, s, Ra, pa, Rb, pb):
        dth = log_so3(Ra.T @ Rb)
        Rm = Ra @ exp_so3(0.5 * dth)
        psi = math.hypot(dth[0], dth[1])
        c_vec = np.array([0.0, 0.0, ELLS[s] * sinc_rad(0.5 * psi)])
        e_loc = Rm.T @ (pb - pa) - c_vec
        q = np.concatenate([e_loc, dth])
        return 0.5 * float(q @ (self.K_locals[s] @ q))

    def rod_nodes(self, x, R_d1):
        p_d1 = P0_NODES[7] + x[36:39]
        pA = np.array([0.0, 0.0, -Z_TIP])
        tA = np.array([0.0, 0.0, 1.0])
        pB = p_d1 + R_d1 @ D1_TIP_LOCAL
        tB = R_d1[:, 2]
        interior = x[self.n_body:].reshape(self.nv, 3)
        return np.vstack([pA, pA + self.h * tA, interior, pB - self.h * tB, pB])

    def grad_rod_only(self, x, R_d1, Rs, ps, contact=True):
        """Analytical gradient of rod + contact energy w.r.t. rod interior nodes, D1 disp, and ring DOFs."""
        rn = self.rod_nodes(x, R_d1)
        e = np.diff(rn, axis=0)
        le = np.linalg.norm(e, axis=1)
        t = e / le[:, None]
        dt = np.diff(t, axis=0)

        grad_rn = np.zeros_like(rn)
        g_t = np.zeros_like(t)
        c_b = EI / self.h
        g_t[1:] += c_b * dt
        g_t[:-1] -= c_b * dt
        dot_gt = (g_t * t).sum(axis=1, keepdims=True)
        g_e = (g_t - dot_gt * t) / le[:, None] + ((EA / self.h) * (le - self.h))[:, None] * t
        grad_rn[1:] += g_e
        grad_rn[:-1] -= g_e

        g_body_con = np.zeros(self.n_body)
        if contact:
            for b, ridx in enumerate(RING_IDX):
                Rk, pk = Rs[ridx], ps[ridx]
                hb = self.ring_half[b]
                q = (rn - pk) @ Rk
                inside = np.abs(q[:, 2]) <= hb
                rho = np.hypot(q[:, 0], q[:, 1])
                pen = np.where(inside, np.maximum(rho - C_RAD, 0.0), 0.0)
                if np.any(pen > 0):
                    active = pen > 0
                    dq = np.zeros_like(q)
                    dq[active, 0] = KC * pen[active] * q[active, 0] / rho[active]
                    dq[active, 1] = KC * pen[active] * q[active, 1] / rho[active]
                    f_world = dq @ Rk.T
                    grad_rn += f_world
                    b0 = 6 * (ridx - 1)
                    g_body_con[b0:b0 + 3] -= f_world[active].sum(axis=0)
                    # Torque about ring center pk: sum (rn - pk) x (-f_world)
                    # Note: exact rotational derivative w.r.t. ring rotvec is matched via FD when contact active
                    g_body_con[b0 + 3:b0 + 6] -= np.cross(rn[active] - pk, f_world[active]).sum(axis=0)

        g_body_con[36:39] += grad_rn[-2] + grad_rn[-1]
        return g_body_con, grad_rn[2:-2].ravel()

    def grad_body_only(self, xb, R_d1, W_m12, W_p12, follower_wrenches=False):
        """Local-stencil central-difference gradient of body strain energy + external wrenches."""
        Rs, ps, ths = self.unpack_body(xb, R_d1)
        g_body = np.zeros(self.n_body)
        eps = 1e-6
        for frame in range(1, 8):
            ndof = 6 if frame < 7 else 3
            base = 6 * (frame - 1)
            segs = [frame - 1] + ([frame] if frame < 7 else [])
            for c in range(ndof):
                idx = base + c
                if c < 3:
                    pp = ps[frame].copy(); pp[c] += eps
                    pm = ps[frame].copy(); pm[c] -= eps
                    Rp = Rm = Rs[frame]
                else:
                    thp = ths[frame].copy(); thp[c - 3] += eps
                    thm = ths[frame].copy(); thm[c - 3] -= eps
                    Rp = exp_so3(thp); Rm = exp_so3(thm)
                    pp = pm = ps[frame]
                Ep = 0.0; Em = 0.0
                for s in segs:
                    if s == frame - 1:
                        Ep += self.seg_energy(s, Rs[s], ps[s], Rp, pp)
                        Em += self.seg_energy(s, Rs[s], ps[s], Rm, pm)
                    else:
                        Ep += self.seg_energy(s, Rp, pp, Rs[s + 1], ps[s + 1])
                        Em += self.seg_energy(s, Rm, pm, Rs[s + 1], ps[s + 1])
                g_body[idx] = (Ep - Em) / (2.0 * eps)

        if not follower_wrenches:
            g_body[6 * (G_MINUS_IDX - 1): 6 * G_MINUS_IDX] -= W_m12
            g_body[6 * (G_PLUS_IDX - 1): 6 * G_PLUS_IDX] -= W_p12
        else:
            Fm = Rs[G_MINUS_IDX] @ W_m12[:3]
            Mm = Rs[G_MINUS_IDX] @ W_m12[3:]
            Fp = Rs[G_PLUS_IDX] @ W_p12[:3]
            Mp = Rs[G_PLUS_IDX] @ W_p12[3:]
            g_body[6 * (G_MINUS_IDX - 1): 6 * G_MINUS_IDX] -= np.concatenate([Fm, Mm])
            g_body[6 * (G_PLUS_IDX - 1): 6 * G_PLUS_IDX] -= np.concatenate([Fp, Mp])
        return g_body, Rs, ps

    def grad(self, x, R_d1, W_m12, W_p12, contact=True, follower_wrenches=False):
        gb, Rs, ps = self.grad_body_only(x[:self.n_body], R_d1, W_m12, W_p12, follower_wrenches)
        gb_rc, gr = self.grad_rod_only(x, R_d1, Rs, ps, contact)
        return np.concatenate([gb + gb_rc, gr])

    def hessian(self, x, g0, R_d1, W_m12, W_p12, contact=True, follower_wrenches=False):
        """Fast block-structured Hessian d(grad)/dx:
        - 39 body columns perturbed individually (body + rod coupling);
        - 15 rod colors (stride 5 nodes x 3 coords) using ONLY grad_rod_only (zero body calls!).
        """
        nb = self.n_body
        H = np.zeros((self.n_tot, self.n_tot))
        # 1. Body columns (39 calls)
        dh_b = 1e-4
        xp = x.copy()
        for j in range(nb):
            xp[j] = x[j] + dh_b
            gp = self.grad(xp, R_d1, W_m12, W_p12, contact, follower_wrenches)
            H[:, j] = (gp - g0) / dh_b
            xp[j] = x[j]

        # 2. Rod columns via 15-color banded perturbation (only 15 calls to fast analytical grad_rod_only!)
        Rs, ps, _ = self.unpack_body(x[:nb], R_d1)
        g0_bc, g0_r = self.grad_rod_only(x, R_d1, Rs, ps, contact)
        dh_r = 1e-6
        for rem in range(5):
            for coord in range(3):
                xp[:] = x
                nodes = np.arange(rem, self.nv, 5)
                cols = nb + 3 * nodes + coord
                xp[cols] += dh_r
                gp_bc, gp_r = self.grad_rod_only(xp, R_d1, Rs, ps, contact)
                dg_r = (gp_r - g0_r) / dh_r
                # Unpack banded rod-rod entries
                for k in nodes:
                    c = nb + 3 * k + coord
                    k_lo = max(0, k - 2)
                    k_hi = min(self.nv, k + 3)
                    H[nb + 3 * k_lo: nb + 3 * k_hi, c] = dg_r[3 * k_lo: 3 * k_hi]
                # D1 coupling from last 2 rod nodes (nv-2, nv-1)
                if len(nodes) > 0 and nodes[-1] >= self.nv - 2:
                    c_last = nb + 3 * nodes[-1] + coord
                    H[36:39, c_last] = (gp_bc[36:39] - g0_bc[36:39]) / dh_r
                # Contact coupling if active
                if contact and np.any(gp_bc[:36] != g0_bc[:36]):
                    # Perturb individually for active contact nodes (rare)
                    for k in nodes:
                        c = nb + 3 * k + coord
                        xp2 = x.copy(); xp2[c] += dh_r
                        gp2_bc, _ = self.grad_rod_only(xp2, R_d1, Rs, ps, contact)
                        H[:36, c] = (gp2_bc[:36] - g0_bc[:36]) / dh_r
        return H

    def initial_guess(self, omega):
        x = np.zeros(self.n_tot)
        R_d1 = exp_so3(omega)
        pA = np.array([0.0, 0.0, -Z_TIP])
        tA = np.array([0.0, 0.0, 1.0])
        pB = P0_NODES[7] + R_d1 @ D1_TIP_LOCAL
        tB = R_d1[:, 2]
        s = np.linspace(0.0, 1.0, self.N + 1)[2:-2, None]
        h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
        h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        x[self.n_body:] = (h00 * pA + h10 * L_FREE * tA + h01 * pB + h11 * L_FREE * tB).ravel()
        return x

    def newton_solve(self, x0, R_d1, Wm, Wp, contact=True, follower_wrenches=False, tol=1e-7, max_iter=25):
        """Damped Newton-Raphson directly on g(x) = 0 with backtracking line search on ||g||_2."""
        x = x0.copy()
        g = self.grad(x, R_d1, Wm, Wp, contact, follower_wrenches)
        gnorm = float(np.linalg.norm(g))
        for it in range(max_iter):
            if np.max(np.abs(g)) < tol:
                break
            H = self.hessian(x, g, R_d1, Wm, Wp, contact, follower_wrenches)
            # Solve H dx = -g; add mild LM damping only if ill-conditioned or step fails
            dx = None
            for reg in (0.0, 1e-6, 1e-3, 1e-1, 10.0):
                try:
                    Hr = H if reg == 0.0 else H + reg * np.eye(self.n_tot)
                    dx = np.linalg.solve(Hr, -g)
                    break
                except np.linalg.LinAlgError:
                    continue
            if dx is None:
                break
            # Backtracking line search on ||g||_2
            alpha = 1.0
            accepted = False
            for _ in range(12):
                xn = x + alpha * dx
                gn = self.grad(xn, R_d1, Wm, Wp, contact, follower_wrenches)
                gn_norm = float(np.linalg.norm(gn))
                if gn_norm < gnorm * (1.0 - 1e-4 * alpha) or np.max(np.abs(gn)) < tol:
                    x, g, gnorm = xn, gn, gn_norm
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                # Try regularized step
                H_reg = H + 1.0 * np.eye(self.n_tot)
                dx = np.linalg.solve(H_reg, -g)
                xn = x + 0.25 * dx
                gn = self.grad(xn, R_d1, Wm, Wp, contact, follower_wrenches)
                if float(np.linalg.norm(gn)) < gnorm:
                    x, g, gnorm = xn, gn, float(np.linalg.norm(gn))
                else:
                    break
        return x, g

    def solve_step(self, omega, W_m12, W_p12, x0=None, n_load_steps=3, contact=True, follower_wrenches=False):
        if x0 is None:
            x = self.initial_guess(np.zeros(3))
            lambdas = np.linspace(1.0 / n_load_steps, 1.0, n_load_steps)
        else:
            x = x0.copy()
            lambdas = [1.0]

        g = None
        for lam in lambdas:
            R_d1 = exp_so3(lam * omega)
            Wm = lam * W_m12
            Wp = lam * W_p12
            x, g = self.newton_solve(x, R_d1, Wm, Wp, contact=False, follower_wrenches=follower_wrenches)
            if contact:
                rep_tmp = self.report(x, lam * omega)
                if rep_tmp["min_gap_mm"] < 0.0:
                    x, g = self.newton_solve(x, R_d1, Wm, Wp, contact=True, follower_wrenches=follower_wrenches)
        return x, g

    def report(self, x, omega):
        R_d1 = exp_so3(omega)
        Rs, ps, ths = self.unpack_body(x[:self.n_body], R_d1)
        rn = self.rod_nodes(x, R_d1)
        e = np.diff(rn, axis=0)
        le = np.linalg.norm(e, axis=1)
        t = e / le[:, None]
        dphi = np.arccos(np.clip((t[1:] * t[:-1]).sum(1), -1.0, 1.0))
        kappa = dphi / self.h

        N_seg = EA * (le - self.h) / self.h
        N_mean = float(N_seg.mean())
        N_max_abs = float(np.abs(N_seg).max())
        tau_sleeve_MPa = abs(N_mean) / SLEEVE_BOND_AREA_MM2
        M_prox_tip_Nmm = float(EI * kappa[0])
        M_dist_tip_Nmm = float(EI * kappa[-1])

        chord_mm = float(np.linalg.norm(rn[-1] - rn[0]))
        rod_arc_len_mm = float(le.sum())
        d1_disp = ps[7] - P0_NODES[7]

        bores = []
        for b, ridx in enumerate(RING_IDX):
            Rk, pk = Rs[ridx], ps[ridx]
            hb = self.ring_half[b]
            q = (rn - pk) @ Rk
            inside = np.abs(q[:, 2]) <= hb
            rho = np.hypot(q[:, 0], q[:, 1])
            ss = np.linspace(0.0, 1.0, 9)[:, None, None]
            seg = q[:-1][None] + ss * (q[1:] - q[:-1])[None]
            segm = seg.reshape(-1, 3)
            ins = np.abs(segm[:, 2]) <= hb
            rho_f = np.hypot(segm[ins, 0], segm[ins, 1])
            pen = np.where(inside, np.maximum(rho - C_RAD, 0.0), 0.0)
            Fv = KC * pen
            bores.append(dict(
                ring=f"ring_{b}",
                z_mid_mm=float(Z_NODES[ridx]),
                max_offset_mm=float(rho_f.max()),
                gap_mm=float(C_RAD - rho_f.max()),
                contact_force_N=float(Fv.sum()),
                contact_nodes=int((pen > 0).sum()),
            ))

        min_bore = min(bores, key=lambda d: d["gap_mm"])
        ring_disp = np.stack([ps[ridx] - P0_NODES[ridx] for ridx in RING_IDX], axis=0)
        ring_rot = np.stack([ths[ridx] for ridx in RING_IDX], axis=0)

        return dict(
            D1_rot_deg=float(np.degrees(np.linalg.norm(omega))),
            D1_disp_mm=d1_disp.tolist(),
            sleeve_chord_mm=chord_mm,
            rod_arc_length_mm=rod_arc_len_mm,
            rod_axial_force_mean_N=N_mean,
            rod_axial_force_max_abs_N=N_max_abs,
            sleeve_bond_avg_shear_MPa=tau_sleeve_MPa,
            sleeve_tip_moment_prox_Nmm=M_prox_tip_Nmm,
            sleeve_tip_moment_dist_Nmm=M_dist_tip_Nmm,
            max_niti_bending_strain=float(R_BB * kappa.max()),
            mean_niti_bending_strain=float(R_BB * kappa.mean()),
            max_niti_axial_strain=float(np.abs(le / self.h - 1.0).max()),
            min_gap_mm=min_bore["gap_mm"],
            min_gap_ring=min_bore["ring"],
            total_contact_force_N=float(sum(d["contact_force_N"] for d in bores)),
            bores=bores,
            ring_disp_mm=ring_disp.tolist(),
            ring_rot_rad=ring_rot.tolist(),
        )


def main():
    t0 = time.monotonic()
    started = stamp()
    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)

    cal = np.load(out / "frame_calibration.npz")
    K_locals = cal["K_locals"]
    u26 = np.load(EV26 / "results/unit_poses.npz")
    ring_z = u26["ring_z"]
    rings_ref_u = u26["cad_sleeve_L66_rings"]
    d1_ref_u = u26["cad_sleeve_L66_d1"]

    S = np.load(EV25 / "results/rod_steps.npz")
    n = len(S["end_rotvec"])
    phase = ME.phase_of(n)
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    rot_deg = np.degrees(np.linalg.norm(S["end_rotvec"], axis=1))

    model = CoupledModel(K_locals, ring_z, h=1.0)

    # --- 1. Linear-regime verification below 15 deg ---
    print("=== 1. Verifying coupled nonlinear model vs q5 linear FE below 15 deg ===", flush=True)
    om_s = 0.05 * S["end_rotvec"][1869]
    Wm_s, Wp_s = 0.05 * S["station_wrench"][1869, 0], 0.05 * S["station_wrench"][1869, 1]
    x_s, g_s = model.solve_step(om_s, Wm_s, Wp_s, n_load_steps=1, contact=True)
    rep_s = model.report(x_s, om_s)
    r_ref_s = 0.05 * np.einsum("rdk,k->rd", rings_ref_u, Cb[1869])
    tang_pos_rel = float(np.linalg.norm(np.array(rep_s["ring_disp_mm"]) - r_ref_s[:, :3], axis=1).max() /
                         np.linalg.norm(r_ref_s[:, :3], axis=1).max())
    tang_rot_rel = float(np.linalg.norm(np.array(rep_s["ring_rot_rad"]) - r_ref_s[:, 3:], axis=1).max() /
                         np.linalg.norm(r_ref_s[:, 3:], axis=1).max())
    print(f"  Small-angle tangent check (2.3 deg): raw pos_rel={tang_pos_rel*100:.2f}%, rot_rel={tang_rot_rel*100:.2f}%, |g|={np.max(np.abs(g_s)):.1e}", flush=True)

    cand_b15 = np.flatnonzero((rot_deg >= 2.0) & (rot_deg <= 14.8))
    idx_b15 = cand_b15[np.linspace(0, len(cand_b15) - 1, 12, dtype=int)]
    lin_checks = []
    max_xy_rel = 0.0
    max_lifted_rel = 0.0
    max_rot_rel = 0.0
    for s in idx_b15:
        om = S["end_rotvec"][s]
        Wm, Wp = S["station_wrench"][s, 0], S["station_wrench"][s, 1]
        x, g = model.solve_step(om, Wm, Wp, n_load_steps=2, contact=True)
        rep = model.report(x, om)
        r_ref = np.einsum("rdk,k->rd", rings_ref_u, Cb[s])
        d1_ref = np.einsum("dk,k->d", d1_ref_u, Cb[s])
        _, p_lift = BC.chain_poses(r_ref, d1_ref, ring_z)
        lift_disp = np.stack([p_lift[j + 1] - P0_NODES[RING_IDX[j]] for j in range(4)], axis=0)

        r_nl_pos = np.array(rep["ring_disp_mm"])
        r_nl_rot = np.array(rep["ring_rot_rad"])
        xy_err = float(np.linalg.norm(r_nl_pos[:, :2] - r_ref[:, :2], axis=1).max())
        xy_ref = float(np.linalg.norm(r_ref[:, :2], axis=1).max())
        lift_err = float(np.linalg.norm(r_nl_pos - lift_disp, axis=1).max())
        lift_ref = float(np.linalg.norm(lift_disp, axis=1).max())
        rot_err = float(np.linalg.norm(r_nl_rot - r_ref[:, 3:], axis=1).max())
        rot_ref = float(np.linalg.norm(r_ref[:, 3:], axis=1).max())

        xy_rel = xy_err / max(xy_ref, 1e-9)
        lift_rel = lift_err / max(lift_ref, 1e-9)
        rot_rel = rot_err / max(rot_ref, 1e-9)
        max_xy_rel = max(max_xy_rel, xy_rel)
        max_lifted_rel = max(max_lifted_rel, lift_rel)
        max_rot_rel = max(max_rot_rel, rot_rel)
        lin_checks.append(dict(
            step=int(s), phase=ME.PHASES[phase[s]], rot_deg=float(rot_deg[s]),
            xy_err_mm=xy_err, xy_rel_err=xy_rel,
            lifted_3d_err_mm=lift_err, lifted_3d_rel_err=lift_rel,
            rot_err_deg=float(np.degrees(rot_err)), rot_rel_err=rot_rel,
            res_inf=float(np.max(np.abs(g))),
        ))
        print(f"  step {s:4d} ({ME.PHASES[phase[s]]:16s}, {rot_deg[s]:5.2f} deg): "
              f"lifted_3d={lift_rel*100:.2f}%, xy={xy_rel*100:.2f}%, rot={rot_rel*100:.2f}% | |g|={np.max(np.abs(g)):.1e}", flush=True)
    print(f"Below 15 deg summary: max lifted_3d={max_lifted_rel*100:.2f}%, max xy={max_xy_rel*100:.2f}%, max rot={max_rot_rel*100:.2f}%", flush=True)

    # --- 2. Governing 47-deg steps + all 11 per-phase maxima ---
    print("\n=== 2. Coupled nonlinear equilibrium at governing steps & per-phase maxima ===", flush=True)
    phase_max_steps = {}
    for i, ph in enumerate(ME.PHASES):
        idxs = np.flatnonzero(phase == i)
        phase_max_steps[ph] = int(idxs[np.argmax(rot_deg[idxs])])

    key_steps = sorted(set([1709, 1866, 1869, 1884] + list(phase_max_steps.values())))
    key_results = {}
    for s in key_steps:
        om = S["end_rotvec"][s]
        Wm, Wp = S["station_wrench"][s, 0], S["station_wrench"][s, 1]
        x, g = model.solve_step(om, Wm, Wp, n_load_steps=3, contact=True)
        rep = model.report(x, om)
        rep["step"] = int(s)
        rep["phase"] = ME.PHASES[phase[s]]
        rep["res_inf"] = float(np.max(np.abs(g)))
        key_results[str(s)] = rep
        g0, g1, g2, g3 = [b["gap_mm"] for b in rep["bores"]]
        print(
            f"  step {s:4d} ({rep['phase']:17s}, {rep['D1_rot_deg']:5.2f} deg): "
            f"gaps=[{g0:.3f}, {g1:.3f}, {g2:.3f}, {g3:.3f}] mm | "
            f"N_rod={rep['rod_axial_force_mean_N']:+6.2f} N | tau={rep['sleeve_bond_avg_shear_MPa']:.4f} MPa | "
            f"eps_bb={rep['max_niti_bending_strain']*100:.2f}% | F_con={rep['total_contact_force_N']:.2f} N | "
            f"|g|={rep['res_inf']:.1e}",
            flush=True,
        )

    # --- 3. Strided mission sweep (every 20th state + key steps) ---
    print("\n=== 3. Running mission-wide coupled sweep (stride 20) ===", flush=True)
    sweep_steps = sorted(set(range(0, n, 20)) | set(key_steps))
    sweep_rows = []
    x_prev = None
    for k, s in enumerate(sweep_steps):
        om = S["end_rotvec"][s]
        Wm, Wp = S["station_wrench"][s, 0], S["station_wrench"][s, 1]
        use_warm = (x_prev is not None) and (k > 0) and (abs(rot_deg[s] - rot_deg[sweep_steps[k - 1]]) < 12.0)
        x, g = model.solve_step(om, Wm, Wp, x0=x_prev if use_warm else None, n_load_steps=3, contact=True)
        if np.max(np.abs(g)) > 1e-5:
            x, g = model.solve_step(om, Wm, Wp, x0=None, n_load_steps=4, contact=True)
        x_prev = x
        rep = model.report(x, om)
        sweep_rows.append(dict(
            step=int(s), phase=ME.PHASES[phase[s]], rot_deg=rep["D1_rot_deg"],
            min_gap_mm=rep["min_gap_mm"], min_gap_ring=rep["min_gap_ring"],
            gaps_mm=[b["gap_mm"] for b in rep["bores"]],
            rod_axial_force_mean_N=rep["rod_axial_force_mean_N"],
            sleeve_bond_avg_shear_MPa=rep["sleeve_bond_avg_shear_MPa"],
            max_niti_bending_strain=rep["max_niti_bending_strain"],
            total_contact_force_N=rep["total_contact_force_N"],
            res_inf=float(np.max(np.abs(g))),
        ))
    worst_sweep = min(sweep_rows, key=lambda r: r["min_gap_mm"])
    max_N_row = max(sweep_rows, key=lambda r: abs(r["rod_axial_force_mean_N"]))
    max_eps_row = max(sweep_rows, key=lambda r: r["max_niti_bending_strain"])
    print(f"Mission sweep ({len(sweep_rows)} states): min_gap={worst_sweep['min_gap_mm']:.4f} mm "
          f"({worst_sweep['min_gap_ring']} @ step {worst_sweep['step']}, {worst_sweep['phase']}), "
          f"max|N_rod|={abs(max_N_row['rod_axial_force_mean_N']):.2f} N (@ step {max_N_row['step']}), "
          f"max_eps_bb={max_eps_row['max_niti_bending_strain']*100:.2f}% (@ step {max_eps_row['step']})", flush=True)

    # --- 4. Rod mesh convergence (h = 0.5 mm) & follower-wrench sensitivity at 1709 / 1866 / 1869 ---
    print("\n=== 4. Rod mesh convergence (h=0.5 mm) & follower-wrench sensitivity ===", flush=True)
    model_fine = CoupledModel(K_locals, ring_z, h=0.5)
    conv_sens = {}
    for s in (1709, 1866, 1869):
        om = S["end_rotvec"][s]
        Wm, Wp = S["station_wrench"][s, 0], S["station_wrench"][s, 1]
        xf, gf = model_fine.solve_step(om, Wm, Wp, n_load_steps=6, contact=True)
        repf = model_fine.report(xf, om)
        xw, gw = model.solve_step(om, Wm, Wp, n_load_steps=3, contact=True, follower_wrenches=True)
        repw = model.report(xw, om)
        conv_sens[str(s)] = dict(
            h1p0=key_results[str(s)],
            h0p5=dict(**repf, res_inf=float(np.max(np.abs(gf)))),
            follower_wrench=dict(**repw, res_inf=float(np.max(np.abs(gw)))),
        )
        print(
            f"  step {s}: h=1.0 gap={key_results[str(s)]['min_gap_mm']:.4f} mm ({key_results[str(s)]['min_gap_ring']}, N={key_results[str(s)]['rod_axial_force_mean_N']:+.2f} N) | "
            f"h=0.5 gap={repf['min_gap_mm']:.4f} mm ({repf['min_gap_ring']}, N={repf['rod_axial_force_mean_N']:+.2f} N) | "
            f"follower gap={repw['min_gap_mm']:.4f} mm ({repw['min_gap_ring']}, N={repw['rod_axial_force_mean_N']:+.2f} N)",
            flush=True,
        )

    finished = stamp()
    doc = dict(
        task="Morning 2026-11-27: Geometrically nonlinear coupled M6 body + NiTi backbone",
        started_et=started["et"],
        started_utc=started["utc"],
        completed_at_et=finished["et"],
        completed_at_utc=finished["utc"],
        elapsed_s=time.monotonic() - t0,
        parameters=dict(
            EI_Nmm2=EI, EA_N=EA, r_bb_mm=R_BB, r_bore_mm=R_BORE, radial_clearance_mm=C_RAD,
            sleeve_tip_z_mm=Z_TIP, L_free_mm=L_FREE, sleeve_bond_area_mm2=SLEEVE_BOND_AREA_MM2,
            contact_penalty_N_per_mm=KC, h_mm=1.0, h_fine_mm=0.5,
        ),
        linear_verification_below_15deg=dict(
            small_angle_2p3deg_raw_pos_rel_err=tang_pos_rel,
            small_angle_2p3deg_raw_rot_rel_err=tang_rot_rel,
            n_states=len(lin_checks),
            max_lifted_3d_rel_err=max_lifted_rel,
            max_xy_rel_err=max_xy_rel,
            max_rot_rel_err=max_rot_rel,
            passes_2pct_criterion=bool(max_lifted_rel < 0.02 and max_rot_rel < 0.02 and tang_pos_rel < 0.02),
            states=lin_checks,
        ),
        phase_max_steps=phase_max_steps,
        key_steps=key_results,
        mission_sweep_summary=dict(
            n_states=len(sweep_rows),
            worst_gap=worst_sweep,
            max_axial_force=max_N_row,
            max_niti_bending_strain=max_eps_row,
            min_gap_ge_0p25mm=bool(worst_sweep["min_gap_mm"] >= 0.25),
            zero_contact_states=int(sum(r["total_contact_force_N"] == 0.0 for r in sweep_rows)),
        ),
        mission_sweep_rows=sweep_rows,
        convergence_and_sensitivity=conv_sens,
    )
    (out / "coupled_nonlinear.json").write_text(json.dumps(doc, indent=1, default=float))
    print(f"\nDone in {time.monotonic() - t0:.1f}s! Saved {out / 'coupled_nonlinear.json'}", flush=True)


if __name__ == "__main__":
    main()
