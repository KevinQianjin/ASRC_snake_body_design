"""Joint-concept screen on the rib-level model (companion to rib_joint_model.py).

Each mounting rib's land patch at z = +/-12 mm is a rigid master with in-plane
DOFs (u_r, u_z, beta). A joint variant ties a subset of them to the rigid guide
body; released components get their own free DOFs (an ideal frictionless
release):

  rigid_bond : u_r, u_z, beta tied (the published bonded-land concept)
  pinned     : u_r, u_z tied, beta released (in-plane hinge at the land)
  radial_only: u_r tied, u_z and beta released (axially sliding saddle)
  none       : nothing tied (must reproduce the unbonded module)

Reported at the record-146 curvature (linear scaling): module EI, joint loads,
joint stroke (relative land/guide motion in released components), strut-point
motion inside the +/-1.62 mm socket relative to the guide, and the peak
in-plane principal strain in the ribs. Same assumptions as rib_joint_model.py.
"""
import argparse, json
from pathlib import Path
import numpy as np
import trimesh
import rib_joint_model as R

VARIANTS = dict(rigid_bond=(0, 1, 2), pinned=(0, 1), radial_only=(0,), none=())


def setup(max_area, E, nu):
    body = trimesh.load(R.BODY)
    poly, e_r, e_z, n = R.rib_polygon(body, 22.5)
    X, T = R.mesh_polygon(poly, max_area)
    t = R.thickness(body, X[T].mean(axis=1), e_r, e_z, n)
    r, z = X[:, 0], X[:, 1]
    ring_z = [(-20.0, -16.95), (-6.5, -3.45), (3.45, 6.5), (16.95, 20.0)]
    ms = [('D0', (z <= -45.0) | ((r < 3.3) & (z < -30))), ('D1', (z >= 45.0) | ((r < 3.3) & (z > 30)))]
    ms += [(f'R{k}', (r < 8.6) & (z >= lo) & (z <= hi)) for k, (lo, hi) in enumerate(ring_z)]
    land = {s: (np.abs(z - s) <= R.LAND_HALF + 1e-9) & (r > 15) & (r < 24) for s in (-12., 12.)}
    socket = {s: (np.abs(z - s) <= R.SOCKET_HALF) & (r > 13) & (r < 26) for s in (-12., 12.)}
    ms += [('G-12', land[-12.]), ('G+12', land[12.])]
    ms = [(nm, mk, (X[mk, 0].mean(), X[mk, 1].mean())) for nm, mk in ms]
    tt = np.where(np.isfinite(t), t, 3.0)
    K = R.cst_stiffness(X, T, tt, E, nu)
    Kc, rec = R.condense(K, X, ms)
    return dict(X=X, T=T, t=tt, ms=ms, Kc=Kc, rec=rec, socket=socket, E=E, nu=nu)


def strains(X, T, U):
    x, y = X[T, 0], X[T, 1]
    A2 = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], 1) / A2[:, None]
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], 1) / A2[:, None]
    ux, uy = U[T, 0], U[T, 1]
    exx = (b * ux).sum(1); eyy = (c * uy).sum(1); gxy = (c * ux + b * uy).sum(1)
    m = (exx + eyy) / 2; rr = np.sqrt(((exx - eyy) / 2) ** 2 + (gxy / 2) ** 2)
    return np.maximum(np.abs(m + rr), np.abs(m - rr))


