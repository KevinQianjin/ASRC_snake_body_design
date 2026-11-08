"""M-module axial stiffness (EA) requirement sweep for U4+M2.

Question: how much stiffer must the M module be axially (EA) and in bending
(EI) before an actively straightened front exists at or
below the 5% axial strain diagnostic?

Reuses the 2026-11-06 planar kernel (stiffness_63mm_20261106/run_study.py)
read-only. Only M EA and M EI are multiplied by scale factors. U properties,
masses, geometry, 500 g head, tendon routing and search bounds are unchanged.
Results are planar elastic diagnostics, not hardware ratings.

Usage:
    python run_sweep.py [--u 4 --m 2 --pitch 20 --scales 1 3 10 30 100 1000]
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import sys, json, argparse, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'stiffness_63mm_20261106'))
sys.path.insert(0, str(HERE.parent))
import run_study as base  # noqa: E402
from refine_front import finer_seed  # noqa: E402
from front_solver import write_csv  # noqa: E402

OUT = HERE / 'results'
STRAIN_LIMIT = .05
COARSE_BOUND = .0485  # same coarse margin below 5% as the 2026-11-06 study


class ScaledRod(base.DatabaseRod):
    def __init__(self, u, m, anchors, pitch=20, sub=4, common=0, ea_scale=1., ei_scale=1.):
        super().__init__(u, m, anchors, pitch, sub, common)
        self.ea_scale, self.ei_scale = float(ea_scale), float(ei_scale)
        self.module_EA = self.module_EA.copy()
        self.module_EI = self.module_EI.copy()
        self.module_EA[u:] *= self.ea_scale
        self.module_EI[u:] *= self.ei_scale
        self.EA = np.repeat(self.module_EA, sub)
        self.EI = np.repeat(self.module_EI, sub)

    def solve_ramped(self, D, seed, steps=20):
        """Direct solve, then fall back to a tension ramp from the seed shape."""
        x = self.solve(D, seed)
        if x is not None:
            return x
        x = self.free()
        for f in np.linspace(1 / steps, 1, steps):
            if x is None:
                return None
            x = self.solve(np.asarray(D) * f, x)
        return x


def layouts(u, m):
    return [('single', [u + m]), ('two', [u, u + m]), ('three', [u // 2, u, u + m]),
            ('three_distal', [u, u + max(1, m // 2), u + m])]


def score(row):
    return row['maximum_axis_deviation_mm'] + .5 * max(0, row['nominal_front_length_mm'] - row['axial_projection_mm'])


def run(u, m, pitch, scales, ei_scales):
    OUT.mkdir(parents=True, exist_ok=True)
    rows, attempts, arrays = [], [], {}
    for ei in ei_scales:
     carried = {}
     for scale in scales:
        for arch, anchors in layouts(u, m):
            r = ScaledRod(u, m, anchors, pitch, ea_scale=scale, ei_scale=ei)
            free = r.free()
            if free is None:
                print(scale, arch, 'no free equilibrium', flush=True)
                continue
            seeds = [(free, np.zeros(len(anchors)), 'sag')]
            ideal = r.ideal_controls()
            seed = r.straight_seed()
            for g in np.linspace(9.81 / 30, 9.81, 30):
                q = r.solve(ideal * g / 9.81, seed, g)
                if q is None:
                    break
                seed = q
            else:
                seeds.append((seed, ideal, 'moment_compensation'))
            for mode, bound in [('shape_only', .3), ('low_strain', COARSE_BOUND)]:
                use = list(seeds)
                for key in [(arch, mode), (arch, 'shape_only')]:
                    if key in carried:
                        px, pD = carried[key]
                        sx = r.solve(pD, px)
                        if sx is not None:
                            use.append((sx, pD, 'continuation_' + key[1]))
                cands = []
                for x, D, label in use:
                    t0 = time.time()
                    xx, DD, info = r.optimize(x, D, bound)
                    res = r.residual(r.evaluate(xx, r.control_matrix(DD))[1])
                    ok = res < 2e-7 and np.max(np.abs(xx[1::2])) <= bound + 1e-7
                    attempts.append(dict(ea_scale=scale, ei_scale=ei, architecture=arch, strain_mode=mode, seed=label,
                                         residual=res, admissible=bool(ok), **info))
                    if ok:
                        row, _, _ = r.metrics(xx, DD)
                        cands.append((score(row), xx, DD))
                if not cands:
                    print(f'scale {scale:g} {arch} {mode}: no admissible solution', flush=True)
                    rows.append(dict(ea_scale=scale, ei_scale=ei, architecture=arch, strain_mode=mode, anchors=anchors,
                                     status='no_admissible_stationary_solution_found'))
                    continue
                _, x, D = min(cands, key=lambda q: q[0])
                carried[arch, mode] = (x.copy(), D.copy())
                fine = ScaledRod(u, m, anchors, pitch, sub=8, ea_scale=scale, ei_scale=ei)
                xf = fine.solve_ramped(D, finer_seed(x, r, fine))
                if xf is None:
                    rows.append(dict(ea_scale=scale, ei_scale=ei, architecture=arch, strain_mode=mode, anchors=anchors,
                                     status='fine_mesh_solve_failed'))
                    continue
                row, p, d = fine.metrics(xf, D, geometry=True)
                sid = f'ea{scale:g}_ei{ei:g}_{arch}_{mode}'
                arrays[sid + '_points_m'] = p
                arrays[sid + '_strain'] = d['eps']
                row.update(ea_scale=scale, ei_scale=ei, M_EA_n=float(fine.module_EA[-1]),
                           M_EI_nm2=float(fine.module_EI[-1]), architecture=arch,
                           strain_mode=mode, state_id=sid, status='best_local_stationary_solution_found')
                rows.append(row)
                print(f'EA x{scale:g} EI x{ei:g} {arch:12s} {mode:10s} offset {row["maximum_axis_deviation_mm"]:7.2f} mm '
                      f'tan {row["maximum_tangent_error_deg"]:6.2f} deg strain {100*row["max_abs_axial_strain"]:6.2f}% '
                      f'straight {row["all_straight_diagnostics_pass"]} T {np.round(D,1)}', flush=True)
        (OUT / 'sweep_rows.json').write_text(json.dumps(rows, indent=1, default=float), encoding='utf-8')
        np.savez_compressed(OUT / 'sweep_states.npz', **arrays)
    write_csv(OUT / 'sweep_rows.csv', [r for r in rows if 'maximum_axis_deviation_mm' in r])
    write_csv(OUT / 'optimizer_attempts.csv', attempts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--u', type=int, default=4)
    ap.add_argument('--m', type=int, default=2)
    ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--scales', type=float, nargs='+', default=[1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 100, 300, 1000])
    ap.add_argument('--ei-scales', type=float, nargs='+', default=[1, 1.25, 1.5, 2, 3, 5])
    a = ap.parse_args()
    run(a.u, a.m, a.pitch, a.scales, a.ei_scales)
