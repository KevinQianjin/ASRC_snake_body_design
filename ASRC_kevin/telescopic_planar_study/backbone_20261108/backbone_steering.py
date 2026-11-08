"""Spatial steering and held-elevation search for U4+M2 with the NiTi backbone in M.

Reuses the 2026-11-06 spatial kernel, optimizer and acceptance rules
(steering_63mm_20261106/search_steering.py, extend_search.py) unchanged; only
the rod properties differ (backbone.spatial_rod). Directions: right (unrestricted
yaw), up, down, and right_level (yaw with world head elevation held at
pitch +/- 5 deg). Low-strain mode (coarse |strain| <= 4.75%) only.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse, time
import numpy as np
from backbone import spatial_rod, planar_rod, HERE
from search_steering import optimize, acceptable, DIRECTIONS, layouts
from spatial_model import refine_seed
from front_solver import write_csv

OUT = HERE / 'results'


def validate(variant):
    out = []
    for u, m in [(4, 2), (6, 3)]:
        r = spatial_rod(u, m, [u, u + m], sub=2, variant=variant)
        rng = np.random.default_rng(u)
        z = rng.normal(size=r.ndof) * .01
        T = np.array([[4., 2., 1., .5], [3., .7, 1., 2.]])
        E, g = r.evaluate(z, T)
        v = rng.normal(size=r.ndof); v /= np.linalg.norm(v); h = 2e-6
        fd = (r.evaluate(z + h * v, T)[0] - r.evaluate(z - h * v, T)[0]) / (2 * h)
        assert abs(fd - g @ v) < 2e-7, (fd, g @ v)
        p = r.planar
        x = p.straight_seed(); x[::2] += np.linspace(-.02, -.4, p.m); x[1::2] = -.001
        C = np.array([[5., 0, 0, 0], [3., 0, 0, 0]])
        ep = r.evaluate(r.lift_planar(x), C)[0]
        E2 = p.evaluate(x, C)[0]
        assert abs(ep - E2) < 1e-9, (ep, E2)
        out.append(dict(configuration=r.label, variant=variant, gradient_error=float(abs(fd - g @ v)), planar_energy_error=float(abs(ep - E2))))
    return out


def held_seed_tensions(variant, pitch, arch, k):
    """Actively straightened planar tensions from backbone_planar.py, if available."""
    f = OUT / 'planar_U4_M2_rows.json'
    if not f.exists():
        return None
    name = {'three_U': 'three', 'three_M': 'three_distal'}.get(arch, arch)
    rows = [q for q in json.loads(f.read_text()) if q.get('variant') == variant and round(q.get('pitch_deg', 0)) == pitch
            and q.get('architecture') == name and q.get('strain_mode') == 'low_strain' and 'top_extra_tensions_n' in q]
    if not rows:
        return None
    C = np.zeros((k, 4)); C[:, 0] = rows[0]['top_extra_tensions_n']
    return C


def run(u, m, variant, pitch, maxiter):
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f'steer_U{u}_M{m}_{variant}_p{pitch:g}'
    rows, attempts, states = [], [], {}
    mode = 'low_strain'
    for arch, anchors in layouts(u, m):
        r = spatial_rod(u, m, anchors, pitch, 2, variant)
        xp = r.planar.free()
        zbase = r.solve(np.zeros((r.k, 4)), r.lift_planar(xp)) if xp is not None else None
        if zbase is None:
            rows.append(dict(arch=arch, status='no_loaded_baseline')); continue
        Czero = np.zeros((r.k, 4))
        baseline, _, _ = r.metrics(zbase, Czero, stability=True)
        held = None
        Ch = held_seed_tensions(variant, pitch, arch, r.k)
        if Ch is not None:
            held = r.solve(Ch, zbase)
        for direction in ['right', 'up', 'down', 'right_level']:
            base_dir = 'right' if direction == 'right_level' else direction
            cross = np.radians(pitch) if direction == 'right_level' else None
            seeds = [(zbase, Czero, 'loaded_sag')]
            trial = np.zeros_like(Czero); trial[-1, {'right': 1, 'up': 0, 'down': 2}[base_dir]] = 4.
            if base_dir == 'right': trial[-1, 0] = 2.
            zs = r.solve(trial, zbase)
            if zs is not None: seeds.append((zs, trial, 'small_active_tension'))
            if held is not None:
                seeds.append((held, Ch, 'actively_held_front'))
                if base_dir != 'down':
                    T2 = Ch.copy(); T2[-1, 1 if base_dir == 'right' else 0] += 4.
                    z2 = r.solve(T2, held)
                    if z2 is not None: seeds.append((z2, T2, 'held_plus_steer'))
            if direction == 'right_level':
                prev = next((q for q in rows if q.get('architecture') == arch and q.get('direction') == 'right' and q.get('qualifies')), None)
                if prev: seeds.append((states[prev['state_id'] + '_z'], states[prev['state_id'] + '_T'], 'unrestricted_yaw'))
            cands = []
            for z0, T0, label in seeds:
                t0 = time.time()
                z, C, info = optimize(r, z0, T0, base_dir, mode, cross_reference=cross, maxiter=maxiter)
                info.update(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch, direction=direction, seed=label)
                attempts.append(info)
                if not info['feasible_stationary']:
                    continue
                row, _, _ = r.metrics(z, C, stability=True)
                row['qualifies'] = acceptable(row, mode, base_dir, cross)
                row['directional_angle_deg'] = DIRECTIONS[base_dir][1] * (row['yaw_deg'] if base_dir == 'right' else row['vertical_projected_deg'])
                if row['qualifies']:
                    cands.append((row, z, C))
            if direction != 'right_level' and acceptable(baseline, mode, base_dir):
                b = dict(baseline, qualifies=True, directional_angle_deg=DIRECTIONS[base_dir][1] * (baseline['yaw_deg'] if base_dir == 'right' else baseline['vertical_projected_deg']))
                cands.append((b, zbase, Czero))
            if not cands:
                rows.append(dict(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch, anchors=anchors,
                                 direction=direction, strain_mode=mode, qualifies=False, status='no_qualifying_stationary_solution_found'))
                print(f'{tag} {arch:8s} {direction:12s} none', flush=True)
                continue
            best = max(c[0]['directional_angle_deg'] for c in cands)
            row, z, C = min([c for c in cands if c[0]['directional_angle_deg'] >= best - .01], key=lambda c: c[0]['maximum_single_tendon_n'])
            sid = f'{arch}_{direction}'
            row.update(variant=variant, architecture=arch, direction=direction, strain_mode=mode, state_id=sid, status='coarse_2cell')
            # Same-tension 8-cell check.
            f8 = spatial_rod(u, m, anchors, pitch, 8, variant)
            z8 = f8.solve(C, refine_seed(z, r, f8))
            if z8 is not None:
                r8, _, _ = f8.metrics(z8, C, stability=True)
                row['fine8_qualifies'] = acceptable(r8, mode, base_dir, cross)
                for key in ['yaw_deg', 'vertical_projected_deg', 'world_elevation_deg', 'max_abs_axial_strain', 'geometry_pass', 'stable_fixed_winch']:
                    row['fine8_' + key] = r8[key]
            else:
                row['fine8_qualifies'] = None
            rows.append(row); states[sid + '_z'] = z; states[sid + '_T'] = C
            print(f"{tag} {arch:8s} {direction:12s} angle {row['directional_angle_deg']:8.2f} elev {row['world_elevation_deg']:7.2f} "
                  f"strain {100*row['max_abs_axial_strain']:5.2f}% peakT {row['maximum_single_tendon_n']:7.2f} "
                  f"8cell ok {row.get('fine8_qualifies')} elev8 {row.get('fine8_world_elevation_deg', float('nan')):7.2f}", flush=True)
            (OUT / f'{tag}.json').write_text(json.dumps(dict(baseline=baseline, rows=rows), indent=1, default=float))
            np.savez_compressed(OUT / f'{tag}_states.npz', **states)
    write_csv(OUT / f'{tag}_attempts.csv', attempts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['validate', 'run'])
    ap.add_argument('--u', type=int, default=4); ap.add_argument('--m', type=int, default=2)
    ap.add_argument('--variant', default='niti18_E40'); ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--maxiter', type=int, default=180)
    a = ap.parse_args()
    if a.action == 'validate':
        res = validate(a.variant) + validate('none')
        (OUT / 'spatial_validation.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
    else:
        run(a.u, a.m, a.variant, a.pitch, a.maxiter)