def run_variant(S, tied, psi, kappa):
    ms, Kc = S['ms'], S['Kc']; names = [nm for nm, _, _ in ms]
    bodies = names; nb = len(bodies); zc = {nm: ref[1] for nm, _, ref in ms}
    mounts = [th for th in (22.5 + 45 * k for k in range(8)) if any(np.isclose((th - a) % 360, 0) for a in R.MOUNT_ANGLES)]
    nextra = len(mounts) * 2 * (3 - len(tied)) + (8 - len(mounts)) * 6
    Ntot = 6 * nb + nextra
    Kg = np.zeros((Ntot, Ntot)); Ps = {}; ex = 6 * nb
    for k in range(8):
        th = 22.5 + 45 * k; mount = th in mounts
        P = np.zeros((3 * len(ms), Ntot))
        for j, (nm, _, (r0, z0)) in enumerate(ms):
            b = bodies.index(nm); Pj = R.projection(th, r0, z0, zc[nm])
            if nm.startswith('G'):
                # non-mounting ribs: their land patch is internal (free); mounting ribs: tie selected components
                for c in range(3):
                    if mount and c in tied: P[3 * j + c, 6 * b:6 * b + 6] = Pj[c]
                    else: P[3 * j + c, ex] = 1.; ex += 1
            else:
                P[3 * j:3 * j + 3, 6 * b:6 * b + 6] = Pj
        Kg += P.T @ Kc @ P
        Ps[th] = P
    assert ex == Ntot
    N = Kg.shape[0]
    fixed = list(range(6)) + [6 * b + 5 for b in range(nb)]
    gb = [bodies.index('G-12'), bodies.index('G+12')]
    for b in gb:   # guide DOFs not reached by the tied components (e.g. axial ones when sliding) are null: tiny regularisation
        Kg[6 * b:6 * b + 6, 6 * b:6 * b + 6] += 1e-9 * np.eye(6)
    fr = np.setdiff1d(np.arange(N), fixed)
    a = np.array([np.cos(np.radians(psi)), np.sin(np.radians(psi)), 0.])
    F = np.zeros(N); F[9:12] = a
    q = np.zeros(N); q[fr] = np.linalg.solve(Kg[np.ix_(fr, fr)], F[fr])
    phi = a @ q[9:12]; EI = R.MODULE_L / phi
    q *= kappa * R.MODULE_L / phi
    out = dict(EI_Nmm2=EI, peak_principal_strain=0.0, stations={})
    for k in range(8):
        th = 22.5 + 45 * k; P = Ps[th]
        qq = P @ q
        U = S['rec'](qq)
        out['peak_principal_strain'] = max(out['peak_principal_strain'], float(strains(S['X'], S['T'], U).max()))
        if th not in mounts: continue
        for st in (-12., 12.):
            nm = f'G{st:+.0f}'; j = names.index(nm); b = bodies.index(nm)
            f = Kc[3 * j:3 * j + 3] @ qq
            guide = R.projection(th, *ms[j][2], zc[nm]) @ q[6 * b:6 * b + 6] if tied else np.zeros(3)
            stroke = qq[3 * j:3 * j + 3] - guide
            # strut points inside the socket relative to the guide rigid motion (in-plane)
            Xs = S['X'][S['socket'][st]]; r0, z0 = ms[j][2]
            gu = np.c_[guide[0] - guide[2] * (Xs[:, 1] - z0), guide[1] + guide[2] * (Xs[:, 0] - r0)]
            rel = U[S['socket'][st]] - gu
            out['stations'].setdefault(nm, []).append(dict(
                rib_deg=th, radial_N=float(f[0]), axial_N=float(f[1]), moment_Nmm=float(f[2]),
                stroke_radial_mm=float(stroke[0]), stroke_axial_mm=float(stroke[1]), stroke_rotation_rad=float(stroke[2]),
                socket_rel_max_mm=float(np.linalg.norm(rel, axis=1).max()),
                socket_rel_axial_max_mm=float(np.abs(rel[:, 1]).max())))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', type=float, default=0.02)
    ap.add_argument('--E', type=float, default=1700.0)
    ap.add_argument('--nu', type=float, default=0.4)
    ap.add_argument('--kappa', type=float, default=0.01748791036298669)
    ap.add_argument('--psi', type=float, nargs='+', default=[0, 22.5, 67.5])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    S = setup(a.area, a.E, a.nu)
    res = dict(scope=__doc__, parameters=vars(a), mesh=dict(nodes=len(S['X']), triangles=len(S['T'])), cases=[])
    for psi in a.psi:
        for name, tied in VARIANTS.items():
            o = run_variant(S, tied, psi, a.kappa); o.update(variant=name, bending_axis_deg=psi)
            res['cases'].append(o)
            g = o['stations']['G+12']
            print(f"psi {psi:6.2f} {name:12s} EI {o['EI_Nmm2']:8.0f} peak strain {o['peak_principal_strain']:.4f} "
                  f"max|Fa| {max(abs(x['axial_N']) for x in g):6.2f} max|Fr| {max(abs(x['radial_N']) for x in g):6.2f} "
                  f"max|M| {max(abs(x['moment_Nmm']) for x in g):7.1f} stroke ax {max(abs(x['stroke_axial_mm']) for x in g):.4f} "
                  f"rot {max(abs(x['stroke_rotation_rad']) for x in g):.4f} sock {max(x['socket_rel_max_mm'] for x in g):.4f}", flush=True)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'joint_variants.json').write_text(json.dumps(res, indent=1, default=float))
