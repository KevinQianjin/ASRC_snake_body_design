"""Whole-body solid (P2 tetrahedral) stiffness of the M6 module lattice — evening, 24 November 2026.

Stage 1 of handoff item 1 from the 23 November 2026 evening run: before any bond traction from
a solid rib model is trusted, its bare-body stiffness must reproduce the Round 2 plate/membrane
rib model (``rib_joint_3d.setup`` on ``M6_lane_anchorC.stl``: bare EI 46,708 N mm^2,
GJ 43,299 N mm^2) and be compared with the rod cell stiffness (EI ~ 64,700 N mm^2).

Geometry: the actual CAD ``cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl`` cropped with
capped planes at z = -44.9 mm (0.1 mm above the proximal disk face, z = -45 mm) and
z = +40.9 mm (0.1 mm below the distal anchor block, which starts at z ~ +41 mm). The crop splits
into three watertight bodies: the lattice (one connected body) and two central posts
(r < 3 mm, |z| > 33 mm) that touch only the end disks. The posts belong to the rigid D0/D1
masters of the plate model and are dropped. Nothing else is simplified.

Boundary conditions (the plate model's masters, transferred to 3D):
  D0  all lattice nodes on the z = -44.9 mm cut face: clamped;
  D1  all lattice nodes on the z = +40.9 mm cut face: one rigid body (6 DOF), loaded by a unit
      wrench; EI = 96 mm / rotation per unit moment, GJ likewise, EA = 96 mm / axial stretch
      (the plate model's 96 mm module-length convention; translations of D1 are free).
Variants:
  solid_rings      every other node is free (the CAD hub rings are elastic solid);
  rigid_rings      nodes with r < 8.6 mm inside the four plate-model ring bands
                   z in [-20,-16.95], [-6.5,-3.45], [3.45,6.5], [16.95,20] mm are tied to one
                   free rigid body per band (exactly the plate model's R0..R3 masters);
  rigid_rings_lands  additionally ties each rib's guide-land patch (|z -/+ 12| <= 0.25 mm,
                   15 < r < 24 mm, grouped by the nearest of the 8 rib angles) to its own free
                   rigid body, as the plate model's bare body does.

Linear elasticity, PA12 E = 1,530 MPa, nu = 0.4 (the Round 2 values). P2 (10-node) tetrahedra
from ``../evening_20261123/strut_fe.py``; direct solve with MKL PARDISO (pypardiso).
Outputs go only under ``results/`` of this folder.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import tetgen
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261123"))
import strut_fe as F  # noqa: E402

BODY = HERE / "../../../../cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl"
Z_LO, Z_HI = -44.9, 40.9
MODULE_L = 96.0
RING_Z = [(-20.0, -16.95), (-6.5, -3.45), (3.45, 6.5), (16.95, 20.0)]
RIBS = 22.5 + 45.0 * np.arange(8)
PLATE = dict(EI=46708.2520297896, GJ=43299.163436836294)  # Round 2 m6_support.json bare_body_Nmm2
ROD_EI = 5.394e3 * 12.0  # rod cell stiffness 5.394 N m/rad per 12 mm cell -> N mm^2


def lattice():
    m = trimesh.load_mesh(BODY)
    c = trimesh.intersections.slice_mesh_plane(m, [0, 0, 1], [0, 0, Z_LO], cap=True)
    c = trimesh.intersections.slice_mesh_plane(c, [0, 0, -1], [0, 0, Z_HI], cap=True)
    parts = sorted(c.split(only_watertight=False), key=lambda p: -p.volume)
    main = parts[0]
    info = dict(crop_bodies=len(parts), crop_volumes_mm3=[float(p.volume) for p in parts],
                lattice_watertight=bool(main.is_watertight), lattice_body_count=int(main.body_count),
                lattice_volume_mm3=float(main.volume), lattice_faces=len(main.faces),
                dropped_bounds_mm=[p.bounds.tolist() for p in parts[1:]])
    assert main.is_watertight and main.body_count == 1
    for p in parts[1:]:  # dropped parts must be the central posts (plate-model D0/D1 masters r < 3.3)
        assert np.hypot(*p.vertices[:, :2].T).max() < 3.3 and np.abs(p.vertices[:, 2]).min() > 30
    return main, info


def tet_mesh(solid, quality, max_vol):
    tg = tetgen.TetGen(np.asarray(solid.vertices, float), np.asarray(solid.faces, np.int32))
    nodes, tets = tg.tetrahedralize(switches=f"pq{quality}a{max_vol}Q")[:2]
    return np.asarray(nodes, float), np.asarray(tets, np.int64)


def assemble(X, conn, chunk=20000):
    K = None; vol = 0.0
    for i in range(0, len(conn), chunk):
        k, v = F.stiffness(X, conn[i:i + chunk]); vol += v
        K = k if K is None else K + k
    return K.tocsr(), vol


def rigid_rows(Xn, x0):
    """(n,3,6) map from rigid (U, Omega) about x0 to nodal displacement."""
    d = Xn - x0; n = len(Xn)
    A = np.zeros((n, 3, 6)); A[:, [0, 1, 2], [0, 1, 2]] = 1
    A[:, 0, 4], A[:, 0, 5] = d[:, 2], -d[:, 1]
    A[:, 1, 3], A[:, 1, 5] = -d[:, 2], d[:, 0]
    A[:, 2, 3], A[:, 2, 4] = d[:, 1], -d[:, 0]
    return A


def transform(X, groups, clamped):
    """Sparse T (3n x m): free nodes keep 3 DOFs, each rigid group gets 6, clamped nodes 0."""
    n = len(X); owner = -np.ones(n, int); owner[clamped] = -2
    for g, idx in enumerate(groups): owner[idx] = g
    free = np.flatnonzero(owner == -1)
    rows = list((3 * free[:, None] + np.arange(3)).ravel()); cols = list(range(3 * len(free))); vals = [1.0] * len(cols)
    base = 3 * len(free); gcol = []
    for g, idx in enumerate(groups):
        c0 = base + 6 * g; gcol.append(c0)
        A = rigid_rows(X[idx], np.r_[0.0, 0.0, X[idx, 2].mean()] if g else np.r_[0.0, 0.0, Z_HI])
        r = (3 * idx[:, None, None] + np.arange(3)[None, :, None]) + np.zeros((1, 1, 6), int)
        cc = c0 + np.zeros((len(idx), 3, 1), int) + np.arange(6)[None, None, :]
        nz = A != 0
        rows += list(r[nz]); cols += list(cc[nz]); vals += list(A[nz])
    m = base + 6 * len(groups)
    return sp.csr_matrix((vals, (rows, cols)), shape=(3 * n, m)), gcol


def run_variant(X, K, variant):
    r = np.hypot(X[:, 0], X[:, 1]); z = X[:, 2]; tol = 1e-6
    clamped = np.flatnonzero(np.abs(z - Z_LO) < tol)
    groups = [np.flatnonzero(np.abs(z - Z_HI) < tol)]  # D1 first (reference point (0,0,Z_HI))
    if variant in ("rigid_rings", "rigid_rings_lands"):
        groups += [np.flatnonzero((r < 8.6) & (z >= lo) & (z <= hi)) for lo, hi in RING_Z]
    if variant == "rigid_rings_lands":
        ang = np.degrees(np.arctan2(X[:, 1], X[:, 0]))
        rib = np.argmin(np.abs((ang[:, None] - RIBS[None, :] + 180) % 360 - 180), axis=1)
        for s in (-12.0, 12.0):
            band = (np.abs(z - s) <= 0.25 + 1e-9) & (r > 15) & (r < 24)
            groups += [np.flatnonzero(band & (rib == k)) for k in range(8) if (band & (rib == k)).any()]
    T, gcol = transform(X, groups, clamped)
    Kr = (T.T @ K @ T).tocsr(); Kr = 0.5 * (Kr + Kr.T)
    import pypardiso
    c = gcol[0]; Fm = np.zeros((Kr.shape[0], 6)); Fm[c:c + 6] = np.eye(6)
    t0 = time.monotonic()
    solver = pypardiso.PyPardisoSolver(); solver.set_matrix_type(2)  # real SPD
    Ku = sp.triu(Kr, format="csr"); Ku.eliminate_zeros(); Ku.sort_indices()
    U = solver.solve(Ku, Fm)  # PARDISO mtype 2 reads the upper triangle only
    t1 = time.monotonic() - t0
    resid = float(np.abs(Kr @ U - Fm).max())
    solver.free_memory(everything=True)
    C = U[c:c + 6]  # D1 compliance (6x6) at (0,0,Z_HI)
    out = dict(variant=variant, reduced_dofs=int(Kr.shape[0]), rigid_groups=len(groups),
               group_node_counts=[int(len(g)) for g in groups], clamped_nodes=int(len(clamped)),
               solve_s=t1, max_residual=resid,
               compliance_D1=C.tolist(),
               EIxx_Nmm2=MODULE_L / C[3, 3], EIyy_Nmm2=MODULE_L / C[4, 4], GJ_Nmm2=MODULE_L / C[5, 5],
               EA_N=MODULE_L / C[2, 2],
               symmetry_error=float(np.abs(C - C.T).max() / np.abs(C).max()))
    out["EI_mean_Nmm2"] = 0.5 * (out["EIxx_Nmm2"] + out["EIyy_Nmm2"])
    out["EI_over_plate"] = out["EI_mean_Nmm2"] / PLATE["EI"]
    out["GJ_over_plate"] = out["GJ_Nmm2"] / PLATE["GJ"]
    out["EI_over_rod"] = out["EI_mean_Nmm2"] / ROD_EI
    # bending-mode field for later reuse: D1 rotation about x (unit moment)
    u = (T @ U[:, 3]).reshape(-1, 3)
    out["unit_Mx_max_disp_mm"] = float(np.linalg.norm(u, axis=1).max())
    return out, u


def checks(X, conn, K, vol, solid_vol):
    """Rigid-body modes give zero force; uniform strain gives the exact strain energy."""
    n = len(X); A = rigid_rows(X, np.zeros(3)).transpose(0, 1, 2).reshape(3 * n, 6)
    rb = float(np.abs(K @ A).max() / np.abs(K).max())
    eps = np.array([[1e-3, 2e-4, 0], [2e-4, -4e-4, 3e-4], [0, 3e-4, 5e-4]])
    u = (X @ eps.T).ravel()
    lam = F.E_PA12 * F.NU_PA12 / ((1 + F.NU_PA12) * (1 - 2 * F.NU_PA12)); mu = F.E_PA12 / (2 * (1 + F.NU_PA12))
    W = vol * (0.5 * lam * np.trace(eps) ** 2 + mu * (eps * eps).sum())
    return dict(rigid_mode_force_rel=rb, uniform_strain_energy_rel_err=float(abs(0.5 * u @ (K @ u) - W) / W),
                mesh_volume_mm3=vol, cad_volume_mm3=solid_vol, volume_rel_err=abs(vol - solid_vol) / solid_vol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=float, default=5.0)
    ap.add_argument("--max-vol", type=float, nargs="+", default=[0.4])
    ap.add_argument("--variants", nargs="+", default=["solid_rings", "rigid_rings", "rigid_rings_lands"])
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--save-field", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    solid, info = lattice()
    doc = dict(scope=__doc__, body=str(BODY.relative_to(HERE.parents[3])),
               body_sha256=hashlib.sha256(BODY.read_bytes()).hexdigest(), crop=info,
               parameters=dict(vars(a), E_MPa=F.E_PA12, nu=F.NU_PA12, z_lo=Z_LO, z_hi=Z_HI, module_length_mm=MODULE_L,
                               ring_bands_mm=RING_Z),
               comparators=dict(plate_bare_EI_Nmm2=PLATE["EI"], plate_bare_GJ_Nmm2=PLATE["GJ"], rod_EI_Nmm2=ROD_EI,
                                plate_source="simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/m6_support.json"),
               meshes=[])
    for mv in a.max_vol:
        t0 = time.monotonic()
        v, t = tet_mesh(solid, a.quality, mv); X, conn = F.p2(v, t)
        K, vol = assemble(X, conn)
        rec = dict(max_tet_volume_mm3=mv, quality=a.quality, vertices=len(v), tets=len(t), p2_nodes=len(X), dofs=3 * len(X),
                   mesh_assemble_s=time.monotonic() - t0, checks=checks(X, conn, K, vol, solid.volume), variants=[])
        print(f"mesh a={mv}: {len(t)} tets, {3*len(X)} dofs, checks {rec['checks']}", flush=True)
        for var in a.variants:
            o, u = run_variant(X, K, var); rec["variants"].append(o)
            print(f"  {var:18s} EIxx {o['EIxx_Nmm2']:9.0f} EIyy {o['EIyy_Nmm2']:9.0f} GJ {o['GJ_Nmm2']:9.0f} EA {o['EA_N']:9.0f} "
                  f"EI/plate {o['EI_over_plate']:.3f} EI/rod {o['EI_over_rod']:.3f} GJ/plate {o['GJ_over_plate']:.3f} "
                  f"solve {o['solve_s']:.0f}s resid {o['max_residual']:.1e}", flush=True)
            if a.save_field and var == "solid_rings":
                np.savez_compressed(out / f"field_unitMx_a{mv}.npz", X=X.astype(np.float32), conn=conn.astype(np.int32),
                                    u=u.astype(np.float32))
        rec["elapsed_s"] = time.monotonic() - t0
        doc["meshes"].append(rec)
        (out / "body_stiffness.json").write_text(json.dumps(doc, indent=1, default=float))
        del K


if __name__ == "__main__":
    main()
