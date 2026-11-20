"""Rib-level joint model with in-plane AND out-of-plane rib stiffness.

Extends rib_joint_model.py. Each 3.0 mm rib is a flat plate: the in-plane
(membrane) field uses the same constant-strain triangles, and the out-of-plane
field uses linear Mindlin-Reissner triangles (shear factor 5/6) on the same
mesh. For a flat linear plate the two fields are uncoupled. Every rigid
master (disks, rings, guide lands) now has six DOFs per rib:
in-plane (u_r, u_z, beta about -e_theta) and out-of-plane (w along -e_theta,
Omega_r = omega.e_r, Omega_z = omega.e_z). Torsion about z is therefore
resisted and the database GJ can be checked as well as EA and EI.

Joint variants at the four mounting lands (z = +/-12 mm):
  rigid_bond : all six components tied to the rigid guide
  hinge_t    : beta (rotation about the rib's tangential axis) released, others tied
  ball       : translations (u_r, u_z, w) tied, all three rotations released (point contact)
  none       : nothing tied
Limitations: linear, small rotation; plate theory is approximate for struts
narrower (1.53 mm) than the plate thickness (3.0 mm); rings, disks and guides
rigid; ideal bonds/releases.
"""
import argparse, json, time, hashlib
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import trimesh
import rib_joint_model as R

# database GJ column is the whole-module torsion spring T/theta (N m/rad); rod coefficient = T/theta x 0.096 m
# (same convention as backbone_20261108/export_model_data.py)
DB_GJ_Nmm2 = 0.437396e3 * 96.0


def plate_stiffness(X, T, t, E, nu, ks=5.0 / 6.0):
    """Linear Mindlin triangle. Node DOFs (w, phi_x, phi_y); u_x = zeta*phi_x, u_y = zeta*phi_y,
    shear gamma = grad w + phi. Bending: one-point exact (constant curvature); shear: 3-point."""
    G = E / (2 * (1 + nu))
    Db = E / (1 - nu**2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    rows, cols, vals = [], [], []
    gp = [(2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3)]
    for e, tri in enumerate(T):
        x, y = X[tri, 0], X[tri, 1]
        A2 = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0]); A = abs(A2) / 2
        b = np.array([y[1] - y[2], y[2] - y[0], y[0] - y[1]]) / A2
        c = np.array([x[2] - x[1], x[0] - x[2], x[1] - x[0]]) / A2
        Bb = np.zeros((3, 9)); Bb[0, 1::3] = b; Bb[1, 2::3] = c; Bb[2, 1::3] = c; Bb[2, 2::3] = b
        k = Bb.T @ Db @ Bb * (A * t[e] ** 3 / 12)
        for N in gp:
            Bs = np.zeros((2, 9)); Bs[0, 0::3] = b; Bs[1, 0::3] = c
            Bs[0, 1::3] = N; Bs[1, 2::3] = N
            k += Bs.T @ Bs * (ks * G * t[e] * A / 3)
        dof = np.ravel(np.c_[3 * tri, 3 * tri + 1, 3 * tri + 2])
        rows.append(np.repeat(dof, 9)); cols.append(np.tile(dof, 9)); vals.append(k.ravel())
    n = 3 * len(X)
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))


def condense_plate(K, X, masters):
    n = len(X); owner = -np.ones(n, int)
    for m, (_, mask, _) in enumerate(masters): owner[mask] = m
    free = np.where(owner < 0)[0]; nf = 3 * len(free); nm = 3 * len(masters)
    rows, cols, vals = [], [], []
    for j, i in enumerate(free):
        rows += [3 * i, 3 * i + 1, 3 * i + 2]; cols += [3 * j, 3 * j + 1, 3 * j + 2]; vals += [1., 1., 1.]
    for m, (_, mask, (x0, y0)) in enumerate(masters):
        c = nf + 3 * m          # master DOFs (W, Ox, Oy)
        for i in np.where(mask)[0]:
            # w = W - Oy (x - x0) + Ox (y - y0); phi_x = Oy; phi_y = -Ox
            rows += [3 * i, 3 * i, 3 * i, 3 * i + 1, 3 * i + 2]
            cols += [c, c + 2, c + 1, c + 2, c + 1]
            vals += [1., -(X[i, 0] - x0), X[i, 1] - y0, 1., -1.]
    Tr = sp.csr_matrix((vals, (rows, cols)), shape=(3 * n, nf + nm))
    Kr = (Tr.T @ K @ Tr).tocsc()
    Kff = Kr[:nf, :nf]; Kfm = Kr[:nf, nf:].toarray(); Kmm = Kr[nf:, nf:].toarray()
    Xf = spla.splu(Kff).solve(Kfm)
    Kc = Kmm - Kfm.T @ Xf
    def recover(q):
        return (Tr @ np.r_[-Xf @ q, q]).reshape(-1, 3)
    return 0.5 * (Kc + Kc.T), recover


