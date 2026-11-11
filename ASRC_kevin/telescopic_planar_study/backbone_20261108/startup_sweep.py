"""Stable startup: raise the head from natural sag to the working elevation with every rope tensioned.

Start: natural sag with every rope at the pretension P (yaw 0). Then the held
world head elevation is raised in steps to the installation pitch (20 deg).
At each step the largest rope tension is minimised (min_force_sweep.min_force,
exact elevation, yaw 0, all ropes >= P, smoothness penalty), solved at 4 cells
per module and re-solved at 8. Each 8-cell state is checked for equilibrium,
geometry, strain <= 4.75 %, all tensions >= P - 0.05 N and fixed-winch stability.
The states are the startup reference poses for length_cycle.py (--startup).
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse
import numpy as np
from backbone import spatial_rod, HERE
from spatial_model import refine_seed
from refine_steering import stationary
from min_force_sweep import min_force

OUT = HERE / 'results'
ANCH = [4, 5, 6]


def check(r, z, C, P, elev=None):
    m, _, _ = r.metrics(z, C, stability=True)
    ok = (m['equilibrium_residual'] < 2e-6 and m['geometry_pass'] and m['stable_fixed_winch'] and m['max_abs_axial_strain'] <= .0475 + 1e-6
          and float(np.min(C)) >= P - .05 and abs(m['yaw_deg']) <= 1.0 and (elev is None or abs(m['world_elevation_deg'] - elev) <= 1.0))
    return ok, m


def run(variant, pitch, P, step):
    r4 = spatial_rod(4, 2, ANCH, pitch, 4, variant); r8 = spatial_rod(4, 2, ANCH, pitch, 8, variant)
    C = np.full((3, 4), float(P))
    z = r4.solve(C, r4.lift_planar(r4.planar.free()))
    ok, m = check(r4, z, C, P)
    e0 = m['world_elevation_deg']
    print(f'sag with {P:g} N on every rope: elevation {e0:.2f} deg, stable {m["stable_fixed_winch"]}', flush=True)
    targets = list(np.arange(np.ceil(e0 / step) * step, pitch, step)) + [float(pitch)]
    rows, states = [], {}
    z8 = r8.solve(C, refine_seed(z, r4, r8)); ok8, m8 = check(r8, z8, C, P)
    rows.append(dict(elevation_target_deg=float(e0), elevation_deg=m8['world_elevation_deg'], ok8=ok8, tensions_n=C.tolist(),
                     peak_n=float(C.max()), stable=m8['stable_fixed_winch'], eig=m8['minimum_fixed_winch_eigenvalue'], kind='natural_sag'))
    states['k0_z8'] = z8; states['k0_T8'] = C; states['k0_z4'] = z; states['k0_T4'] = C
    k = 1
    for e in targets:
        z4, C4, info = min_force(r4, z, C, 0., pitch, pretension=P, exact=True, smooth=1., Cprev=C, elev=e)
        ok4, _ = check(r4, z4, C4, P, e)
        if not ok4:
            print(f'elevation {e:6.2f}: 4-cell state not acceptable ({info["message"][:40]}); stop', flush=True); break
        g8 = refine_seed(z4, r4, r8); x8 = stationary(r8, C4, g8); C8 = C4
        ok8 = False
        if x8 is not None:
            ok8, m8 = check(r8, x8, C8, P, e)
        if not ok8:
            x8, C8, _ = min_force(r8, g8 if x8 is None else x8, C4, 0., pitch, maxiter=120, pretension=P, exact=True, smooth=1., Cprev=C4, elev=e)
            ok8, m8 = check(r8, x8, C8, P, e)
        rows.append(dict(elevation_target_deg=float(e), elevation_deg=m8['world_elevation_deg'], ok8=ok8, tensions_n=np.asarray(C8).tolist(),
                         peak_n=float(np.max(C8)), stable=m8['stable_fixed_winch'], eig=m8['minimum_fixed_winch_eigenvalue'], kind='raise'))
        print(f"elevation {e:6.2f}: 8-cell ok {ok8} elev {m8['world_elevation_deg']:6.2f} peak {np.max(C8):6.2f} N eig {m8['minimum_fixed_winch_eigenvalue']:.3f}", flush=True)
        if not ok8:
            break
        states[f'k{k}_z8'] = x8; states[f'k{k}_T8'] = np.asarray(C8); states[f'k{k}_z4'] = z4; states[f'k{k}_T4'] = np.asarray(C4); k += 1
        z, C = z4, C4
    tag = f'startup_{variant}_p{pitch:g}_pre{P:g}'
    (OUT / f'{tag}.json').write_text(json.dumps(rows, indent=1, default=float))
    np.savez_compressed(OUT / f'{tag}_states.npz', **states)
    print(f'{tag}: {k} states, all ok {all(q["ok8"] for q in rows)}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='niti18_E40'); ap.add_argument('--pitch', type=float, default=20)
    ap.add_argument('--pretension', type=float, default=3.); ap.add_argument('--step', type=float, default=2.5)
    a = ap.parse_args(); run(a.variant, a.pitch, a.pretension, a.step)
