"""Re-run the 3 N startup, yaw sweep, reference cycle, gains and closed loop with separate tendon lanes.

Usage (from this folder), in order:
    python lanes_study.py startup
    python lanes_study.py sweep
    python lanes_study.py reference
    python lanes_study.py gains
    python lanes_study.py cycle --case nominal      # also E75, payload550g, free1500mm, ropeEA80pct

Lanes: anchor set A (U4) 21 mm, B (M5) 24 mm, C (M6) 27 mm (lanes.py). Every step
uses the existing, unchanged scripts with the lane rope geometry installed, and
writes to separate folders so the shared-hole results stay untouched:
results_lanes/, length_cycle_results_lanes/, closed_loop_lanes_results/.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import sys, argparse, runpy, json
from pathlib import Path
import lanes

HERE = Path(__file__).resolve().parent
RES = HERE / 'results_lanes'
REF = HERE / 'length_cycle_results_lanes'
CL = HERE / 'closed_loop_lanes_results'
STARTUP = RES / 'startup_niti18_E40_p20_pre3_states.npz'
SWEEP = RES / 'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['startup', 'sweep', 'reference', 'gains', 'cycle'])
    ap.add_argument('--case', default='nominal')
    ap.add_argument('--radii', type=float, nargs=3, default=list(lanes.DEFAULT_RADII_MM), help='lane radii (mm) for sets A, B, C')
    a = ap.parse_args()
    lanes.install(a.radii)  # before importing anything that binds spatial_rod
    for d in (RES, REF, CL):
        d.mkdir(exist_ok=True)
    (RES / 'lanes.json').write_text(json.dumps(dict(lane_radii_mm=dict(A_U4=a.radii[0], B_M5=a.radii[1], C_M6=a.radii[2]),
                                                    directions='up, right, down, left on the same rays'), indent=1))
    if a.step == 'startup':
        import startup_sweep as m
        m.OUT = RES
        m.run('niti18_E40', 20., 3., 2.5)
    elif a.step == 'sweep':
        import min_force_sweep as m
        m.OUT = RES
        m.run('niti18_E40', 20., [4, 5, 6], 5., 3., exact=True, smooth=1., seed_startup=str(STARTUP), elev_tol=1.)
    elif a.step == 'reference':
        import length_cycle as L
        L.SOURCE = SWEEP; L.STARTUP = STARTUP; L.OUT = REF
        L.run('nominal', L.FastTank())
    elif a.step == 'gains':
        import closed_loop_cycle as v1
        v1.REF = REF; v1.OUT = CL
        v1.prepare()
    else:
        sys.argv = ['closed_loop_v2.py', '--case', a.case, '--ref', str(REF), '--gains', str(CL / 'nominal_gains.npz'), '--out', str(CL)]
        runpy.run_path(str(HERE / 'closed_loop_v2.py'), run_name='__main__')


if __name__ == '__main__':
    main()
