"""Yaw vs side-rope pull: horizontal flexibility of U4+M2 with the NiTi backbone.

Two control modes. 'tension': rope tensions are prescribed (force control).
'winch' (default, realistic): rope lengths are set by winches; each rope is a
linear elastic PA6 line with 1 m of free length, and the right rope is pulled
in by small length steps, so its tension follows from the deformation.

Start: the actively straightened front at the installation pitch (anchors
[4,5,6], top-rope tensions from pretension_recheck.py, 1 N on every rope).
Then only the RIGHT rope is pulled (tension or length) in small steps, at one anchor
(4, 5 or 6) or at all three equally; all other ropes keep their start tension.
Each step is solved by continuation from the previous equilibrium at 8 cells
per module. Recorded: head heading in the horizontal plane (yaw), world head
elevation (not held), head position, strain, geometry, fixed-winch stability,
and the head jump between steps (snap-through detector).

Free space (no tank); left pull is the mirror image under the symmetric model.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse
import numpy as np
from backbone import spatial_rod, planar_rod, HERE
from refine_front import finer_seed

OUT = HERE / 'results'
ANCH = [4, 5, 6]
STEPS = np.r_[np.arange(0, 20, .5), np.arange(20, 60, 1.), np.arange(60, 150.001, 2.5)]


def start_state(variant, pitch, sub=8):
    rec = json.loads((OUT / 'pretension1_recheck.json').read_text())
    D = np.array(next(q for q in rec if q['variant'] == variant and q['pitch_deg'] == pitch)['top_extra_tensions_n'])
    c = planar_rod(4, 2, ANCH, pitch, 4, variant, common=1.)
    f = planar_rod(4, 2, ANCH, pitch, sub, variant, common=1.)
    xf = f.solve_ramped(D, finer_seed(c.solve_ramped(D, c.straight_seed()), c, f))
    r = spatial_rod(4, 2, ANCH, pitch, sub, variant)
    C = np.ones((3, 4)); C[:, 0] += D
    z = r.solve(C, r.lift_planar(xf))
    assert z is not None
    return r, z, C


class Winch:
    """Fixed-winch rope model: each rope is a linear elastic line of unstretched length R
    (front routing length L(z) plus 1 m of free rope to the winch). Tension
    T = EA * max(0, L + 1 - R) / R. Pulling a rope in = reducing its R."""

    def __init__(self, r, z, C):
        self.r = r; self.EA = r.planar.rope_ea
        _, _, d = r.evaluate(z, C, detail=True)
        L = d['rope_lengths']
        self.R = (L + 1.) / (1. + np.asarray(C) / self.EA)

    def tensions(self, L):
        return self.EA * np.maximum(0., L + 1. - self.R) / self.R

    def energy_grad(self, z):
        E0, _, d = self.r.evaluate(z, np.zeros_like(self.R), detail=True)
        L = d['rope_lengths']; T = self.tensions(L)
        E = E0 + np.sum(.5 * self.EA * np.maximum(0., L + 1. - self.R) ** 2 / self.R)
        g = self.r.evaluate(z, T)[1]  # d/dz of sum T*L at fixed T equals the rope-spring gradient
        return E, g

    def solve(self, z0):
        from scipy.optimize import minimize
        r = self.r
        bounds = [(-.7 * s, .2 * s) if j % 4 == 3 else (-1.5 * s, 1.5 * s) for j, s in enumerate(r.scale)]
        opt = minimize(self.energy_grad, z0, jac=True, method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': 3000, 'gtol': 1e-10, 'ftol': 1e-16, 'maxls': 50, 'maxcor': 40})
        z = opt.x
        _, _, d = r.evaluate(z, np.zeros_like(self.R), detail=True)
        T = self.tensions(d['rope_lengths'])
        res = r.residual(r.evaluate(z, T)[1])
        return (z, T) if res < 2e-6 else (None, T)


def run(variant, pitch, pull, mode='winch', max_pull_mm=80., step_mm=.25):
    r, z, C0 = start_state(variant, pitch)
    rows, prev_head = [], None
    sets = {'a4': [0], 'a5': [1], 'a6': [2], 'all': [0, 1, 2]}[pull]
    if mode == 'tension':
        controls = [(float(e), None) for e in STEPS]
    else:
        w = Winch(r, z, C0); R0 = w.R.copy()
        controls = [(None, float(dl)) for dl in np.arange(0, max_pull_mm + 1e-9, step_mm)]
    for extra, pull_mm in controls:
        if mode == 'tension':
            C = C0.copy()
            for i in sets: C[i, 1] += extra
            zn = r.solve(C, z)
        else:
            w.R = R0.copy()
            for i in sets: w.R[i, 1] -= pull_mm / 1000
            zn, C = w.solve(z)
        if zn is None:
            rows.append(dict(extra_right_n=extra, pull_in_mm=pull_mm, status='no_converged_equilibrium_from_previous_state'))
            print(f'{variant} p{pitch} {pull} {mode}: no equilibrium at {extra if mode == "tension" else pull_mm}; stop', flush=True)
            break
        m, _, _ = r.metrics(zn, C, stability=True)
        head = np.array(m['head_world_mm'])
        jump = None if prev_head is None else float(np.linalg.norm(head - prev_head))
        row = dict(variant=variant, pitch_deg=pitch, pull=pull, mode=mode, pull_in_mm=pull_mm,
                   right_rope_n=[float(C[i, 1]) for i in sets], tensions_n=np.asarray(C).tolist(),
                   yaw_deg=m['yaw_deg'], world_elevation_deg=m['world_elevation_deg'], head_world_mm=m['head_world_mm'],
                   max_strain=m['max_abs_axial_strain'], geometry_pass=m['geometry_pass'], stable=m['stable_fixed_winch'],
                   fixed_winch_eig=m['minimum_fixed_winch_eigenvalue'], constant_tension_eig=m['minimum_force_control_eigenvalue'],
                   twist_deg=m['total_material_twist_deg'], peak_n=m['maximum_single_tendon_n'], head_jump_mm=jump)
        rows.append(row)
        z, prev_head = zn, head
        if not m['geometry_pass'] or abs(m['yaw_deg']) >= 180:
            print(f'{variant} p{pitch} {pull} {mode}: stop (geometry {m["geometry_pass"]}, yaw {m["yaw_deg"]:.1f})', flush=True)
            break
    (OUT / f'sidepull_{mode}_{variant}_p{pitch:g}_{pull}.json').write_text(json.dumps(rows, indent=1, default=float))
    ok = [q for q in rows if 'yaw_deg' in q]
    for q in ok[::max(1, len(ok) // 10)] + ok[-1:]:
        ctrl = f"pull {q['pull_in_mm']:5.2f} mm" if mode == 'winch' else ''
        print(f"{variant} p{pitch} {pull} {mode}: {ctrl} right rope {max(q['right_rope_n']):6.1f} N  yaw {q['yaw_deg']:7.2f}  "
              f"elev {q['world_elevation_deg']:6.1f}  head {np.round(q['head_world_mm']).astype(int)}  stable {q['stable']}  "
              f"jump {q['head_jump_mm'] or 0:.1f} mm", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='niti18_E40'); ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--pull', default='a6', choices=['a4', 'a5', 'a6', 'all'])
    ap.add_argument('--mode', default='winch', choices=['winch', 'tension'])
    ap.add_argument('--max-pull-mm', type=float, default=80.); ap.add_argument('--step-mm', type=float, default=.25)
    a = ap.parse_args(); run(a.variant, a.pitch, a.pull, a.mode, a.max_pull_mm, a.step_mm)
