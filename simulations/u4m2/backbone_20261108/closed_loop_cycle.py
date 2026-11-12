"""Quasi-static output feedback with nominal-model gains and perturbed plants.

Positive command increments pay rope out. The controller observes only yaw,
elevation and 12 tensions. Plant parameters are not used to construct gains.
No dynamics, sensor noise, latency, friction or hardware-rate claims are made.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,csv,json,hashlib,time,pickle
from pathlib import Path
import numpy as np
from scipy.linalg import solve
from scipy.optimize import minimize, root
from length_cycle import LengthDrive,FastTank,spatial_rod,HERE,to_tank

REF=HERE/'length_cycle_results_pre3'
OUT=HERE/'closed_loop_results'
NAMES=[f'a{a}_{d}' for a in [4,5,6] for d in ['up','right','down','left']]
CASES={'nominal':('niti18_E40',.5,1.,1.),'E75':('niti18_E75',.5,1.,1.),
       'payload550g':('niti18_E40',.55,1.,1.),'free1500mm':('niti18_E40',.5,1.,1.5),
       'ropeEA80pct':('niti18_E40',.5,.8,1.)}

class FeedbackDrive(LengthDrive):
    """Warm-start root solver with a reused Jacobian and original fallback.

    The previous inspected tangent is only a numerical solver preconditioner.
    Acceptance still uses the actual equilibrium residual and a newly computed
    tangent eigenvalue at every distinct inspected state.
    """
    def tangent(self,z,rest,T):
        J=self.r.control_jacobian(z);active=T.ravel()>1e-8
        return self.r.hessian(z,T)+J[active].T@((self.ea/rest.ravel()[active])[:,None]*J[active])

    def stability(self,z,rest,T):
        from scipy.linalg import eigvalsh
        self._last_hessian=self.tangent(z,rest,T)
        return float(eigvalsh(self._last_hessian,subset_by_index=[0,0])[0])

    def solve(self,z,rest):
        H=getattr(self,'_last_hessian',None)
        kw={} if H is None else dict(jac=lambda x:H)
        got=root(lambda x:self.energy(x,rest)[1],z,method='hybr',
                 options={'xtol':1e-9,'maxfev':1200 if H is None else 100},**kw)
        q=(got.x/self.r.scale).reshape(-1,4)
        if self.r.residual(self.energy(got.x,rest)[1])<2e-6 and np.max(abs(q[:,3]))<=.0475 and np.max(abs(q[:,:3]))<=1.5:
            return got.x
        return super().solve(z,rest)

def angles(r,z):return np.degrees(r.kinematic_metrics(z)[0][[0,2]])
def error(target,actual):
    e=np.asarray(target)-actual;e[0]=(e[0]+180)%360-180;return e

def gains(r,d,z,R):
    """d[angles(deg), tensions(N)]/d(rest length(mm)), implicit equilibrium."""
    T=d.force(z,R).ravel();J=r.control_jacobian(z)
    H=r.hessian(z,T.reshape(3,4))+J.T@((d.ea/R.ravel())[:,None]*J)
    a=-(d.ea+T)/R.ravel()
    dz=solve(H,-J.T*a,assume_a='sym')
    D=np.empty((2,r.ndof));h=1e-6
    for k in range(r.ndof):
        v=np.zeros(r.ndof);v[k]=h
        D[:,k]=error(angles(r,z+v),angles(r,z-v))/(2*h)
    return np.vstack((D@dz,(d.ea/R.ravel())[:,None]*(J@dz)+np.diag(a)))/1000

def prepare():
    OUT.mkdir(exist_ok=True)
    rows=json.loads((REF/'nominal.json').read_text()); zs=np.load(REF/'nominal_states.npz')['z']
    r=spatial_rod(4,2,[4,5,6],20,8);d=LengthDrive(r);cache={};B=[];Rs=[];targets=[]
    for i,(q,z) in enumerate(zip(rows,zs)):
        R=np.array([q[n+'_rest_mm'] for n in NAMES]).reshape(3,4)/1000
        key=np.round(R,10).tobytes()
        if key not in cache:cache[key]=gains(r,d,z,R)
        B.append(cache[key]);Rs.append(R)
        targets.append([q['target_yaw_deg'],q['elevation_deg'] if q['phase']=='straighten' else 20.])
        if i%100==0:print('gains',i,flush=True)
    np.savez_compressed(OUT/'nominal_gains.npz',B=B,R=Rs,target=targets)
    meta=dict(reference_sha256=hashlib.sha256((REF/'nominal.json').read_bytes()).hexdigest(),
              states_sha256=hashlib.sha256((REF/'nominal_states.npz').read_bytes()).hexdigest(),
              controller='nominal E40 / 500g / 1m; angle+tension measurements only',
              correction_limit_mm=.25,total_offset_limit_mm=5.,feedback_tension_target_n=1.5,
              settled_angle_tolerance_deg=.2,maximum_iterations=16,adaptive_scale_floor=.0625,error_growth_threshold=1.05,unique_gains=len(cache))
    (OUT/'settings.json').write_text(json.dumps(meta,indent=2));print(meta,flush=True)

def adapt_scale(previous_error,current_error,scale):
    """Reduce later corrections after measured angular-error growth.

    Only outputs from already applied commands are used. The scale is carried
    across references; comparisons reset when the feedforward command changes.
    """
    if previous_error is not None and previous_error>.2 and current_error>1.05*previous_error:
        return max(.0625,scale/2)
    return scale

def correction(B,err,T,offset):
    A=B[:2];C=B[2:]
    def fun(x):return .5*np.sum((A@x-err)**2)+.0001*np.sum(x*x)
    def jac(x):return A.T@(A@x-err)+.0002*x
    lo=np.maximum(-.25,-5-offset);hi=np.minimum(.25,5-offset)
    cons=[dict(type='ineq',fun=lambda x:T+C@x-1.5,jac=lambda x:C),
          dict(type='ineq',fun=lambda x:250-T-C@x,jac=lambda x:-C)]
    opt=minimize(fun,np.zeros(12),jac=jac,bounds=list(zip(lo,hi)),constraints=cons,method='SLSQP',
                 options=dict(maxiter=100,ftol=1e-10))
    return opt.x,bool(opt.success)

def inspect(r,d,z,R,q,tank,target):
    key=(z.tobytes(),R.tobytes())
    if getattr(d,'_inspect_key',None)!=key:
        T=d.force(z,R);m,_,world=r.metrics(z,T);eig=d.stability(z,R,T)
        d._inspect_key=key;d._inspect_value=(T,m,world,eig)
    T,m,world,eig=d._inspect_value
    P=to_tank(world*1000,20,q['clamp_s_mm'],tank.entry_h)
    gap=tank.clearance(P)[0];a=np.array([m['yaw_deg'],m['world_elevation_deg']]);err=error(target,a)
    passed=bool(gap-1.5>=5 and eig>1e-7 and m['geometry_pass'] and m['max_abs_axial_strain']<=.05 and T.min()>=.95 and T.max()<=250 and np.max(abs(err))<=1)
    return dict(yaw_deg=float(a[0]),elevation_deg=float(a[1]),yaw_error_deg=float(err[0]),elevation_error_deg=float(err[1]),
        minimum_tension_n=float(T.min()),peak_tension_n=float(T.max()),clearance_mm=gap,minimum_eigenvalue=eig,
        geometry_pass=m['geometry_pass'],strain=m['max_abs_axial_strain'],residual=m['equilibrium_residual'],checks_pass=passed,
        tensions_n=T.ravel().tolist(),head_tank_mm=P[-1].tolist()),P

def run(case,limit=None):
    rows=json.loads((REF/'nominal.json').read_text());refzs=np.load(REF/'nominal_states.npz')['z'];data=np.load(OUT/'nominal_gains.npz')
    if limit:rows=rows[:limit]
    variant,payload,ea,free=CASES[case]
    r=spatial_rod(4,2,[4,5,6],20,8,variant);r.payload=payload;d=FeedbackDrive(r,free,ea);do=FeedbackDrive(r,free,ea)
    nominal=spatial_rod(4,2,[4,5,6],20,8)
    z=refzs[0]/nominal.scale*r.scale;zo=z.copy();offset=np.zeros(12)
    tank=FastTank();records=[];trace=[];Z=[];ZO=[];P=[];PO=[];savedR=[];prevkey=None;cache=None
    checkpoint=OUT/f'{case}_checkpoint.pkl'
    start=0;damping=1.
    if checkpoint.exists() and limit is None:
        saved=pickle.loads(checkpoint.read_bytes())
        records,trace,Z,ZO,P,PO,savedR,z,zo,offset,prevkey,cache,damping=saved
        start=len(records)
        print('Resuming',case,start,flush=True)
    for i,q in enumerate(rows):
        if i<start:continue
        R0=data['R'][i]+free-1.;target=data['target'][i];B=data['B'][i]
        key=np.r_[R0.ravel(),target].tobytes()
        reused=key==prevkey
        if not reused:
            xo=do.solve(zo,R0)
            if xo is None:raise RuntimeError(f'{case} open solve failed at {i}')
            zo=xo;R=R0+offset.reshape(3,4)/1000
            x=d.solve(z,R)
            if x is None:raise RuntimeError(f'{case} closed solve failed at {i}')
            z=x;iterations=0;qp_failures=0;previous_error=None
            # Record the feedforward arrival and every physically applied correction.
            for it in range(17):
                metrics,points=inspect(r,d,z,R,q,tank,target)
                trace.append(dict(index=i,iteration=it,phase=q['phase'],offset_mm=offset.tolist(),**metrics))
                err=error(target,angles(r,z));T=d.force(z,R).ravel()
                norm=float(np.max(abs(err)));damping=adapt_scale(previous_error,norm,damping);previous_error=norm
                trace[-1]['next_correction_scale']=damping
                if (np.max(abs(err))<=.2 and T.min()>=1.25) or it==16:break
                delta,ok=correction(B,err,T,offset);delta*=damping
                if not ok:qp_failures+=1
                if np.max(abs(delta))<1e-8:break
                candidate=d.solve(z,R+delta.reshape(3,4)/1000)
                if candidate is None:break
                offset+=delta;R=R0+offset.reshape(3,4)/1000;z=candidate;iterations+=1
            cache=(iterations,qp_failures)
        R=R0+offset.reshape(3,4)/1000
        # Translation changes clearance even when rope commands and state are reused.
        closed,points=inspect(r,d,z,R,q,tank,target);opened,pointso=inspect(r,do,zo,R0,q,tank,target)
        rec=dict(index=i,phase=q['phase'],clamp_s_mm=q['clamp_s_mm'],target_yaw_deg=float(target[0]),target_elevation_deg=float(target[1]),
                 closed=closed,open=opened,iterations=0 if reused else cache[0],qp_failures=0 if reused else cache[1],offset_mm=offset.tolist(),correction_scale=damping)
        records.append(rec);Z.append(z.copy());ZO.append(zo.copy());P.append(points);PO.append(pointso);savedR.append(R.copy());prevkey=key
        if i%25==0 or i==len(rows)-1:
            tmp=checkpoint.with_suffix('.tmp')
            tmp.write_bytes(pickle.dumps((records,trace,Z,ZO,P,PO,savedR,z,zo,offset,prevkey,cache,damping)))
            tmp.replace(checkpoint)
        if i%50==0:print(case,i,q['phase'],'open',round(max(abs(opened['yaw_error_deg']),abs(opened['elevation_error_deg'])),2),'closed',round(max(abs(closed['yaw_error_deg']),abs(closed['elevation_error_deg'])),3),'Tmin',round(closed['minimum_tension_n'],2),flush=True)
    summary=dict(case=case,completed=len(records)==1069,samples=len(records),controller_uses_plant_parameters=False)
    for mode in ['open','closed']:
        vv=[q[mode] for q in records]
        summary[mode]=dict(failed_samples=sum(not v['checks_pass'] for v in vv),
            maximum_yaw_error_deg=max(abs(v['yaw_error_deg']) for v in vv),maximum_elevation_error_deg=max(abs(v['elevation_error_deg']) for v in vv),
            minimum_tension_n=min(v['minimum_tension_n'] for v in vv),peak_tension_n=max(v['peak_tension_n'] for v in vv),
            minimum_clearance_mm=min(v['clearance_mm'] for v in vv),minimum_eigenvalue=min(v['minimum_eigenvalue'] for v in vv))
    summary['feedback_trace']=dict(samples=len(trace),failed_samples=sum(not v['checks_pass'] for v in trace),
        unstable_samples=sum(v['minimum_eigenvalue']<=1e-7 for v in trace),geometry_failures=sum(not v['geometry_pass'] for v in trace),
        clearance_failures=sum(v['clearance_mm']-1.5<5 for v in trace),minimum_tension_n=min(v['minimum_tension_n'] for v in trace))
    summary['minimum_correction_scale']=min(q['correction_scale'] for q in records)
    summary['maximum_offset_mm']=max(np.max(np.abs(v['offset_mm'])) for v in records)
    (OUT/f'{case}.json').write_text(json.dumps(records,indent=1));(OUT/f'{case}_feedback.json').write_text(json.dumps(trace,indent=1))
    (OUT/f'{case}_summary.json').write_text(json.dumps(summary,indent=2))
    np.savez_compressed(OUT/f'{case}_states.npz',closed=Z,open=ZO,points=P,open_points=PO,rest=savedR)
    flat=[]
    for q in records:
        row={k:q[k] for k in ['index','phase','clamp_s_mm','target_yaw_deg','target_elevation_deg','iterations','qp_failures','correction_scale']}
        for mode in ['open','closed']:
            row.update({mode+'_'+k:v for k,v in q[mode].items() if not isinstance(v,list)})
        for k,name in enumerate(NAMES):
            row[name+'_offset_mm']=q['offset_mm'][k];row[name+'_rest_mm']=float(savedR[q['index']].ravel()[k]*1000);row[name+'_tension_n']=q['closed']['tensions_n'][k]
        flat.append(row)
    with (OUT/f'{case}.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    checkpoint.unlink(missing_ok=True)
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--case',choices=list(CASES));p.add_argument('--limit',type=int)
    a=p.parse_args()
    if a.prepare:prepare()
    if a.case:run(a.case,a.limit)
