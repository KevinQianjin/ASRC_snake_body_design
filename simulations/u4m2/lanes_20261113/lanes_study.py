"""Re-run the 3 N startup, yaw sweep, reference cycle, gains and closed loop with separate tendon lanes.

Usage (from this folder), in order:
    python lanes_study.py startup --guide-spacing-mm 24
    python lanes_study.py sweep --guide-spacing-mm 24
    python lanes_study.py reference --guide-spacing-mm 24
    python lanes_study.py gains --guide-spacing-mm 24
    python lanes_study.py cycle --case nominal --guide-spacing-mm 24      # also E75, payload550g, free1500mm, ropeEA80pct

Lanes: anchor set A (U4) 21 mm, B (M5) 24 mm, C (M6) 27 mm (lanes.py). Every step
reuses the solvers in ../backbone_20261108 with the lane rope geometry installed, and
writes to separate guide-specific folders, leaving the original lane results untouched.
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
    ap.add_argument('step', choices=['startup', 'sweep', 'fine_sweep', 'reference', 'gains', 'cycle'])
    ap.add_argument('--case', default='nominal')
    ap.add_argument('--radii', type=float, nargs=3, default=list(lanes.DEFAULT_RADII_MM), help='lane radii (mm) for sets A, B, C')
    ap.add_argument('--guide-spacing-mm', type=float, default=None,
                    help='ideal internal guide pitch in M5/M6; omit for legacy endpoint-only chords')
    ap.add_argument('--output-tag', default=None,
                    help='optional isolated output suffix for comparison runs')
    ap.add_argument('--output-root', type=Path, help='group inverse/reference/closed_loop outputs under one folder')
    ap.add_argument('--mass-config', type=Path, help='CAD-estimated module mass JSON; homogenised stiffness remains nominal')
    ap.add_argument('--resume', action='store_true', help='resume a fine_sweep after revalidating saved states')
    a = ap.parse_args()
    global RES, REF, CL, STARTUP, SWEEP
    suffix = '' if a.guide_spacing_mm is None else f'_guides_{a.guide_spacing_mm:g}mm'
    if a.output_tag:
        suffix += f'_{a.output_tag}'
    RES = HERE / f'results_lanes{suffix}'
    REF = HERE / f'length_cycle_results_lanes{suffix}'
    CL = HERE / f'closed_loop_lanes_results{suffix}'
    if a.output_root is not None:
        root=a.output_root.resolve()
        RES,REF,CL=(root/name for name in ('inverse','reference','closed_loop'))
    STARTUP = RES / 'startup_niti18_E40_p20_pre3_states.npz'
    SWEEP = RES / 'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'
    mass_config = None if a.mass_config is None else json.loads(a.mass_config.read_text())
    lanes.install(a.radii, a.guide_spacing_mm, mass_config)  # before importing anything that binds spatial_rod
    for d in (RES, REF, CL):
        d.mkdir(exist_ok=True,parents=True)
    (RES / 'lanes.json').write_text(json.dumps(dict(lane_radii_mm=dict(A_U4=a.radii[0], B_M5=a.radii[1], C_M6=a.radii[2]),
        directions='up, right, down, left on the same rays', guide_max_span_mm=a.guide_spacing_mm,
        fine_mesh_guide_z_mm=None if a.guide_spacing_mm is None else [-24,-12,12,24],
        mass_config=mass_config,
        scope='Frictionless quasi-static rod. Four-cell optimisation is a coarse seed with three uniform guides; accepted eight-cell states use four CAD stations. fine_sweep uses eight cells throughout. CAD-estimated mass is included only when mass_config is supplied. Nominal homogenised stiffness retained; guide stiffness, clamp compliance and contact excluded.'), indent=1))
    if a.step == 'startup':
        import startup_sweep as m
        m.OUT = RES
        m.run('niti18_E40', 20., 3., 2.5)
    elif a.step == 'sweep':
        import min_force_sweep as m
        m.OUT = RES
        m.run('niti18_E40', 20., [4, 5, 6], 5., 3., exact=True, smooth=1., seed_startup=str(STARTUP), elev_tol=1.)
    elif a.step == 'fine_sweep':
        import numpy as np
        from min_force_sweep import min_force, accept
        r=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
        with np.load(STARTUP) as d:
            last=max(int(k[1:-3]) for k in d.files if k.endswith('_z8'))
            z=d[f'k{last}_z8']; T=d[f'k{last}_T8']
        rows=[];states={};previous_yaw=0
        if a.resume and SWEEP.exists():
            with np.load(SWEEP) as saved:states={k:saved[k].copy() for k in saved.files}
        for yaw in range(0,176,5):
            if a.resume and f'y{yaw}_z8' in states:
                z,T=states[f'y{yaw}_z8'],states[f'y{yaw}_T8']
                ok,m=accept(r,z,T,yaw,20,.2)
                if not ok:raise ValueError(f'Saved yaw {yaw} does not satisfy this model configuration')
                rows.append(dict(yaw_target_deg=yaw,ok8=True,peak_n=float(T.max()),metrics=m,resumed=True))
                previous_yaw=yaw
                continue
            seed_z,seed_T=z.copy(),T.copy()
            z,T,info=min_force(r,z,T,yaw,20,maxiter=300,pretension=3,exact=True,smooth=1.,Cprev=T)
            ok,m=accept(r,z,T,yaw,20,.2)
            if not ok and yaw>previous_yaw:
                attempts=[dict(yaw=yaw,accepted=False,optimisation=info)]
                z,T=seed_z,seed_T
                for intermediate in range(previous_yaw+1,yaw+1):
                    z,T,subinfo=min_force(r,z,T,intermediate,20,maxiter=120,pretension=3,exact=True,smooth=1.,Cprev=T)
                    ok,m=accept(r,z,T,intermediate,20,.2)
                    attempts.append(dict(yaw=intermediate,accepted=bool(ok),optimisation=subinfo))
                    print('adaptive fine sweep',intermediate,'accepted',ok,flush=True)
                    if not ok:break
                info=dict(adaptive_attempts=attempts)
            rows.append(dict(yaw_target_deg=yaw,ok8=bool(ok),peak_n=float(T.max()),world_elevation_deg=m['world_elevation_deg'],metrics=m,optimisation=info))
            print('fine sweep',yaw,'accepted',ok,'peak',float(T.max()),flush=True)
            if ok: states[f'y{yaw}_z8']=z;states[f'y{yaw}_T8']=T
            np.savez_compressed(SWEEP,**states)
            (RES/'fine_sweep.json').write_text(json.dumps(rows,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x)))
            if not ok: raise RuntimeError(f'Fine continuation failed at yaw {yaw}; no missing states are skipped')
            previous_yaw=yaw
    elif a.step == 'reference':
        import numpy as np
        with np.load(SWEEP) as data:
            required = [f'y{y}_z8' for y in range(0,176,5)]
            if any(k not in data.files for k in required):
                raise ValueError('Incomplete yaw sweep: full 0..175 degree coverage is required')
        import length_cycle as L
        L.SOURCE = SWEEP; L.STARTUP = STARTUP; L.OUT = REF
        L.run('nominal', L.FastTank())
    elif a.step == 'gains':
        import closed_loop_cycle as v1
        v1.REF = REF; v1.OUT = CL
        v1.prepare()
        settings=CL/'settings.json';meta=json.loads(settings.read_text())
        for key in ('feedback_tension_target_n','settled_angle_tolerance_deg','maximum_iterations','adaptive_scale_floor','error_growth_threshold'):
            meta.pop(key,None)
        meta['scope']='Gain preparation only. Actual controller settings and outcomes are in nominal_summary.json.'
        settings.write_text(json.dumps(meta,indent=2))
    else:
        sys.argv = ['closed_loop_v2.py', '--case', a.case, '--ref', str(REF), '--gains', str(CL / 'nominal_gains.npz'), '--out', str(CL)]
        runpy.run_path(str(lanes.BACKBONE_DIR / 'closed_loop_v2.py'), run_name='__main__')


if __name__ == '__main__':
    main()
