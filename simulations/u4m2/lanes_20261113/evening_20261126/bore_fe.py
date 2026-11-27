"""Evening 2026-11-26, stage 1: CAD-consistent NiTi backbone attachment and hub-ring pose fields.

Why: the 26 Nov morning study (morning_20261126/backbone_strain.py) clamped the NiTi backbone at the
D0/D1 cut faces (z = -44.9 / +40.9 mm, free length 85.8 mm) and flagged a 4.25 mm backbone-to-ring_0
offset (> 3.30 mm radial clearance). The actual M6 CAD (M6_lane_anchorC.stl) carries the rod in
integral Ø1.85 mm sleeves over z = -48..-33 and +33..+48 mm (lane_design.json
rod_support_length_per_end_mm = 15, installation guide: "bond only the 15 mm at each end ... 66 mm
free to bend"). This script

1. measures the CAD central bore profile by ray casting from the axis (sleeve ends, hub-ring bores,
   minimum radial material distance between sleeves);
2. rebuilds the same q5 bonded solid body (G = 500 MPa, crown 0.06 mm) and solves the 15 kinematic
   unit fields (3 prescribed D1 rotations + 12 station wrench components) for
   (a) the morning backbone model (L = 85.8 mm beam on the D1 reference point), and
   (b) the CAD-consistent backbone: L = 66.0 mm, clamped at the D0 sleeve tip (0,0,-33) and the D1
       sleeve tip (0,0,+33), rigidly offset 7.9 mm from the D1 reference point (0,0,40.9);
3. extracts least-squares rigid poses (translation + small rotation) of the four hub-ring bore bands
   and the D1 master for every unit field, and the q5 hub strain at the governing steps, and saves a
   checkpoint consumed by bore_contact.py.

Linear small-strain FE only; the sleeves between the cut faces and z = +-33 are treated as rigid
parts of the D0/D1 masters (as in the morning model's central-post removal).
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("PYPARDISO_MKL_RT", "/usr/local/lib/libmkl_rt.so.3")
import numpy as np
import scipy.sparse as sp
import trimesh

HERE = Path(__file__).resolve().parent
MORN = HERE.parent / "morning_20261126"
PREV25 = HERE.parent / "evening_20261125"
PREV24 = HERE.parent / "evening_20261124"
for p in (MORN, PREV25, PREV24):
    sys.path.insert(0, str(p))
import backbone_strain as MB  # noqa: E402  (morning model; reused unchanged)
import body_solid as BS  # noqa: E402
import mission_envelope as ME  # noqa: E402
from strain_check import element_strain  # noqa: E402

OUT = HERE / "results"
SLEEVE_TIP = 33.0      # mm, CAD: Ø1.85 bore sleeve spans |z| = 33..48
L_FREE = 2 * SLEEVE_TIP
D1_REF_Z = BS.Z_HI     # 40.9 mm


def stamp():
    now = datetime.now(timezone.utc)
    return dict(et=now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z"),
                utc=now.strftime("%Y-%m-%d %H:%M:%S UTC"))


def cad_bore_profile(n_dir=36, dz=0.1):
    """Ray-cast from the axis outward: minimum radial distance to material vs z."""
    m = trimesh.load_mesh(BS.BODY)
    assert m.is_watertight
    zs = np.round(np.arange(-47.95, 47.951, dz), 4)
    ang = np.linspace(0, 2 * np.pi, n_dir, endpoint=False)
    d = np.c_[np.cos(ang), np.sin(ang), np.zeros(n_dir)]
    O = np.repeat(np.c_[np.zeros_like(zs), np.zeros_like(zs), zs], n_dir, 0)
    D = np.tile(d, (len(zs), 1))
    loc, iray, _ = m.ray.intersects_location(O, D, multiple_hits=True)
    rr = np.full(len(O), np.inf)
    dist = np.hypot(loc[:, 0], loc[:, 1])
    np.minimum.at(rr, iray, dist)
    rmin = rr.reshape(len(zs), n_dir).min(1)
    sleeve = zs[rmin < 1.0]
    free = (np.abs(zs) < SLEEVE_TIP - 0.05)
    return dict(z=zs, rmin=rmin), dict(
        sleeve_bore_radius_mm=float(rmin[rmin < 1.0].mean()),
        sleeve_z_extent_mm=[[float(sleeve[sleeve < 0].min()), float(sleeve[sleeve < 0].max())],
                            [float(sleeve[sleeve > 0].min()), float(sleeve[sleeve > 0].max())]],
        free_span_min_radius_mm=float(rmin[free].min()),
        free_span_min_radius_z_mm=float(zs[free][np.argmin(rmin[free])]),
        rays=int(len(O)), n_directions=n_dir, dz_mm=dz)


def sleeve_backbone_stiffness_d1():
    """6x6 backbone stiffness on D1 (about (0,0,40.9)) for a beam clamped at z=-33 and z=+33."""
    Kb = MB.backbone_stiffness_d1(L_FREE)  # beam-end DOFs at its own tip (0,0,+33), clamped at -33
    d = np.array([0.0, 0.0, SLEEVE_TIP - D1_REF_Z])  # -7.9 mm
    A = BS.rigid_rows(d[None, :], np.zeros(3))[0]
    Tr = np.zeros((6, 6)); Tr[:3, :] = A; Tr[3:, 3:] = np.eye(3)
    return Tr.T @ Kb @ Tr, Tr


def add_k(B, Kt, Kd1):
    c1 = B.c1
    gi, gj = np.meshgrid(np.arange(6) + c1, np.arange(6) + c1, indexing="ij")
    K = (Kt + sp.csr_matrix((Kd1.ravel(), (gi.ravel(), gj.ravel())), shape=Kt.shape)).tocsr()
    return 0.5 * (K + K.T)


def ring_pose_maps(B, U15):
    """(4,6,15) least-squares rigid (u, theta) of each hub-ring bore band about (0,0,z_mid)."""
    r = np.hypot(B.X[:, 0], B.X[:, 1])
    out = []
    for lo, hi in BS.RING_Z:
        m = np.flatnonzero((B.X[:, 2] >= lo) & (B.X[:, 2] <= hi) & (r < 8.6))
        A = BS.rigid_rows(B.X[m], np.r_[0.0, 0.0, 0.5 * (lo + hi)]).reshape(-1, 6)
        P = np.linalg.pinv(A)
        rows = (3 * m[:, None] + np.arange(3)).ravel()
        Tm = B.T[rows]
        out.append(P @ (Tm @ U15[:B.n]))
    return np.stack(out)


def main():
    t0 = time.monotonic(); started = stamp()
    OUT.mkdir(parents=True, exist_ok=True)
    prof, bore = cad_bore_profile()
    print("CAD bore:", json.dumps(bore), flush=True)

    S = np.load(PREV25 / "results/rod_steps.npz")
    n = len(S["end_rotvec"])
    phase = ME.phase_of(n)
    Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
    rhs15 = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]

    MB._install_safe_tet_mesh()
    B = MB.build_body(5.0, 0.4, 0.08, refine_passes=0)
    print("mesh", B.mesh["tets"], "tets", B.n, "reduced DOFs", flush=True)
    Kt = B.system(500.0, 0.06)
    K_morn = MB.backbone_stiffness_d1(MB.BB_L_CROP)
    K_cad, Tr = sleeve_backbone_stiffness_d1()
    res = {}
    store = {}
    for name, Kd1 in (("morning_L85p8", K_morn), ("cad_sleeve_L66", K_cad)):
        Ktot = add_k(B, Kt, Kd1)
        U15, resid = B.solve(Ktot, rhs15)
        rings = ring_pose_maps(B, U15)                  # (4,6,15)
        d1 = U15[B.c1:B.c1 + 6]                         # (6,15)
        store[f"{name}_rings"] = rings; store[f"{name}_d1"] = d1
        # moment split + hub strain at governing steps
        steps = {}
        for s in (1709, 1869, 1884):
            Ul = U15 @ Cb[s]
            u = (B.T @ Ul[:B.n]).reshape(-1, 3)
            eps, _ = element_strain(B.X, B.conn, u)
            pk = np.abs(np.linalg.eigvalsh(eps)).max(1)
            i = int(np.argmax(pk)); c = B.X[B.conn[i, :4]].mean(0)
            Mbb = (Kd1 @ Ul[B.c1:B.c1 + 6])[3:]
            Mbody = (Kt @ Ul)[B.c1 + 3:B.c1 + 6]
            steps[str(s)] = dict(phase=ME.PHASES[phase[s]], end_rot_deg=float(np.degrees(np.linalg.norm(S["end_rotvec"][s]))),
                                 peak_abs_principal_strain=float(pk[i]), peak_location_mm=c.tolist(),
                                 backbone_moment_share=float(np.linalg.norm(Mbb) / np.linalg.norm(Mbb + Mbody)),
                                 M_backbone_Nmm=float(np.linalg.norm(Mbb)), M_body_Nmm=float(np.linalg.norm(Mbody)))
        res[name] = dict(residual=resid, steps=steps)
        print(name, json.dumps(res[name]), flush=True)
    # equivalent stiffness (unit D1 moments, load controlled) for the CAD-consistent model
    for name, Kd1 in (("bare", np.zeros((6, 6))), ("morning_L85p8", K_morn), ("cad_sleeve_L66", K_cad)):
        Ktot = add_k(B, Kt, Kd1)
        Uu, _ = MB.solve_load_controlled(B, Ktot, [(np.eye(3)[i], np.zeros(12)) for i in range(2)])
        C = Uu[B.c1 + 3:B.c1 + 5, :]
        res.setdefault("equivalent_EI_over_85p8mm_Nmm2", {})[name] = [float(MB.BB_L_CROP / C[0, 0]), float(MB.BB_L_CROP / C[1, 1])]
    np.savez_compressed(OUT / "unit_poses.npz", bore_z=prof["z"], bore_rmin=prof["rmin"], **store,
                        ring_z=np.array(BS.RING_Z), Tr=Tr)
    rec = dict(task="Evening 2026-11-26 stage 1 (bore_fe.py)", started_et=started["et"], started_utc=started["utc"],
               completed_et=stamp()["et"], completed_utc=stamp()["utc"], elapsed_s=time.monotonic() - t0,
               mesh=dict(tets=int(B.mesh["tets"]), reduced_dofs=int(B.n), quality=5.0, max_vol=0.4),
               parameters=dict(G_MPa=500.0, crown_mm=0.06, sleeve_tip_z_mm=SLEEVE_TIP, L_free_mm=L_FREE,
                               morning_L_mm=MB.BB_L_CROP, d1_ref_z_mm=D1_REF_Z, backbone_EI_Nmm2=MB.BB_EI),
               cad_bore=bore, solves=res,
               versions=dict(numpy=np.__version__, scipy=__import__("scipy").__version__, trimesh=trimesh.__version__,
                             python=sys.version.split()[0]))
    json.dump(rec, open(OUT / "bore_fe.json", "w"), indent=1)
    print("done", rec["elapsed_s"], flush=True)


if __name__ == "__main__":
    main()
