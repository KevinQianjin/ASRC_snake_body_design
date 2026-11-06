"""Refine candidate maxima, validate left symmetry, and test 15/25 deg pitches."""
import argparse,json,time
import numpy as np
from scipy.optimize import root
from spatial_model import HERE,SpatialDatabaseRod,refine_seed,dump,write_csv
from search_steering import OUT,DIRECTIONS,optimize,acceptable

def stationary(r,T,z):
    try:
        result=root(lambda x:r.evaluate(x,T)[1],z,jac=lambda x:r.hessian(x,T),method='hybr',options={'xtol':1e-9,'maxfev':500})
        q=(result.x/r.scale).reshape(-1,4)
        if r.residual(r.evaluate(result.x,T)[1])<2e-6 and np.max(np.abs(q[:,3]))<.6 and np.max(np.abs(q[:,:3]))<1.5:return result.x
    except (ValueError,np.linalg.LinAlgError):pass
    return r.solve(T,z)

def score(row,direction):return (row['yaw_deg'] if direction.startswith('right') else DIRECTIONS[direction][1]*row['vertical_projected_deg'])

def baseline(r):
    x=r.planar.free()
    if x is None:return None
    return r.solve(np.zeros((r.k,4)),r.lift_planar(x))

def refined_candidate(u,m,original,z,T,target_sub,maxiter=90):
    direction=original['direction'];mode=original['strain_mode'];plain='right' if direction=='right_level' else direction
    cross=np.radians(20) if direction=='right_level' else None
    old=SpatialDatabaseRod(u,m,original['anchors'],sub=original['cells_per_module'])
    r=SpatialDatabaseRod(u,m,original['anchors'],sub=target_sub)
    guess=refine_seed(z,old,r);xf=stationary(r,T,guess)
    attempts=[]
    if xf is not None:
        row,_,_=r.metrics(xf,T,stability=True)
        ok=acceptable(row,mode,plain,cross)
    else:row=None;ok=False
    # Re-optimize an actual finer equilibrium when a coarse boundary does not
    # survive refinement. Never promote an out-of-bound fine state to a maximum.
    if not ok:
        seed=guess if xf is None else xf
        xx,TT,info=optimize(r,seed,T,plain,mode,cross_reference=cross,maxiter=maxiter)
        info.update(kind='fine_boundary_optimization',target_sub=target_sub);attempts.append(info)
        if info['feasible_stationary']:
            metric,_,_=r.metrics(xx,TT,stability=True)
            if acceptable(metric,mode,plain,cross):xf,T,row,ok=xx,TT,metric,True
    # A local boundary recovery on the documented force ray is a fallback,
    # explicitly labelled; it is not advertised as a new global optimum.
    if not ok:
        choices=[]
        for fraction in [.95,.85,.7,.5]:
            xx=stationary(r,T*fraction,guess)
            if xx is None:continue
            metric,_,_=r.metrics(xx,T*fraction,stability=True)
            if acceptable(metric,mode,plain,cross):choices.append((score(metric,direction),metric,xx,T*fraction,fraction))
        if choices:
            _,row,xf,T,fraction=max(choices,key=lambda x:x[0]);ok=True
            attempts.append(dict(kind='force_ray_recovery',fraction=fraction,target_sub=target_sub))
    if not ok:return None,attempts
    row.update(architecture=original['architecture'],direction=direction,strain_mode=mode,
        state_id=original['state_id'],baseline_elevation_deg=original['baseline_elevation_deg'],baseline_vertical_deg=original['baseline_vertical_deg'],
        qualifies=True,directional_angle_deg=score(row,direction),kind='refined_candidate',
        previous_cells_per_module=original['cells_per_module'],previous_directional_angle_deg=original['directional_angle_deg'],
        mesh_angle_change_deg=abs(score(row,direction)-original['directional_angle_deg']),
        cross_reference_deg=20 if direction=='right_level' else None)
    return (row,xf,T),attempts

