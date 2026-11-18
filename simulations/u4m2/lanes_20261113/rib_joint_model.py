"""Rib-level (strut-level) linear model of the M-module guide joint at z = +/-12 mm.

The M body is eight identical planar radial ribs (45 deg pitch, rib mid-planes at
22.5 + 45 k deg) joined only by the two end disks and four small inner rings.
This script

1. cuts the actual CAD body along one rib mid-plane (r-z plane);
2. measures the rib's tangential thickness at every element by ray casting the
   3D CAD;
3. meshes the rib with constant-strain triangles (plane stress, variable
   thickness) and condenses it onto rigid master bodies (disks, rings and,
   optionally, the four bonded guide lands at z = +/-12 mm);
4. assembles the eight ribs in 3D (in-plane rib stiffness only) and solves
   pure-moment and axial load cases;
5. compares the land incompatibility a rigid guide must absorb with the
   homogenised plane-section estimate used by the 16 Nov compatibility screen.

Assumptions (also written to the output JSON): linear elasticity and small
rotations, isotropic PA12, rigid disks/rings/guides, rib out-of-plane
(tangential) stiffness neglected, bond rigid when 'bonded'. Results per unit
curvature are scaled linearly to the record-146 curvature; the module's
global rotation at that curvature (~1.7 rad over 96 mm) is far outside the
linear range, so these are first-order local estimates, not a nonlinear FE.
"""
import argparse, json, time, hashlib
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import trimesh, shapely.geometry as sg, triangle

HERE = Path(__file__).resolve().parent
BODY = HERE / '../../../cad/lanes_u4m2/end_bellmouth_v1/M5_lane_anchorB.stl'
MODULE_L = 96.0
DB_EI_Nmm2 = 0.0441178e6   # data/materials/module_stiffness.sqlite3, middle_stiffness_pa12 (N m^2 -> N mm^2)
DB_EA_N = 166.694
MOUNT_ANGLES = (-22.5, 67.5, 157.5, 247.5)
LAND_HALF = 0.25
SOCKET_HALF = 1.62


def rib_polygon(mesh, th_deg):
    th = np.radians(th_deg)
    e_r = np.array([np.cos(th), np.sin(th), 0.]); e_z = np.array([0, 0, 1.])
    n = np.cross(e_r, e_z)   # = -e_theta
    T = np.eye(4); T[:3, :3] = np.vstack([e_r, e_z, n])
    s = mesh.section(plane_origin=[0, 0, 0], plane_normal=n)
    pl, _ = s.to_2D(to_2D=T)
    polys = [p for p in pl.polygons_full if p.representative_point().x > 0]
    return max(polys, key=lambda p: p.area), e_r, e_z, n


def mesh_polygon(poly, max_area):
    verts, segs, holes = [], [], []
    def add_ring(coords):
        c = np.asarray(coords)[:-1]; i0 = len(verts); verts.extend(c.tolist())
        k = len(c); segs.extend([[i0 + j, i0 + (j + 1) % k] for j in range(k)])
    add_ring(poly.exterior.coords)
    for r in poly.interiors:
        add_ring(r.coords); holes.append(list(sg.Polygon(r).representative_point().coords[0]))
    A = dict(vertices=np.array(verts), segments=np.array(segs))
    if holes: A['holes'] = np.array(holes)
    t = triangle.triangulate(A, f'pq30a{max_area}')
    return t['vertices'], t['triangles']


def thickness(mesh, pts2, e_r, e_z, n):
    P = np.outer(pts2[:, 0], e_r) + np.outer(pts2[:, 1], e_z)
    d = []
    for sgn in (1., -1.):
        dirs = np.tile(sgn * n, (len(P), 1))
        loc, idx, _ = mesh.ray.intersects_location(P, dirs, multiple_hits=False)
        dist = np.full(len(P), np.nan); dist[idx] = np.linalg.norm(loc - P[idx], axis=1)
        d.append(dist)
    return d[0] + d[1]


def cst_stiffness(X, T, t, E, nu):
    D = E / (1 - nu**2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    rows, cols, vals = [], [], []
    for e, tri in enumerate(T):
        x, y = X[tri, 0], X[tri, 1]
        A2 = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        b = np.array([y[1] - y[2], y[2] - y[0], y[0] - y[1]]) / A2
        c = np.array([x[2] - x[1], x[0] - x[2], x[1] - x[0]]) / A2
        B = np.zeros((3, 6)); B[0, 0::2] = b; B[1, 1::2] = c; B[2, 0::2] = c; B[2, 1::2] = b
        k = B.T @ D @ B * (abs(A2) / 2 * t[e])
        dof = np.ravel(np.c_[2 * tri, 2 * tri + 1])
        rows.append(np.repeat(dof, 6)); cols.append(np.tile(dof, 6)); vals.append(k.ravel())
    n = 2 * len(X)
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))


