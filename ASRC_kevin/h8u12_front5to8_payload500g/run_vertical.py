"""Recompute all 22 front splits and all former targets with a 500 g head load."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,csv,concurrent.futures,multiprocessing,argparse,time
from pathlib import Path
import numpy as np
import run_rope_sweep as sweep
from payload_planar import PayloadPlanarRod
from rope_planar import HERE

sweep.PlanarRod=PayloadPlanarRod
sweep.SETTINGS['common_tension_arc_grid_n']=[0.,.5,2.,8.,16.,32.]
sweep.SETTINGS['fallback_common_level_grid_n']=[1.,4.,8.,16.,32.]

def process(counts):
    out=HERE/'results/vertical';out.mkdir(parents=True,exist_ok=True)
    label='-'.join(f'{k}{v}' for k,v in zip('HUDL',counts));file=out/(label+'.json')
    if file.exists() and json.loads(file.read_text()).get('search_revision')==2:return json.loads(file.read_text())['summary']
    start=time.monotonic();rod=PayloadPlanarRod(counts,4)
    found,trials=sweep.search_case(rod,{})
    rows=[];saved={}
    free=PayloadPlanarRod(counts,8);x=free.free_equilibrium()
    if x is not None:
        metrics,data,H=free.shape_metrics(x,0)
        metrics.update(sweep.self_screen(free,data));metrics['stable_in_plane']=free.stability(H,data,np.zeros(4))>=-1e-8
        metrics.update(combination=label,target='free_sag',target_reached=True,qualifies=bool(metrics['passes_reference_yield'] and metrics['passes_self_envelope_screen'] and metrics['stable_in_plane']))
        rows.append(metrics);saved['free_sag']=dict(x=x,T=np.zeros(4))
    for name in ['level','up','down']:
        fine,best=found[name]
        direct=PayloadPlanarRod(counts,8)
        kind='level' if name=='level' else 'arc';sense=-1 if name=='down' else 1
        sol=direct.load_inverse(kind,sense)
        direct_candidate=sweep.candidate(direct,sol,0.,kind,sense,stability=True)
        if direct_candidate is not None:
            if best is None or (name!='level' and direct_candidate['metrics']['semicircle_max_error_mm']<best['metrics']['semicircle_max_error_mm']):
                fine,best=direct,direct_candidate
        # Follow the no-payload solution into the loaded model in small steps.
        from rope_planar import PlanarRod
        unloaded=PlanarRod(counts,8);seed=unloaded.load_inverse(kind,sense)
        for payload in np.linspace(.025,.5,20):
            if seed is None:break
            ramp=PayloadPlanarRod(counts,8,payload_kg=payload)
            seed=ramp.inverse(kind,sense,initial=seed,maxiter=55)
        if seed is not None:
            ramp_candidate=sweep.candidate(ramp,seed,0.,kind,sense,stability=True)
            if ramp_candidate is not None and (best is None or (name!='level' and ramp_candidate['metrics']['semicircle_max_error_mm']<best['metrics']['semicircle_max_error_mm'])):
                fine,best=ramp,ramp_candidate
        # Independent common top/bottom and side modes; all trials must
        # solve the actual loaded equilibrium, without artificial reactions.
        for A,S in [(.5,0),(2,0),(8,0),(16,0),(32,0),(2,2),(8,8),(16,16)]:
            trial=PayloadPlanarRod(counts,8,antagonistic_common=A)
            seed=None
            if best is not None:
                seed=best['solution']
            sol=trial.load_inverse('level' if name=='level' else 'arc',-1 if name=='down' else 1,S,initial=seed)
            trials[name]+=1
            candidate=sweep.candidate(trial,sol,S,'level' if name=='level' else 'arc',-1 if name=='down' else 1,stability=True)
            if candidate is None:continue
            new=candidate['metrics'];old=best['metrics'] if best else None
            improve=old is None or (new['target_reached'] and not old['target_reached'])
            if old and new['target_reached']==old['target_reached']:
                improve=(new['total_tension_n']<old['total_tension_n']) if new['target_reached'] else (name!='level' and new['semicircle_max_error_mm']<old['semicircle_max_error_mm'])
            if improve:fine,best=trial,candidate
        row,x,T=sweep.make_row(counts,name,fine,best,trials[name]);row['payload_kg']=.5
        row['qualifies']=bool(row['target_reached'] and row['passes_reference_yield'] and row['passes_self_envelope_screen'] and row['stable_in_plane'])
        row['top_bottom_pair_common_n']=fine.antagonistic_common if fine else None
        rows.append(row)
        if x is not None:saved[row['target']]=dict(x=x,T=T)
    summary=dict(combination=label,front=sum(counts[2:]),target_found=sum(bool(r['target_reached']) for r in rows),qualifies=sum(bool(r['qualifies']) for r in rows),seconds=time.monotonic()-start)
    sweep.write_json(file,dict(search_revision=2,summary=summary,rows=rows))
    arrays={}
    for name,state in saved.items():
        arrays[name+'_x']=state['x'];arrays[name+'_T']=state['T']
    np.savez_compressed(out/(label+'_states.npz'),**arrays)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    jobs=[(8,12,d,f-d) for f in range(5,9) for d in range(1,f)]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        summaries=[]
        for summary in pool.map(process,jobs):summaries.append(summary);print(json.dumps(summary),flush=True)
    sweep.write_json(HERE/'results/vertical_summary.json',summaries)

if __name__=='__main__':main()
