"""Minimum peak-tendon-force allocation along a held-elevation yaw sweep, U4+M2 with backbone.

For yaw targets 0, 15, ..., 180 deg (continuation: each target seeded from the
previous solution), minimise the largest single tendon tension subject to:
equilibrium; yaw == target; world head elevation within pitch +/- 5 deg; the
2026-11-06 geometry (local radius curvature, nonlocal 63 mm capsules) and
projection constraints; |strain| <= 4.75%; pretension-250 N per rope. A small
pretension on every rope (default 1 N) is required: with only the up ropes
tensioned the straightened front is laterally unstable in 3D (fixed winch). Solved at 4 cells
per module, then re-solved at 8 cells with the same tensions and, if the 8-cell
state fails acceptance, re-optimised at 8 cells. Acceptance (incl. fixed-winch
stability) uses search_steering.acceptable unchanged, plus |yaw - target| <= 1 deg.

Optional --smooth adds a penalty on the squared change in tensions from the
previous yaw step, selecting a smooth allocation among near-equal-peak ones.

Local optimisation: results are the lowest peak force found, not a proven
global minimum. A sequence of stable sampled states at 15 deg steps is evidence
for, not proof of, a continuous quasi-static path.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse, time
import numpy as np
from scipy.optimize import minimize
from backbone import spatial_rod, planar_rod, HERE
from search_steering import acceptable, derivative
from spatial_model import refine_seed
from refine_steering import stationary
from front_solver import write_csv

OUT = HERE / 'results'
STRAIN = .0475


def straight_seed(variant, pitch, anchors, sub, pretension=0.):
    """Actively straightened planar state (top ropes) lifted to 3D: yaw 0, held elevation."""
    rows = json.loads((OUT / 'planar_U4_M2_rows.json').read_text())
    name = {(4, 6): 'two', (4, 5, 6): 'three_distal', (6,): 'single'}[tuple(anchors)]
    row = next(q for q in rows if q.get('variant') == variant and round(q['pitch_deg']) == pitch
               and q.get('architecture') == name and q.get('strain_mode') == 'low_strain' and 'top_extra_tensions_n' in q)
    r = spatial_rod(4, 2, anchors, pitch, sub, variant)
    C = np.full((r.k, 4), float(pretension)); C[:, 0] += row['top_extra_tensions_n']
    xp = r.planar.free()
    z = r.solve(C, r.lift_planar(xp))
    return r, z, C


def min_force(r, z0, C0, yaw_target, pitch, maxiter=200, pretension=0., exact=False, smooth=0., Cprev=None):
    n = r.ndof; k = r.k * 4; cache = {}
    def state(u):
        key = u.tobytes()
        if cache.get('key') != key:
            z = u[:n]; C = u[n:n + k].reshape(r.k, 4) * 100
            _, g, d = r.evaluate(z, C, detail=True)
            a, _ = r.kinematic_metrics(z)
            cache.update(key=key, g=g, d=d, a=a)
        return cache
    # variables: z, C/100, t/100 (peak tension)
    cp = (np.zeros(k) if Cprev is None else np.asarray(Cprev, dtype=float).ravel() / 100)
    def obj(u): return u[-1] + 1e-3 * np.sum(u[n:n + k]) / k + smooth * np.sum((u[n:n + k] - cp) ** 2)
    def jac(u):
        v = np.zeros_like(u); v[-1] = 1; v[n:n + k] = 1e-3 / k + 2 * smooth * (u[n:n + k] - cp); return v
    def eq(u):
        s = state(u)
        e = np.r_[s['g'], s['a'][0] - np.radians(yaw_target)]
        return np.r_[e, s['a'][2] - np.radians(pitch)] if exact else e
    def eqjac(u):
        z = u[:n]; C = u[n:n + k].reshape(r.k, 4) * 100
        J = np.zeros((n + 1 + exact, n + k + 1))
        J[:n, :n] = r.hessian(z, C); J[:n, n:n + k] = 100 * r.control_jacobian(z).T
        D = derivative(lambda zz: r.kinematic_metrics(zz)[0][[0, 2]], z)
        J[n, :n] = D[0]
        if exact: J[n + 1, :n] = D[1]
        return J
    def ineq_z(z):
        a, d = r.kinematic_metrics(z); t = r.R0 @ d['frames'][-1, :, 0]
        return np.r_[r.geometry_constraints(z, d), t[0] ** 2 + t[2] ** 2 - .01,
                     np.radians(5) - (a[2] - np.radians(pitch)), np.radians(5) + (a[2] - np.radians(pitch))]
    def ineq(u):
        return np.r_[ineq_z(u[:n]), u[-1] - u[n:n + k]]
    def ineqjac(u):
        Jz = derivative(ineq_z, u[:n]); m1 = Jz.shape[0]
        J = np.zeros((m1 + k, n + k + 1)); J[:m1, :n] = Jz
        J[m1:, n:n + k] = -np.eye(k); J[m1:, -1] = 1
        return J
    bounds = [(-STRAIN * s, STRAIN * s) if j % 4 == 3 else (-1.5 * s, 1.5 * s) for j, s in enumerate(r.scale)]
    bounds += [(pretension / 100, 2.5)] * k + [(0., 2.5)]
    C0 = np.maximum(np.asarray(C0, dtype=float), pretension)
    u0 = np.r_[z0, C0.ravel() / 100, np.max(C0) / 100]
    t0 = time.time()
    res = minimize(obj, u0, jac=jac, bounds=bounds, method='SLSQP',
                   constraints=[{'type': 'eq', 'fun': eq, 'jac': eqjac}, {'type': 'ineq', 'fun': ineq, 'jac': ineqjac}],
                   options={'maxiter': maxiter, 'ftol': 1e-10})
    z = res.x[:n]; C = res.x[n:n + k].reshape(r.k, 4) * 100
    return z, C, dict(success=bool(res.success), message=str(res.message), iterations=int(res.nit), seconds=time.time() - t0)


def accept(r, z, C, yaw_target, pitch):
    m, _, _ = r.metrics(z, C, stability=True)
    ok = acceptable(m, 'low_strain', 'right', np.radians(pitch)) and abs(m['yaw_deg'] - yaw_target) <= 1.0
    return ok, m


def run(variant, pitch, anchors, step, pretension, exact=False, smooth=0.):
    tag = f'minforce_{variant}_p{pitch:g}_a{"".join(map(str, anchors))}_pre{pretension:g}' + ('_exact' if exact else '') + (f'_smooth{smooth:g}' if smooth else '')
    r4, z, C = straight_seed(variant, pitch, anchors, 4, pretension)
    r8 = spatial_rod(4, 2, anchors, pitch, 8, variant)
    rows = []; states = {}
    for yaw in np.arange(0, 180.001, step):
        z4, C4, info = min_force(r4, z, C, yaw, pitch, pretension=pretension, exact=exact, smooth=smooth if yaw > 0 else 0., Cprev=C)
        ok4, m4 = accept(r4, z4, C4, yaw, pitch)
        rec = dict(variant=variant, pitch_deg=pitch, anchors=anchors, pretension_n=pretension, yaw_target_deg=float(yaw), opt4=info, ok4=ok4,
                   peak4_n=float(np.max(C4)))
        if ok4:
            z, C = z4, C4  # continuation seed
            # 8-cell: same tensions first, then re-optimise if needed.
            g8 = refine_seed(z4, r4, r8)
            x8 = stationary(r8, C4, g8); how = 'same_tension'; ok8 = False
            if x8 is not None:
                ok8, m8 = accept(r8, x8, C4, yaw, pitch); C8 = C4
            if not ok8:
                x8, C8, info8 = min_force(r8, g8 if x8 is None else x8, C4, yaw, pitch, maxiter=120, pretension=pretension, exact=exact, smooth=smooth if yaw > 0 else 0., Cprev=C4); how = 'reoptimised'
                ok8, m8 = accept(r8, x8, C8, yaw, pitch)
            rec.update(ok8=ok8, refine8=how)
            if ok8:
                rec.update(yaw_deg=m8['yaw_deg'], world_elevation_deg=m8['world_elevation_deg'], peak_n=m8['maximum_single_tendon_n'],
                           sum_n=m8['sum_tensions_n'], max_strain=m8['max_abs_axial_strain'], tensions_n=np.asarray(C8).tolist(),
                           stable=m8['stable_fixed_winch'], fixed_winch_eig=m8['minimum_fixed_winch_eigenvalue'],
                           head_world_mm=m8['head_world_mm'])
                states[f'y{yaw:g}_z8'] = x8; states[f'y{yaw:g}_T8'] = C8
        print(f"{tag} yaw {yaw:5.1f}: 4-cell ok {ok4} peak {np.max(C4):6.1f} N | 8-cell ok {rec.get('ok8')} "
              f"peak {rec.get('peak_n', float('nan')):6.1f} N elev {rec.get('world_elevation_deg', float('nan')):6.2f} "
              f"({rec.get('refine8', '-')}, {info['seconds']:.0f}s)", flush=True)
        rows.append(rec)
        (OUT / f'{tag}.json').write_text(json.dumps(rows, indent=1, default=float))
        np.savez_compressed(OUT / f'{tag}_states.npz', **states)
        if not ok4:
            print(f'{tag}: continuation stopped at yaw {yaw}', flush=True)
            break


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='niti18_E40'); ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--anchors', type=int, nargs='+', default=[4, 6]); ap.add_argument('--step', type=float, default=15)
    ap.add_argument('--pretension', type=float, default=1., help='minimum tension on every rope, N')
    ap.add_argument('--exact', action='store_true', help='hold world head elevation exactly at the base pitch')
    ap.add_argument('--smooth', type=float, default=0., help='weight on squared tension change from the previous step (tension in units of 100 N)')
    a = ap.parse_args(); run(a.variant, a.pitch, a.anchors, a.step, a.pretension, a.exact, a.smooth)
