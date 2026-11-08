"""Planar active straightening with the NiTi backbone in M, including rod mass.

Configurations U4+M2, U6+M3, U8+M4; pitches 15/20/25 deg; variants none
(supplied M), niti18_E40 and niti18_E75. Same layouts, optimizer, seeds and
pass criteria as the 2026-11-06 study and the 2026-11-08 EA/EI sweep.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse, time
import numpy as np
from backbone import planar_rod, VARIANTS, HERE
from refine_front import finer_seed
from front_solver import write_csv
from itertools import combinations
from run_sweep import layouts as standard_layouts, score, COARSE_BOUND


def all_three_layouts(u, m):
    """Every 3-set layout with one set anchored at the head."""
    return [(f'a{a}_{b}_{u+m}', [a, b, u + m]) for a, b in combinations(range(1, u + m), 2)]


LAYOUTS = standard_layouts

OUT = HERE / 'results'
TAG_SUFFIX = ''


def fine_metrics(u, m, anchors, pitch, variant, x, coarse, D, sub):
    fine = planar_rod(u, m, anchors, pitch, sub, variant)
    xf = fine.solve_ramped(D, finer_seed(x, coarse, fine))
    if xf is None:
        return None, None, None
    row, p, d = fine.metrics(xf, D, geometry=True)
    return row, p, xf


def run(u, m, pitches, variants):
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f'U{u}_M{m}' + TAG_SUFFIX
    rows, attempts, arrays = [], [], {}
    for variant in variants:
        for pitch in pitches:
            for arch, anchors in LAYOUTS(u, m):
                r = planar_rod(u, m, anchors, pitch, 4, variant)
                free = r.free()
                if free is None:
                    rows.append(dict(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch, status='no_free_equilibrium'))
                    continue
                seeds = [(free, np.zeros(len(anchors)), 'sag')]
                ideal = r.ideal_controls(); seed = r.straight_seed()
                for g in np.linspace(9.81 / 30, 9.81, 30):
                    q = r.solve(ideal * g / 9.81, seed, g)
                    if q is None:
                        break
                    seed = q
                else:
                    seeds.append((seed, ideal, 'moment_compensation'))
                shape_best = None
                for mode, bound in [('shape_only', .3), ('low_strain', COARSE_BOUND)]:
                    use = list(seeds) + ([(shape_best[0], shape_best[1], 'shape_only_branch')] if shape_best else [])
                    cands = []
                    for x, D, label in use:
                        xx, DD, info = r.optimize(x, D, bound)
                        res = r.residual(r.evaluate(xx, r.control_matrix(DD))[1])
                        ok = res < 2e-7 and np.max(np.abs(xx[1::2])) <= bound + 1e-7
                        attempts.append(dict(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch,
                                             strain_mode=mode, seed=label, residual=res, admissible=bool(ok), **info))
                        if ok:
                            cands.append((score(r.metrics(xx, DD)[0]), xx, DD))
                    if not cands:
                        rows.append(dict(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch,
                                         strain_mode=mode, anchors=anchors, status='no_admissible_stationary_solution_found'))
                        continue
                    _, x, D = min(cands, key=lambda q: q[0])
                    if mode == 'shape_only':
                        shape_best = (x.copy(), D.copy())
                    row, p, _ = fine_metrics(u, m, anchors, pitch, variant, x, r, D, 8)
                    if row is None:
                        rows.append(dict(configuration=r.label, variant=variant, pitch_deg=pitch, architecture=arch,
                                         strain_mode=mode, anchors=anchors, status='fine_mesh_solve_failed'))
                        continue
                    sid = f'{tag}_{variant}_p{pitch:g}_{arch}_{mode}'
                    arrays[sid + '_points_m'] = p
                    row.update(variant=variant, architecture=arch, strain_mode=mode, state_id=sid,
                               module_mass_with_rod_g=float(r.bare_mass.sum() * 1000),
                               M_EA_n=float(r.module_EA[-1]), M_EI_nm2=float(r.module_EI[-1]),
                               status='best_local_stationary_solution_found')
                    rows.append(row)
                    print(f'{r.label} {variant:10s} {pitch:4.0f} {arch:12s} {mode:10s} off {row["maximum_axis_deviation_mm"]:7.2f} '
                          f'tan {row["maximum_tangent_error_deg"]:6.2f} strain {100*row["max_abs_axial_strain"]:5.2f}% '
                          f'pass {row["all_straight_diagnostics_pass"]} T {np.round(D,1)}', flush=True)
            (OUT / f'planar_{tag}_rows.json').write_text(json.dumps(rows, indent=1, default=float))
            np.savez_compressed(OUT / f'planar_{tag}_states.npz', **arrays)
    write_csv(OUT / f'planar_{tag}_rows.csv', [q for q in rows if 'maximum_axis_deviation_mm' in q])
    write_csv(OUT / f'planar_{tag}_optimizer_attempts.csv', attempts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--u', type=int, required=True); ap.add_argument('--m', type=int, required=True)
    ap.add_argument('--pitches', type=float, nargs='+', default=[15, 20, 25])
    ap.add_argument('--variants', nargs='+', default=list(VARIANTS))
    ap.add_argument('--all-three', action='store_true', help='search every 3-set layout instead of the 4 standard ones')
    a = ap.parse_args()
    if a.all_three:
        LAYOUTS = all_three_layouts
        TAG_SUFFIX = '_all3'
    run(a.u, a.m, a.pitches, a.variants)
