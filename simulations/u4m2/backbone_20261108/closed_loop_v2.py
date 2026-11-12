"""Closed-loop round trip v2: operating pretension enforced and refined motion path.

Builds on closed_loop_cycle.py (same nominal gains, reference, plants, solver
and inspection checks). Changes to the control sequence only:

1. Operating tension: the correction QP keeps every predicted rope tension at
   or above --tension-target (default 3 N, the operating pretension) instead
   of 1.5 N. A sample is settled when the angle error is at most 0.2 deg and
   the measured minimum tension is at least --settle-tension (default 2.5 N).
2. Tension-aware arrival: before each new feedforward command, rope tensions
   are predicted from the MEASURED tensions and the nominal tension gains.
   If any predicted tension is below the target, a pre-correction (at most
   --precomp-limit mm per rope, within the 5 mm total offset budget) is added
   that disturbs the head angles as little as possible.
3. Refined path: every transition (feedforward command change with clamp
   travel, and every feedback correction) is applied in sub-steps of at most
   --rope-step mm of rope, halved recursively until no centreline node moves
   more than --node-step mm in tank coordinates. Every intermediate state is
   solved from the previous one and inspected (stability, tension, geometry,
   strain, tank clearance), and recorded in the trace.

The controller still uses only measured yaw/elevation and the 12 tensions;
plant parameters are not used. Quasi-static: no dynamics, noise, delay,
friction, backlash or hysteresis.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import argparse, json, csv, time, pickle
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from closed_loop_cycle import (REF, OUT as OUT1, NAMES, CASES, FeedbackDrive, angles, error, adapt_scale, inspect)
from length_cycle import FastTank, spatial_rod, HERE

OUT = HERE / 'closed_loop_v2_results'


def qp(A, C, T, err, offset, target, step_limit, angle_weight=1.):
    """min ||A x - err||^2 + reg  s.t.  T + C x >= target, T + C x <= 250, step and total-offset bounds."""
    def fun(x): return .5 * angle_weight * np.sum((A @ x - err) ** 2) + 1e-4 * np.sum(x * x)
    def jac(x): return angle_weight * A.T @ (A @ x - err) + 2e-4 * x
    lo = np.maximum(-step_limit, -5 - offset); hi = np.minimum(step_limit, 5 - offset)
    cons = [dict(type='ineq', fun=lambda x: T + C @ x - target, jac=lambda x: C),
            dict(type='ineq', fun=lambda x: 250 - T - C @ x, jac=lambda x: -C)]
    opt = minimize(fun, np.zeros(12), jac=jac, bounds=list(zip(lo, hi)), constraints=cons, method='SLSQP', options=dict(maxiter=150, ftol=1e-10))
    x = np.clip(opt.x, lo, hi)
    return x, bool(opt.success)


class Runner:
    def __init__(self, case, args):
        self.case, self.a = case, args
        variant, payload, ea, free = CASES[case]
        self.r = spatial_rod(4, 2, [4, 5, 6], 20, 8, variant); self.r.payload = payload
        self.d = FeedbackDrive(self.r, free, ea); self.free = free
        self.tank = FastTank()
        self.trace = []; self.last_points = None; self.max_move = 0.

    def check(self, z, R, s, target, kind, index, phase):
        m, P = inspect(self.r, self.d, z, R, dict(clamp_s_mm=s), self.tank, target)
        move = 0. if self.last_points is None else float(np.linalg.norm(P - self.last_points, axis=1).max())
        rec = dict(index=index, phase=phase, kind=kind, clamp_s_mm=float(s), node_move_mm=move,
                   operating_tension_pass=bool(m['minimum_tension_n'] >= self.a.settle_tension), **m)
        return rec, P

    def move(self, z, Ra, sa, ta, Rb, sb, tb, kind, index, phase, depth=0):
        """Move from (Ra, sa) at state z to (Rb, sb); subdivide until node motion <= node_step. Returns new z.

        ta/tb are the angle targets at the two ends; intermediate states are checked against the
        interpolated target, so progress along a commanded move is not counted as error."""
        zb = self.d.solve(z, Rb)
        if zb is not None:
            rec, P = self.check(zb, Rb, sb, tb, kind, index, phase)
            if rec['node_move_mm'] <= self.a.node_step or depth >= self.a.max_depth:
                self.trace.append(rec); self.last_points = P
                self.max_move = max(self.max_move, rec['node_move_mm'])
                return zb
        if depth >= self.a.max_depth:
            raise RuntimeError(f'{self.case}: transition failed at sample {index} ({kind})')
        Rm = (Ra + Rb) / 2; sm = (sa + sb) / 2; tm = (np.asarray(ta) + np.asarray(tb)) / 2
        zm = self.move(z, Ra, sa, ta, Rm, sm, tm, kind, index, phase, depth + 1)
        return self.move(zm, Rm, sm, tm, Rb, sb, tb, kind, index, phase, depth + 1)

    def transition(self, z, Ra, sa, ta, Rb, sb, tb, kind, index, phase):
        n = max(1, int(np.ceil(np.max(np.abs(Rb - Ra)) * 1000 / self.a.rope_step - 1e-9)))
        ta = np.asarray(ta, float); tb = np.asarray(tb, float)
        for k in range(1, n + 1):
            f0, f1 = (k - 1) / n, k / n
            z = self.move(z, Ra + (Rb - Ra) * f0, sa + (sb - sa) * f0, ta + (tb - ta) * f0,
                          Ra + (Rb - Ra) * f1, sa + (sb - sa) * f1, ta + (tb - ta) * f1, kind, index, phase)
        return z

    def run(self):
        a = self.a
        rows = json.loads((REF / 'nominal.json').read_text()); refzs = np.load(REF / 'nominal_states.npz')['z']
        data = np.load(OUT1 / 'nominal_gains.npz')
        if a.limit: rows = rows[:a.limit]
        nominal = spatial_rod(4, 2, [4, 5, 6], 20, 8)
        z = refzs[0] / nominal.scale * self.r.scale
        offset = np.zeros(12); damping = 1.
        R_applied = data['R'][0] + self.free - 1.; s_prev = rows[0]['clamp_s_mm']
        records, Z = [], []; prevkey = None; t0 = time.time()
        first = True; t_prev = np.asarray(data['target'][0], float)
        for i, q in enumerate(rows):
            R0 = data['R'][i] + self.free - 1.; target = data['target'][i]; B = data['B'][i]; A, C = B[:2], B[2:]
            key = np.r_[R0.ravel(), target].tobytes(); s = q['clamp_s_mm']
            iterations = 0; precomp = 0.
            if key != prevkey or s != s_prev or first:
                # Tension-aware arrival: predict from measured tensions and nominal gains.
                T_now = self.d.force(z, R_applied).ravel()
                dR = (R0 + offset.reshape(3, 4) / 1000 - R_applied).ravel() * 1000
                T_pred = T_now + C @ dR
                if not first and T_pred.min() < a.tension_target:
                    x, _ = qp(A, C, T_pred, np.zeros(2), offset, a.tension_target, a.precomp_limit)
                    offset = offset + x; precomp = float(np.max(np.abs(x)))
                R_new = R0 + offset.reshape(3, 4) / 1000
                if first:
                    zs = self.d.solve(z, R_new)
                    z = z if zs is None else zs
                    rec, P = self.check(z, R_new, s, target, 'start', i, q['phase']); self.trace.append(rec); self.last_points = P
                else:
                    z = self.transition(z, R_applied, s_prev, t_prev, R_new, s, target, 'feedforward', i, q['phase'])
                R_applied = R_new; s_prev = s; first = False
                previous_error = None
                for it in range(a.max_iter):
                    err = error(target, angles(self.r, z)); T = self.d.force(z, R_applied).ravel()
                    norm = float(np.max(np.abs(err))); damping = adapt_scale(previous_error, norm, damping); previous_error = norm
                    if norm <= .2 and T.min() >= a.settle_tension:
                        break
                    delta, _ = qp(A, C, T, err, offset, a.tension_target, .25); delta *= damping
                    if np.max(np.abs(delta)) < 1e-8:
                        break
                    offset = offset + delta; R_new = R0 + offset.reshape(3, 4) / 1000
                    z = self.transition(z, R_applied, s, target, R_new, s, target, 'correction', i, q['phase'])
                    R_applied = R_new; iterations += 1
            rec, P = self.check(z, R_applied, s, target, 'settled', i, q['phase'])
            rec.update(target_yaw_deg=float(target[0]), target_elevation_deg=float(target[1]), iterations=iterations,
                       precompensation_mm=precomp, offset_mm=offset.tolist(), correction_scale=damping)
            records.append(rec); Z.append(z.copy()); prevkey = key; t_prev = np.asarray(target, float)
            if i % 50 == 0:
                print(f"{self.case} {i} {q['phase']} err {max(abs(rec['yaw_error_deg']), abs(rec['elevation_error_deg'])):.3f} "
                      f"Tmin {rec['minimum_tension_n']:.2f} trace {len(self.trace)} maxmove {self.max_move:.2f} t {time.time() - t0:.0f}s", flush=True)
        return records, Z


def summarize(case, records, trace, args):
    def block(v):
        return dict(states=len(v), failed_checks=sum(not x['checks_pass'] for x in v),
                    below_operating_tension=sum(not x['operating_tension_pass'] for x in v),
                    unstable=sum(x['minimum_eigenvalue'] <= 1e-7 for x in v), geometry_failures=sum(not x['geometry_pass'] for x in v),
                    clearance_failures=sum(x['clearance_mm'] - 1.5 < 5 for x in v),
                    minimum_tension_n=min(x['minimum_tension_n'] for x in v), peak_tension_n=max(x['peak_tension_n'] for x in v),
                    minimum_eigenvalue=min(x['minimum_eigenvalue'] for x in v), minimum_clearance_mm=min(x['clearance_mm'] for x in v),
                    maximum_node_move_mm=max(x['node_move_mm'] for x in v))
    settled = block(records); tr = block([t for t in trace if t['kind'] != 'start'])
    start = next((t for t in trace if t['kind'] == 'start'), None)
    settled.update(maximum_yaw_error_deg=max(abs(x['yaw_error_deg']) for x in records),
                   maximum_elevation_error_deg=max(abs(x['elevation_error_deg']) for x in records),
                   maximum_offset_mm=max(np.max(np.abs(x['offset_mm'])) for x in records),
                   samples_not_settled=sum((max(abs(x['yaw_error_deg']), abs(x['elevation_error_deg'])) > .2) or x['minimum_tension_n'] < args.settle_tension for x in records))
    kinds = {k: sum(t['kind'] == k for t in trace) for k in ('start', 'feedforward', 'correction')}
    return dict(case=case, samples=len(records), completed=len(records) == 1069, controller_uses_plant_parameters=False,
                settings=dict(tension_target_n=args.tension_target, settle_tension_n=args.settle_tension, precomp_limit_mm=args.precomp_limit,
                              rope_step_mm=args.rope_step, node_step_mm=args.node_step, max_iterations=args.max_iter),
                settled=settled, trace=tr, trace_states_by_kind=kinds,
                pre_control_start=None if start is None else dict(minimum_tension_n=start['minimum_tension_n'], minimum_eigenvalue=start['minimum_eigenvalue']))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=list(CASES), required=True); p.add_argument('--limit', type=int)
    p.add_argument('--tension-target', type=float, default=3.); p.add_argument('--settle-tension', type=float, default=2.5)
    p.add_argument('--precomp-limit', type=float, default=.5); p.add_argument('--rope-step', type=float, default=.25)
    p.add_argument('--node-step', type=float, default=4.5); p.add_argument('--max-depth', type=int, default=8)
    p.add_argument('--max-iter', type=int, default=16); p.add_argument('--out', default=None)
    a = p.parse_args()
    out = Path(a.out).resolve() if a.out else OUT; out.mkdir(exist_ok=True)
    run = Runner(a.case, a)
    records, Z = run.run()
    summary = summarize(a.case, records, run.trace, a)
    tag = a.case + (f'_limit{a.limit}' if a.limit else '')
    (out / f'{tag}.json').write_text(json.dumps(records, indent=1))
    (out / f'{tag}_trace.json').write_text(json.dumps(run.trace, indent=1))
    (out / f'{tag}_summary.json').write_text(json.dumps(summary, indent=2))
    np.savez_compressed(out / f'{tag}_states.npz', closed=np.asarray(Z))
    flat = []
    for q in records:
        row = {k: v for k, v in q.items() if not isinstance(v, list)}
        for k, n in enumerate(NAMES):
            row[n + '_offset_mm'] = q['offset_mm'][k]; row[n + '_tension_n'] = q['tensions_n'][k]
        flat.append(row)
    with open(out / f'{tag}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
