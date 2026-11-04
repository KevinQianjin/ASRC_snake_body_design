"""Retry missing level targets from neighbouring converged compositions.

The final model properties remain the original values. Only initial guesses
are transferred. Each recovered state must re-satisfy the target and statics.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,csv,json,time,concurrent.futures,multiprocessing,shutil
from pathlib import Path
import numpy as np
from rope_planar import PlanarRod,HERE
from run_rope_sweep import candidate,make_row,BASE_FIELDS,write_json,jsonable

def parse(r):
    out={}
    for k,v in r.items():
        if v=='':out[k]=None
        elif v in ['True','False']:out[k]=v=='True'
        elif k in ['rope_path_lengths_mm','rope_strains','take_up_mm','slack_ropes']:out[k]=json.loads(v)
        else:
            try:out[k]=int(v)
            except ValueError:
                try:out[k]=float(v)
                except ValueError:out[k]=v
    return out

def load_group(output,f,rear):
    stem=f'F{f:02d}_R{rear:02d}';folder=output/'groups'
    file=folder/(stem+'.csv')
    if not file.exists():return None
    rows=[parse(r) for r in csv.DictReader(file.open())]
    z=np.load(folder/(stem+'_states.npz'))
    return rows,z['state'].copy(),z['tensions'].copy()

def process(job):
    f,rear,path=job;output=Path(path);start=time.monotonic()
    seeds=output/'rescue_seed_snapshot'
    loaded=load_group(seeds,f,rear);rows,states,tensions=loaded
    sources=[]
    for nr in [rear,rear-1,rear+1]:
        group=loaded if nr==rear else load_group(seeds,f,nr)
        if group is None:continue
        for i,r in enumerate(group[0]):
            if r['target']=='head_level' and r['target_reached'] and r['stable_in_plane']:
                sources.append((r,group[1][i]))
    attempted=0;rescued=0;notes=[]
    for i,r in enumerate(rows):
        if r['target']!='head_level' or r['target_reached']:continue
        counts=tuple(r[k] for k in ['n_high','n_uni','n_directional','n_low'])
        target=PlanarRod(counts,8)
        nearby=sorted(sources,key=lambda item:3*abs(item[0]['rear_modules']-rear)+
                    abs(item[0]['n_high']-r['n_high'])+abs(item[0]['n_directional']-r['n_directional']))[:3]
        best=None
        for src,xx in nearby:
            source_rear=src['rear_modules']*8;source_front=f*8
            angle=np.r_[0,xx[::2]];eps=xx[1::2]
            seed=np.zeros(target.ndof)
            theta_rear=np.interp(np.linspace(0,1,target.b+1),np.linspace(0,1,source_rear+1),angle[:source_rear+1])
            seed[::2]=np.r_[theta_rear[1:],angle[source_rear+1:]]
            seed[1::2]=np.r_[np.interp((np.arange(target.b)+.5)/target.b,
                       (np.arange(source_rear)+.5)/source_rear,eps[:source_rear]),eps[source_rear:]]
            attempted+=1
            sol=target.inverse('level',common=src['common_n'],initial=(seed,src['D_n'],{}),maxiter=32)
            cc=candidate(target,sol,src['common_n'],'level',1,stability=True)
            if cc is None:continue
            if best is None or cc['metrics']['total_tension_n']<best['metrics']['total_tension_n']:best=cc
            if cc['metrics']['stable_in_plane'] and cc['metrics']['passes_self_envelope_screen']:break
        if best is not None:
            rr,x,T=make_row(counts,'level',target,best,(r['search_trials'] or 0)+len(nearby))
            rr['status']='target_equilibrium_found_after_neighbour_continuation'
            rows[i]=rr;states[i]=x;tensions[i]=T;rescued+=1
            sources.append((rr,x.copy()))
            notes.append(dict(combination=rr['combination'],tension_n=rr['target_total_tension_n']))
    stem=f'F{f:02d}_R{rear:02d}';folder=output/'groups'
    if rescued:
        with (folder/(stem+'.csv')).open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=BASE_FIELDS);w.writeheader()
            for r in rows:w.writerow({k:json.dumps(v,default=jsonable) if isinstance(v,list) else v for k,v in r.items()})
        np.savez_compressed(folder/(stem+'_states.npz'),state=states,tensions=tensions)
        meta=json.loads((folder/(stem+'.json')).read_text())
        meta['summary']['level_found']=sum(r['target']=='head_level' and r['target_reached'] for r in rows)
        meta['summary']['converged_states']=sum(r['head_x_mm'] is not None for r in rows)
        write_json(folder/(stem+'.json'),meta)
    return dict(front=f,rear=rear,attempts=attempted,recovered=rescued,notes=notes,seconds=time.monotonic()-start)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results');p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();summ=json.loads((a.output_dir/'group_summary.json').read_text())
    assert summ['configurations']==10170
    snapshot=a.output_dir/'rescue_seed_snapshot'/'groups';snapshot.mkdir(parents=True,exist_ok=True)
    for source in (a.output_dir/'groups').glob('*'):
        if source.suffix in ['.csv','.npz']:shutil.copy2(source,snapshot/source.name)
    jobs=[]
    for path in sorted((a.output_dir/'groups').glob('*.csv')):
        rows=list(csv.DictReader(path.open()))
        if any(r['target']=='head_level' and r['target_reached']=='False' for r in rows):
            f,rear=int(rows[0]['front_modules']),int(rows[0]['rear_modules']);jobs.append((f,rear,str(a.output_dir)))
    audits=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        for s in pool.map(process,jobs):audits.append(s);print(json.dumps({k:v for k,v in s.items() if k!='notes'}),flush=True)
    allrows=[]
    for path in sorted((a.output_dir/'groups').glob('*.csv')):allrows.extend(csv.DictReader(path.open()))
    assert len(allrows)==30510
    with (a.output_dir/'all_targets.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=BASE_FIELDS);w.writeheader();w.writerows(allrows)
    write_json(a.output_dir/'neighbour_continuation_audit.json',dict(groups=audits,recovered=sum(s['recovered'] for s in audits)))
    print(json.dumps(dict(recovered=sum(s['recovered'] for s in audits),rows=len(allrows))),flush=True)

if __name__=='__main__':main()
