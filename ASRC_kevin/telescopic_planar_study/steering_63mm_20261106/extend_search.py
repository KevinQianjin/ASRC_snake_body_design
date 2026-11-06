"""Nonplanar seed checks and a horizontal inspection-attitude diagnostic."""
import json,argparse,time
import numpy as np
from spatial_model import HERE,PLANAR,SpatialDatabaseRod,dump
from search_steering import OUT,layouts,optimize,acceptable,DIRECTIONS

def better(candidate,old):
    if old is None or not old.get('qualifies'):return True
    a=candidate['directional_angle_deg'];b=old['directional_angle_deg']
    return a>b+.01 or (abs(a-b)<=.01 and candidate['maximum_single_tendon_n']<old['maximum_single_tendon_n'])

def run(u,m):
    rows=json.loads((OUT/f'U{u}_M{m}_coarse.json').read_text())
    attempts=json.loads((OUT/f'U{u}_M{m}_optimization_attempts.json').read_text())
    raw=np.load(OUT/f'U{u}_M{m}_coarse_states.npz');states={k:raw[k] for k in raw.files}
    baseline_rows=json.loads((OUT/f'U{u}_M{m}_baselines.json').read_text())
    for architecture,anchors in layouts(u,m):
        r=SpatialDatabaseRod(u,m,anchors,sub=2);p=r.planar;free=p.free();base=r.solve(np.zeros((r.k,4)),r.lift_planar(free))
        baseline=next(q for q in baseline_rows if q['architecture']==architecture)
        for direction in ['up','down']:
            for mode in ['low_strain','exploratory']:
                C=np.zeros((r.k,4));C[-1,1]=2.;C[-1,0 if direction=='up' else 2]=4.
                seed=r.solve(C,base)
                if seed is None:continue
                z,T,info=optimize(r,seed,C,direction,mode,maxiter=180)
                attempts.append(dict(info,configuration=r.label,architecture=architecture,seed='nonplanar_active_branch'))
                if not info['feasible_stationary']:continue
                row,_,_=r.metrics(z,T,stability=True)
                row.update(architecture=architecture,direction=direction,strain_mode=mode,kind='coarse_optimized',
                    baseline_elevation_deg=baseline['world_elevation_deg'],baseline_vertical_deg=baseline['vertical_projected_deg'])
                row['qualifies']=acceptable(row,mode,direction);row['directional_angle_deg']=DIRECTIONS[direction][1]*row['vertical_projected_deg']
                old=next(q for q in rows if q['architecture']==architecture and q['direction']==direction and q['strain_mode']==mode)
                if row['qualifies'] and better(row,old):
                    sid=f'{architecture}_{direction}_{mode}';row['state_id']=sid
                    rows[rows.index(old)]=row;states[sid+'_z']=z;states[sid+'_T']=T
                    print(r.label,architecture,'nonplanar',direction,mode,round(row['directional_angle_deg'],2),flush=True)
        # Supplement: demand world elevation within 5 degrees of the base pitch.
        # This is deliberately separate from unrestricted azimuth at a sagged tip.
        previous=None
        for mode in ['low_strain','exploratory']:
            direction='right';reference=np.radians(r.pitch);candidates=[]
            seeds=[(base,np.zeros((r.k,4)),'loaded_sag')]
            old=next(q for q in rows if q['architecture']==architecture and q['direction']=='right' and q['strain_mode']==mode)
            if old.get('qualifies'):
                sid=old['state_id'];seeds.append((states[sid+'_z'],states[sid+'_T'],'unrestricted_yaw'))
            old_arch={'three_U':'three','three_M':'three_distal'}.get(architecture,architecture)
            planar=json.loads((PLANAR/'results'/f'U{u}_M{m}_best.json').read_text())
            match=[q for q in planar if q.get('architecture')==old_arch and q.get('strain_mode')=='shape_only' and abs(q['pitch_deg']-20)<1e-6 and q.get('fine_converged')]
            if match:
                C=np.zeros((r.k,4));C[:,0]=match[0]['top_extra_tensions_n'];seed=r.solve(C,base)
                if seed is not None:seeds.append((seed,C,'actively_held_front'))
            if previous is not None:seeds.append((*previous,'previous_held_branch'))
            for seed,C,label in seeds:
                z,T,info=optimize(r,seed,C,direction,mode,cross_reference=reference,maxiter=180)
                attempts.append(dict(info,configuration=r.label,architecture=architecture,seed='level_'+label))
                if not info['feasible_stationary']:continue
                row,_,_=r.metrics(z,T,stability=True)
                row.update(architecture=architecture,direction='right_level',strain_mode=mode,kind='coarse_optimized',
                    baseline_elevation_deg=baseline['world_elevation_deg'],baseline_vertical_deg=baseline['vertical_projected_deg'],cross_reference_deg=r.pitch)
                row['qualifies']=acceptable(row,mode,'right',reference);row['directional_angle_deg']=row['yaw_deg']
                if row['qualifies']:candidates.append((row,z,T))
            if candidates:
                maximum=max(q[0]['directional_angle_deg'] for q in candidates)
                near=[q for q in candidates if q[0]['directional_angle_deg']>=maximum-.01]
                row,z,T=min(near,key=lambda q:q[0]['maximum_single_tendon_n'])
                sid=f'{architecture}_right_level_{mode}';row['state_id']=sid;rows.append(row);states[sid+'_z']=z;states[sid+'_T']=T;previous=(z,T)
                print(r.label,architecture,'held elevation',mode,round(row['directional_angle_deg'],2),'strain',round(row['max_abs_axial_strain']*100,2),flush=True)
            else:
                rows.append(dict(configuration=r.label,architecture=architecture,direction='right_level',strain_mode=mode,qualifies=False,status='no_stationary_solution_meeting_elevation_band_found'))
                print(r.label,architecture,'held elevation',mode,'no candidate',flush=True)
        dump(OUT/f'U{u}_M{m}_coarse.json',rows);np.savez_compressed(OUT/f'U{u}_M{m}_coarse_states.npz',**states)
        dump(OUT/f'U{u}_M{m}_optimization_attempts.json',attempts)
    dump(OUT/f'U{u}_M{m}_extended_completion.json',dict(completed=True,attempts=len(attempts)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--u',type=int);parser.add_argument('--m',type=int);a=parser.parse_args();run(a.u,a.m)