def condense(K, X, masters):
    """masters: list of (name, node_mask, (r0, z0)). Returns Kc, recovery operator, tie T."""
    n = len(X); owner = -np.ones(n, int)
    for m, (_, mask, _) in enumerate(masters):
        assert not (owner[mask] >= 0).any(), 'overlapping masters'
        owner[mask] = m
    free = np.where(owner < 0)[0]; nm = 3 * len(masters)
    # full-dof transformation u = Tr @ [u_free; q]
    rows, cols, vals = [], [], []
    for j, i in enumerate(free):
        rows += [2 * i, 2 * i + 1]; cols += [2 * j, 2 * j + 1]; vals += [1., 1.]
    nf = 2 * len(free)
    for m, (_, mask, (r0, z0)) in enumerate(masters):
        for i in np.where(mask)[0]:
            c = nf + 3 * m
            rows += [2 * i, 2 * i, 2 * i + 1, 2 * i + 1]; cols += [c, c + 2, c + 1, c + 2]
            vals += [1., -(X[i, 1] - z0), 1., X[i, 0] - r0]
    Tr = sp.csr_matrix((vals, (rows, cols)), shape=(2 * n, nf + nm))
    Kr = (Tr.T @ K @ Tr).tocsc()
    Kff = Kr[:nf, :nf]; Kfm = Kr[:nf, nf:].toarray(); Kmm = Kr[nf:, nf:].toarray()
    lu = spla.splu(Kff)
    Xf = lu.solve(Kfm)
    Kc = Kmm - Kfm.T @ Xf
    def recover(q):
        uf = -Xf @ q
        return (Tr @ np.r_[uf, q]).reshape(-1, 2)
    return 0.5 * (Kc + Kc.T), recover


def projection(theta_deg, r0, z0, zc):
    th = np.radians(theta_deg)
    e_r = np.array([np.cos(th), np.sin(th), 0.]); e_t = np.array([-np.sin(th), np.cos(th), 0.]); e_z = np.array([0, 0, 1.])
    d = r0 * e_r + (z0 - zc) * e_z
    P = np.zeros((3, 6))
    P[0, :3] = e_r; P[0, 3:] = np.cross(d, e_r)        # e_r.(w x d) = w.(d x e_r)
    P[1, :3] = e_z; P[1, 3:] = np.cross(d, e_z)
    P[2, 3:] = -e_t
    return P


def _rows(Xp, Er):
    """Rows mapping a small rigid motion (t, w) to in-plane (radial, axial) point displacements."""
    A = np.zeros((2 * len(Xp), 6)); ez = np.array([0, 0, 1.])
    for i, (x, er) in enumerate(zip(Xp, Er)):
        A[2 * i, :3] = er; A[2 * i, 3:] = np.cross(x, er)       # er.(w x x) = w.(x x er)
        A[2 * i + 1, :3] = ez; A[2 * i + 1, 3:] = np.cross(x, ez)
    return A


def rigid_fit(Xp, Er, U2):
    """Least-squares small rigid motion fitted to in-plane (u_r, u_z) only.

    Rib out-of-plane displacement is not modelled, so tangential components are
    excluded from the fit and from the residual. Returns (residual (n,2), sol).
    """
    A = _rows(Xp, Er)
    sol, *_ = np.linalg.lstsq(A, U2.ravel(), rcond=None)
    return (U2.ravel() - A @ sol).reshape(-1, 2), sol


def to3d(theta_deg, X2):
    th = np.radians(theta_deg); e_r = np.array([np.cos(th), np.sin(th), 0.]); e_z = np.array([0, 0, 1.])
    return np.outer(X2[:, 0], e_r) + np.outer(X2[:, 1], e_z), np.tile(e_r, (len(X2), 1))


