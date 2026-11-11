"""Reproducible position-controlled quasi-static cycle; no hardware commands.

Replay nominal inverse-elastic rest lengths through forward equilibrium, including
intermediate commands and return legs. Sensitivities replay identical commands.
Collision is a sampled 63 mm envelope screen, not continuous collision proof.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, root
from scipy.linalg import eigvalsh
from backbone import HERE, spatial_rod
from tank3d_screen import Tank, to_tank

SOURCE = HERE/'results/minforce_niti18_E40_p20_a456_pre1_exact_smooth1_states.npz'
OUT = HERE/'length_cycle_results'
CASE_EN={'nominal':'Nominal','E75':'Backbone modulus 75 GPa','payload550g':'Payload 550 g','ropeEA80pct':'Rope axial stiffness -20%','free1500mm':'Free rope length 1.5 m'}
PHASE_EN={'straighten':'Straightening','entry':'Insertion','right_out':'Right sweep','right_return':'Return from right','left_out':'Left sweep','left_return':'Return from left','exit':'Withdrawal'}


class FastTank(Tank):
    """Same triangle mesh and clearance algorithm, accelerated nearest triangles."""
    def __init__(self):
        super().__init__()
        import vtk
        from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
        points=vtk.vtkPoints(); points.SetData(numpy_to_vtk(np.asarray(self.mesh.vertices),deep=True))
        cells=vtk.vtkCellArray()
        cells.SetCells(len(self.F),numpy_to_vtkIdTypeArray(np.c_[np.full(len(self.F),3),self.F].astype(np.int64).ravel(),deep=True))
        self.poly=vtk.vtkPolyData(); self.poly.SetPoints(points); self.poly.SetPolys(cells)
        locator=vtk.vtkStaticCellLocator(); locator.SetDataSet(self.poly); locator.BuildLocator()
        class Query:
            def on_surface(self,pts):
                closest=[]; distances=[]; ids=[]
                cp=[0.,0.,0.]; cid=vtk.reference(0); sub=vtk.reference(0); d2=vtk.reference(0.)
                for point in pts:
                    locator.FindClosestPoint(point,cp,cid,sub,d2)
                    closest.append(cp.copy()); distances.append(float(d2)**.5); ids.append(int(cid))
                return np.asarray(closest),np.asarray(distances),np.asarray(ids)
        self.query=Query()

class LengthDrive:
    def __init__(self, rod, free=1., ea_scale=1.):
        self.r = rod
        self.free = free
        self.ea = rod.planar.rope_ea * ea_scale

    def inverse(self, z, tension):
        L = self.r.evaluate(z, detail=True)[2]['rope_lengths']
        return (L+self.free)/(1+np.asarray(tension)/self.ea)

    def force(self, z, rest):
        L = self.r.evaluate(z, detail=True)[2]['rope_lengths']
        return self.ea*np.maximum(0., L+self.free-rest)/rest

    def energy(self, z, rest):
        E, _, d = self.r.evaluate(z, detail=True)
        ext = np.maximum(0., d['rope_lengths']+self.free-rest)
        T = self.ea*ext/rest
        return E+np.sum(.5*self.ea*ext**2/rest), self.r.evaluate(z,T)[1]

    def solve(self, z, rest):
        bounds=[(-.0475*s,.0475*s) if j%4==3 else (-1.5*s,1.5*s) for j,s in enumerate(self.r.scale)]
        got=minimize(lambda x:self.energy(x,rest),z,jac=True,bounds=bounds,method='L-BFGS-B',
                     options=dict(maxiter=2000,gtol=1e-10,ftol=1e-16,maxls=50,maxcor=40))
        x=got.x
        if self.r.residual(self.energy(x,rest)[1])>2e-6:
            rr=root(lambda v:self.energy(v,rest)[1],x,tol=1e-9)
            if self.r.residual(self.energy(rr.x,rest)[1])<self.r.residual(self.energy(x,rest)[1]): x=rr.x
        if any(xi<lo-1e-9 or xi>hi+1e-9 for xi,(lo,hi) in zip(x,bounds)): return None
        return x if self.r.residual(self.energy(x,rest)[1])<2e-6 else None

    def stability(self,z,rest,T):
        J=self.r.control_jacobian(z); active=T.ravel()>1e-8
        H=self.r.hessian(z,T)
        H+=J[active].T@((self.ea/rest.ravel()[active])[:,None]*J[active])
        return float(eigvalsh(H,subset_by_index=[0,0])[0])


STARTUP=None  # optional startup_sweep.py states (.npz); None keeps the original 10 mm payout start


def references(max_yaw=175.):
    data=np.load(SOURCE); r=spatial_rod(4,2,[4,5,6],20,8)
    drive=LengthDrive(r); poses=[]
    for yaw in sorted(float(k[1:-3]) for k in data.files if k.endswith('_z8')):
        if yaw>max_yaw: continue
        z=data[f'y{yaw:g}_z8']; T=data[f'y{yaw:g}_T8']
        poses.append((yaw,z,drive.inverse(z,T)))
    if len(poses)<2: raise ValueError('Insufficient reference states')
    # Reflect right to left by swapping right/left rest-length channels.
    right=[(y,z,R) for y,z,R in poses]
    left=[(-y,None,R[:,[0,3,2,1]]) for y,z,R in poses]
    knots=[]
    z_start=poses[0][1]
    if STARTUP is None:
        # Defined slackened start: pay out upper ropes 10 mm, then reel to held baseline.
        for payout in np.arange(10.,-.001,-1.):
            R=right[0][2].copy(); R[:,0]+=payout/1000
            knots.append(('straighten',0.,-750.,R))
    else:
        # Stable startup: natural sag with every rope at the pretension, then held-elevation
        # states raised step by step to the working elevation (startup_sweep.py).
        st=np.load(STARTUP); ks=sorted(int(k[1:-3]) for k in st.files if k.endswith('_z8'))
        for k in ks:
            knots.append(('straighten',0.,-750.,drive.inverse(st[f'k{k}_z8'],st[f'k{k}_T8'])))
        knots.append(('straighten',0.,-750.,right[0][2]))
        z_start=st[f'k{ks[0]}_z8']
    # Entry/exit is rigid translation of a held straight front. No release-to-sag.
    for s in np.arange(-750.,15.001,5.): knots.append(('entry',0.,float(s),right[0][2]))
    for leg,seq in [('right_out',right[1:]),('right_return',right[-2::-1]),('left_out',left[1:]),('left_return',left[-2::-1])]:
        for yaw,_,R in seq: knots.append((leg,yaw,15.,R))
    for s in np.arange(10.,-750.001,-5.): knots.append(('exit',0.,float(s),right[0][2]))
    return r, z_start, knots, right[0][2]


def run(case,tank,max_yaw=175.):
    _,z0,knots,R_base=references(max_yaw)
    settings={'nominal':('niti18_E40',.5,1.,1.), 'E75':('niti18_E75',.5,1.,1.),
              'payload550g':('niti18_E40',.55,1.,1.),'ropeEA80pct':('niti18_E40',.5,.8,1.),
              'free1500mm':('niti18_E40',.5,1.,1.5)}
    variant,payload,ea,free=settings[case]
    r=spatial_rod(4,2,[4,5,6],20,8,variant); r.payload=payload
    # Preserve physical q when stiffness scaling changes.
    rn=spatial_rod(4,2,[4,5,6],20,8)
    z=z0/rn.scale*r.scale
    drive=LengthDrive(r,free,ea)
    # Extra physical free length is matched by an equal zero-offset in commands.
    knots=[(leg,y,s,R+(free-1.)) for leg,y,s,R in knots]
    rows=[]; states=[]; last_world=None; last_R=knots[0][3]; last_y=0.; last_s=knots[0][2]
    failed=False
    cached_R=None; cached_x=None; cached_eig=None
    def advance(R,y,s,leg,depth=0):
        nonlocal z,last_world,last_R,last_y,last_s,failed,cached_R,cached_x,cached_eig
        same=cached_R is not None and np.array_equal(R,cached_R)
        x=cached_x if same else drive.solve(z,R)
        if x is None:
            if depth<7 and np.max(abs(R-last_R))>1e-7:
                Rm=(R+last_R)/2; ym=(y+last_y)/2; sm=(s+last_s)/2
                return advance(Rm,ym,sm,leg,depth+1) and advance(R,y,s,leg,depth+1)
            rows.append(dict(index=len(rows),phase=leg,status='solve_failed',target_yaw_deg=y,clamp_s_mm=s));failed=True;return False
        T=drive.force(x,R); m,d,world=r.metrics(x,T)
        tank_world=to_tank(world*1000,20,s,tank.entry_h)
        movement=0 if last_world is None else float(np.linalg.norm(tank_world-last_world,axis=1).max())
        if movement>5. and depth<9:
            Rm=(R+last_R)/2;ym=(y+last_y)/2;sm=(s+last_s)/2
            return advance(Rm,ym,sm,leg,depth+1) and advance(R,y,s,leg,depth+1)
        gap,_,_=tank.clearance(tank_world)
        eig=cached_eig if same else drive.stability(x,R,T)
        cached_R=R.copy();cached_x=x.copy();cached_eig=eig
        # 2 mm centreline spacing => <=1 mm distance sampling error; mesh tolerance .5 mm.
        gap_bound=gap-1.5
        rec=dict(index=len(rows),phase=leg,status='solved',target_yaw_deg=float(y),clamp_s_mm=float(s),
                 yaw_deg=m['yaw_deg'],yaw_error_deg=float(m['yaw_deg']-y),elevation_deg=m['world_elevation_deg'],
                 head_x_mm=float(tank_world[-1,0]),head_y_mm=float(tank_world[-1,1]),head_z_mm=float(tank_world[-1,2]),
                 clearance_mm=gap,clearance_margin_mm=gap_bound,geometry_pass=m['geometry_pass'],
                 self_clearance_mm=m['nonlocal_capsule_clearance_mm'],strain=m['max_abs_axial_strain'],
                 eigenvalue=eig,stable=bool(eig>1e-7),residual=m['equilibrium_residual'],
                 min_tension_n=float(T.min()),peak_tension_n=float(T.max()),max_point_step_mm=movement,
                 checks_pass=bool(gap_bound>=5 and eig>1e-7 and m['geometry_pass'] and m['max_abs_axial_strain']<=.05 and T.min()>=.95 and T.max()<=250 and movement<=5.001 and (leg=='straighten' or (abs(m['yaw_deg']-y)<=1 and abs(m['world_elevation_deg']-20)<=5))))
        for i,a in enumerate([4,5,6]):
            for j,name in enumerate(['up','right','down','left']):
                key=f'a{a}_{name}'
                rec[key+'_rest_mm']=float(R[i,j]*1000)
                rec[key+'_pull_mm']=float((R_base[i,j]+(free-1.)-R[i,j])*1000)
                rec[key+'_tension_n']=float(T[i,j])
        rows.append(rec);states.append(x.copy());z=x;last_R=R.copy();last_y=y;last_s=s;last_world=tank_world
        if len(rows)%50==0: print(case,len(rows),leg,round(y,1),round(gap,1),flush=True)
        return True
    for leg,y,s,R in knots:
        n=max(1,int(np.ceil(np.max(abs(R-last_R))/.001)))
        Rstart=last_R.copy(); ys=last_y; ss=last_s
        for t in np.linspace(0,1,n+1)[1:]:
            if not advance(Rstart+(R-Rstart)*t,ys+(y-ys)*t,ss+(s-ss)*t,leg): break
        if failed:break
    OUT.mkdir(exist_ok=True)
    (OUT/f'{case}.json').write_text(json.dumps(rows,indent=1))
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/f'{case}.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    np.savez_compressed(OUT/f'{case}_states.npz',z=np.asarray(states))
    good=[q for q in rows if q['status']=='solved']; steering=[q for q in good if q['phase'] not in ['straighten','entry','exit']]
    summary=dict(case=case,variant=variant,payload_kg=payload,rope_ea_scale=ea,free_length_m=free,
                 completed=not failed,states=len(good),all_checks_pass=bool(not failed and all(q['checks_pass'] for q in good)),
                 failed_checks=sum(not q['checks_pass'] for q in good),minimum_clearance_mm=min(q['clearance_mm'] for q in good),
                 minimum_eigenvalue=min(q['eigenvalue'] for q in good),minimum_tension_n=min(q['min_tension_n'] for q in good),
                 peak_tension_n=max(q['peak_tension_n'] for q in good),maximum_yaw_error_deg=max(abs(q['yaw_error_deg']) for q in (steering or good)),
                 maximum_elevation_error_deg=max(abs(q['elevation_deg']-20) for q in (steering or good)),
                 maximum_point_step_mm=max(q['max_point_step_mm'] for q in good),
                 source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),tank_sha256=tank.sha,
                 scope='Quasi-static frictionless sampled path; 63mm head envelope; no dynamics, real head CAD or external cables')
    # Return error is evaluated at equal clamp depth, before extraction.
    zero=[q for q in steering if abs(q['target_yaw_deg'])<1e-9]
    if zero:
        start=next(q for q in good if q['phase']=='entry' and q['clamp_s_mm']==15)
        end=zero[-1]
        summary['return_head_error_mm']=float(np.linalg.norm([end[k]-start[k] for k in ['head_x_mm','head_y_mm','head_z_mm']]))
    (OUT/f'{case}_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)
    return summary


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='DejaVu Sans'
    plt.rcParams['axes.unicode_minus']=False
    fig,axs=plt.subplots(6,1,figsize=(12,15),sharex=True)
    for f in sorted(OUT.glob('*_summary.json')):
        case=f.name.removesuffix('_summary.json');rows=json.loads((OUT/f'{case}.json').read_text()); rows=[q for q in rows if q['status']=='solved']
        phase_order=['straighten','entry','right_out','right_return','left_out','left_return','exit']
        x=[]
        for q in rows:
            phase=q['phase']; base=phase_order.index(phase)
            if phase=='entry': f=(q['clamp_s_mm']+750)/765
            elif phase=='exit': f=(15-q['clamp_s_mm'])/765
            elif phase.endswith('_out'): f=abs(q['target_yaw_deg'])/175
            elif phase.endswith('_return'): f=1-abs(q['target_yaw_deg'])/175
            else:
                local=[v for v in rows if v['phase']==phase]
                f=(q['index']-local[0]['index'])/max(1,len(local)-1)
            x.append(base+f)
        x=np.asarray(x)
        for ax,key in zip(axs,['yaw_deg','elevation_deg','clearance_mm','peak_tension_n','min_tension_n','eigenvalue']):ax.plot(x,[q[key] for q in rows],label=CASE_EN.get(case,case))
    for ax,label in zip(axs,['Yaw (deg)','Elevation (deg)','Tank clearance (mm)','Peak rope force (N)','Minimum rope force (N)','Minimum tangent eigenvalue']):ax.set_ylabel(label);ax.grid(alpha=.3)
    axs[0].legend(ncol=3);axs[2].axhline(6.5,color='r',ls='--');axs[4].axhline(.95,color='r',ls='--');axs[5].axhline(0,color='r',ls='--');axs[-1].set_xticks(np.arange(7)+.5,['Straighten','Insert','Right','Return','Left','Return','Withdraw']);axs[-1].set_xlabel('Command phase progress (not time)')
    fig.suptitle('U4+M2 length-controlled round trip: straightening, insertion, steering and withdrawal')
    fig.tight_layout();fig.savefig(OUT/'cycle_comparison.png',dpi=150);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cases',nargs='+',default=['nominal','E75','payload550g','ropeEA80pct','free1500mm']);p.add_argument('--max-yaw',type=float,default=175)
    p.add_argument('--source',default=None,help='min_force_sweep.py states (.npz) to follow; default: the 1 N reference sweep')
    p.add_argument('--startup',default=None,help='startup_sweep.py states (.npz); default: 10 mm upper-rope payout start')
    p.add_argument('--out',default=None,help='results folder; default length_cycle_results')
    a=p.parse_args()
    if a.source: SOURCE=Path(a.source).resolve()
    if a.startup: STARTUP=Path(a.startup).resolve()
    if a.out: OUT=Path(a.out).resolve()
    tank=FastTank()
    for case in a.cases: run(case,tank,a.max_yaw);plot()
