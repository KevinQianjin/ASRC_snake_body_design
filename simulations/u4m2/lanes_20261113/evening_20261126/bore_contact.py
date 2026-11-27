"""Evening 2026-11-26, stage 2: NiTi backbone vs hub-ring bore clearance and contact over the mission.

Inputs: results/unit_poses.npz (bore_fe.py; q5 bonded solid body, 15 kinematic unit fields) and the
archived 3,405-state mission evening_20261125/results/rod_steps.npz.

Three levels, all clearly labelled:
  L0  morning reproduction: cubic-Hermite backbone clamped at z=-44.9 / D1 ref (L=85.8 mm) vs
      mean ring-node displacement at the band mid-plane (exactly the morning metric).
  L1  linear, CAD-consistent: backbone clamped in the sleeves at z=-33 / +33 (L=66 mm), offset
      evaluated over the whole bore band (both band faces), ring pose = least-squares rigid fit.
  L2  geometrically nonlinear, CAD-consistent: body chain D0 -> R0..R3 -> D1 rebuilt by exact SO(3)
      composition of the per-segment linear relative poses (segment-wise corotational lift);
      backbone = discrete extensible elastica (h = 1.0 mm, EI, EA of the Ø1.8 mm, 40 GPa rod) clamped
      in both sleeves, with unilateral penalty contact against the four Ø8.40 mm ring bores (finite
      band length, ring-frame radial gap).  Reports gap, contact force, backbone bending strain.

The ring bores are the only material inside r < 5.5 mm in the free span (ray-cast profile,
bore_fe.json), so they are the only possible contact surfaces for the backbone.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import scipy.sparse as sp
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as Rot

HERE = Path(__file__).resolve().parent
PREV25 = HERE.parent / "evening_20261125"
sys.path.insert(0, str(PREV25)); sys.path.insert(0, str(HERE.parent / "evening_20261124"))
OUT = HERE / "results"

EI = 40000.0 * np.pi * 1.8 ** 4 / 64.0     # 20,612 N mm^2
EA = 40000.0 * np.pi * 1.8 ** 2 / 4.0      # 101,788 N
R_BB = 0.9
R_BORE = 4.2
C_RAD = R_BORE - R_BB                      # 3.30 mm radial clearance of the centreline
Z_TIP = 33.0
Z_LO, Z_HI = -44.9, 40.9
H = 1.0                                    # mm; h=0.5 at max_nfev=400 was under-converged (see convergence.py)
KC = 2.0e4                                 # N/mm contact penalty (per node)
PHASES = None
ARC_LIFT = True     # False reproduces the rejected plain linear-translation lift
AXIAL_FLOAT = True  # distal rod end free to slide along its sleeve axis (zero axial force)


def stamp():
    now = datetime.now(timezone.utc)
    return dict(et=now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z"),
                utc=now.strftime("%Y-%m-%d %H:%M:%S UTC"))


def cross_rows(theta, d):
    return np.cross(theta, d)


# ----------------------------------------------------------------------------- linear levels
def hermite(z, z0, L, u1, s1):
    xi = (z - z0) / L
    return (3 * xi ** 2 - 2 * xi ** 3) * u1 + (xi ** 3 - xi ** 2) * L * s1


def linear_offsets(rings, d1, ring_z, variant, nz=7):
    """rings (n,4,6), d1 (n,6) -> radial backbone-to-bore-axis offset (n,4) max over band."""
    n = len(d1)
    th1 = d1[:, 3:]
    if variant == "morning":
        z0, L = Z_LO, Z_HI - Z_LO
        u1 = d1[:, :3]
    else:
        z0, L = -Z_TIP, 2 * Z_TIP
        u1 = d1[:, :3] + cross_rows(th1, np.array([0, 0, Z_TIP - Z_HI]))
    s1 = np.c_[th1[:, 1], -th1[:, 0]]
    out = np.zeros((n, 4))
    for j, (lo, hi) in enumerate(ring_z):
        zm = 0.5 * (lo + hi)
        zz = [zm] if variant == "morning" else np.linspace(lo, hi, nz)
        best = np.zeros(n)
        for z in zz:
            bb = hermite(z, z0, L, u1[:, :2], s1)
            ring = rings[:, j, :3] + cross_rows(rings[:, j, 3:], np.array([0, 0, z - zm]))
            best = np.maximum(best, np.hypot(*(bb - ring[:, :2]).T))
        out[:, j] = best
    return out


# ----------------------------------------------------------------------------- nonlinear level
def chain_poses(rings, d1, ring_z):
    """Segment-wise corotational lift. Returns list of (R, p) for D0, R0..R3, D1 (ring centres)."""
    X = [np.r_[0, 0, Z_LO]] + [np.r_[0, 0, 0.5 * (lo + hi)] for lo, hi in ring_z] + [np.r_[0, 0, Z_HI]]
    U = [np.zeros(6)] + [rings[j] for j in range(4)] + [d1]
    R, p = [np.eye(3)], [X[0].copy()]
    for j in range(5):
        dX = X[j + 1] - X[j]; ell = dX[2]
        dth = U[j + 1][3:] - U[j][3:]
        du = U[j + 1][:3] - U[j][:3] - np.cross(U[j][3:], dX)
        if ARC_LIFT:
            # exact circular-arc chord of the bending part + linear residual (axial strain, shear offset)
            bend = np.r_[dth[0], dth[1], 0.0]; psi = np.linalg.norm(bend)
            resid = du - 0.5 * np.cross(dth, dX)
            if psi > 1e-12:
                nvec = bend / psi
                chord = ell * ((1 - np.cos(psi)) / psi * np.cross(nvec, [0, 0, 1.0]) + np.sin(psi) / psi * np.r_[0, 0, 1.0])
            else:
                chord = dX.copy()
            Rmid = Rot.from_rotvec(0.5 * dth).as_matrix()
            p.append(p[j] + R[j] @ (chord + Rmid @ resid))
        else:
            p.append(p[j] + R[j] @ (dX + du))
        R.append(R[j] @ Rot.from_rotvec(dth).as_matrix())
    return R, p


class Elastica:
    def __init__(self, h=H):
        self.N = int(round(2 * Z_TIP / h)); self.h = 2 * Z_TIP / self.N
        self.a, self.s = np.sqrt(EI / self.h), np.sqrt(EA / self.h)
        nv = self.N - 3  # free nodes 2..N-2
        self.nv = nv
        # Jacobian sparsity: tangent residual i (3) depends on nodes i-1..i+1, stretch on i..i+1
        m_t, m_s = 3 * (self.N - 1), self.N
        rows, cols = [], []
        def add(r, node):
            k = node - 2
            if 0 <= k < nv:
                for c in range(3):
                    rows.append(r); cols.append(3 * k + c)
        for i in range(1, self.N):            # tangent diff between edges i-1, i -> nodes i-1, i, i+1
            for c in range(3):
                for node in (i - 1, i, i + 1):
                    add(3 * (i - 1) + c, node)
        for e in range(self.N):
            for node in (e, e + 1):
                add(m_t + e, node)
        self.m_t, self.m_s = m_t, m_s
        self.base_rows, self.base_cols = rows, cols

    def setup(self, pA, tA, pB, tB, bores):
        self.ends = (pA, pA + self.h * tA, pB - self.h * tB, pB)
        self.bores = bores  # list of (R, p, zlo, zhi) local
        nc = (self.N + 1) * len(bores)
        rows, cols = list(self.base_rows), list(self.base_cols)
        r0 = self.m_t + self.m_s
        for b in range(len(bores)):
            for node in range(self.N + 1):
                k = node - 2
                if 0 <= k < self.nv:
                    for c in range(3):
                        rows.append(r0 + b * (self.N + 1) + node); cols.append(3 * k + c)
        ncol = 3 * self.nv + (1 if AXIAL_FLOAT else 0)
        if AXIAL_FLOAT:
            for r in range(r0 + nc):
                rows.append(r); cols.append(ncol - 1)
        self.sparsity = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(r0 + nc, ncol)).tocsr()
        self.sparsity.data[:] = 1
        self.tB = tB

    def nodes(self, v):
        a0, a1, b1, b0 = self.ends
        if AXIAL_FLOAT:
            sh = v[-1] * self.tB
            return np.vstack([a0, a1, v[:-1].reshape(-1, 3), b1 + sh, b0 + sh])
        return np.vstack([a0, a1, v.reshape(-1, 3), b1, b0])

    def residual(self, v, contact=True):
        x = self.nodes(v)
        e = np.diff(x, axis=0); le = np.linalg.norm(e, axis=1); t = e / le[:, None]
        r_t = self.a * np.diff(t, axis=0).ravel()
        r_s = self.s * (le - self.h)
        res = [r_t, r_s]
        for (R, p, zlo, zhi) in self.bores:
            q = (x - p) @ R
            rho = np.hypot(q[:, 0], q[:, 1])
            inside = (q[:, 2] >= zlo) & (q[:, 2] <= zhi)
            pen = np.where(inside, np.maximum(rho - C_RAD, 0.0), 0.0)
            res.append(np.sqrt(KC) * pen if contact else 0 * pen)
        return np.concatenate(res)

    def solve(self, v0, contact=True):
        sol = least_squares(self.residual, v0, jac_sparsity=self.sparsity, method="trf", x_scale="jac",
                            xtol=1e-12, ftol=1e-12, gtol=1e-10, max_nfev=400, kwargs=dict(contact=contact))
        return sol

    def guess(self, pA, tA, pB, tB):
        L = 2 * Z_TIP
        s = np.linspace(0, 1, self.N + 1)[2:-2, None]
        h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
        h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        g = (h00 * pA + h10 * L * tA + h01 * pB + h11 * L * tB).ravel()
        return np.r_[g, 0.0] if AXIAL_FLOAT else g

    def report(self, v):
        x = self.nodes(v)
        e = np.diff(x, axis=0); le = np.linalg.norm(e, axis=1); t = e / le[:, None]
        dphi = np.arccos(np.clip((t[1:] * t[:-1]).sum(1), -1, 1))
        kappa = dphi / self.h
        out = dict(max_bending_strain=float(R_BB * kappa.max()), mean_bending_strain=float(R_BB * kappa.mean()),
                   axial_float_mm=float(v[-1]) if AXIAL_FLOAT else 0.0,
                   max_axial_strain=float(np.abs(le / self.h - 1).max()), bores=[])
        for (R, p, zlo, zhi) in self.bores:
            q = (x - p) @ R
            inside = (q[:, 2] >= zlo) & (q[:, 2] <= zhi)
            rho = np.hypot(q[:, 0], q[:, 1])
            # continuous band check: interpolate the polyline at fine resolution inside the band
            ss = np.linspace(0, 1, 9)[:, None, None]
            seg = q[:-1][None] + ss * (q[1:] - q[:-1])[None]
            segm = seg.reshape(-1, 3)
            ins = (segm[:, 2] >= zlo) & (segm[:, 2] <= zhi)
            rho_f = np.hypot(segm[ins, 0], segm[ins, 1])
            pen = np.where(inside, np.maximum(rho - C_RAD, 0), 0)
            Fv = KC * pen
            out["bores"].append(dict(max_offset_mm=float(rho_f.max()), gap_mm=float(C_RAD - rho_f.max()),
                                     contact_force_N=float(Fv.sum()), contact_nodes=int((pen > 0).sum())))
        return out


def nonlinear_state(el, rings, d1, ring_z, contact=True):
    R, p = chain_poses(rings, d1, ring_z)
    RB, pB0 = R[-1], p[-1]
    pA, tA = np.r_[0, 0, -Z_TIP], np.r_[0, 0, 1.0]
    tB = RB[:, 2]; pB = pB0 + RB @ np.r_[0, 0, Z_TIP - Z_HI]
    bores = [(R[j + 1], p[j + 1], lo - 0.5 * (lo + hi), hi - 0.5 * (lo + hi)) for j, (lo, hi) in enumerate(ring_z)]
    el.setup(pA, tA, pB, tB, bores)
    v0 = el.guess(pA, tA, pB, tB)
    free = el.solve(v0, contact=False)
    rep_free = el.report(free.x)
    rec = dict(D1_rot_deg=float(np.degrees(np.linalg.norm(Rot.from_matrix(RB).as_rotvec()))),
               chord_mm=float(np.linalg.norm(pB - pA)), free=rep_free, free_status=int(free.status))
    if contact and min(b["gap_mm"] for b in rep_free["bores"]) < 0:
        con = el.solve(free.x, contact=True)
        rec["contact"] = el.report(con.x); rec["contact_status"] = int(con.status)
    return rec


_EL = None


def _worker(rings, d1, ring_z):
    global _EL
    if _EL is None:
        _EL = Elastica()
    return nonlinear_state(_EL, rings, d1, ring_z)


def verify_arc(el):
    """Analytic check: pure-bending circular arc (end pose on an arc of length 66 mm) must be exact."""
    out = {}
    for deg in (20.0, 47.0, 60.0):
        th = np.radians(deg); L = 2 * Z_TIP; Rr = L / th
        pA, tA = np.r_[0, 0, -Z_TIP], np.r_[0, 0, 1.0]
        pB = pA + np.r_[Rr * (1 - np.cos(th)), 0, Rr * np.sin(th)]
        tB = np.r_[np.sin(th), 0, np.cos(th)]
        el.setup(pA, tA, pB, tB, [])
        sol = el.solve(el.guess(pA, tA, pB, tB), contact=False)
        x = el.nodes(sol.x)
        c = pA + np.r_[Rr, 0, 0]
        dev = np.abs(np.hypot(x[:, 0] - c[0], x[:, 2] - c[2]) - Rr).max()
        rep = el.report(sol.x)
        out[f"{deg:.0f}deg"] = dict(max_radius_error_mm=float(dev), max_bending_strain=rep["max_bending_strain"],
                                    analytic_strain=float(R_BB / Rr))
    return out


def main():
    t0 = time.monotonic(); st = stamp()
    import mission_envelope as ME
    P = np.load(OUT / "unit_poses.npz")
    S = np.load(PREV25 / "results/rod_steps.npz")
    n = len(S["end_rotvec"]); phase = ME.phase_of(n)
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    ring_z = [tuple(r) for r in P["ring_z"]]
    res = dict(task="Evening 2026-11-26 stage 2 (bore_contact.py)", started_et=st["et"], started_utc=st["utc"],
               parameters=dict(EI_Nmm2=EI, EA_N=EA, backbone_radius_mm=R_BB, bore_radius_mm=R_BORE,
                               radial_clearance_mm=C_RAD, sleeve_tip_z_mm=Z_TIP, h_mm=H, contact_penalty_N_per_mm=KC,
                               states=int(n)))
    lin = {}
    for var, key in (("morning", "morning_L85p8"), ("cad", "cad_sleeve_L66")):
        rings = np.einsum("jkc,nc->njk", P[f"{key}_rings"], Cb)
        d1 = Cb @ P[f"{key}_d1"].T
        off = linear_offsets(rings, d1, ring_z, var)
        lin[var] = dict(off=off, rings=rings, d1=d1)
        res[f"L{0 if var == 'morning' else 1}_linear_{var}"] = dict(
            per_ring_max_offset_mm=off.max(0).tolist(), per_ring_argmax_step=off.argmax(0).tolist(),
            max_offset_mm=float(off.max()), states_exceeding_clearance=int((off.max(1) > C_RAD).sum()),
            step_1869=off[1869].tolist(), step_1709=off[1709].tolist(), min_gap_mm=float(C_RAD - off.max()))
        print(var, res[f"L{0 if var == 'morning' else 1}_linear_{var}"], flush=True)

    el = Elastica()
    res["L2_verification_circular_arc"] = verify_arc(el)
    print("arc check", res["L2_verification_circular_arc"], flush=True)
    # nonlinear: CAD-consistent model; stride over the full mission + governing states
    ROT = np.degrees(np.linalg.norm(S["end_rotvec"], axis=1))
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    off = lin["cad"]["off"].max(1)
    must = set(np.argsort(off)[-40:].tolist()) | {1709, 1869, 1884} | set(np.argsort(ROT)[-20:].tolist())
    for p_ in range(phase.max() + 1):
        idx = np.flatnonzero(phase == p_); must.add(int(idx[np.argmax(off[idx])]))
    steps = sorted(set(range(0, n, stride)) | must)
    t1 = time.monotonic()
    from multiprocessing import Pool
    jobs = [(lin["cad"]["rings"][s], lin["cad"]["d1"][s], ring_z) for s in steps]
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 4) as pool:
        out = pool.starmap(_worker, jobs, chunksize=4)
    rows = [dict(step=int(s), phase=ME.PHASES[phase[s]], end_rot_deg=float(ROT[s]),
                 linear_offsets_mm=lin["cad"]["off"][s].tolist(), **r) for s, r in zip(steps, out)]
    print("nonlinear states", len(rows), "in", round(time.monotonic() - t1, 1), "s", flush=True)
    gmin = np.array([min(b["gap_mm"] for b in r["free"]["bores"]) for r in rows])
    i = int(np.argmin(gmin))
    per_ring = np.array([[b["gap_mm"] for b in r["free"]["bores"]] for r in rows])
    strain = np.array([r["free"]["max_bending_strain"] for r in rows])
    res["L2_nonlinear_cad"] = dict(
        states_evaluated=len(rows), stride=stride, coverage="all 11 mission phases (stride + 40 largest L1 offsets + 20 largest rotations + per-phase L1 maxima + steps 1709/1869/1884)",
        min_gap_mm=float(gmin.min()), min_gap_step=rows[i]["step"], min_gap_phase=rows[i]["phase"],
        per_ring_min_gap_mm=per_ring.min(0).tolist(), per_ring_min_gap_step=[rows[j]["step"] for j in per_ring.argmin(0)],
        states_in_contact=int((gmin < 0).sum()),
        max_contact_force_N=float(max([sum(b["contact_force_N"] for b in r["contact"]["bores"]) for r in rows if "contact" in r] or [0.0])),
        max_backbone_bending_strain=float(strain.max()), max_strain_step=rows[int(strain.argmax())]["step"],
        max_D1_rotation_lift_error_deg=float(max(abs(r["D1_rot_deg"] - r["end_rot_deg"]) for r in rows)),
        governing=[r for r in rows if r["step"] in (1709, 1869, 1884, rows[i]["step"])])
    res["completed_et"], res["completed_utc"] = stamp()["et"], stamp()["utc"]
    res["elapsed_s"] = time.monotonic() - t0
    json.dump(res, open(OUT / "bore_contact.json", "w"), indent=1)
    np.savez_compressed(OUT / "bore_contact_rows.npz", step=[r["step"] for r in rows], gap=per_ring,
                        strain=strain, rot=[r["end_rot_deg"] for r in rows],
                        lin_cad=lin["cad"]["off"], lin_morning=lin["morning"]["off"])
    print(json.dumps({k: v for k, v in res["L2_nonlinear_cad"].items() if k != "governing"}, indent=1))


if __name__ == "__main__":
    main()