def mirror_state(r,z,T,row):
    q=(z/r.scale).reshape(-1,4).copy();q[:,[0,2]]*=-1;zz=q.ravel()*r.scale;C=np.asarray(T)[:,[0,3,2,1]]
    rr,dd,world=r.metrics(zz,C,stability=True)
    assert abs(rr['equilibrium_residual']-row['equilibrium_residual'])<1e-7
    assert abs(rr['max_abs_axial_strain']-row['max_abs_axial_strain'])<1e-10
    assert abs(rr['yaw_deg']+row['yaw_deg'])<1e-5
    rr.update(architecture=row['architecture'],direction=row['direction'].replace('right','left'),strain_mode=row['strain_mode'],
        state_id=row['state_id'].replace('right','left'),kind='mirror_verified',qualifies=row['qualifies'],directional_angle_deg=-rr['yaw_deg'],
        baseline_elevation_deg=row['baseline_elevation_deg'],baseline_vertical_deg=row['baseline_vertical_deg'],
        mirror_equilibrium_verified=True,mirror_scope='Exact symmetric stiffness, gravity, circular envelope and frictionless tendon model',
        mesh_angle_change_deg=row['mesh_angle_change_deg'],cross_reference_deg=row.get('cross_reference_deg'))
    return rr,zz,C