def run(max_area, E, nu, kappa, psi_list, out):
    t0 = time.monotonic()
    body = trimesh.load(BODY)
    poly, e_r, e_z, n = rib_polygon(body, 22.5)
    X, T = mesh_polygon(poly, max_area)
    cen = X[T].mean(axis=1)
    t = thickness(body, cen, e_r, e_z, n)
    r, z = X[:, 0], X[:, 1]
    # ring windows measured from the inter-rib (theta = 0 deg) section
    ring_z = [(-20.0, -16.95), (-6.5, -3.45), (3.45, 6.5), (16.95, 20.0)]
    def ring(lo, hi): return (r < 8.6) & (z >= lo) & (z <= hi)
    masters = [('D0', (z <= -45.0) | ((r < 3.3) & (z < -30))), ('D1', (z >= 45.0) | ((r < 3.3) & (z > 30)))]
    masters += [(f'R{k}', ring(*w)) for k, w in enumerate(ring_z)]
    land = {s: (np.abs(z - s) <= LAND_HALF + 1e-9) & (r > 15) & (r < 24) for s in (-12., 12.)}
    socket = {s: (np.abs(z - s) <= SOCKET_HALF) & (r > 13) & (r < 26) for s in (-12., 12.)}
    with_ref = lambda ms: [(nm, mk, (X[mk, 0].mean(), X[mk, 1].mean())) for nm, mk in ms]
    mA = with_ref(masters); mB = with_ref(masters + [('G-12', land[-12.]), ('G+12', land[12.])])
    tt = np.nan_to_num(t, nan=0.0)
    deform = ~np.any([np.all(np.stack([mk[T[:, j]] for j in range(3)]), axis=0) for _, mk, _ in mB], axis=0)
    K = cst_stiffness(X, T, np.where(np.isfinite(t), t, 3.0), E, nu)
    KcA, recA = condense(K, X, mA)
    KcB, recB = condense(K, X, mB)
    bodies = ['D0', 'D1', 'R0', 'R1', 'R2', 'R3', 'G-12', 'G+12']
    zc = {nm: ref[1] for nm, _, ref in mB}
    def solve(bonded, load):
        nb = len(bodies) if bonded else 6
        Kg = np.zeros((6 * nb, 6 * nb))
        for k in range(8):
            th = 22.5 + 45 * k
            mount = any(np.isclose((th - a) % 360, 0) for a in MOUNT_ANGLES)
            ms, Kc = (mB, KcB) if (bonded and mount) else (mA, KcA)
            P = np.zeros((3 * len(ms), 6 * nb))
            for j, (nm, _, (r0, z0)) in enumerate(ms):
                b = bodies.index(nm)
                P[3 * j:3 * j + 3, 6 * b:6 * b + 6] = projection(th, r0, z0, zc[nm])
            Kg += P.T @ Kc @ P
        fixed = list(range(6)) + [6 * b + 5 for b in range(nb)]   # D0 clamped; torsion about z removed
        fr = np.setdiff1d(np.arange(6 * nb), fixed)
        F = np.zeros(6 * nb); F[6:12] = load
        q = np.zeros(6 * nb); q[fr] = np.linalg.solve(Kg[np.ix_(fr, fr)], F[fr])
        return q, Kg
    def rib_disp(bonded, q, th):
        mount = any(np.isclose((th - a) % 360, 0) for a in MOUNT_ANGLES)
        ms, rec = (mB, recB) if (bonded and mount) else (mA, recA)
        qq = np.concatenate([projection(th, r0, z0, zc[nm]) @ q[6 * bodies.index(nm):6 * bodies.index(nm) + 6]
                             for nm, _, (r0, z0) in ms])
        return rec(qq), ms
    res = dict(mesh=dict(max_triangle_area_mm2=max_area, nodes=len(X), triangles=len(T),
                         rib_polygon_area_mm2=poly.area),
               thickness_mm=dict(strut_at_z12=float(np.nanmedian(t[(np.abs(cen[:, 1] - 12) < 1.6) & (cen[:, 0] > 14) & (cen[:, 0] < 25)])),
                                 deformable_median=float(np.nanmedian(t[deform])),
                                 deformable_min=float(np.nanmin(t[deform])), deformable_max=float(np.nanmax(t[deform])),
                                 missing_rays=int(np.isnan(t).sum())))
    # axial
    qa, _ = solve(False, np.array([0, 0, 1., 0, 0, 0]))
    EA = MODULE_L / qa[6 + 2]
    qab, _ = solve(True, np.array([0, 0, 1., 0, 0, 0]))
    res['axial'] = dict(EA_free_N=EA, EA_bonded_N=MODULE_L / qab[6 + 2])
    cases = []
    for psi in psi_list:
        a = np.array([np.cos(np.radians(psi)), np.sin(np.radians(psi)), 0.])
        row = dict(bending_axis_deg=psi)
        for bonded in (False, True):
            q, _ = solve(bonded, np.r_[0, 0, 0, a])
            phi = a @ q[9:12]; EI = MODULE_L / phi
            s = kappa * MODULE_L / phi          # scale so mean curvature = kappa
            q = q * s
            tag = 'bonded' if bonded else 'free'
            row[f'EI_{tag}_Nmm2'] = EI
            for st in (12., -12.):
                LX, LE, LU, SX, SE, SU = [], [], [], [], [], []
                for th in MOUNT_ANGLES:
                    U, _ = rib_disp(bonded, q, th)
                    x3, e3 = to3d(th, X[land[st]]); LX.append(x3); LE.append(e3); LU.append(U[land[st]])
                    x3, e3 = to3d(th, X[socket[st]]); SX.append(x3); SE.append(e3); SU.append(U[socket[st]])
                LX, LE, LU, SX, SE, SU = map(np.vstack, (LX, LE, LU, SX, SE, SU))
                resid, sol = rigid_fit(LX, LE, LU)
                # socket-span motion relative to the land rigid fit (= guide motion when bonded)
                srel = (SU.ravel() - _rows(SX, SE) @ sol).reshape(-1, 2)
                d = dict(land_residual_max_mm=float(np.linalg.norm(resid, axis=1).max()),
                         land_residual_axial_max_mm=float(np.abs(resid[:, 1]).max()),
                         socket_relative_max_mm=float(np.linalg.norm(srel, axis=1).max()),
                         socket_relative_axial_max_mm=float(np.abs(srel[:, 1]).max()),
                         socket_relative_radial_max_mm=float(np.abs(srel[:, 0]).max()))
                if bonded:
                    loads = []
                    for th in MOUNT_ANGLES:
                        P = projection(th, *[ref for nm, _, ref in mB if nm == f'G{st:+.0f}'][0], zc[f'G{st:+.0f}'])
                        j = [nm for nm, _, _ in mB].index(f'G{st:+.0f}')
                        qq = np.concatenate([projection(th, r0, z0, zc[nm]) @ q[6 * bodies.index(nm):6 * bodies.index(nm) + 6]
                                             for nm, _, (r0, z0) in mB])
                        f = KcB[3 * j:3 * j + 3] @ qq
                        loads.append(dict(rib_deg=th, radial_N=float(f[0]), axial_N=float(f[1]), inplane_moment_Nmm=float(f[2])))
                    d['land_loads'] = loads
                if not bonded:
                    # homogenised plane-section field on the same land points
                    # homogenised plane-section field (section rotation kappa*dz about a) on the same points
                    hom = np.c_[np.zeros(len(LX)), kappa * (LX[:, 2] - st) * (a[0] * LX[:, 1] - a[1] * LX[:, 0])]
                    hres, _ = rigid_fit(LX, LE, hom)
                    d['homogenised_land_residual_axial_max_mm'] = float(np.abs(hres[:, 1]).max())
                    homS = np.c_[np.zeros(len(SX)), kappa * (SX[:, 2] - st) * (a[0] * SX[:, 1] - a[1] * SX[:, 0])]
                    _, hsol = rigid_fit(LX, LE, hom)
                    hs = (homS.ravel() - _rows(SX, SE) @ hsol).reshape(-1, 2)
                    d['homogenised_socket_relative_axial_max_mm'] = float(np.abs(hs[:, 1]).max())
                row[f'{tag}_z{st:+.0f}'] = d
        cases.append(row)
    res['bending'] = cases
    res['elapsed_s'] = time.monotonic() - t0
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--areas', type=float, nargs='+', default=[0.02, 0.01])
    ap.add_argument('--E', type=float, default=1700.0, help='nominal PA12 modulus, MPa (calibrated afterwards)')
    ap.add_argument('--nu', type=float, default=0.4)
    ap.add_argument('--kappa', type=float, default=0.01748791036298669, help='record 146 M5 curvature, rad/mm')
    ap.add_argument('--psi', type=float, nargs='+', default=[0, 11.25, 22.5, 33.75, 45, 67.5, 90])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    runs = [run(A, a.E, a.nu, a.kappa, a.psi, out) for A in a.areas]
    doc = dict(scope=__doc__, body=str(BODY.relative_to(HERE.parent.parent.parent) if False else '../../../cad/lanes_u4m2/end_bellmouth_v1/M5_lane_anchorB.stl'),
               body_sha256=hashlib.sha256(BODY.read_bytes()).hexdigest(),
               parameters=dict(E_nominal_MPa=a.E, nu=a.nu, kappa_rad_per_mm=a.kappa, module_length_mm=MODULE_L,
                               land_half_mm=LAND_HALF, socket_half_mm=SOCKET_HALF, mount_rib_angles_deg=MOUNT_ANGLES,
                               database_EI_Nmm2=DB_EI_Nmm2, database_EA_N=DB_EA_N),
               runs=runs)
    (out / 'rib_joint_results.json').write_text(json.dumps(doc, indent=1, default=float))
    for rr in runs:
        print('mesh', rr['mesh'], 'thk', rr['thickness_mm'], 'axial', rr['axial'], f"{rr['elapsed_s']:.0f}s")
        for c in rr['bending']:
            print(' psi', c['bending_axis_deg'], 'EI free/bonded', round(c['EI_free_Nmm2']), round(c['EI_bonded_Nmm2']),
                  'free+12', {k: round(v, 4) for k, v in c['free_z+12'].items()},
                  'bonded+12', {k: round(v, 4) for k, v in c['bonded_z+12'].items() if k != 'land_loads'},
                  'loads+12', [(round(l['radial_N'], 2), round(l['axial_N'], 2), round(l['inplane_moment_Nmm'], 1)) for l in c['bonded_z+12']['land_loads']])