def projection6(theta_deg, r0, z0, zc):
    """3D rigid body (u, omega) at (0,0,zc) -> rib master DOFs (u_r, u_z, beta, W, Omega_r, Omega_z)."""
    th = np.radians(theta_deg)
    e_r = np.array([np.cos(th), np.sin(th), 0.]); e_t = np.array([-np.sin(th), np.cos(th), 0.]); e_z = np.array([0, 0, 1.])
    nrm = -e_t
    d = r0 * e_r + (z0 - zc) * e_z
    P = np.zeros((6, 6))
    P[:3] = R.projection(theta_deg, r0, z0, zc)
    P[3, :3] = nrm; P[3, 3:] = np.cross(d, nrm)
    P[4, 3:] = e_r
    P[5, 3:] = e_z
    return P


VARIANTS = dict(rigid_bond=(0, 1, 2, 3, 4, 5), hinge_t=(0, 1, 3, 4, 5), ball=(0, 1, 3), none=())


def setup(max_area, E, nu, body_path=None):
    body = trimesh.load(R.BODY if body_path is None else body_path)
    poly, e_r, e_z, n = R.rib_polygon(body, 22.5)
    X, T = R.mesh_polygon(poly, max_area)
    t = R.thickness(body, X[T].mean(axis=1), e_r, e_z, n)
    tt = np.where(np.isfinite(t), t, 3.0)
    r, z = X[:, 0], X[:, 1]
    ring_z = [(-20.0, -16.95), (-6.5, -3.45), (3.45, 6.5), (16.95, 20.0)]
    ms = [('D0', (z <= -45.0) | ((r < 3.3) & (z < -30))), ('D1', (z >= 45.0) | ((r < 3.3) & (z > 30)))]
    ms += [(f'R{k}', (r < 8.6) & (z >= lo) & (z <= hi)) for k, (lo, hi) in enumerate(ring_z)]
    land = {s: (np.abs(z - s) <= R.LAND_HALF + 1e-9) & (r > 15) & (r < 24) for s in (-12., 12.)}
    socket = {s: (np.abs(z - s) <= R.SOCKET_HALF) & (r > 13) & (r < 26) for s in (-12., 12.)}
    ms += [('G-12', land[-12.]), ('G+12', land[12.])]
    ms = [(nm, mk, (X[mk, 0].mean(), X[mk, 1].mean())) for nm, mk in ms]
    # rigid master regions are excluded from the thickness-based plate/membrane stiffness only through the tie
    Km = R.cst_stiffness(X, T, tt, E, nu)
    Kp = plate_stiffness(X, T, tt, E, nu)
    Kcm, recm = R.condense(Km, X, ms)
    Kcp, recp = condense_plate(Kp, X, ms)
    nm = len(ms)
    # interleave per master: [u_r, u_z, beta, W, Or, Oz]
    perm = np.concatenate([[3 * j, 3 * j + 1, 3 * j + 2, 3 * nm + 3 * j, 3 * nm + 3 * j + 1, 3 * nm + 3 * j + 2] for j in range(nm)])
    Kc = np.zeros((6 * nm, 6 * nm))
    Kblk = np.zeros((6 * nm, 6 * nm)); Kblk[:3 * nm, :3 * nm] = Kcm; Kblk[3 * nm:, 3 * nm:] = Kcp
    Kc = Kblk[np.ix_(perm, perm)]
    def recover(qq):
        qm = np.concatenate([qq[6 * j:6 * j + 3] for j in range(nm)])
        qp = np.concatenate([qq[6 * j + 3:6 * j + 6] for j in range(nm)])
        return recm(qm), recp(qp)
    return dict(X=X, T=T, t=tt, ms=ms, Kc=Kc, recover=recover, socket=socket, land=land, E=E, nu=nu,
                mesh=dict(max_triangle_area_mm2=max_area, nodes=len(X), triangles=len(T)))


