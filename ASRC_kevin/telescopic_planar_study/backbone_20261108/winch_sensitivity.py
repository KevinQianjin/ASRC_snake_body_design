"""Sensitivity of the head pose to winch position error and rope stretch calibration.

Poses: the coordinated-winch minimum-force sweep (head held at 20 deg, anchors
[4,5,6], 1 N pretension), at yaw 0/30/60/90/120/150/175 deg (E 40 GPa) or up
to 180 deg (E 75 GPa). Rope model: fixed winch, elastic PA6 line, 1 m free rope.

1. Single-winch errors: each of the 12 winch lengths is offset by -1, -0.5,
   +0.5, +1 mm (positive = extra rope reeled in) and the equilibrium re-solved
   from the nominal state (full nonlinear model, 8 cells per module). Records
   change in yaw, world head elevation and head position, rope tensions (slack),
   stability and geometry.
2. Sensitivity matrix J (per mm) from the +/-0.5 mm central difference.
3. All 12 winches wrong at once: worst case sum |J| e, and 2000 random samples
   (independent, uniform in +/-e) predicted with J; the 10 worst predicted
   samples at e = 1 mm are re-solved with the full model to check linearity.
4. Rope stretch calibration: rope EA scaled by 0.9 and 1.1 on all ropes while
   the winch lengths stay at their nominal commands.
Allowable winch error is reported for yaw/elevation tolerances of 1 and 2 deg
(worst case and 3-sigma for uniform independent errors).
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse
import numpy as np
from backbone import spatial_rod, HERE
from coordinated_winch import RUNS, ANCH, load_poses
from side_pull import Winch

OUT = HERE / 'results'
DIRS = ['up', 'right', 'down', 'left']
NAMES = [f'a{a}_{d}' for a in ANCH for d in DIRS]


def outputs(r, z, T):
    m, _, _ = r.metrics(z, T, stability=True)
    return np.r_[m['yaw_deg'], m['world_elevation_deg'], m['head_world_mm']], m


def run(case, yaws, seed=0):
    runname, variant, pitch = RUNS[case]
    r = spatial_rod(4, 2, ANCH, pitch, 8, variant)
    poses = {p[0]: p for p in load_poses(runname)}
    rng = np.random.default_rng(seed)
    result = dict(case=case, run=runname, variant=variant, pitch_deg=pitch, ropes=NAMES, outputs=['yaw_deg', 'elev_deg', 'head_x_mm', 'head_y_mm', 'head_z_mm'], poses=[])
    for yaw in yaws:
        if yaw not in poses:
            continue
        _, z0, T0 = poses[yaw]
        w = Winch(r, z0, T0); R0 = w.R.copy()
        y0, m0 = outputs(r, z0, T0)
        singles, J = [], np.zeros((5, 12))
        for k in range(12):
            i, j = divmod(k, 4)
            res = {}
            for e in (-1., -.5, .5, 1.):
                w.R = R0.copy(); w.R[i, j] -= e / 1000
                zn, Tn = w.solve(z0)
                if zn is None:
                    singles.append(dict(rope=NAMES[k], error_mm=e, status='no_equilibrium')); continue
                yn, mn = outputs(r, zn, Tn)
                d = yn - y0; d[0] = (d[0] + 180) % 360 - 180
                res[e] = d
                singles.append(dict(rope=NAMES[k], error_mm=e, d_yaw_deg=d[0], d_elev_deg=d[1], d_head_mm=float(np.linalg.norm(d[2:])),
                                    min_tension_n=float(np.min(Tn)), stable=mn['stable_fixed_winch'], geometry=mn['geometry_pass']))
            if .5 in res and -.5 in res:
                J[:, k] = (res[.5] - res[-.5]) / 1.0
        lin_err = []
        for k in range(12):
            a = [s for s in singles if s['rope'] == NAMES[k] and 'd_yaw_deg' in s and s['error_mm'] in (1., -1.)]
            for s in a:
                lin_err.append(max(abs(s['d_yaw_deg'] - J[0, k] * s['error_mm']), abs(s['d_elev_deg'] - J[1, k] * s['error_mm'])))
        # combined errors
        A = np.abs(J)
        worst = {f'{e:g}mm': dict(yaw_deg=float(A[0].sum() * e), elev_deg=float(A[1].sum() * e), head_mm=float(np.linalg.norm(A[2:].sum(1)) * e)) for e in (.25, .5, 1.)}
        E = rng.uniform(-1, 1, size=(2000, 12))
        P = E @ J.T  # per 1 mm amplitude
        mc = {f'{e:g}mm': dict(yaw_p99_deg=float(np.percentile(np.abs(P[:, 0]) * e, 99)), elev_p99_deg=float(np.percentile(np.abs(P[:, 1]) * e, 99)),
                               head_p99_mm=float(np.percentile(np.linalg.norm(P[:, 2:], axis=1) * e, 99))) for e in (.25, .5, 1.)}
        # verify the 10 worst predicted samples at 1 mm with the full model
        score = np.abs(P[:, 0]) + np.abs(P[:, 1])
        checks = []
        for idx in np.argsort(score)[-10:]:
            w.R = R0.copy() - E[idx].reshape(3, 4) / 1000
            zn, Tn = w.solve(z0)
            if zn is None:
                checks.append(dict(status='no_equilibrium')); continue
            yn, mn = outputs(r, zn, Tn); d = yn - y0; d[0] = (d[0] + 180) % 360 - 180
            checks.append(dict(pred_yaw=float(P[idx, 0]), true_yaw=float(d[0]), pred_elev=float(P[idx, 1]), true_elev=float(d[1]),
                               min_tension_n=float(np.min(Tn)), stable=mn['stable_fixed_winch'], geometry=mn['geometry_pass']))
        # rope stretch calibration: EA x0.9 / x1.1, same commanded winch lengths
        stretch = {}
        for f in (.9, 1.1):
            w.R = R0.copy(); EA0 = w.EA; w.EA = EA0 * f
            zn, Tn = w.solve(z0); w.EA = EA0
            if zn is None:
                stretch[f'EAx{f:g}'] = dict(status='no_equilibrium'); continue
            yn, mn = outputs(r, zn, Tn); d = yn - y0; d[0] = (d[0] + 180) % 360 - 180
            stretch[f'EAx{f:g}'] = dict(d_yaw_deg=float(d[0]), d_elev_deg=float(d[1]), d_head_mm=float(np.linalg.norm(d[2:])),
                                        min_tension_n=float(np.min(Tn)), stable=mn['stable_fixed_winch'])
        # allowable error (worst case, and 99th percentile of uniform independent errors)
        allow = {}
        for tol in (1., 2.):
            allow[f'{tol:g}deg_worst_case_mm'] = float(tol / max(A[0].sum(), A[1].sum()))
            allow[f'{tol:g}deg_p99_mm'] = float(tol / max(mc['1mm']['yaw_p99_deg'], mc['1mm']['elev_p99_deg']))
        ok_single = [s for s in singles if 'd_yaw_deg' in s]
        pose = dict(yaw=yaw, nominal_elevation_deg=float(y0[1]), J_per_mm=J.tolist(),
                    most_sensitive_yaw=NAMES[int(np.argmax(np.abs(J[0])))], most_sensitive_elev=NAMES[int(np.argmax(np.abs(J[1])))],
                    max_single_1mm=dict(yaw_deg=float(max(abs(s['d_yaw_deg']) for s in ok_single if abs(s['error_mm']) == 1)),
                                        elev_deg=float(max(abs(s['d_elev_deg']) for s in ok_single if abs(s['error_mm']) == 1)),
                                        head_mm=float(max(s['d_head_mm'] for s in ok_single if abs(s['error_mm']) == 1))),
                    singles_all_stable=all(s['stable'] for s in ok_single), singles_all_geometry=all(s['geometry'] for s in ok_single),
                    singles_min_tension_n=float(min(s['min_tension_n'] for s in ok_single)), singles_failed=len(singles) - len(ok_single),
                    linearity_max_error_deg_at_1mm=float(max(lin_err)) if lin_err else None,
                    worst_case=worst, random_p99=mc, full_model_check_1mm=checks, rope_stretch=stretch, allowable_winch_error=allow, singles=singles)
        result['poses'].append(pose)
        print(f"{case} yaw {yaw:5.0f}: single 1 mm max dyaw {pose['max_single_1mm']['yaw_deg']:.2f} delev {pose['max_single_1mm']['elev_deg']:.2f} "
              f"dhead {pose['max_single_1mm']['head_mm']:.1f} mm | all 12 @1mm worst yaw {worst['1mm']['yaw_deg']:.2f} elev {worst['1mm']['elev_deg']:.2f} "
              f"p99 yaw {mc['1mm']['yaw_p99_deg']:.2f} elev {mc['1mm']['elev_p99_deg']:.2f} | allow(1 deg) worst {allow['1deg_worst_case_mm']:.2f} p99 {allow['1deg_p99_mm']:.2f} mm "
              f"| stable {pose['singles_all_stable']} minT {pose['singles_min_tension_n']:.2f} lin err {pose['linearity_max_error_deg_at_1mm']:.3f} "
              f"| EA-10% dyaw {stretch['EAx0.9'].get('d_yaw_deg', float('nan')):+.2f} delev {stretch['EAx0.9'].get('d_elev_deg', float('nan')):+.2f} "
              f"| check yaw pred/true {checks[-1].get('pred_yaw', float('nan')):+.2f}/{checks[-1].get('true_yaw', float('nan')):+.2f}", flush=True)
        (OUT / f'winch_sensitivity_{case}.json').write_text(json.dumps(result, indent=1, default=float))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', default='E40', choices=list(RUNS))
    ap.add_argument('--yaws', type=float, nargs='+', default=[0, 30, 60, 90, 120, 150, 175])
    a = ap.parse_args(); run(a.case, a.yaws)
