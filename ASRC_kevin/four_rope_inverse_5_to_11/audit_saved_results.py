"""Reload and verify saved forces, equilibrium, target semantics and refinement."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,csv,json,concurrent.futures,multiprocessing
from pathlib import Path
import numpy as np
from rope_planar import PlanarRod,HERE
from rope_three_parameter import ThreeParameterRod
from run_rope_sweep import write_json
from rescue_level_continuation import parse

def group_audit(job):
    csvfile=Path(job);rows=[parse(r) for r in csv.DictReader(csvfile.open())]
    z=np.load(csvfile.with_name(csvfile.stem+'_states.npz'));states=z['state'];forces=z['tensions']
    residual=0.;tension_error=0.;target_errors=[];checked=0;failures=[];cache={}
    for i,r in enumerate(rows):
        x=states[i];T=forces[i]
        if not np.isfinite(x).all():
            if r['head_x_mm'] is not None:failures.append([i,'state/row availability mismatch'])
            continue
        counts=tuple(r[k] for k in ['n_high','n_uni','n_directional','n_low'])
        rod=cache.setdefault(counts,PlanarRod(counts,8))
        if (T < -1e-10).any():failures.append([i,'negative tension'])
        _,g,H,d=rod.evaluate(x,T,detail=True)
        res=rod.residual(g);residual=max(residual,res)
        if res>5e-8:failures.append([i,'equilibrium residual',res])
        prefix='target' if r['target_reached'] else 'diagnostic'
        expected=np.array([r.get(f'{prefix}_tension_{name}_n') for name in ['top','right','bottom','left']],dtype=float)
        err=float(np.max(np.abs(expected-T)));tension_error=max(tension_error,err)
        if not np.isfinite(err) or err>1e-8:failures.append([i,'force column mismatch'])
        rest=d['rope_lengths']/(1+T/rod.rope_ea)+np.where(T>1e-7,0.,.001)
        recovered=rod.rope_ea/rest*np.maximum(d['rope_lengths']-rest,0.)
        if np.max(abs(recovered-T))>1e-7:failures.append([i,'fixed-length tension recovery'])
        if r['target']=='head_level' and r['target_reached']:
            h=abs(float(d['points'][-1,1]*1000));target_errors.append(h)
            if h>1.:failures.append([i,'head-level tolerance'])
        if r['target'].startswith('front_semicircle'):
            turn=np.degrees(d['theta'][-1]-d['theta'][rod.b]);sense=1 if r['target'].endswith('_up') else -1
            if abs(turn-sense*180)>1:failures.append([i,'180-degree diagnostic tolerance'])
            if not r['target_reached'] and r['target_total_tension_n'] is not None:failures.append([i,'failed semicircle labelled valid tension'])
        checked+=1
    return dict(group=csvfile.stem,states_checked=checked,max_residual=residual,
                max_force_column_error_n=tension_error,max_head_level_error_mm=max(target_errors,default=0),failures=failures)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results');p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();out=a.output_dir
    rows=[parse(r) for r in csv.DictReader((out/'all_targets.csv').open())]
    assert len(rows)==30510 and len({(r['combination'],r['target']) for r in rows})==30510
    assert len({r['combination'] for r in rows})==10170
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        groups=list(pool.map(group_audit,sorted((out/'final_groups').glob('*.csv'))))
    refinements=[]
    for front in range(5,12):
        d=round(front*8/11)
        for r in rows:
            if (r['front_modules'],r['n_high'],r['n_uni'],r['n_directional']) != (front,8,12,d):continue
            row=dict(front_modules=front,target=r['target'],state_found=r['head_x_mm'] is not None)
            if r['head_x_mm'] is not None:
                i=((r['n_high']-1)*(front-1)+(d-1))*3+{'head_level':0,'front_semicircle_up':1,'front_semicircle_down':2}[r['target']]
                z=np.load(out/'final_groups'/f'F{front:02d}_R20_states.npz');x=z['state'][i]
                fine=ThreeParameterRod((8,12,d,front-d),16,antagonistic_common=r.get('top_bottom_pair_common_n',0.))
                xx=np.zeros(fine.ndof)
                xx[::2]=np.interp(np.linspace(0,1,fine.m+1)[1:],np.linspace(0,1,len(x)//2+1),np.r_[0,x[::2]])
                xx[1::2]=np.repeat(x[1::2],2)
                kind='level' if r['target']=='head_level' else 'arc';sense=-1 if r['target'].endswith('_down') else 1
                got=fine.inverse(kind,sense,r['common_n'],initial=(xx,r['D_n'],{}),maxiter=70)
                row['refined_converged']=got is not None
                if got is not None:
                    m,dt,H=fine.shape_metrics(*got[:2],r['common_n'])
                    row.update(tension_change_n=abs(m['total_tension_n']-r['computed_total_tension_n']),
                        head_position_change_mm=float(np.hypot(m['head_x_mm']-r['head_x_mm'],m['head_y_mm']-r['head_y_mm'])),
                        core_stress_change_mpa=abs(m['max_core_stress_mpa']-r['max_core_stress_mpa']))
            refinements.append(row)
    valid=[r for r in refinements if r.get('refined_converged')]
    summary=dict(configurations=10170,rows=30510,states_checked=sum(g['states_checked'] for g in groups),
         max_equilibrium_residual=max(g['max_residual'] for g in groups),
         max_force_column_error_n=max(g['max_force_column_error_n'] for g in groups),
         max_head_level_error_mm=max(g['max_head_level_error_mm'] for g in groups),
         failures=[g for g in groups if g['failures']],
         reference_refinements=refinements,
         max_reference_tension_change_n=max(r['tension_change_n'] for r in valid),
         max_reference_position_change_mm=max(r['head_position_change_mm'] for r in valid),
         max_reference_core_stress_change_mpa=max(r['core_stress_change_mpa'] for r in valid))
    summary['passed']=bool(not summary['failures'] and all(not r['state_found'] or r.get('refined_converged',False) for r in refinements)
        and summary['max_reference_tension_change_n']<.02 and summary['max_reference_position_change_mm']<1.)
    write_json(out/'final_numerical_audit.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['reference_refinements','failures']}),flush=True)
    return 0 if summary['passed'] else 2

if __name__=='__main__':raise SystemExit(main())