def surface_strain(S, Um, Up):
    X, T, t = S['X'], S['T'], S['t']
    x, y = X[T, 0], X[T, 1]
    A2 = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], 1) / A2[:, None]
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], 1) / A2[:, None]
    def grad(f):
        return (b * f[T]).sum(1), (c * f[T]).sum(1)
    ux_x, ux_y = grad(Um[:, 0]); uy_x, uy_y = grad(Um[:, 1])
    px_x, px_y = grad(Up[:, 1]); py_x, py_y = grad(Up[:, 2])
    peak = np.zeros(len(T))
    for s in (1, -1):
        h = s * t / 2
        exx = ux_x + h * px_x; eyy = uy_y + h * py_y; gxy = ux_y + uy_x + h * (px_y + py_x)
        m = (exx + eyy) / 2; rr = np.sqrt(((exx - eyy) / 2) ** 2 + (gxy / 2) ** 2)
        peak = np.maximum(peak, np.maximum(np.abs(m + rr), np.abs(m - rr)))
    return peak


def solve(S, tied, load, mounts_only=True):
    ms, Kc = S['ms'], S['Kc']; names = [nm for nm, _, _ in ms]; nb = len(names)
    zc = {nm: ref[1] for nm, _, ref in ms}
    mounts = [th for th in (22.5 + 45 * k for k in range(8)) if any(np.isclose((th - a) % 360, 0) for a in R.MOUNT_ANGLES)]
    Ntot = 6 * nb + len(mounts) * 2 * (6 - len(tied)) + (8 - len(mounts)) * 12
    Kg = np.zeros((Ntot, Ntot)); Ps = {}; ex = 6 * nb
    for k in range(8):
        th = 22.5 + 45 * k; mount = th in mounts
        P = np.zeros((6 * len(ms), Ntot))
        for j, (nm, _, (r0, z0)) in enumerate(ms):
            b = names.index(nm); Pj = projection6(th, r0, z0, zc[nm])
            if nm.startswith('G'):
                for c in range(6):
                    if mount and c in tied: P[6 * j + c, 6 * b:6 * b + 6] = Pj[c]
                    else: P[6 * j + c, ex] = 1.; ex += 1
            else:
                P[6 * j:6 * j + 6, 6 * b:6 * b + 6] = Pj
        Kg += P.T @ Kc @ P; Ps[th] = P
    assert ex == Ntot
    gb = [names.index('G-12'), names.index('G+12')]
    for b in gb: Kg[6 * b:6 * b + 6, 6 * b:6 * b + 6] += 1e-9 * np.eye(6)
    fr = np.arange(6, Ntot)
    F = np.zeros(Ntot); F[6:12] = load
    q = np.zeros(Ntot); q[fr] = np.linalg.solve(Kg[np.ix_(fr, fr)], F[fr])
    return q, Ps, mounts


