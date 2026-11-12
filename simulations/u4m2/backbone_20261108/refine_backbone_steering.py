"""Refine backbone steering candidates 2 -> 4 -> 8 cells per module.

Same procedure as steering_63mm_20261106/refine_steering.py: same-tension
re-solve; if the finer state fails acceptance, local re-optimization on the
finer mesh; then a labelled force-ray recovery (0.95/0.85/0.7/0.5 x tensions).
Only states that pass acceptance at 8 cells are reported as results.
"""
import json, argparse
import numpy as np
from backbone import spatial_rod, HERE
from search_steering import optimize, acceptable, DIRECTIONS
from spatial_model import refine_seed
from refine_steering import stationary

OUT = HERE / 'results'


def score(row, direction):
    return row['yaw_deg'] if direction.startswith('right') else DIRECTIONS[direction][1] * row['vertical_projected_deg']


def refine_to(u, m, row, z, T, old_sub, new_sub, variant, pitch, maxiter):
    direction = row['direction']; plain = 'right' if direction == 'right_level' else direction
    cross = np.radians(pitch) if direction == 'right_level' else None
    old = spatial_rod(u, m, row['anchors'], pitch, old_sub, variant)
    r = spatial_rod(u, m, row['anchors'], pitch, new_sub, variant)
    guess = refine_seed(z, old, r)
    xf = stationary(r, T, guess); how = 'same_tension'
    ok = False; met = None
    if xf is not None:
        met, _, _ = r.metrics(xf, T, stability=True); ok = acceptable(met, 'low_strain', plain, cross)
    if not ok:
        xx, TT, info = optimize(r, guess if xf is None else xf, T, plain, 'low_strain', cross_reference=cross, maxiter=maxiter)
        if info['feasible_stationary']:
            mm, _, _ = r.metrics(xx, TT, stability=True)
            if acceptable(mm, 'low_strain', plain, cross):
                xf, T, met, ok, how = xx, TT, mm, True, 'fine_reoptimization'
    if not ok:
        for frac in [.95, .85, .7, .5]:
            xx = stationary(r, T * frac, guess)
            if xx is None: continue
            mm, _, _ = r.metrics(xx, T * frac, stability=True)
            if acceptable(mm, 'low_strain', plain, cross):
                xf, T, met, ok, how = xx, T * frac, mm, True, f'force_ray_{frac}'
                break
    return (xf, T, met, how) if ok else None


def run(u, m, variant, pitch, top=2, maxiter8=60):
    tag = f'steer_U{u}_M{m}_{variant}_p{pitch:g}'
    data = json.loads((OUT / f'{tag}.json').read_text())
    st = np.load(OUT / f'{tag}_states.npz')
    final = []
    suffix = '' if (top, maxiter8) == (2, 60) else f'_top{top}_it{maxiter8}'
    for direction in ['right', 'up', 'down', 'right_level']:
        group = sorted([q for q in data['rows'] if q.get('qualifies') and q['direction'] == direction],
                       key=lambda q: (-round(q['directional_angle_deg'], 2), q['maximum_single_tendon_n']))[:top]
        best = None; fours = []
        for row in group:
            z, T = st[row['state_id'] + '_z'], st[row['state_id'] + '_T']
            r4 = refine_to(u, m, row, z, T, 2, 4, variant, pitch, 110)
            if r4 is None: continue
            fours.append((row, r4))
            r8 = refine_to(u, m, row, r4[0], r4[1], 4, 8, variant, pitch, maxiter8)
            if r8 is None: continue
            xf, T8, met, how = r8
            met.update(variant=variant, architecture=row['architecture'], direction=direction, refine_4=r4[3], refine_8=how,
                       coarse_angle_deg=row['directional_angle_deg'], directional_angle_deg=score(met, direction))
            if best is None or met['directional_angle_deg'] > best['directional_angle_deg'] + .01:
                best = met
        if best is None and fours:
            # Angle-cap ladder: if no 180-deg state survives at 8 cells, find the
            # largest lower cap that does (documented, separately labelled).
            import search_steering
            for cap in [165, 150, 135, 120, 90]:
                search_steering.ANGLE_CAP = np.radians(cap)
                for row, r4 in fours:
                    r8 = refine_to(u, m, row, r4[0], r4[1], 4, 8, variant, pitch, maxiter8)
                    if r8 is None or score(r8[2], direction) > cap + .01: continue
                    met = r8[2]
                    met.update(variant=variant, architecture=row['architecture'], direction=direction, refine_4=r4[3],
                               refine_8=r8[3] + f'_cap{cap}', angle_cap_deg=cap, coarse_angle_deg=row['directional_angle_deg'],
                               directional_angle_deg=score(met, direction))
                    best = met; break
                if best is not None: break
            search_steering.ANGLE_CAP = np.pi
        if best is None:
            final.append(dict(variant=variant, pitch_deg=pitch, direction=direction, status='no_candidate_survived_8cell_refinement'))
            print(f'{tag} {direction:12s} no 8-cell result', flush=True)
        else:
            final.append(best)
            print(f"{tag} {direction:12s} {best['architecture']:8s} angle {best['directional_angle_deg']:7.2f} elev {best['world_elevation_deg']:7.2f} "
                  f"strain {100*best['max_abs_axial_strain']:.2f}% peakT {best['maximum_single_tendon_n']:.1f} via {best['refine_4']}/{best['refine_8']}", flush=True)
    (OUT / f'{tag}_refined8{suffix}.json').write_text(json.dumps(final, indent=1, default=float))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--u', type=int, default=4); ap.add_argument('--m', type=int, default=2)
    ap.add_argument('--variant', default='niti18_E40'); ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--top', type=int, default=2); ap.add_argument('--maxiter8', type=int, default=60)
    a = ap.parse_args(); run(a.u, a.m, a.variant, a.pitch, a.top, a.maxiter8)
