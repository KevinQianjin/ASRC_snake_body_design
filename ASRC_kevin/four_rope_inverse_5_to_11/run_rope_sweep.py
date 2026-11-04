"""Primary inverse-tendon sweep for the previous 10,170 configurations.

This stage searches the symmetric planar subset with zero opposing top/bottom
common tension A and allocation [max(D,0), S/2, max(-D,0), S/2]. Real disk
chords require a third independent common mode. check_opposing_pairs.py adds
A>0 and mixed A/S trials; merge_pair_search.py combines the final states.
All minima are the lowest found in the documented finite planar search.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,concurrent.futures,copy,csv,hashlib,json,multiprocessing,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
from rope_planar import PlanarRod,HERE

SETTINGS=dict(front_counts=list(range(5,12)),rear_range=[2,20],fixed_total=31,
    search_cells_per_module=4,final_cells_per_module=8,
    common_tension_arc_grid_n=[0.,.5,2.,8.],
    fallback_common_level_grid_n=[1.,4.,8.],
    level_common_fraction_grid=[.25,.5,.75],
    fallback_angle_grid_deg=[210,240,270,300,330,450,540,720],
    angle_tolerance_deg=1.,arc_tolerance_mm=1.,level_tolerance_mm=1.,
    small_axial_strain_reporting_threshold=.05,
    numerical_max_abs_axial_strain=.85,numerical_max_tension_difference_n=300.,
    stability_scope='planar, fixed winch lengths; no independent torsion or spatial bifurcation',
    rope_weight_model='reference rope mass uniformly transferred to rod; no slack catenary model',
    minimum_claim='lowest found in the documented symmetric planar search; no global proof')


def jsonable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    raise TypeError(type(x).__name__)


def write_json(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=jsonable,allow_nan=False)+'\n')


def self_screen(rod,data):
    xy=data['points'];length=rod.l*(1+data['eps']);arc=np.r_[0,np.cumsum(length)]
    a,b=xy[:-1],xy[1:];n=len(a)
    ii,jj=np.triu_indices(n,2)
    keep=np.abs((arc[ii]+arc[ii+1])/2-(arc[jj]+arc[jj+1])/2)>.064
    ii,jj=ii[keep],jj[keep]
    if len(ii):
        gap=np.maximum(0,np.maximum(np.minimum(a[ii],b[ii]),np.minimum(a[jj],b[jj]))-
                       np.minimum(np.maximum(a[ii],b[ii]),np.maximum(a[jj],b[jj])))
        mask=np.sum(gap*gap,axis=1)<.032**2
        ii,jj=ii[mask],jj[mask]
    overlap=False;cross=False;minimum=None
    if len(ii):
        aa,bb,cc,dd=a[ii],b[ii],a[jj],b[jj]
        def orient(u,v):return u[:,0]*v[:,1]-u[:,1]*v[:,0]
        cross=((orient(bb-aa,cc-aa)*orient(bb-aa,dd-aa)<0)&
               (orient(dd-cc,aa-cc)*orient(dd-cc,bb-cc)<0)).any()
        def point_segment(p,u,v):
            d=v-u;t=np.sum((p-u)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-30)
            return np.linalg.norm(p-u-np.clip(t,0,1)[:,None]*d,axis=1)
        dist=np.minimum.reduce([point_segment(aa,cc,dd),point_segment(bb,cc,dd),
                                point_segment(cc,aa,bb),point_segment(dd,aa,bb)])
        minimum=0. if cross else float(dist.min()*1000)
        overlap=bool(cross or dist.min()<.032)
    current_curv=np.abs(np.diff(data['theta'])/length)
    local=bool(current_curv.max()*.016>=1.)
    return dict(centerline_self_intersection=bool(cross),nonlocal_capsule_overlap=overlap,
                minimum_tested_nonlocal_clearance_mm=minimum,
                local_capsule_curvature_exceeded=local,
                passes_self_envelope_screen=not (overlap or local))


def candidate(rod,solution,common,kind,sense,*,stability=False):
    if solution is None:return None
    x,D,info=solution
    m,data,H=rod.shape_metrics(x,D,common)
    m.update(self_screen(rod,data))
    m['target_reached']=bool(abs(m['head_y_mm'])<=1.) if kind=='level' else bool(
        abs(m['front_angle_deg']-sense*180)<=1 and m['semicircle_max_error_mm']<=1)
    if stability:
        m['minimum_scaled_fixed_length_eigenvalue']=rod.stability(H,data,rod.tensions(D,common))
        m['stable_in_plane']=m['minimum_scaled_fixed_length_eigenvalue']>=-1e-8
    else:m['minimum_scaled_fixed_length_eigenvalue']=None;m['stable_in_plane']=None
    return dict(solution=solution,common=common,metrics=m)


def lift_from_state(rod,start,common,steps=10):
    if start is None:return None
    h0=rod.evaluate(start[0],rod.tensions(start[1],common),detail=True)[3]['points'][-1,1]
    got=start
    for h in np.linspace(h0,0.,steps+1)[1:]:
        new=rod.inverse('level',common=common,initial=got,goal=h,maxiter=45)
        if new is None:return None
        got=new
    return got


def profile_level(rod,arc_seed,common):
    if arc_seed is None:return None,0
    trials=0;got=arc_seed;best=None;best_y=-np.inf
    for deg in SETTINGS['fallback_angle_grid_deg']:
        trials+=1
        s=rod.inverse('arc',1,common,initial=got,goal=np.radians(deg),maxiter=35)
        if s is None:continue
        got=s
        _,_,_,data=rod.evaluate(s[0],rod.tensions(s[1],common),detail=True)
        y=data['points'][-1,1]
        if y>best_y:best=s;best_y=y
        if y>=-.001:
            target=rod.inverse('level',common=common,initial=s,maxiter=50)
            if target is not None:return target,trials+1
        if self_screen(rod,data)['centerline_self_intersection']:
            break
    # A final local attempt at the best point can cross a shallow fold.
    if best is not None:
        target=rod.inverse('level',common=common,initial=best,maxiter=45)
        trials+=1
        if target is not None:return target,trials
    return None,trials


def refine(rod,cand,kind,sense):
    if cand is None:return None,None
    fine=PlanarRod(rod.counts,SETTINGS['final_cells_per_module'])
    x,D,_=cand['solution'];theta=np.r_[0,x[::2]]
    xx=np.zeros(fine.ndof)
    xx[::2]=np.interp(np.linspace(0,1,fine.m+1)[1:],np.linspace(0,1,rod.m+1),theta)
    xx[1::2]=np.repeat(x[1::2],fine.sub//rod.sub)
    sol=fine.inverse(kind,sense,cand['common'],initial=(xx,D,{}),maxiter=60)
    if sol is None:return None,None
    return fine,candidate(fine,sol,cand['common'],kind,sense,stability=True)


def search_case(rod,warm):
    found={};trials={};arc_bases={}
    for sense in [1,-1]:
        key='up' if sense==1 else 'down'
        sol=rod.load_inverse('arc',sense,initial=warm.get(key))
        arc_bases[sense]=sol
        if sol is not None:warm[key]=sol
    level=rod.load_inverse('level',initial=warm.get('level'))
    trials['level']=1
    if level is None:
        level=rod.lift_from_sag();trials['level']+=1
    if level is None and arc_bases[1] is not None:
        level,n=profile_level(rod,arc_bases[1],0.);trials['level']+=n
    level_candidates=[]
    if level is not None:
        warm['level']=level
        level_candidates.append(candidate(rod,level,0,'level',1))
        baseP=abs(level[1]);previous=level
        for fraction in SETTINGS['level_common_fraction_grid']:
            c=fraction*baseP;trials['level']+=1
            sol=rod.inverse('level',common=c,initial=previous,maxiter=35)
            if sol is not None:
                previous=sol;level_candidates.append(candidate(rod,sol,c,'level',1))
        # Multistart from the descending 180-degree branch.
        if arc_bases[-1] is not None:
            sol=rod.inverse('level',initial=arc_bases[-1],maxiter=25);trials['level']+=1
            if sol is not None:level_candidates.append(candidate(rod,sol,0,'level',1))
    else:
        # Finite, explicitly reported fallback domain, not a proof of infeasibility.
        prev=arc_bases[1]
        for c in SETTINGS['fallback_common_level_grid_n']:
            if prev is None:break
            trials['level']+=1
            arc=rod.inverse('arc',1,c,initial=prev,maxiter=35)
            if arc is None:continue
            prev=arc
            sol=lift_from_state(rod,arc,c,steps=7)
            if sol is None:
                sol,n=profile_level(rod,arc,c);trials['level']+=n
            if sol is not None:level_candidates.append(candidate(rod,sol,c,'level',1))
    level_candidates=[a for a in level_candidates if a is not None]
    level_candidates.sort(key=lambda a:a['metrics']['total_tension_n'])
    selected=None;selected_rod=None
    for c in level_candidates[:3]:
        f,refined=refine(rod,c,'level',1)
        if refined is None:continue
        if selected is None:selected_rod,selected=f,refined
        if refined['metrics']['stable_in_plane'] and refined['metrics']['passes_self_envelope_screen']:
            selected_rod,selected=f,refined;break
    found['level']=(selected_rod,selected)
    for sense in [1,-1]:
        key='up' if sense==1 else 'down';trials[key]=0
        choices=[];previous=arc_bases[sense]
        for c in SETTINGS['common_tension_arc_grid_n']:
            trials[key]+=1
            sol=previous if c==0 else (rod.inverse('arc',sense,c,initial=previous,maxiter=40) if previous else None)
            if sol is None:continue
            previous=sol;choices.append(candidate(rod,sol,c,'arc',sense))
        choices=[a for a in choices if a is not None]
        # Refine a sampled interior shape-error minimum along the 180-degree branch.
        if len(choices)>=3:
            ordered=sorted(choices,key=lambda a:a['common']);j=int(np.argmin([a['metrics']['semicircle_max_error_mm'] for a in ordered]))
            if 0<j<len(ordered)-1:
                seed=ordered[j]['solution']
                def objective(c):
                    trials[key]+=1
                    sol=rod.inverse('arc',sense,c,initial=seed,maxiter=35)
                    cc=candidate(rod,sol,c,'arc',sense)
                    if cc is not None:choices.append(cc);return cc['metrics']['semicircle_max_error_mm']
                    return 1e6
                minimize_scalar(objective,bounds=(ordered[j-1]['common'],ordered[j+1]['common']),
                                method='bounded',options={'maxiter':8,'xatol':.02})
        passing=[a for a in choices if a['metrics']['target_reached']]
        # If the semicircle is not found, preserve the closest 180-degree equilibrium
        # as a diagnostic; its tensions are NOT semicircle target tensions.
        ranking=sorted(passing,key=lambda a:a['metrics']['total_tension_n']) if passing else sorted(
            choices,key=lambda a:a['metrics']['semicircle_max_error_mm'])
        chosen_rod,chosen=None,None
        for c in ranking[:2]:
            f,rc=refine(rod,c,'arc',sense)
            if rc is not None:chosen_rod,chosen=f,rc;break
        found[key]=(chosen_rod,chosen)
    return found,trials


BASE_FIELDS=['combination','n_high','n_uni','n_directional','n_low','rear_modules','front_modules','total_modules',
 'comparison_rear_sweep','comparison_fixed_N31','target','status','target_reached','stable_in_plane','passes_self_envelope_screen',
 'passes_reference_yield','passes_empty_box','axial_strain_exceeds_5_percent','target_tension_top_n','target_tension_right_n',
 'target_tension_bottom_n','target_tension_left_n','target_total_tension_n','diagnostic_tension_top_n','diagnostic_tension_right_n',
 'diagnostic_tension_bottom_n','diagnostic_tension_left_n','diagnostic_total_tension_n','computed_total_tension_n',
 'head_x_mm','head_y_mm','head_z_mm','front_angle_deg','rear_angle_deg','front_current_length_mm',
 'semicircle_max_error_mm','semicircle_rms_error_mm','max_module_axial_compression','max_module_axial_extension',
 'max_core_stress_mpa','core_reference_yield_ratio','horizontal_span_mm','vertical_span_mm','equilibrium_residual',
 'minimum_scaled_fixed_length_eigenvalue','centerline_self_intersection','nonlocal_capsule_overlap',
 'minimum_tested_nonlocal_clearance_mm','local_capsule_curvature_exceeded','D_n','common_n','rope_path_lengths_mm',
 'rope_strains','take_up_mm','slack_ropes','cells_per_module','search_trials','failure_note']


def make_row(counts,name,rod,cand,trials):
    h,u,d,l=counts;front=d+l;rear=h+u
    r={key:None for key in BASE_FIELDS}
    r.update(combination='-'.join(f'{a}{b}' for a,b in zip('HUDL',counts)),n_high=h,n_uni=u,n_directional=d,n_low=l,
        rear_modules=rear,front_modules=front,total_modules=rear+front,
        comparison_rear_sweep=2<=rear<=20,comparison_fixed_N31=(rear+front==31),
        target={'level':'head_level','up':'front_semicircle_up','down':'front_semicircle_down'}[name],search_trials=trials)
    if cand is None:
        r.update(status='not_found_in_documented_search',target_reached=False,
                 failure_note='No converged target equilibrium found in the documented branches and bounds; not a global infeasibility proof.')
        return r,None,None
    m=cand['metrics']
    for key in r:
        if key in m:r[key]=m[key]
    r['computed_total_tension_n']=m['total_tension_n'];r['cells_per_module']=rod.sub
    r['status']='target_equilibrium_found' if m['target_reached'] else 'angle180_diagnostic_semicircle_not_met'
    prefix='target' if m['target_reached'] else 'diagnostic'
    for label,value in zip(['top','right','bottom','left'],m['tensions_n']):r[f'{prefix}_tension_{label}_n']=value
    r[f'{prefix}_total_tension_n']=m['total_tension_n']
    if name=='level':r['semicircle_max_error_mm']=None;r['semicircle_rms_error_mm']=None
    if not m['stable_in_plane']:r['failure_note']='Planar fixed-length stability screen failed.'
    if not m['passes_self_envelope_screen']:
        r['failure_note']=(r['failure_note'] or '')+' Conservative self-envelope screen failed.'
    return r,cand['solution'][0],np.asarray(m['tensions_n'])


def run_group(job):
    front,rear,out,stamp=job;folder=Path(out)/'groups';folder.mkdir(parents=True,exist_ok=True)
    stem=f'F{front:02d}_R{rear:02d}';path=folder/(stem+'.json')
    if path.exists():
        data=json.loads(path.read_text())
        if data.get('run_stamp')==stamp:return data['summary']
    rows=[];states=[];tensions=[];warm_by_d={};start=time.monotonic()
    for high in range(1,rear):
        for directional in range(1,front):
            counts=(high,rear-high,directional,front-directional)
            rod=PlanarRod(counts,SETTINGS['search_cells_per_module'])
            warm=warm_by_d.setdefault(directional,{})
            try:found,trials=search_case(rod,warm)
            except Exception as error:
                found={name:(None,None) for name in ['level','up','down']};trials={name:0 for name in found}
                exception=str(error)
            else:exception=None
            for name in ['level','up','down']:
                fine,cand=found[name]
                row,x,T=make_row(counts,name,fine,cand,trials[name])
                if exception:row['status']='numeric_exception';row['failure_note']=exception
                rows.append(row)
                ndof=2*(front+rear)*SETTINGS['final_cells_per_module']
                states.append(x if x is not None else np.full(ndof,np.nan))
                tensions.append(T if T is not None else np.full(4,np.nan))
    with (folder/(stem+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=BASE_FIELDS);w.writeheader()
        for row in rows:w.writerow({k:(json.dumps(v,default=jsonable) if isinstance(v,list) else v) for k,v in row.items()})
    np.savez_compressed(folder/(stem+'_states.npz'),state=np.asarray(states),tensions=np.asarray(tensions))
    summary=dict(front=front,rear=rear,configurations=(front-1)*(rear-1),rows=len(rows),
        converged_states=sum(r['head_x_mm'] is not None for r in rows),
        level_found=sum(r['target']=='head_level' and r['target_reached'] for r in rows),
        semicircles_found=sum(r['target']!='head_level' and r['target_reached'] for r in rows),
        numeric_exceptions=sum(r['status']=='numeric_exception' for r in rows),seconds=time.monotonic()-start)
    write_json(path,dict(run_stamp=stamp,summary=summary))
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results')
    p.add_argument('--workers',type=int,default=4);p.add_argument('--front',type=int,nargs='*');p.add_argument('--rear',type=int,nargs='*')
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    sources=[HERE/'rope_planar.py',Path(__file__),HERE/'inputs/craft_data.py',HERE/'inputs/rope_materials.json']
    hashes={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}
    stamp=hashlib.sha256(json.dumps(dict(settings=SETTINGS,hashes=hashes),sort_keys=True).encode()).hexdigest()
    write_json(a.output_dir/'run_settings.json',dict(settings=SETTINGS,input_sha256=hashes,run_stamp=stamp))
    groups=[]
    for front in a.front or SETTINGS['front_counts']:
        rears=sorted(set(range(2,21))|{31-front})
        if a.rear:rears=[r for r in rears if r in a.rear]
        groups.extend((front,rear,str(a.output_dir),stamp) for rear in rears)
    done=[];context=multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=context) as pool:
        tasks=[pool.submit(run_group,j) for j in groups]
        for task in concurrent.futures.as_completed(tasks):
            s=task.result();done.append(s);print(json.dumps(dict(done=len(done),groups=len(groups),**s)),flush=True)
    all_rows=[]
    for front,rear,_,_ in groups:
        with (a.output_dir/'groups'/f'F{front:02d}_R{rear:02d}.csv').open() as f:all_rows.extend(csv.DictReader(f))
    with (a.output_dir/'all_targets.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=BASE_FIELDS);w.writeheader();w.writerows(all_rows)
    write_json(a.output_dir/'group_summary.json',dict(groups=done,configurations=sum(x['configurations'] for x in done),
         target_rows=len(all_rows),numeric_exceptions=sum(x['numeric_exceptions'] for x in done)))
    print(json.dumps(dict(complete=True,output=str(a.output_dir),configurations=sum(x['configurations'] for x in done),
                         rows=len(all_rows))),flush=True)

if __name__=='__main__':main()