def post(S, tied, q, Ps, mounts):
    ms, Kc = S['ms'], S['Kc']; names = [nm for nm, _, _ in ms]; zc = {nm: ref[1] for nm, _, ref in ms}
    out = dict(peak_surface_principal_strain=0.0, stations={})
    for th, P in Ps.items():
        qq = P @ q
        Um, Up = S['recover'](qq)
        out['peak_surface_principal_strain'] = max(out['peak_surface_principal_strain'], float(surface_strain(S, Um, Up).max()))
        if th not in mounts: continue
        for st in (-12., 12.):
            nm = f'G{st:+.0f}'; j = names.index(nm); b = names.index(nm)
            f = Kc[6 * j:6 * j + 6] @ qq
            guide = projection6(th, *ms[j][2], zc[nm]) @ q[6 * b:6 * b + 6] if tied else np.zeros(6)
            stroke = qq[6 * j:6 * j + 6] - guide
            Xs = S['X'][S['socket'][st]]; x0, y0 = ms[j][2]
            gin = np.c_[guide[0] - guide[2] * (Xs[:, 1] - y0), guide[1] + guide[2] * (Xs[:, 0] - x0)]
            gout = guide[3] - guide[5] * (Xs[:, 0] - x0) + guide[4] * (Xs[:, 1] - y0)
            rel_in = Um[S['socket'][st]] - gin; rel_out = Up[S['socket'][st], 0] - gout
            out['stations'].setdefault(nm, []).append(dict(
                rib_deg=th, radial_N=float(f[0]), axial_N=float(f[1]), inplane_moment_Nmm=float(f[2]),
                tangential_N=float(f[3]), moment_about_r_Nmm=float(f[4]), moment_about_z_Nmm=float(f[5]),
                hinge_rotation_rad=float(stroke[2]),
                socket_rel_inplane_max_mm=float(np.linalg.norm(rel_in, axis=1).max()),
                socket_rel_tangential_max_mm=float(np.abs(rel_out).max())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--areas', type=float, nargs='+', default=[0.02, 0.01])
    ap.add_argument('--E', type=float, default=1700.0)
    ap.add_argument('--nu', type=float, default=0.4)
    ap.add_argument('--kappa', type=float, default=0.01748791036298669)
    ap.add_argument('--psi', type=float, nargs='+', default=[0, 22.5, 45, 67.5])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    runs = []
    for area in a.areas:
        t0 = time.monotonic(); S = setup(area, a.E, a.nu)
        run = dict(mesh=S['mesh'], setup_s=time.monotonic() - t0, global_stiffness={}, cases=[])
        for name, tied in VARIANTS.items():
            qa, *_ = solve(S, tied, np.array([0, 0, 1., 0, 0, 0]))
            qt, *_ = solve(S, tied, np.array([0, 0, 0, 0, 0, 1.]))
            run['global_stiffness'][name] = dict(EA_N=R.MODULE_L / qa[8], GJ_Nmm2=R.MODULE_L / qt[11])
        for psi in a.psi:
            ax = np.array([np.cos(np.radians(psi)), np.sin(np.radians(psi)), 0.])
            for name, tied in VARIANTS.items():
                q, Ps, mounts = solve(S, tied, np.r_[0, 0, 0, ax])
                phi = ax @ q[9:12]; EI = R.MODULE_L / phi
                q = q * (a.kappa * R.MODULE_L / phi)
                o = post(S, tied, q, Ps, mounts); o.update(variant=name, bending_axis_deg=psi, EI_Nmm2=EI)
                run['cases'].append(o)
                g = o['stations']['G+12']
                print(f"area {area} psi {psi:5.1f} {name:10s} EI {EI:8.0f} strain {o['peak_surface_principal_strain']:.4f} "
                      f"|Fa|{max(abs(x['axial_N']) for x in g):6.2f} |Ft|{max(abs(x['tangential_N']) for x in g):6.2f} "
                      f"|Fr|{max(abs(x['radial_N']) for x in g):6.2f} |Mb|{max(abs(x['inplane_moment_Nmm']) for x in g):6.1f} "
                      f"|Mr|{max(abs(x['moment_about_r_Nmm']) for x in g):6.1f} |Mz|{max(abs(x['moment_about_z_Nmm']) for x in g):6.1f} "
                      f"hinge {max(abs(x['hinge_rotation_rad']) for x in g):.4f} sock_in {max(x['socket_rel_inplane_max_mm'] for x in g):.3f} "
                      f"sock_t {max(x['socket_rel_tangential_max_mm'] for x in g):.3f}", flush=True)
        run['elapsed_s'] = time.monotonic() - t0
        print('area', area, run['global_stiffness'], f"{run['elapsed_s']:.0f}s", flush=True)
        runs.append(run)
    doc = dict(scope=__doc__, body='../../../cad/lanes_u4m2/end_bellmouth_v1/M5_lane_anchorB.stl',
               body_sha256=hashlib.sha256(R.BODY.read_bytes()).hexdigest(),
               parameters=dict(vars(a), module_length_mm=R.MODULE_L, database_EA_N=R.DB_EA_N,
                               database_EI_Nmm2=R.DB_EI_Nmm2, database_GJ_Nmm2=DB_GJ_Nmm2,
                               mount_rib_angles_deg=R.MOUNT_ANGLES, land_half_mm=R.LAND_HALF, socket_half_mm=R.SOCKET_HALF),
               runs=runs)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'rib_joint_3d_results.json').write_text(json.dumps(doc, indent=1, default=float))


if __name__ == '__main__':
    main()
