"""Calibrate a 7-segment corotational M6 lattice frame from evening_20261126/results/unit_poses.npz.

Chain nodes (8 frames along z):
  0: D0  (z = -44.900 mm, clamped)
  1: R0  (z = -18.475 mm, hub ring 0)
  2: G-  (z = -12.000 mm, guide station z = -12 mm)
  3: R1  (z =  -4.975 mm, hub ring 1)
  4: R2  (z =  +4.975 mm, hub ring 2)
  5: G+  (z = +12.000 mm, guide station z = +12 mm)
  6: R3  (z = +18.475 mm, hub ring 3)
  7: D1  (z = +40.900 mm, distal cut face; rotation prescribed, translations free)

The 5 physical segments between (D0, R0, R1, R2, R3, D1) are split at G- (inside R0-R1) and
G+ (inside R2-R3) so external guide wrenches W_-12 and W_+12 act directly on nodes 2 and 5.
Each physical segment j in 0..4 has 4 axisymmetric stiffness parameters (EA_j, GA_j, EI_j, GJ_j)
giving local 6x6 diagonal stiffness K_j = diag(GA_j/L, GA_j/L, EA_j/L, EI_j/L, EI_j/L, GJ_j/L)
for the corotational mid-frame deformation vector [e_x, e_y, e_z, dth_x, dth_y, dth_z].
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
EV26 = HERE.parent / "evening_20261126"
EV25 = HERE.parent / "evening_20261125"
sys.path.insert(0, str(EV26))
sys.path.insert(0, str(EV25))
import bore_fe as BF  # noqa: E402

Z_NODES = np.array([-44.9, -18.475, -12.0, -4.975, 4.975, 12.0, 18.475, 40.9])
ELLS = np.diff(Z_NODES)  # 7 sub-segments
# Map each of the 7 sub-segments to its physical segment index 0..4
SEG_MAP = [0, 1, 1, 2, 3, 3, 4]
RING_IDX = [1, 3, 4, 6]  # indices of R0, R1, R2, R3 in Z_NODES
G_MINUS_IDX = 2
G_PLUS_IDX = 5
D1_IDX = 7


def linear_B_matrix(ell):
    """(6, 12) linear deformation map q_j = B_j [u_a, th_a, u_b, th_b] in mid-frame."""
    # e = (u_b - u_a) - 0.5*(th_a + th_b) x [0, 0, ell]
    # [th x (0,0,ell)] = [ell*th_y, -ell*th_x, 0]
    B = np.zeros((6, 12))
    # e = u_b - u_a
    B[:3, 0:3] = -np.eye(3)
    B[:3, 6:9] = +np.eye(3)
    # -0.5 * (th_a + th_b) x [0, 0, ell]
    # e_x += -0.5 * ell * (th_ay + th_by)
    B[0, 4] = -0.5 * ell
    B[0, 10] = -0.5 * ell
    # e_y += +0.5 * ell * (th_ax + th_bx)
    B[1, 3] = +0.5 * ell
    B[1, 9] = +0.5 * ell
    # dth = th_b - th_a
    B[3:6, 3:6] = -np.eye(3)
    B[3:6, 9:12] = +np.eye(3)
    return B


B_LIST = [linear_B_matrix(ell) for ell in ELLS]


def make_seg_K(p):
    """Build guaranteed-SPD 6x6 local stiffness K_local from 6 params:
    p = [log10_ks, log10_kb, c_sb, log10_kz, log10_kt, c_zt]
    where:
      X-Z block (e_x, dth_y): L = [[sqrt(ks), 0], [c_sb*sqrt(kb), sqrt(kb)]] -> L @ L.T (SPD!)
      Y-Z block (e_y, dth_x): same with -c_sb (axisymmetric!)
      Axial-torsion (e_z, dth_z): L = [[sqrt(kz), 0], [c_zt*sqrt(kt), sqrt(kt)]] -> L @ L.T (SPD!)
    """
    ks = 10.0 ** p[0]
    kb = 10.0 ** p[1]
    c_sb = p[2]
    kz = 10.0 ** p[3]
    kt = 10.0 ** p[4]
    c_zt = p[5]

    K = np.zeros((6, 6))
    # X-Z plane: indices (0, 4) = (e_x, dth_y)
    # Use Cholesky factor L_xz = [[s0, 0], [s1, s2]] with s0=sqrt(ks), s2=sqrt(kb), s1=c_sb*sqrt(ks)
    # Wait: better parameterization: K_xz = [[ks, c_sb*sqrt(ks*kb)], [c_sb*sqrt(ks*kb), kb]] with |c_sb| < 0.98
    k_sb = c_sb * np.sqrt(ks * kb)
    K[0, 0] = ks
    K[4, 4] = kb
    K[0, 4] = K[4, 0] = k_sb
    # Y-Z plane: indices (1, 3) = (e_y, dth_x); opposite sign for cross-term by axisymmetry
    K[1, 1] = ks
    K[3, 3] = kb
    K[1, 3] = K[3, 1] = -k_sb
    # Axial-torsion: indices (2, 5) = (e_z, dth_z)
    k_zt = c_zt * np.sqrt(kz * kt)
    K[2, 2] = kz
    K[5, 5] = kt
    K[2, 5] = K[5, 2] = k_zt
    return K


def assemble_linear_body(params, K_bb_d1=None):
    """Assemble 42x42 linear stiffness matrix for nodes 1..7 (node 0 clamped).
    params: (7, 6) array of segment parameters for each of the 7 sub-segments.
    """
    K = np.zeros((42, 42))
    for s in range(7):
        kl = make_seg_K(params[s])
        Bs = B_LIST[s]
        Ke = Bs.T @ kl @ Bs  # (12, 12) for [node s, node s+1]
        if s == 0:
            K[0:6, 0:6] += Ke[6:12, 6:12]
        else:
            i0 = 6 * (s - 1)
            i1 = 6 * s
            idx = np.r_[np.arange(i0, i0 + 6), np.arange(i1, i1 + 6)]
            K[np.ix_(idx, idx)] += Ke
    if K_bb_d1 is not None:
        K[36:42, 36:42] += K_bb_d1
    return 0.5 * (K + K.T)


def solve_linear_15(params, K_bb_d1):
    """Solve the 15 kinematic unit cases (3 D1 rots + 6 W_-12 + 6 W_+12) on the linear frame."""
    K = assemble_linear_body(params, K_bb_d1)
    pres = np.array([39, 40, 41])  # D1 rotations
    free = np.setdiff1d(np.arange(42), pres)
    Kff = K[np.ix_(free, free)]
    Kfp = K[np.ix_(free, pres)]

    B = np.zeros((len(free), 15))
    Up = np.zeros((3, 15))
    # cols 0..2: unit D1 rotations
    for j in range(3):
        Up[j, j] = 1.0
        B[:, j] = -Kfp @ Up[:, j]
    # cols 3..8: unit W_-12 at node 2 (DOFs 6..11 in 0-indexed free-node space: node 1 is 0..5, node 2 is 6..11)
    # cols 9..14: unit W_+12 at node 5 (DOFs 24..29)
    for j in range(6):
        f_full = np.zeros(42)
        f_full[6 * (G_MINUS_IDX - 1) + j] = 1.0
        B[:, 3 + j] = f_full[free]
        f_full2 = np.zeros(42)
        f_full2[6 * (G_PLUS_IDX - 1) + j] = 1.0
        B[:, 9 + j] = f_full2[free]

    Uf = np.linalg.solve(Kff, B)
    U = np.zeros((42, 15))
    U[free] = Uf
    U[pres] = Up
    rings = np.stack([U[6 * (idx - 1): 6 * idx] for idx in RING_IDX], axis=0)  # (4, 6, 15)
    d1 = U[36:42]  # (6, 15)
    return rings, d1, K


def bare_EI(params):
    """Equivalent bare-body EI over 85.8 mm (matching bore_fe.json)."""
    K = assemble_linear_body(params, K_bb_d1=None)
    F = np.zeros((42, 2))
    F[39, 0] = 1.0
    F[40, 1] = 1.0
    U = np.linalg.solve(K, F)
    return 85.8 / U[39, 0], 85.8 / U[40, 1]


def calibrate():
    u = np.load(EV26 / "results/unit_poses.npz")
    rings_ref = u["cad_sleeve_L66_rings"]  # (4, 6, 15)
    d1_ref = u["cad_sleeve_L66_d1"]        # (6, 15)
    K_cad, _ = BF.sleeve_backbone_stiffness_d1()
    bf = json.loads((EV26 / "results/bore_fe.json").read_text())
    ei_bare_ref = float(np.mean(bf["solves"]["equivalent_EI_over_85p8mm_Nmm2"]["bare"]))

    # Also load actual mission coefficients so we weight the 15 unit columns by their real mission scale!
    S = np.load(EV25 / "results/rod_steps.npz")
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]  # (3405, 15)
    # Representative mission steps across all phases (e.g. every 20th + governing)
    sample_steps = sorted(set(range(0, len(Cb), 25)) | {1709, 1866, 1869, 1884, 805, 930, 2390, 2819})
    Cs = Cb[sample_steps]  # (M, 15)

    rings_mission_ref = np.einsum("rdk,sk->srd", rings_ref, Cs)  # (M, 4, 6)
    d1_mission_ref = np.einsum("dk,sk->sd", d1_ref, Cs)          # (M, 6)

    # Initial guess for 7 sub-segments: [log10_ks, log10_kb, c_sb, log10_kz, log10_kt, c_zt]
    p0 = np.array([
        [2.0, 4.4,  0.0, 2.7, 3.3, 0.0],  # 0: D0->R0 (26.425 mm)
        [1.5, 3.4,  0.0, 1.0, 3.3, 0.0],  # 1: R0->G- (6.475 mm)
        [1.5, 3.4,  0.0, 1.0, 3.3, 0.0],  # 2: G-->R1 (7.025 mm)
        [1.5, 3.2,  0.0, 0.7, 3.3, 0.0],  # 3: R1->R2 (9.950 mm)
        [1.5, 3.4,  0.0, 1.0, 3.3, 0.0],  # 4: R2->G+ (7.025 mm)
        [1.5, 3.4,  0.0, 1.0, 3.3, 0.0],  # 5: G+->R3 (6.475 mm)
        [2.0, 4.4,  0.0, 2.7, 3.3, 0.0],  # 6: R3->D1 (22.425 mm)
    ])
    x0 = p0.ravel()
    lb = np.tile([-1.0, 1.0, -0.95, -0.5, 1.0, -0.8], 7)
    ub = np.tile([ 6.0, 7.0,  0.95,  6.0, 7.0,  0.8], 7)

    # Scale weights: translations in mm, rotations in rad*20 mm so both have comparable mm magnitude
    w_dof = np.array([1.0, 1.0, 1.0, 20.0, 20.0, 20.0])

    def resid(x):
        params = x.reshape(7, 6)
        rings, d1, _ = solve_linear_15(params, K_cad)
        rm = np.einsum("rdk,sk->srd", rings, Cs)
        dm = np.einsum("dk,sk->sd", d1, Cs)
        err_r = ((rm - rings_mission_ref) * w_dof[None, None, :]).ravel()
        err_d = ((dm - d1_mission_ref) * w_dof[None, :]).ravel()
        ei_x, ei_y = bare_EI(params)
        err_ei = np.array([(ei_x - ei_bare_ref) / ei_bare_ref * 100.0])
        return np.concatenate([err_r, err_d, err_ei])

    t0 = time.monotonic()
    sol = least_squares(resid, x0, bounds=(lb, ub), xtol=1e-12, ftol=1e-12, max_nfev=400)
    params = sol.x.reshape(7, 6)
    rings, d1, _ = solve_linear_15(params, K_cad)
    ei_x, ei_y = bare_EI(params)

    # Check mission accuracy on ALL 3,405 states!
    rm_all = np.einsum("rdk,sk->srd", rings, Cb)
    dm_all = np.einsum("dk,sk->sd", d1, Cb)
    rm_ref_all = np.einsum("rdk,sk->srd", rings_ref, Cb)
    dm_ref_all = np.einsum("dk,sk->sd", d1_ref, Cb)

    rot_deg = np.degrees(np.linalg.norm(S["end_rotvec"], axis=1))
    below15 = (rot_deg > 1.0) & (rot_deg < 15.0)
    err_pos_all = np.linalg.norm(rm_all[:, :, :3] - rm_ref_all[:, :, :3], axis=-1)
    ref_pos_all = np.linalg.norm(rm_ref_all[:, :, :3], axis=-1)
    err_rot_all = np.linalg.norm(rm_all[:, :, 3:] - rm_ref_all[:, :, 3:], axis=-1)
    ref_rot_all = np.linalg.norm(rm_ref_all[:, :, 3:], axis=-1)

    d1_err_pos = np.linalg.norm(dm_all[:, :3] - dm_ref_all[:, :3], axis=-1)
    d1_ref_pos = np.linalg.norm(dm_ref_all[:, :3], axis=-1)

    print(f"Calibration converged={sol.success} in {time.monotonic()-t0:.2f}s (nfev={sol.nfev})")
    print(f"Bare EI (85.8 mm): fitted={ei_x:.1f} vs ref={ei_bare_ref:.1f} N mm^2 (err={(ei_x-ei_bare_ref)/ei_bare_ref*100:+.3f}%)")
    print("Sub-segment local stiffness [k_s (N/mm), k_b (N mm/rad), c_sb, k_z (N/mm), k_t (N mm/rad), c_zt]:")
    for s in range(7):
        p = params[s]
        print(f"  Sub {s} (L={ELLS[s]:6.3f}): ks={10**p[0]:9.2f} kb={10**p[1]:10.1f} c_sb={p[2]:+.3f} kz={10**p[3]:8.2f} kt={10**p[4]:10.1f} c_zt={p[5]:+.3f}")
    print(f"All 3,405 states max ring pos err: {err_pos_all.max():.4f} mm (max ref {ref_pos_all.max():.2f} mm, rel {err_pos_all.max()/ref_pos_all.max()*100:.2f}%)")
    print(f"All 3,405 states max ring rot err: {np.degrees(err_rot_all.max()):.4f} deg (max ref {np.degrees(ref_rot_all.max()):.2f} deg, rel {err_rot_all.max()/ref_rot_all.max()*100:.2f}%)")
    print(f"All 3,405 states max D1 pos err:   {d1_err_pos.max():.4f} mm (max ref {d1_ref_pos.max():.2f} mm, rel {d1_err_pos.max()/d1_ref_pos.max()*100:.2f}%)")
    print(f"Below 15 deg ({below15.sum()} states) max ring pos err: {err_pos_all[below15].max():.4f} mm "
          f"(rel to step max: {(err_pos_all[below15].max(1)/np.maximum(ref_pos_all[below15].max(1), 1e-6)).max()*100:.2f}%)")
    print(f"Below 15 deg max ring rot err: {np.degrees(err_rot_all[below15].max()):.4f} deg "
          f"(rel to step max: {(err_rot_all[below15].max(1)/np.maximum(ref_rot_all[below15].max(1), 1e-6)).max()*100:.2f}%)")

    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)
    K_locals = np.stack([make_seg_K(params[s]) for s in range(7)], axis=0)
    np.savez(out / "frame_calibration.npz", params=params, K_locals=K_locals, z_nodes=Z_NODES, ells=ELLS)
    return params


if __name__ == "__main__":
    calibrate()
