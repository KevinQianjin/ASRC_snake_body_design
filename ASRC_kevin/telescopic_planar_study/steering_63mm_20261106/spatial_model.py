"""Spatial finite-rotation rod with reverse derivatives and actual disk tendons.

Local axes: forward X, up Y, right Z. World up is Y; base pitch rotates X-Y.
All anchor sets start at the base. No artificial tendon-force decoupling.
Numba accelerates existing numerical operations; no new packages are installed.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import sys,json,hashlib
from pathlib import Path
import numpy as np
from numba import njit
from scipy.optimize import minimize,root
from scipy.linalg import eigvalsh

HERE=Path(__file__).resolve().parent
PLANAR=HERE.parent/'stiffness_63mm_20261106'
sys.path.insert(0,str(PLANAR))
from run_study import DatabaseRod,DATA,DB,RIGIDITY,U,M,dump,write_csv

@njit(cache=True)
def rotation(phi):
    x,y,z=phi
    K=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    DK=np.zeros((3,3,3))
    DK[0,1,2]=-1;DK[0,2,1]=1
    DK[1,0,2]=1;DK[1,2,0]=-1
    DK[2,0,1]=-1;DK[2,1,0]=1
    t=np.dot(phi,phi)
    if t<1e-5:
        a=1-t/6+t*t/120-t*t*t/5040
        b=.5-t/24+t*t/720-t*t*t/40320
        da=-1/6+t/60-t*t/1680
        db=-1/24+t/360-t*t/13440
    else:
        s=np.sqrt(t);a=np.sin(s)/s;b=(1-np.cos(s))/t
        da=(s*np.cos(s)-np.sin(s))/(2*s**3)
        db=(s*np.sin(s)-2*(1-np.cos(s)))/(2*t*t)
    K2=K@K
    R=np.eye(3)+a*K+b*K2
    derivatives=np.empty((3,3,3))
    for j in range(3):derivatives[j]=2*phi[j]*da*K+a*DK[j]+2*phi[j]*db*K2+b*(DK[j]@K+K@DK[j])
    return R,derivatives

@njit(cache=True)
def kernel(z,C,scale,K,mass,length,sub,routes,offsets,gauss_u,gauss_w,gravity,gw,payload):
    """Energy and exact first derivative using a reverse frame recursion."""
    cells=len(mass);ndof=4*cells;modules=cells//sub;sets=len(C)
    q=(z/scale).reshape((cells,4))
    F=np.zeros((cells+1,3,3));F[0]=np.eye(3)
    p=np.zeros((cells+1,3));R=np.empty((cells,3,3));dR=np.empty((cells,3,3,3))
    v=np.empty((cells,3));vc=np.empty((cells,3));dv=np.empty((cells,4,3));dc=np.empty((cells,4,3))
    mapping=np.array([0,2,1]);signs=np.array([1.,1.,-1.])
    energy=.5*np.sum(K*q*q)
    for i in range(cells):
        phi=np.array([q[i,0],-q[i,2],q[i,1]])
        Ri,DR=rotation(phi);R[i]=Ri
        for k in range(3):dR[i,k]=DR[mapping[k]]*signs[k]
        t=np.zeros(3);c=np.zeros(3);jt=np.zeros((3,3));jc=np.zeros((3,3))
        for j in range(len(gauss_u)):
            u=gauss_u[j];w=gauss_w[j];Rq,DQ=rotation(phi*u)
            t+=w*Rq[:,0];c+=w*(1-u)*Rq[:,0]
            for k in range(3):
                jt[k]+=w*u*signs[k]*DQ[mapping[k],:,0]
                jc[k]+=w*(1-u)*u*signs[k]*DQ[mapping[k],:,0]
        lam=1+q[i,3]
        v[i]=length*lam*t;vc[i]=length*lam*c
        for k in range(3):dv[i,k]=length*lam*jt[k];dc[i,k]=length*lam*jc[k]
        dv[i,3]=length*t;dc[i,3]=length*c
        p[i+1]=p[i]+F[i]@v[i]
        F[i+1]=F[i]@Ri
        energy+=mass[i]*gravity*np.dot(gw,p[i]+F[i]@vc[i])
    energy+=payload*gravity*np.dot(gw,p[-1])
    ap=np.zeros((cells+1,3));af=np.zeros((cells+1,3,3))
    ap[-1]+=payload*gravity*gw
    for i in range(cells):
        force=mass[i]*gravity*gw
        ap[i]+=force;af[i]+=np.outer(force,vc[i])
    rope_lengths=np.zeros((sets,4))
    for j in range(modules):
        i0=j*sub;i1=(j+1)*sub
        for rope in range(4):
            off=offsets[rope];a=p[i0]+F[i0]@off;b=p[i1]+F[i1]@off
            chord=b-a;ll=np.sqrt(np.dot(chord,chord))
            if ll<1e-10:ll=1e-10
            tension=0.
            for k in range(sets):
                rope_lengths[k,rope]+=routes[k,j]*ll
                tension+=routes[k,j]*C[k,rope]
            energy+=tension*ll
            force=tension*chord/ll
            ap[i0]-=force;ap[i1]+=force
            af[i0]-=np.outer(force,off);af[i1]+=np.outer(force,off)
    grad=K*q
    for i in range(cells-1,-1,-1):
        pv=F[i].T@ap[i+1];fr=F[i].T@af[i+1]
        force_local=F[i].T@(mass[i]*gravity*gw)
        for k in range(3):grad[i,k]+=np.sum(fr*dR[i,k])+np.dot(pv,dv[i,k])+np.dot(force_local,dc[i,k])
        grad[i,3]+=np.dot(pv,dv[i,3])+np.dot(force_local,dc[i,3])
        af[i]+=af[i+1]@R[i].T+np.outer(ap[i+1],v[i])
        ap[i]+=ap[i+1]
    return energy,grad.ravel()/scale,p,F,q,rope_lengths

@njit(cache=True)
def segment_distance_sq(a,b,c,d):
    u=b-a;v=d-c;w=a-c
    A=np.dot(u,u);B=np.dot(u,v);CC=np.dot(v,v);D=np.dot(u,w);E=np.dot(v,w)
    answer=1e100
    for k in range(4):
        if k==0:point=a;start=c;end=d
        elif k==1:point=b;start=c;end=d
        elif k==2:point=c;start=a;end=b
        else:point=d;start=a;end=b
        vec=end-start;den=np.dot(vec,vec);t=np.dot(point-start,vec)/max(den,1e-30)
        t=min(1.,max(0.,t));delta=point-start-t*vec;answer=min(answer,np.dot(delta,delta))
    den=A*CC-B*B
    if den>1e-20:
        s=(B*E-CC*D)/den;t=(A*E-B*D)/den
        if s>=0 and s<=1 and t>=0 and t<=1:
            delta=w+s*u-t*v;answer=min(answer,np.dot(delta,delta))
    return answer

@njit(cache=True)
def capsule_values(p,ii,jj,diameter):
    result=np.empty(len(ii))
    for k in range(len(ii)):
        i,j=ii[k],jj[k]
        result[k]=segment_distance_sq(p[i],p[i+1],p[j],p[j+1])/(diameter*diameter)-1
    return result

class SpatialDatabaseRod:
    def __init__(self,u,m,anchors,pitch=20,sub=1):
        self.planar=DatabaseRod(u,m,anchors,pitch,sub)
        p=self.planar;self.u_count=u;self.m_count=m;self.n=p.n;self.m=p.m;self.sub=sub;self.l=p.l
        self.anchors=list(anchors);self.k=len(anchors);self.ndof=4*self.m;self.routes=p.routes
        self.mass=p.mass;self.payload=.5;self.diameter=.063;self.radius=.024;self.pitch=pitch
        vertical=p.EI
        horizontal=np.repeat(np.r_[np.full(u,RIGIDITY[U,'EI','horizontal']),np.full(m,RIGIDITY[M,'EI','all_directions'])],sub)
        spring=np.r_[np.full(u,RIGIDITY[U,'GJ','not_specified']),np.full(m,RIGIDITY[M,'GJ','not_specified'])]
        self.twist=np.repeat(spring*.096,sub)
        self.K=np.c_[self.twist/self.l,vertical/self.l,horizontal/self.l,p.EA*self.l]
        self.scale=np.sqrt(self.K).ravel()
        self.offsets=.024*np.array([[0.,1.,0.],[0.,0.,1.],[0.,-1.,0.],[0.,0.,-1.]])
        a=np.radians(pitch);self.R0=np.array([[np.cos(a),-np.sin(a),0.],[np.sin(a),np.cos(a),0.],[0.,0.,1.]])
        self.gw=self.R0[1]
        # Nonlocal capsule screening uses reference separation >= two diameters.
        arc=np.r_[0.,.02+np.arange(self.m+1)*self.l]
        pairs=[(i,j) for i in range(self.m+1) for j in range(i+2,self.m+1) if arc[j]-arc[i+1]>=2*self.diameter-1e-12]
        self.ii=np.array([p[0] for p in pairs],dtype=np.int64);self.jj=np.array([p[1] for p in pairs],dtype=np.int64)

    @property
    def label(self):return f'U{self.u_count}-M{self.m_count}'

    def evaluate(self,z,T=None,gravity=9.81,detail=False):
        C=np.zeros((self.k,4)) if T is None else np.asarray(T,dtype=float).reshape(self.k,4)
        result=kernel(np.asarray(z),C,self.scale,self.K,self.mass,self.l,self.sub,self.routes,self.offsets,self.planar.u,self.planar.w,gravity,self.gw,self.payload)
        if not detail:return result[:2]
        E,g,p,F,q,lengths=result
        return E,g,dict(points=p,frames=F,q=q,rope_lengths=lengths)

    def residual(self,g):
        raw=(np.asarray(g)*self.scale).reshape(-1,4)
        return max(float(np.max(np.abs(raw[:,:3]))),float(np.max(np.abs(raw[:,3]/self.l)))*.01)

    def lift_planar(self,x):
        q=np.zeros((self.m,4));q[:,1]=np.diff(np.r_[self.planar.root_pitch,x[::2]]);q[:,3]=x[1::2]
        return q.ravel()*self.scale

    def hessian(self,z,T):
        step=2e-5;H=np.empty((self.ndof,self.ndof))
        for j in range(self.ndof):
            dz=np.zeros(self.ndof);dz[j]=step
            H[:,j]=(self.evaluate(z+dz,T)[1]-self.evaluate(z-dz,T)[1])/(2*step)
        return (H+H.T)/2

    def control_jacobian(self,z):
        C=np.zeros((self.k,4));base=self.evaluate(z,C)[1];J=np.empty((self.k*4,self.ndof))
        for j in range(self.k*4):
            C.ravel()[j]=1.;J[j]=self.evaluate(z,C)[1]-base;C.ravel()[j]=0.
        return J

    def kinematic_metrics(self,z):
        _,_,d=self.evaluate(z,detail=True)
        tang=np.einsum('ij,nj->ni',self.R0,d['frames'][:,:,0])
        yaw=float(np.unwrap(np.arctan2(tang[:,2],tang[:,0]))[-1])
        vertical=float(np.unwrap(np.arctan2(tang[:,1],tang[:,0]))[-1]-np.radians(self.pitch))
        elevation=float(np.arctan2(tang[-1,1],np.hypot(tang[-1,0],tang[-1,2])))
        return np.array([yaw,vertical,elevation]),d

    def geometry_constraints(self,z,d=None):
        if d is None:_,_,d=self.evaluate(z,detail=True)
        q=d['q'];p=np.vstack((np.zeros(3),d['points']+np.array([.02,0,0])))
        # Positive values pass. A small radius-curvature margin is explicit.
        local=(.98*self.l*(1+q[:,3])/(self.diameter/2))**2-np.sum(q[:,1:3]**2,axis=1)
        nonlocal_=capsule_values(p,self.ii,self.jj,self.diameter)
        return np.r_[local,nonlocal_]

    def solve(self,T,initial,maxiter=800):
        def fun(z):return self.evaluate(z,T)
        bounds=[]
        for j,s in enumerate(self.scale):bounds.append((-.7*s,.2*s) if j%4==3 else (-1.5*s,1.5*s))
        opt=minimize(fun,initial,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':maxiter,'gtol':1e-9,'ftol':1e-15,'maxls':40,'maxcor':40})
        res=self.residual(self.evaluate(opt.x,T)[1])
        if res>2e-6:
            try:
                got=root(lambda z:self.evaluate(z,T)[1],opt.x,jac=lambda z:self.hessian(z,T),method='hybr',options={'xtol':1e-9})
                rr=self.residual(self.evaluate(got.x,T)[1])
                if rr<res:opt.x=got.x;res=rr
            except (ValueError,np.linalg.LinAlgError):pass
        q=(opt.x/self.scale).reshape(-1,4)
        if res<2e-6 and np.max(np.abs(q[:,3]))<.7 and np.max(np.abs(q[:,:3]))<1.5:
            return opt.x
        return None

    def metrics(self,z,T,stability=False):
        E,g,d=self.evaluate(z,T,detail=True);angles,_=self.kinematic_metrics(z)
        q=d['q'];t=d['frames'][-1,:,0];world_t=self.R0@t
        world=np.vstack((np.zeros(3),(d['points']+np.array([.02,0,0]))@self.R0.T))
        geom=self.geometry_constraints(z,d);local_r=np.linalg.norm(q[:,1:3],axis=1)/(self.l*(1+q[:,3]))*.0315
        nonlocal_=geom[self.m:]
        eigen=None;force_eigen=None
        if stability:
            H=self.hessian(z,T);force_eigen=float(eigvalsh(H,subset_by_index=[0,0])[0])
            J=self.control_jacobian(z);forces=np.asarray(T).ravel();active=forces>1e-7
            rest=d['rope_lengths'].ravel()/(1+forces/self.planar.rope_ea)+1.
            H+=J[active].T@((self.planar.rope_ea/rest[active])[:,None]*J[active])
            eigen=float(eigvalsh(H,subset_by_index=[0,0])[0])
        row=dict(configuration=self.label,n_uni=self.u_count,n_medium=self.m_count,anchors=self.anchors,anchor_sets=self.k,
            pitch_deg=self.pitch,cells_per_module=self.sub,tension_order=['up','right','down','left'],tensions_n=np.asarray(T).reshape(self.k,4).tolist(),
            maximum_single_tendon_n=float(np.max(T)),sum_tensions_n=float(np.sum(T)),
            yaw_deg=float(np.degrees(angles[0])),vertical_projected_deg=float(np.degrees(angles[1])),world_elevation_deg=float(np.degrees(angles[2])),
            true_head_axis_angle_deg=float(np.degrees(np.arccos(np.clip(t[0],-1,1)))),
            head_world_mm=world[-1].tolist(),
            max_abs_axial_strain=float(np.max(np.abs(q[:,3]))),max_compression=float(max(0,-q[:,3].min())),max_extension=float(max(0,q[:,3].max())),max_U_strain=float(np.max(np.abs(q[:self.u_count*self.sub,3]))),max_M_strain=float(np.max(np.abs(q[self.u_count*self.sub:,3]))),
            maximum_strain_module=int(np.argmax(np.abs(q[:,3])))//self.sub+1,
            total_material_twist_deg=float(np.degrees(q[:,0].sum())),
            equilibrium_residual=self.residual(g),minimum_geometry_constraint=float(geom.min()) if len(geom) else None,
            maximum_radius_curvature=float(local_r.max()),
            nonlocal_capsule_clearance_mm=None if not len(nonlocal_) else float((np.sqrt(max(0,nonlocal_.min()+1))-.0)*63-63),
            geometry_pass=bool(np.min(geom)>=-1e-7),strain_5percent_pass=bool(np.max(np.abs(q[:,3]))<=.05+1e-8),
            horizontal_projection_norm=float(np.hypot(world_t[0],world_t[2])),vertical_projection_norm=float(np.hypot(world_t[0],world_t[1])),
            minimum_fixed_winch_eigenvalue=eigen,minimum_force_control_eigenvalue=force_eigen,
            stable_fixed_winch=None if eigen is None else bool(eigen>=-1e-7),
            scope='Finite local free-space spatial equilibrium; no tank, material strength or hardware rating')
        row['head_world_mm']=(world[-1]*1000).tolist()
        return row,d,world

def refine_seed(z,coarse,fine):
    q=(z/coarse.scale).reshape(-1,4);ratio=fine.sub//coarse.sub
    assert ratio*coarse.sub==fine.sub
    qf=np.repeat(q,ratio,axis=0);qf[:,:3]/=ratio
    return qf.ravel()*fine.scale

def validate():
    records=[]
    for u,m in [(4,2),(6,3),(8,4)]:
        r=SpatialDatabaseRod(u,m,[u,u+m],sub=2);rng=np.random.default_rng(u)
        z=rng.normal(size=r.ndof)*.01;T=np.array([[4.,2.,1.,.5],[3.,.7,1.,2.]])
        E,g,d=r.evaluate(z,T,detail=True);v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=2e-6
        fd=(r.evaluate(z+h*v,T)[0]-r.evaluate(z-h*v,T)[0])/(2*h)
        assert abs(fd-g@v)<2e-7,(fd,g@v)
        p=r.planar;x=p.straight_seed();x[::2]+=np.linspace(-.02,-.4,p.m);x[1::2]=-.01
        C=np.array([[5.,0,0,0],[3.,0,0,0]])
        zp=r.lift_planar(x);ep,gp,dp=r.evaluate(zp,C,detail=True)
        E2,g2,H2,d2=p.evaluate(x,C,detail=True)
        # The pitched rigid interface adds a constant gravity energy excluded
        # from both equilibrium kernels; compare elastic/gravity/tendon energy.
        np.testing.assert_allclose(ep,E2,atol=2e-10)
        np.testing.assert_allclose(dp['points']@r.R0.T,np.c_[d2['points'],np.zeros(len(d2['points']))],atol=2e-12)
        dtheta=np.diff(np.r_[0.,np.linspace(0,.02,p.m)])
        dz=np.zeros((p.m,4));dz[:,1]=dtheta
        derivative=gp@(dz.ravel()*r.scale)
        vx=np.zeros(p.ndof);vx[::2]=np.linspace(0,.02,p.m)
        np.testing.assert_allclose(derivative,g2@vx,atol=2e-9)
        # An isolated module twist must preserve its spring energy at any mesh.
        qt=np.zeros((r.m,4));qt[-r.sub:,0]=.1/r.sub
        et=r.evaluate(qt.ravel()*r.scale,gravity=0)[0]
        np.testing.assert_allclose(et,.5*RIGIDITY[M,'GJ','not_specified']*.1**2,atol=1e-11)
        records.append(dict(configuration=r.label,gradient_error=float(abs(fd-g@v)),planar_energy_error=float(abs(ep-E2)),twist_energy_error=float(abs(et-.5*RIGIDITY[M,'GJ','not_specified']*.1**2))))
    return dict(passed=True,records=records,database_sha256=DATA['database_sha256'])

if __name__=='__main__':print(json.dumps(validate(),indent=2))
