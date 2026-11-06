"""Finite bounded steering searches and refinement, with no old result edits."""
import os,time,json,argparse,hashlib,shutil
import numpy as np
from scipy.optimize import minimize
from spatial_model import HERE,PLANAR,SpatialDatabaseRod,refine_seed,validate,DATA,DB,dump,write_csv

OUT=HERE/'results'
DIRECTIONS={'right':(0,1),'up':(1,1),'down':(1,-1)}
ANGLE_CAP=np.pi

def layouts(u,m):return [('single',[u+m]),('two',[u,u+m]),('three_U',[u//2,u,u+m]),('three_M',[u,u+max(1,m//2),u+m])]

def derivative(fun,x,step=2e-5):
    result=np.empty((len(np.atleast_1d(fun(x))),len(x)))
    for j in range(len(x)):
        dx=np.zeros(len(x));dx[j]=step
        result[:,j]=(np.atleast_1d(fun(x+dx))-np.atleast_1d(fun(x-dx)))/(2*step)
    return result

def optimize(r,z0,C0,direction,mode,cross_reference=None,maxiter=140):
    axis,sense=DIRECTIONS[direction];n=r.ndof;k=r.k*4;cache={}
    def state(u):
        z=u[:n];C=u[n:].reshape(r.k,4)*100
        if cache.get('key')!=u.tobytes():
            E,g,d=r.evaluate(z,C,detail=True);a,_=r.kinematic_metrics(z)
            cache.update(key=u.tobytes(),g=g,d=d,a=a)
        return cache
    def obj(u):return -sense*state(u)['a'][axis]+1e-9*np.sum(u[n:]**2)
    def jac(u):
        v=np.zeros(n+k)
        v[:n]=-sense*derivative(lambda z:r.kinematic_metrics(z)[0][axis:axis+1],u[:n])[0]
        v[n:]=2e-9*u[n:];return v
    def eq(u):return state(u)['g']
    def eqjac(u):return np.c_[r.hessian(u[:n],u[n:].reshape(r.k,4)*100),100*r.control_jacobian(u[:n]).T]
    def inequalities_z(z):
        angles,d=r.kinematic_metrics(z);t=r.R0@d['frames'][-1,:,0]
        projection=t[0]**2+(t[2]**2 if axis==0 else t[1]**2)
        result=np.r_[r.geometry_constraints(z,d),projection-.01,ANGLE_CAP-sense*angles[axis]]
        if cross_reference is not None:
            # Additional diagnostic: preserve loaded elevation for yaw, or
            # preserve forward horizontal heading for a vertical-plane turn.
            cross=angles[2]-cross_reference if axis==0 else angles[0]-cross_reference
            result=np.r_[result,np.radians(5)-cross,np.radians(5)+cross]
        return result
    def inequalities(u):return inequalities_z(u[:n])
    def ijac(u):return np.c_[derivative(inequalities_z,u[:n]),np.zeros((len(inequalities_z(u[:n])),k))]
    strain=.0475 if mode=='low_strain' else .3
    bounds=[]
    for j,s in enumerate(r.scale):bounds.append((-strain*s,min(strain,.15)*s) if j%4==3 else (-1.5*s,1.5*s))
    bounds.extend([(0.,2.5)]*k)
    start=time.time()
    answer=minimize(obj,np.r_[z0,np.asarray(C0).ravel()/100],jac=jac,bounds=bounds,
        constraints=[{'type':'eq','fun':eq,'jac':eqjac},{'type':'ineq','fun':inequalities,'jac':ijac}],
        method='SLSQP',options={'maxiter':maxiter,'ftol':2e-10})
    z=answer.x[:n];C=answer.x[n:].reshape(r.k,4)*100
    res=r.residual(r.evaluate(z,C)[1]);iv=float(inequalities(answer.x).min())
    q=(z/r.scale).reshape(-1,4)
    ok=bool(res<2e-6 and iv>=-2e-6 and np.max(np.abs(q[:,3]))<=strain+1e-6)
    return z,C,dict(success=bool(answer.success),message=str(answer.message),iterations=int(answer.nit),seconds=time.time()-start,
        equilibrium_residual=res,minimum_inequality=iv,coarse_strain_bound=strain,feasible_stationary=ok,
        requested_direction=direction,strain_mode=mode,cross_reference_rad=cross_reference)

def acceptable(row,mode,direction,cross_reference=None):
    axis,sense=DIRECTIONS[direction];angle=row['yaw_deg'] if axis==0 else row['vertical_projected_deg']
    projection=row['horizontal_projection_norm'] if axis==0 else row['vertical_projection_norm']
    crossok=True
    if cross_reference is not None:
        value=row['world_elevation_deg'] if axis==0 else row['yaw_deg']
        crossok=abs(value-np.degrees(cross_reference))<=5.001
    return bool(row['equilibrium_residual']<2e-6 and row['geometry_pass'] and row['stable_fixed_winch'] and
        (mode!='low_strain' or row['strain_5percent_pass']) and projection>=.0999 and
        sense*angle<=180.01 and np.max(row['tensions_n'])<=250.0001 and crossok)

def run(u,m):
    OUT.mkdir(parents=True,exist_ok=True)
    attempts=[];coarse=[];base_rows=[];states={};started=time.time()
    # Search only right, then independently check reflected left equilibria.
    for architecture,anchors in layouts(u,m):
        r=SpatialDatabaseRod(u,m,anchors,sub=2)
        p=r.planar;xp=p.free()
        if xp is None:raise RuntimeError('No planar loaded seed')
        zbase=r.lift_planar(xp);Czero=np.zeros((r.k,4))
        zbase=r.solve(Czero,zbase)
        if zbase is None:raise RuntimeError('No spatial loaded baseline')
        baseline,_,_=r.metrics(zbase,Czero,stability=True);baseline.update(architecture=architecture,kind='baseline')
        base_rows.append(baseline)
        for direction in DIRECTIONS:
            previous=None
            for mode in ['low_strain','exploratory']:
                seeds=[(zbase,Czero,'loaded_sag')]
                trial=np.zeros_like(Czero)
                trial[-1,{'right':1,'up':0,'down':2}[direction]]=4.
                if direction=='right':trial[-1,0]=2.
                zs=r.solve(trial,zbase)
                if zs is not None:seeds.append((zs,trial,'small_active_tension'))
                if previous is not None:seeds.append((*previous,'low_strain_branch'))
                if mode=='exploratory' and direction=='up':
                    # Reuse the previous actively straightened planar branch.
                    old_arch={'three_U':'three','three_M':'three_distal'}.get(architecture,architecture)
                    old=json.loads((PLANAR/'results'/f'U{u}_M{m}_best.json').read_text())
                    match=[q for q in old if q.get('architecture')==old_arch and q.get('strain_mode')=='shape_only' and abs(q['pitch_deg']-20)<1e-6 and q.get('fine_converged')]
                    if match:
                        C=np.zeros_like(Czero);C[:,0]=match[0]['top_extra_tensions_n']
                        got=r.solve(C,zbase)
                        if got is not None:seeds.append((got,C,'previous_active_planar'))
                candidates=[]
                for seed,T,label in seeds:
                    z,C,info=optimize(r,seed,T,direction,mode)
                    info.update(configuration=r.label,architecture=architecture,seed=label);attempts.append(info)
                    if not info['feasible_stationary']:continue
                    row,d,world=r.metrics(z,C,stability=True)
                    row.update(architecture=architecture,direction=direction,strain_mode=mode,kind='coarse_optimized',pitch_reference='world horizontal yaw; base-relative projected vertical',baseline_elevation_deg=baseline['world_elevation_deg'],baseline_vertical_deg=baseline['vertical_projected_deg'])
                    row['qualifies']=acceptable(row,mode,direction)
                    row['directional_angle_deg']=DIRECTIONS[direction][1]*(row['yaw_deg'] if direction=='right' else row['vertical_projected_deg'])
                    if row['qualifies']:candidates.append((row,z,C))
                # Preserve baseline as a valid attainable pose, never label a
                # negative upward angle as positive upward reach.
                if acceptable(baseline,mode,direction):
                    row=dict(baseline,architecture=architecture,direction=direction,strain_mode=mode,kind='baseline_retained',qualifies=True,
                        directional_angle_deg=DIRECTIONS[direction][1]*(baseline['yaw_deg'] if direction=='right' else baseline['vertical_projected_deg']),
                        baseline_elevation_deg=baseline['world_elevation_deg'],baseline_vertical_deg=baseline['vertical_projected_deg'])
                    candidates.append((row,zbase,Czero))
                if candidates:
                    row,z,C=max(candidates,key=lambda t:t[0]['directional_angle_deg'])
                    sid=f'{architecture}_{direction}_{mode}'
                    row['state_id']=sid;coarse.append(row);states[sid+'_z']=z;states[sid+'_T']=C
                    previous=(z,C)
                    print(r.label,architecture,direction,mode,'coarse angle',round(row['directional_angle_deg'],2),'strain',round(100*row['max_abs_axial_strain'],2),'peak T',round(row['maximum_single_tendon_n'],2),flush=True)
                else:
                    coarse.append(dict(configuration=r.label,architecture=architecture,direction=direction,strain_mode=mode,qualifies=False,status='no_qualifying_stationary_solution_found'))
                    print(r.label,architecture,direction,mode,'no qualifying candidate',flush=True)
                dump(OUT/f'U{u}_M{m}_coarse.json',coarse);dump(OUT/f'U{u}_M{m}_optimization_attempts.json',attempts)
                np.savez_compressed(OUT/f'U{u}_M{m}_coarse_states.npz',**states)
    dump(OUT/f'U{u}_M{m}_baselines.json',base_rows)
    dump(OUT/f'U{u}_M{m}_coarse_completion.json',dict(completed=True,seconds=time.time()-started,attempts=len(attempts),database_sha256=DATA['database_sha256']))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['validate','coarse']);parser.add_argument('--u',type=int);parser.add_argument('--m',type=int);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.action=='validate':
        result=validate();dump(OUT/'validation.json',result)
        dump(HERE/'input_parameters.json',dict(database=DATA,diameter_mm=63,guide_radius_mm=24,payload_kg=.5,base_pitch_deg=20,
            numerical_tension_bound_n=250,projection_norm_minimum=.1,orientation_search_cap_deg=180,
            coarse_cells_per_module=2,low_strain_coarse_bound=.0475,exploratory_coarse_strain_bound=[-.3,.15],
            capsule_radius_curvature_bound=.98,extra_free_rope_m=1,scope='Free space; no tank clearance or real material limits'))
        shutil.copy2(DB,HERE/'module_stiffness_input.sqlite3');print(json.dumps(result,indent=2))
    else:run(args.u,args.m)
