"""Supplement the primary sweep with the third symmetric tension mode.

Reads only atomically completed primary groups; writes separate trial files.
Merging into the final deliverable happens after both sweeps finish.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,csv,json,time,concurrent.futures,multiprocessing
from pathlib import Path
import numpy as np
from rope_planar import HERE
from rope_three_parameter import ThreeParameterRod
from run_rope_sweep import candidate,make_row,write_json,jsonable
from rescue_level_continuation import load_group

def process(job):
    front,rear,path=job;out=Path(path);dest=out/'opposing_pair_trials';dest.mkdir(exist_ok=True)
    stem=f'F{front:02d}_R{rear:02d}';done=dest/(stem+'.json')
    if done.exists():return json.loads(done.read_text())['summary']
    rows,states,tensions=load_group(out,front,rear)
    stats=[];updates=[];trial_count=0;started=time.monotonic();new_states=[];new_tensions=[]
    for i,row in enumerate(rows):
        counts=tuple(row[k] for k in ['n_high','n_uni','n_directional','n_low'])
        name={'head_level':'level','front_semicircle_up':'up','front_semicircle_down':'down'}[row['target']]
        kind='level' if name=='level' else 'arc';sense=-1 if name=='down' else 1
        has_state=np.isfinite(states[i]).all()
        seed_i=i if has_state else (i+1 if i%3==0 else i)
        if seed_i>=len(rows) or not np.isfinite(states[seed_i]).all():continue
        seed=(states[seed_i],rows[seed_i]['D_n'],{})
        if kind=='level' and has_state:
            P=row['target_total_tension_n']
            grid=[(.25*P,0.),(.75*P,0.),(.25*P,.25*P)]
        elif kind=='level':grid=[(.5,0.),(2.,0.),(1.,1.)]
        else:grid=[(.5,0.),(2.,0.),(8.,0.),(1.,1.),(4.,4.)]
        best=None;min_error=row['semicircle_max_error_mm'];min_force=row['target_total_tension_n']
        for A,S in grid:
            rod=ThreeParameterRod(counts,8,antagonistic_common=A)
            trial_count+=1
            sol=rod.inverse(kind,sense,S,initial=seed,maxiter=24 if not has_state else 32)
            if sol is None:continue
            cc=candidate(rod,sol,S,kind,sense,stability=False)
            if cc is None:continue
            met=cc['metrics']
            if kind!='level':min_error=min(min_error if min_error is not None else 1e30,met['semicircle_max_error_mm'])
            if met['target_reached']:
                min_force=min(min_force if min_force is not None else 1e30,met['total_tension_n'])
            improve=(met['target_reached'] and (not row['target_reached'] or met['total_tension_n']<row['target_total_tension_n']-1e-7))
            improve|=(kind!='level' and not row['target_reached'] and met['semicircle_max_error_mm']<row['semicircle_max_error_mm']-1e-5)
            if improve:
                cc=candidate(rod,sol,S,kind,sense,stability=True)
                if best is None or (met['target_reached'] and met['total_tension_n']<best[1]['metrics']['total_tension_n']) or (
                    not met['target_reached'] and met['semicircle_max_error_mm']<best[1]['metrics']['semicircle_max_error_mm']):best=(rod,cc,A)
        stats.append(dict(combination=row['combination'],target=row['target'],best_tested_total_tension_n=min_force,
                          best_tested_arc_error_mm=min_error))
        if best:
            rod,cc,A=best
            rr,x,T=make_row(counts,name,rod,cc,(row['search_trials'] or 0)+len(grid))
            rr['top_bottom_pair_common_n']=A;rr['primary_row_index']=i
            rr['status']=rr['status']+'_opposing_pair_supplement'
            updates.append(rr);new_states.append(x);new_tensions.append(T)
    write_json(done,dict(summary=dict(front=front,rear=rear,trials=trial_count,updates=len(updates),seconds=time.monotonic()-started),
                         stats=stats,updates=updates))
    if updates:np.savez_compressed(dest/(stem+'_updates.npz'),state=np.asarray(new_states),tensions=np.asarray(new_tensions))
    return dict(front=front,rear=rear,trials=trial_count,updates=len(updates),seconds=time.monotonic()-started)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results');p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();running={};submitted=set();completed=[]
    dest=a.output_dir/'opposing_pair_trials';dest.mkdir(exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        while len(completed)<139:
            for path in sorted((a.output_dir/'groups').glob('*.json')):
                key=path.stem
                if key in submitted:continue
                if len(running)>=a.workers*2:break
                meta=json.loads(path.read_text());s=meta['summary'];job=(s['front'],s['rear'],str(a.output_dir))
                submitted.add(key);running[pool.submit(process,job)]=key
            if not running:
                if (a.output_dir/'group_summary.json').exists() and len(submitted)==139:break
                time.sleep(2);continue
            done,_=concurrent.futures.wait(running,timeout=2,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                running.pop(future);s=future.result();completed.append(s)
                print(json.dumps(dict(done=len(completed),groups=139,**s)),flush=True)
    write_json(a.output_dir/'opposing_pair_summary.json',dict(groups=completed,trials=sum(x['trials'] for x in completed),updates=sum(x['updates'] for x in completed)))

if __name__=='__main__':main()