def run(u,m):
    original=json.loads((OUT/f'U{u}_M{m}_coarse.json').read_text())
    zfile=np.load(OUT/f'U{u}_M{m}_coarse_states.npz')
    refined=[];final=[];diagnostics=[];states={};sensitivity=[]
    for direction in ['right','up','down','right_level']:
        for mode in ['low_strain','exploratory']:
            group=[q for q in original if q.get('qualifies') and q['direction']==direction and q['strain_mode']==mode]
            # Retain multiple architectural candidates; lower force breaks ties
            # within 0.01 degree, which is below this study's angular precision.
            group=sorted(group,key=lambda q:(-round(q['directional_angle_deg'],2),q['maximum_single_tendon_n']))[:2]
            candidates=[]
            for row in group:
                z=zfile[row['state_id']+'_z'];T=zfile[row['state_id']+'_T']
                result,attempts=refined_candidate(u,m,row,z,T,4,maxiter=110)
                diagnostics.extend([dict(a,configuration=f'U{u}-M{m}',state_id=row['state_id']) for a in attempts])
                if result is None:continue
                metric,z,T=result;refined.append(metric);candidates.append((metric,z,T))
                print(f'U{u}-M{m}',row['architecture'],direction,mode,'mesh4',round(metric['directional_angle_deg'],2),flush=True)
            candidates.sort(key=lambda x:(-round(x[0]['directional_angle_deg'],2),x[0]['maximum_single_tendon_n']))
            fine_candidates=[]
            for row,z,T in candidates:
                result,attempts=refined_candidate(u,m,row,z,T,8,maxiter=90)
                diagnostics.extend([dict(a,configuration=f'U{u}-M{m}',state_id=row['state_id']) for a in attempts])
                if result is not None:
                    metric,zz,TT=result;refined.append(metric);fine_candidates.append((metric,zz,TT))
                    print(f'U{u}-M{m}',row['architecture'],direction,mode,'mesh8',round(metric['directional_angle_deg'],2),flush=True)
            if not fine_candidates:
                final.append(dict(configuration=f'U{u}-M{m}',direction=direction,strain_mode=mode,maximum_angle_deg=None,status='no_qualifying_refined_equilibrium_found'))
                continue
            max_angle=max(q[0]['directional_angle_deg'] for q in fine_candidates)
            close=[q for q in fine_candidates if q[0]['directional_angle_deg']>=max_angle-.01]
            row,z,T=min(close,key=lambda q:q[0]['maximum_single_tendon_n'])
            row.update(maximum_angle_deg=row['directional_angle_deg'] if row['directional_angle_deg']>1e-4 else None,
                status='largest_refined_angle_found' if row['directional_angle_deg']>1e-4 else 'head_remains_below_base_axis_no_positive_upward_angle_found',
                orientation_search_cap_reached=bool(row['directional_angle_deg']>=179.99),
                tension_bound_reached=bool(row['maximum_single_tendon_n']>=249.99),
                strain_bound_near=bool(row['max_abs_axial_strain']>= (.049 if mode=='low_strain' else .295)),
                upward_recovery_from_natural_deg=row['vertical_projected_deg']-row['baseline_vertical_deg'],
                angular_mesh_status='last_refinement_change_below_1deg' if row['mesh_angle_change_deg']<=1 else 'mesh_sensitive_largest_found_not_converged_maximum')
            # One more same-tension mesh check on the final candidate; classify
            # it separately and do not silently replace the actual tension state.
            r8=SpatialDatabaseRod(u,m,row['anchors'],sub=8);r16=SpatialDatabaseRod(u,m,row['anchors'],sub=16)
            zz=stationary(r16,T,refine_seed(z,r8,r16))
            mesh=dict(configuration=row['configuration'],state_id=row['state_id'],kind='mesh8_to16',converged=zz is not None)
            if zz is not None:
                mr,_,_=r16.metrics(zz,T,stability=True)
                plane='right' if direction=='right_level' else direction;cross=np.radians(20) if direction=='right_level' else None
                mesh.update(angle_deg=score(mr,direction),angle_change_deg=abs(score(mr,direction)-row['directional_angle_deg']),
                    max_strain=mr['max_abs_axial_strain'],qualifies=acceptable(mr,mode,plane,cross),residual=mr['equilibrium_residual'],
                    geometry_pass=mr['geometry_pass'],stable_fixed_winch=mr['stable_fixed_winch'])
                row['mesh8_to16_angle_change_deg']=mesh['angle_change_deg'];row['mesh16_angle_deg']=mesh['angle_deg'];row['mesh16_qualifies']=mesh['qualifies']
                if mesh['angle_change_deg']>1 or not mesh['qualifies']:row['angular_mesh_status']='mesh_sensitive_or_boundary_classification_changed'
            else:row['angular_mesh_status']='mesh16_equilibrium_not_found'
            diagnostics.append(mesh)
            r=r8;row['state_id']=f'{direction}_{mode}_selected';sid=row['state_id'];states[sid+'_z']=z;states[sid+'_T']=T
            metric,d,world=r.metrics(z,T);states[sid+'_points_world_m']=world;states[sid+'_q']=d['q'];states[sid+'_frames']=d['frames']
            final.append(row)
            if direction.startswith('right'):
                mirrored,zm,Cm=mirror_state(r,z,T,row)
                for key in ['maximum_angle_deg','status','orientation_search_cap_reached','tension_bound_reached','strain_bound_near','angular_mesh_status','mesh8_to16_angle_change_deg','mesh16_qualifies']:
                    if key in row:mirrored[key]=row[key]
                final.append(mirrored);msid=mirrored['state_id'];states[msid+'_z']=zm;states[msid+'_T']=Cm
                _,dm,wm=r.metrics(zm,Cm);states[msid+'_points_world_m']=wm;states[msid+'_q']=dm['q'];states[msid+'_frames']=dm['frames']
            for pitch in [15,25]:
                rp=SpatialDatabaseRod(u,m,row['anchors'],pitch=pitch,sub=8);zp=stationary(rp,T,z)
                if zp is None:
                    sensitivity.append(dict(configuration=row['configuration'],state_id=sid,pitch_deg=pitch,converged=False));continue
                sr,_,_=rp.metrics(zp,T,stability=True)
                plane='right' if direction=='right_level' else direction
                cross=np.radians(pitch) if direction=='right_level' else None
                sr.update(state_id=sid,direction=direction,strain_mode=mode,converged=True,qualifies=acceptable(sr,mode,plane,cross),
                    directional_angle_deg=score(sr,direction),scope='Same 20deg-selected tensions re-equilibrated at a different base pitch; NOT a reoptimized maximum')
                sensitivity.append(sr)
            print(f'U{u}-M{m}',direction,mode,'selected',round(row['directional_angle_deg'],2),'maxT',round(row['maximum_single_tendon_n'],2),row['angular_mesh_status'],flush=True)
            dump(OUT/f'U{u}_M{m}_maximums.json',final);np.savez_compressed(OUT/f'U{u}_M{m}_selected_states.npz',**states)
            dump(OUT/f'U{u}_M{m}_refinement_checks.json',diagnostics)
    dump(OUT/f'U{u}_M{m}_refined_candidates.json',refined);dump(OUT/f'U{u}_M{m}_maximums.json',final)
    dump(OUT/f'U{u}_M{m}_refinement_checks.json',diagnostics);dump(OUT/f'U{u}_M{m}_pitch_sensitivity.json',sensitivity)
    np.savez_compressed(OUT/f'U{u}_M{m}_selected_states.npz',**states)
    dump(OUT/f'U{u}_M{m}_refinement_completion.json',dict(completed=True,maximum_records=len(final),sensitivity_records=len(sensitivity)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--u',type=int);p.add_argument('--m',type=int);a=p.parse_args();run(a.u,a.m)
