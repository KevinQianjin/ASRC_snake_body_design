"""New database driven planar study. Previous inputs and results are read only.

Run mechanics for each U/M configuration, then run postprocess. No CAD packages
are installed. Saved CAD polygons provide explicitly limited section screening.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import sys, json, csv, sqlite3, hashlib, argparse, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, LinearConstraint

HERE = Path(__file__).resolve().parent
OLD = HERE.parent
ROOT = OLD.parent
sys.path.insert(0, str(OLD))
from front_solver import BaseRod, write_csv
from segmented_tendon_study import SegmentedRod
from refine_front import finer_seed, geometry_screen

OUT = HERE/'results'
from project_paths import STIFFNESS_DATABASE
DB = Path(os.environ.get('ASRC_STIFFNESS_DB', str(STIFFNESS_DATABASE)))
PAIRS = [(4, 2), (6, 3), (8, 4)]

def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')

def load_database():
    con = sqlite3.connect(DB.resolve().as_uri()+'?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    data = {name: [dict(r) for r in con.execute('SELECT * FROM '+name)]
            for name in ['metadata', 'modules', 'rigidity']}
    con.close()
    data['database_sha256'] = hashlib.sha256(DB.read_bytes()).hexdigest()
    return data

DATA = load_database()
MODULES = {r['id']: r for r in DATA['modules']}
RIGIDITY = {(r['module_id'],r['quantity'],r['direction']):r['value'] for r in DATA['rigidity']}
U = 'uni_directional_pa12_niti'
M = 'middle_stiffness_pa12'

class DatabaseRod(SegmentedRod):
    def __init__(self, u, m, anchors, pitch=20, sub=4, common=0):
        self.root_pitch = np.radians(pitch)
        self.n_uni, self.n_medium = u, m
        self.anchors = tuple(anchors)
        self.payload_kg = .5
        BaseRod.__init__(self, (0,0,0,u+m), sub=sub)
        self.common = float(common)
        self.r, self.diameter = .024, .063
        self.interface_length = .020
        lengths = np.r_[np.full(u,MODULES[U]['length_mm']), np.full(m,MODULES[M]['length_mm'])]/1000
        assert np.ptp(lengths) < 1e-12, 'Kernel requires equal module lengths'
        self.module_length = float(lengths[0])
        self.flexible_length = float(lengths.sum())
        self.nominal_length = self.flexible_length+self.interface_length
        self.l = self.module_length/sub
        self.module_EI = np.r_[np.full(u,RIGIDITY[U,'EI','vertical_against_gravity']),np.full(m,RIGIDITY[M,'EI','all_directions'])]
        self.module_EA = np.r_[np.full(u,RIGIDITY[U,'EA','not_specified']),np.full(m,RIGIDITY[M,'EA','not_specified'])]
        self.EI = np.repeat(self.module_EI,sub)
        self.EA = np.repeat(self.module_EA,sub)
        self.routes = np.array([np.arange(self.n)<a for a in anchors],dtype=float)
        self.bare_mass = np.r_[np.full(u,MODULES[U]['mass_g']),np.full(m,MODULES[M]['mass_g'])]/1000
        self.rope_module_mass = self.routes.sum(axis=0)*4*self.rope_density*lengths
        self.mass = np.repeat((self.bare_mass+self.rope_module_mass)/sub,sub)
        self.weight_after = np.cumsum(self.mass[::-1])[::-1]-self.mass+self.payload_kg

    @property
    def label(self): return f'U{self.n_uni}-M{self.n_medium}'

    def control_matrix(self,D):
        C=np.full((len(self.anchors),4),self.common,dtype=float)
        C[:,0]+=D
        return C

    def ideal_controls(self):
        centers=(np.arange(self.n)+.5)*self.module_length
        mm=self.mass.reshape(self.n,self.sub).sum(axis=1)
        moment=np.array([9.81*np.cos(self.root_pitch)*(self.payload_kg*(self.flexible_length-x)+np.sum(mm*np.maximum(0,centers-x))) for x in centers])
        starts=np.r_[0,self.anchors[:-1]].astype(int)
        effective=np.array([moment[a:b].mean()/self.r for a,b in zip(starts,self.anchors)])
        return np.clip(effective-np.r_[effective[1:],0],0,250)

    def metrics(self,x,D,geometry=False):
        E,g,H,d=self.evaluate(x,self.control_matrix(D),detail=True)
        t=np.array([np.cos(self.root_pitch),np.sin(self.root_pitch)])
        normal=np.array([-t[1],t[0]])
        offset=self.interface_length*t
        p=np.vstack((np.zeros(2),d['points']+offset))
        C=self.control_matrix(D)
        A=self.dense_h(H)
        scale=1/np.sqrt(np.maximum(np.abs(np.diag(A)),1e-10))
        eig_force=float(np.linalg.eigvalsh(A*scale[:,None]*scale[None,:])[0])
        G=d['anchor_jac'].reshape(-1,self.ndof)
        rope_lengths=d['anchor_lengths'].ravel()
        forces=C.ravel(); active=forces>1e-7
        rest=rope_lengths/(1+forces/self.rope_ea)+1.
        A+=G[active].T@((self.rope_ea/rest[active])[:,None]*G[active])
        scale=1/np.sqrt(np.maximum(np.abs(np.diag(A)),1e-10))
        eig=float(np.linalg.eigvalsh(A*scale[:,None]*scale[None,:])[0])
        # Cell centres of gravity from the same four-point quadrature as energy.
        theta=d['theta']; th=theta[:-1,None]*self.aa+theta[1:,None]*self.bb
        centres=d['points'][:-1]+(1+d['eps'])[:,None]*self.l*np.c_[np.sum(self.w*(1-self.u)*np.cos(th),axis=1),np.sum(self.w*(1-self.u)*np.sin(th),axis=1)]
        centres+=offset
        eps=d['eps']; dev=float(np.max(np.abs(p@normal)))*1000
        angle=float(np.max(np.abs(theta-self.root_pitch)))*180/np.pi
        proj=float(p[-1]@t)*1000
        strain=float(np.max(np.abs(eps)))
        imax=int(np.argmax(np.abs(eps)))//self.sub
        row=dict(configuration=self.label,n_uni=self.n_uni,n_medium=self.n_medium,
            pitch_deg=float(np.degrees(self.root_pitch)),cells_per_module=self.sub,
            anchors=list(self.anchors),anchor_sets=len(self.anchors),top_extra_tensions_n=np.asarray(D).tolist(),
            common_per_rope_n=self.common,all_tendon_tensions_n=C.tolist(),
            proximal_sum_tension_n=float(C.sum()),effective_module_top_tension_n=(C[:,0]@self.routes).tolist(),
            flexible_length_mm=self.flexible_length*1000,nominal_front_length_mm=self.nominal_length*1000,
            module_mass_g=float(self.bare_mass.sum()*1000),rope_mass_g=float(self.rope_module_mass.sum()*1000),
            head_mass_g=500,diameter_mm=63,guide_radius_mm=24,
            equilibrium_residual=self.residual(g),energy_j=float(E),
            maximum_axis_deviation_mm=dev,axial_projection_mm=proj,
            axial_projection_fraction=proj/(1000*self.nominal_length),
            maximum_tangent_error_deg=angle,tip_pitch_deg=float(np.degrees(theta[-1])),
            tip_x_mm=float(p[-1,0]*1000),tip_y_mm=float(p[-1,1]*1000),
            vertical_head_drop_from_interface_mm=float(-p[-1,1]*1000),
            max_abs_axial_strain=strain,max_compression=float(max(0,-eps.min())),max_extension=float(max(0,eps.max())),
            maximum_strain_module=imax+1,maximum_strain_module_type='U' if imax<self.n_uni else 'M',
            max_U_strain=float(np.max(np.abs(eps[:self.n_uni*self.sub]))),
            max_M_strain=float(np.max(np.abs(eps[self.n_uni*self.sub:]))),
            minimum_scaled_eigenvalue=eig,minimum_constant_tension_eigenvalue=eig_force,
            stable_with_1m_extra_rope=bool(eig>=-1e-7),stable_at_constant_tension=bool(eig_force>=-1e-7),
            strain_diagnostic_pass=bool(strain<=.05+1e-9),
            provisional_straight_geometry=bool(dev<=10 and angle<=5 and proj>=.95*self.nominal_length*1000),
            vertical_gravity_reaction_n=float((self.mass.sum()+.5)*9.81),
            gravity_moment_about_interface_nm=float(9.81*(self.mass@centres[:,0]+.5*p[-1,0])),
            scope='Planar elastic diagnostic; no physical load rating, full 3D or hardware validation')
        row['all_straight_diagnostics_pass']=bool(row['strain_diagnostic_pass'] and row['provisional_straight_geometry'] and row['stable_with_1m_extra_rope'])
        if geometry:
            row.update(geometry_screen(p,d,self))
            row['geometry_screen_scope']='63mm capsules and centreline only; no detailed module contact'
            row['nonlocal_reference_arclength_separation_mm']=2*self.diameter*1000
        return row,p,d

    def optimize(self,seed,D0,max_strain=.3):
        """Local constrained equilibrium matching. No artificial lateral support."""
        n=self.ndof;k=len(self.anchors);cache={}
        def state(u):
            key=u.tobytes()
            if cache.get('key')!=key:
                _,g,H,data=self.evaluate(u[:n],self.control_matrix(u[n:]*100),detail=True)
                cache.update(key=key,g=g,H=H,data=data)
            return cache
        def obj(u):
            return .5*np.mean((u[:n:2]-self.root_pitch)**2)+.1*np.mean(u[1:n:2]**2)+1e-7*np.sum(u[n:]**2)
        def jac(u):
            g=np.zeros_like(u);g[:n:2]=(u[:n:2]-self.root_pitch)/self.m;g[1:n:2]=.2*u[1:n:2]/self.m;g[n:]=2e-7*u[n:];return g
        scale=np.ones(n);scale[1::2]=1/(self.EA*self.l)
        def constraint(u):return state(u)['g']*scale
        def cjac(u):
            q=state(u);G=q['data']['anchor_jac'][:,0,:].T*100
            return np.c_[self.dense_h(q['H']),G]*scale[:,None]
        u=np.r_[seed,np.asarray(D0)/100]
        bounds=[(self.root_pitch-np.pi,self.root_pitch+np.pi) if j%2==0 else (-max_strain,min(max_strain,.15)) for j in range(n)]+[(0,2.5)]*k
        B=np.zeros((self.m,n+k))
        for i in range(self.m):
            B[i,2*i]=1
            if i:B[i,2*i-2]=-1
        lo=np.full(self.m,-.55);hi=-lo;lo[0]+=self.root_pitch;hi[0]+=self.root_pitch
        start=time.time()
        opt=minimize(obj,u,jac=jac,bounds=bounds,
            constraints=[{'type':'eq','fun':constraint,'jac':cjac},LinearConstraint(B,lo,hi)],
            method='SLSQP',options={'maxiter':220,'ftol':1e-11})
        return opt.x[:n],opt.x[n:]*100,dict(success=bool(opt.success),message=str(opt.message),iterations=int(opt.nit),objective=float(opt.fun),seconds=time.time()-start,max_strain_bound=max_strain)

def validation():
    errors=[]
    for u,m in PAIRS:
        r=DatabaseRod(u,m,[u//2,u,u+m],sub=2)
        rng=np.random.default_rng(10+u);x=r.straight_seed();x[::2]+=rng.normal(size=r.m)*.01;x[1::2]=rng.normal(size=r.m)*.001
        D=np.array([7.,5.,3.]);v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
        E,g,H,d=r.evaluate(x,r.control_matrix(D),detail=True)
        fd=(r.evaluate(x+h*v,r.control_matrix(D))[0]-r.evaluate(x-h*v,r.control_matrix(D))[0])/(2*h)
        hv=(r.evaluate(x+h*v,r.control_matrix(D))[1]-r.evaluate(x-h*v,r.control_matrix(D))[1])/(2*h)
        np.testing.assert_allclose(fd,g@v,atol=1e-7,rtol=2e-6)
        np.testing.assert_allclose(hv,r.dense_h(H)@v,atol=1e-5,rtol=2e-6)
        dd=np.array([.2,-.3,.4])
        gd=(r.evaluate(x,r.control_matrix(D+h*dd))[1]-r.evaluate(x,r.control_matrix(D-h*dd))[1])/(2*h)
        np.testing.assert_allclose(gd,d['anchor_jac'][:,0,:].T@dd,atol=1e-7,rtol=1e-6)
        # Independent axial response to four equal tensions; bending moments cancel.
        r.common=.1
        xx=r.straight_seed();expected=-4*r.common*r.routes.sum(axis=0)/r.module_EA
        xx[1::2]=np.repeat(expected,r.sub)
        _,gg,_=r.evaluate(xx,r.control_matrix(np.zeros(3)),gravity=0)
        assert r.residual(gg)<1e-8
        # Rigid offset contributes only an energy constant and is massless.
        assert r.n==u+m and abs(r.flexible_length-(u+m)*.096)<1e-12
        assert abs(r.bare_mass.sum()-(u*37.990+m*23.948)/1000)<1e-12
        errors.append(dict(configuration=r.label,gradient_error=abs(fd-g@v),hessian_vector_error=float(np.max(np.abs(hv-r.dense_h(H)@v))),axial_analytic_residual=r.residual(gg)))
    return dict(passed=True,checks=errors,database_sha256=DATA['database_sha256'])

def save_state(arr,sid,r,x,D):
    row,p,d=r.metrics(x,D,geometry=True)
    arr[sid+'_x']=x;arr[sid+'_points_m']=p;arr[sid+'_strain']=d['eps'];arr[sid+'_theta_rad']=d['theta'];arr[sid+'_top_n']=np.asarray(D)
    return row

def mechanics(u,m):
    OUT.mkdir(parents=True,exist_ok=True)
    attempts=[];sweep=[];baselines=[];best=[];arrays={};opts=[]
    # Finite single-head-anchor sweep; these are controls, not strength ratings.
    forces=np.unique(np.r_[np.arange(0,41,2),48,64,80,100,128,160,200]).astype(float)
    for pitch in [15,20,25]:
        r=DatabaseRod(u,m,[u+m],pitch);free=r.free()
        if free is None:raise RuntimeError(f'No zero-tension equilibrium for {r.label} {pitch}')
        rf=DatabaseRod(u,m,[u+m],pitch,sub=8);xf=rf.solve([0],finer_seed(free,r,rf))
        if xf is None:raise RuntimeError('Baseline fine mesh failed')
        sid=f'free_p{pitch}';row=save_state(arrays,sid,rf,xf,[0]);row.update(state_id=sid,kind='natural_baseline',architecture='single',fine_converged=True);baselines.append(row)
        pools=[]
        for common in [0,2]:
            r.common=common;prev=free
            for force in forces:
                got=r.solve([force],prev)
                if got is None:got=r.solve([force],r.straight_seed())
                attempts.append(dict(configuration=r.label,pitch_deg=pitch,common_per_rope_n=common,top_extra_n=force,converged=got is not None))
                if got is None:continue
                prev=got;row,_,_=r.metrics(got,[force]);row.update(top_extra_n=force,kind='finite_single_sweep')
                sweep.append(row);pools.append((row,got.copy(),[force],common))
        for mode in ['low_strain','shape_only']:
            eligible=[q for q in pools if q[0]['stable_with_1m_extra_rope'] and (mode!='low_strain' or q[0]['strain_diagnostic_pass'])]
            if not eligible:continue
            row,x,D,common=min(eligible,key=lambda q:q[0]['maximum_axis_deviation_mm']+.5*max(0,1000*r.nominal_length-q[0]['axial_projection_mm']))
            fine=DatabaseRod(u,m,[u+m],pitch,sub=8,common=common);xx=fine.solve(D,finer_seed(x,r,fine))
            if xx is None:continue
            sid=f'sweep_{mode}_p{pitch}';fm=save_state(arrays,sid,fine,xx,D)
            fm.update(state_id=sid,kind='single_sweep_best',architecture='single',strain_mode=mode,fine_converged=True,
                mesh_tip_change_mm=float(np.linalg.norm(arrays[sid+'_points_m'][-1]-r.metrics(x,D)[1][-1])*1000))
            best.append(fm)
        print(f'{r.label} {pitch} deg sweep completed',flush=True)
        # The fourth layout retains three sets but puts one anchor inside M.
        prior_solutions={}
        layouts=[('single',[u+m]),('two',[u,u+m]),('three',[u//2,u,u+m]),
                 ('three_distal',[u,u+max(1,m//2),u+m])]
        for architecture,anchors in layouts:
            r=DatabaseRod(u,m,anchors,pitch);free=r.free()
            if free is None:raise RuntimeError('Segmented free equilibrium failed')
            ideal=r.ideal_controls();seeds=[(free,np.zeros(len(anchors)),'sag')]
            seed=r.straight_seed()
            for g in np.linspace(9.81/30,9.81,30):
                q=r.solve(ideal*g/9.81,seed,g)
                if q is None:break
                seed=q
            else:seeds.append((seed,ideal,'moment_compensation'))
            # Reserve margin below 5% on the coarse mesh, then enforce the
            # actual diagnostic on the fine solution instead of rounding 5.1%.
            for mode,bound in [('shape_only',.3),('low_strain',.0485)]:
                candidates=[]
                use=seeds if mode=='shape_only' else seeds+[(q[1],q[2],'previous_shape') for q in shape_candidates[:1]]
                # Embed the simpler layout as an additional initial branch.
                # An extra control cannot be evaluated only from one local seed.
                parent='single' if architecture=='two' else 'two'
                if architecture!='single' and (parent,mode) in prior_solutions:
                    px,pD,panchors=prior_solutions[parent,mode]
                    mapped=np.zeros(len(anchors))
                    for old_anchor,tension in zip(panchors,pD):mapped[anchors.index(old_anchor)]=tension
                    sx=r.solve(mapped,px)
                    if sx is not None:use=list(use)+[(sx,mapped,'embedded_'+parent)]
                for x,D,label in use:
                    xx,DD,info=r.optimize(x,D,bound)
                    residual=r.residual(r.evaluate(xx,r.control_matrix(DD))[1])
                    opts.append(dict(configuration=r.label,pitch_deg=pitch,architecture=architecture,strain_mode=mode,seed=label,residual=residual,**info))
                    if residual<2e-7 and np.max(np.abs(xx[1::2]))<=bound+1e-7:
                        candidates.append((info['objective'],xx,DD))
                if mode=='shape_only':shape_candidates=sorted(candidates,key=lambda q:q[0])
                if not candidates:
                    best.append(dict(configuration=r.label,pitch_deg=pitch,architecture=architecture,strain_mode=mode,kind='optimized',fine_converged=False,status='no_admissible_stationary_solution_found',anchors=anchors))
                    print(r.label,pitch,architecture,mode,'no candidate',flush=True);continue
                _,x,D=min(candidates,key=lambda q:q[0])
                prior_solutions[architecture,mode]=(x.copy(),D.copy(),anchors)
                fine=DatabaseRod(u,m,anchors,pitch,sub=8);xx=fine.solve(D,finer_seed(x,r,fine))
                if xx is None:
                    best.append(dict(configuration=r.label,pitch_deg=pitch,architecture=architecture,strain_mode=mode,kind='optimized',fine_converged=False,status='fine_mesh_solve_failed',anchors=anchors));continue
                sid=f'{architecture}_{mode}_p{pitch}';row=save_state(arrays,sid,fine,xx,D)
                coarse=r.metrics(x,D)[0]
                row.update(state_id=sid,kind='optimized',architecture=architecture,strain_mode=mode,fine_converged=True,status='best_local_stationary_solution_found',coarse_max_abs_strain=coarse['max_abs_axial_strain'],mesh_tip_change_mm=float(np.linalg.norm(arrays[sid+'_points_m'][-1]-r.metrics(x,D)[1][-1])*1000))
                best.append(row)
                print(r.label,pitch,architecture,mode,'offset',round(row['maximum_axis_deviation_mm'],2),'strain',round(100*row['max_abs_axial_strain'],2),'T',np.round(D,2),flush=True)
                # Persist after each solved architecture to retain useful progress.
                dump(OUT/f'U{u}_M{m}_best.json',best);np.savez_compressed(OUT/f'U{u}_M{m}_states.npz',**arrays)
    write_csv(OUT/f'U{u}_M{m}_single_sweep.csv',sweep)
    write_csv(OUT/f'U{u}_M{m}_attempts.csv',attempts)
    write_csv(OUT/f'U{u}_M{m}_optimizer_attempts.csv',opts)
    dump(OUT/f'U{u}_M{m}_baseline.json',baselines);dump(OUT/f'U{u}_M{m}_best.json',best)
    np.savez_compressed(OUT/f'U{u}_M{m}_states.npz',**arrays)
    dump(OUT/f'U{u}_M{m}_completion.json',dict(completed=True,sweep_attempts=len(attempts),sweep_equilibria=len(sweep),optimizer_attempts=len(opts),fine_solutions=sum(q.get('fine_converged',False) for q in best),database_sha256=DATA['database_sha256']))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['validate','mechanics']);parser.add_argument('--u',type=int);parser.add_argument('--m',type=int);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.action=='validate':
        dump(HERE/'input_parameters.json',dict(database=DATA,diameter_mm=63,guide_radius_mm=24,head_mass_kg=.5,interface_length_mm=20,configuration_pairs=PAIRS))
        result=validation();dump(OUT/'validation.json',result);print(json.dumps(result,indent=2))
    else: mechanics(args.u,args.m)
