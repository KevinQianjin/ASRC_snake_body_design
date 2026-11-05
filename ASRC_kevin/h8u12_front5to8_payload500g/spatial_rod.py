"""Spatial extensible Kirchhoff rod, discrete real-disk tendons and tip mass.

Piecewise constant material curvature/twist; exponential-map frames, exact
rotation derivatives and Gauss integration. All four tensions and gravity
act simultaneously. Mesh refinement adds no tendon guide disks.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from scipy.optimize import minimize,root
from scipy.linalg import eigvalsh
from payload_planar import PayloadPlanarRod

def rotations(phi):
    """Batch SO(3) exponential and derivative wrt its three Cartesian entries."""
    phi=np.asarray(phi);shape=phi.shape[:-1]
    K=np.zeros(shape+(3,3));x,y,z=np.moveaxis(phi,-1,0)
    K[...,0,1]=-z;K[...,0,2]=y;K[...,1,0]=z;K[...,1,2]=-x;K[...,2,0]=-y;K[...,2,1]=x
    t=np.sum(phi*phi,axis=-1);safe=np.maximum(t,1e-12);u=np.sqrt(safe)
    a=np.where(t<1e-5,1-t/6+t*t/120-t**3/5040,np.sin(u)/u)
    b=np.where(t<1e-5,.5-t/24+t*t/720-t**3/40320,(1-np.cos(u))/safe)
    da=np.where(t<1e-5,-1/6+t/60-t*t/1680,(u*np.cos(u)-np.sin(u))/(2*u**3))
    db=np.where(t<1e-5,-1/24+t/360-t*t/13440,(u*np.sin(u)-2*(1-np.cos(u)))/(2*safe*safe))
    K2=K@K;R=np.eye(3)+a[...,None,None]*K+b[...,None,None]*K2
    dK=np.array([[[0,0,0],[0,0,-1],[0,1,0]],[[0,0,1],[0,0,0],[-1,0,0]],[[0,-1,0],[1,0,0],[0,0,0]]])
    derivatives=np.stack([2*phi[...,j,None,None]*da[...,None,None]*K+a[...,None,None]*dK[j]+
       2*phi[...,j,None,None]*db[...,None,None]*K2+b[...,None,None]*(dK[j]@K+K@dK[j]) for j in range(3)],axis=-1)
    return R,derivatives

class SpatialRod:
    def __init__(self,counts,sub=2,*,payload_kg=.5):
        self.planar=PayloadPlanarRod(counts,sub,payload_kg=payload_kg)
        p=self.planar;self.counts=tuple(counts);self.sub=sub;self.n=p.n;self.m=p.m;self.b=p.b;self.ndof=4*self.m
        self.l=p.l;self.mass=p.mass;self.after=p.weight_after;self.payload_kg=payload_kg
        import craft_data as D
        kinds=np.repeat(np.arange(4),counts);names=['high','unidirectional','directional','low']
        self.vertical=np.repeat([D.MODULES[names[i]]['EI_y' if i in [1,2] else 'EI_x'] for i in kinds],sub)
        self.sidepos=np.repeat([D.MODULES[names[i]]['EI_x' if i in [1,2] else 'EI_y'] for i in kinds],sub)
        self.sideneg=np.repeat([D.MODULES[names[i]]['EI_negx' if i in [1,2] else 'EI_y'] for i in kinds],sub)
        # craft_data identifies module torsional coefficient as T/theta (Nm/rad).
        self.twist=np.repeat([D.MODULES[names[i]]['GJ']*.048 for i in kinds],sub)
        self.core_g=77e9 # additional 304 reference for torsion only; not a module conversion
        core=np.arange(self.m)<self.b
        self.vertical+=core*p.core_ei;self.sidepos+=core*p.core_ei;self.sideneg+=core*p.core_ei
        self.twist+=core*self.core_g*2*p.I
        self.EA=p.EA
        self.scale=np.sqrt(np.c_[self.twist/self.l,self.vertical/self.l,self.sidepos/self.l,self.EA*self.l]).ravel()
        self.offsets=.013*np.array([[0,1,0],[0,0,1],[0,-1,0],[0,0,-1]])

    def evaluate(self,z,T=(0,0,0,0),gravity=9.81,*,detail=False):
        q=(np.asarray(z)/self.scale).reshape(self.m,4);phi=np.c_[q[:,0],-q[:,2],q[:,1]]
        R,dR=rotations(phi);Rq,dRq=rotations(phi[:,None,:]*self.planar.u[None,:,None])
        # derivative order converts Cartesian rotation vector to twist/up/right.
        dR=dR[...,[0,2,1]]*np.array([1,1,-1])
        dRq=dRq[...,[0,2,1]]*np.array([1,1,-1])*self.planar.u[None,:,None,None,None]
        t=np.einsum('q,cqi->ci',self.planar.w,Rq[:,:,:,0])
        c=np.einsum('q,cqi->ci',self.planar.w*(1-self.planar.u),Rq[:,:,:,0])
        jt=np.einsum('q,cqij->cij',self.planar.w,dRq[:,:,:,0,:])
        jc=np.einsum('q,cqij->cij',self.planar.w*(1-self.planar.u),dRq[:,:,:,0,:])
        frames=np.empty((self.m+1,3,3));frames[0]=np.eye(3)
        points=np.zeros((self.m+1,3));jp=np.zeros((3,self.ndof));jf=np.zeros((3,3,self.ndof))
        disk_points=[];disk_frames=[];disk_jp=[];disk_jf=[];centroids=[]
        gravE=0.;gravG=np.zeros(self.ndof)
        for i in range(self.m):
            F=frames[i];lam=1+q[i,3];ll=self.l*lam
            globalt=F@t[i];globalc=F@c[i]
            jv=ll*np.einsum('ijk,j->ik',jf,t[i]);jv[:,i*4:i*4+3]+=ll*F@jt[i]
            jv[:,i*4+3]+=self.l*globalt
            jcent=ll*np.einsum('ijk,j->ik',jf,c[i]);jcent[:,i*4:i*4+3]+=ll*F@jc[i]
            jcent[:,i*4+3]+=self.l*globalc
            gravE+=gravity*ll*(self.after[i]*globalt[1]+self.mass[i]*globalc[1])
            gravG+=gravity*(self.after[i]*jv[1]+self.mass[i]*jcent[1])
            centroids.append(points[i]+ll*globalc)
            if i%self.sub==0:
                disk_points.append(points[i].copy());disk_frames.append(F.copy());disk_jp.append(jp.copy());disk_jf.append(jf.copy())
            points[i+1]=points[i]+ll*globalt;jp+=jv
            frames[i+1]=F@R[i]
            newjf=np.einsum('ijk,jl->ilk',jf,R[i]);newjf[:,:,i*4:i*4+3]+=np.einsum('ij,jlk->ilk',F,dR[i]);jf=newjf
        disk_points.append(points[-1]);disk_frames.append(frames[-1]);disk_jp.append(jp.copy());disk_jf.append(jf.copy())
        disks=np.array(disk_points);df=np.array(disk_frames);dp=np.array(disk_jp);djf=np.array(disk_jf)
        guides=disks[:,None,:]+np.einsum('nij,kj->nki',df,self.offsets)
        jguide=dp[:,None,:,:]+np.einsum('nijk,rj->nrik',djf,self.offsets)
        chord=np.diff(guides,axis=0);length=np.linalg.norm(chord,axis=-1)
        if np.min(length)<1e-9:raise ValueError('collapsed tendon chord')
        units=chord/length[:,:,None]
        J=np.einsum('nri,nrik->rk',units,np.diff(jguide,axis=0))/self.scale
        lengths=length.sum(axis=0);T=np.asarray(T,dtype=float)
        side=np.where(q[:,2]>=0,self.sidepos,self.sideneg)
        K=np.c_[self.twist/self.l,self.vertical/self.l,side/self.l,self.EA*self.l]
        elastic=.5*np.sum(K*q*q);grad=(K*q).ravel()/self.scale+gravG/self.scale+T@J
        energy=elastic+gravE+T@lengths
        if not detail:return float(energy),grad
        return float(energy),grad,dict(q=q,points=points,frames=frames,disks=disks,guide_points=guides,rope_lengths=lengths,
           rope_jac=J,head_jac=jp/self.scale,centroids=np.array(centroids),units=units)

    def residual(self,g):
        raw=(np.asarray(g)*self.scale).reshape(self.m,4)
        return max(float(np.max(abs(raw[:,:3]))),float(np.max(abs(raw[:,3]/self.l)))*.01)

    def solve(self,T,initial=None,*,gravity=9.81,maxiter=450):
        z=np.zeros(self.ndof) if initial is None else np.array(initial,copy=True)
        bounds=[(-1.5*s,1.5*s) for s in self.scale]
        for j in range(3,self.ndof,4):bounds[j]=(-.85*self.scale[j],.85*self.scale[j])
        def f(zz):
            try:return self.evaluate(zz,T,gravity)
            except ValueError:return 1e30,np.zeros(self.ndof)
        opt=minimize(f,z,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':maxiter,'gtol':2e-9,'ftol':1e-14,'maxls':35,'maxcor':30})
        try:_,gradient=self.evaluate(opt.x,T,gravity)
        except ValueError:return None
        res=self.residual(gradient)
        if res<2e-6:return opt.x,dict(residual=res,iterations=opt.nit)
        return None

    def lift_planar(self,x):
        q=np.zeros((self.m,4));q[:,1]=np.diff(np.r_[0,x[::2]]);q[:,3]=x[1::2]
        return q.ravel()*self.scale

    def stationary_refine(self,T,initial):
        """Refine the same force equilibrium, including dead-force saddles.

        A fixed-length cable can stabilise a dead-force saddle; therefore a
        failed energy minimisation is not used to reject its equilibrium.
        Admissibility still requires the separate fixed-length Hessian check.
        """
        try:
            opt=root(lambda z:self.evaluate(z,T)[1],initial,method='krylov',options={'fatol':1e-10,'maxiter':60})
            res=self.residual(self.evaluate(opt.x,T)[1])
            q=(opt.x/self.scale).reshape(self.m,4)
            if res<2e-6 and np.max(abs(q[:,3]))<.85:return opt.x,dict(residual=res)
        except (ValueError,RuntimeError,np.linalg.LinAlgError):pass
        return None

    def solve_locked(self,rest,initial,maxiter=1200):
        """Refine with the same physical winch lengths and nonnegative forces."""
        rest=np.asarray(rest)
        def fun(z):
            try:
                E,g,d=self.evaluate(z,np.zeros(4),detail=True)
                extension=np.maximum(d['rope_lengths']-rest,0.)
                T=self.planar.rope_ea/rest*extension
                return E+.5*np.sum(T*extension),g+T@d['rope_jac']
            except ValueError:return 1e30,np.zeros(self.ndof)
        bounds=[(-1.5*s,1.5*s) for s in self.scale]
        for j in range(3,self.ndof,4):bounds[j]=(-.85*self.scale[j],.85*self.scale[j])
        opt=minimize(fun,initial,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':maxiter,'gtol':1e-9,'ftol':1e-15,'maxcor':40,'maxls':40})
        E,g=fun(opt.x);res=self.residual(g)
        if res>=2e-6:
            try:
                def equation(zz):
                    ee,gg=fun(zz)
                    if ee>1e25:raise ValueError('invalid tendon path during refinement')
                    return gg
                refined=root(equation,opt.x,method='krylov',options={'fatol':1e-10,'maxiter':60})
                _,gg=fun(refined.x);rr=self.residual(gg)
                if rr<res:opt.x=refined.x;res=rr
            except (ValueError,RuntimeError,np.linalg.LinAlgError):pass
        if res<2e-6:
            try:d=self.evaluate(opt.x,detail=True)[2]
            except ValueError:return None
            if np.max(abs(d['q'][:,3]))>=.85 or np.max(abs(d['q'][:,:3]))>1.5:return None
            T=self.planar.rope_ea/rest*np.maximum(d['rope_lengths']-rest,0.)
            if self.residual(self.evaluate(opt.x,T)[1])>=2e-6:return None
            return opt.x,T,dict(residual=res)
        return None

    def metrics(self,z,T,*,stability=False):
        E,g,d=self.evaluate(z,T,detail=True);p=self.planar;q=d['q'];xy=d['points'];frames=d['frames']
        # True end-to-start frame rotation and signed projected turning are
        # separately reported, avoiding an acos cap at 180 degrees.
        relative=np.einsum('ij,njk->nik',frames[self.b].T,frames[self.b:])
        tangent=relative[:,:,0]
        up=float(np.degrees(np.unwrap(np.arctan2(tangent[:,1],tangent[:,0]))[-1]))
        side=float(np.degrees(np.unwrap(np.arctan2(tangent[:,2],tangent[:,0]))[-1]))
        turn=float(np.degrees(np.sum(np.linalg.norm(q[self.b:,1:3],axis=1))))
        core_curv=np.linalg.norm(q[:self.b,1:3],axis=1)/self.l
        normal=p.steel['young_modulus_pa']*(abs(q[:self.b,3])+.0021*core_curv)
        shear=self.core_g*.0021*abs(q[:self.b,0])/self.l
        cellstress=np.sqrt(normal*normal+3*shear*shear)
        after=np.r_[np.cumsum(self.mass[::-1])[::-1],0.]+self.payload_kg
        center=d['centroids'];force_g=9.81*after[:,None]*np.array([0,1,0])
        gravarm=np.cross(center,self.mass[:,None]*np.array([0,-9.81,0]))
        moment_origin=np.r_[np.cumsum(gravarm[::-1],axis=0)[::-1],np.zeros((1,3))]
        moment_origin+=np.cross(xy[-1],np.array([0,-9.81*self.payload_kg,0]))
        recovered=[]
        for j in range(p.rear+1):
            i=j*self.sub;frame=frames[i]
            for segment,module in ([(j,j)] if j==0 else [(j-1,j-1)]+([(j,j)] if j<p.rear else [])):
                units=d['units'][segment]
                force=force_g[i]+(np.asarray(T)[:,None]*units).sum(axis=0)
                axial=-force@frame[:,0]
                gravity_moment=moment_origin[i]-np.cross(xy[i],-force_g[i])
                offset=np.einsum('ij,rj->ri',frame,self.offsets)
                moment=gravity_moment-(np.asarray(T)[:,None]*np.cross(offset,units)).sum(axis=0)
                # Bending moment components in local frame, share with module.
                local=frame.T@moment;idx=module*self.sub
                bending=np.hypot(local[1]*p.core_ei/self.sidepos[idx],local[2]*p.core_ei/self.vertical[idx])
                nc=axial*p.core_ea/self.EA[idx]
                twist=abs(local[0])*(self.core_g*2*p.I)/self.twist[idx]
                sigma=abs(nc)/p.area+bending*.0021/p.I;tau=twist*.0021/(2*p.I)
                recovered.append(np.hypot(sigma,np.sqrt(3)*tau))
        stress=float(max(max(recovered),max(cellstress))/1e6)
        # Exact closest distance: four constrained edges plus an admissible
        # unconstrained interior point of the segment/segment quadratic.
        a,b=xy[:-1],xy[1:];arclength=np.r_[0,np.cumsum(self.l*(1+q[:,3]))]
        ii,jj=np.triu_indices(len(a),2)
        keep=abs((arclength[ii]+arclength[ii+1]-arclength[jj]-arclength[jj+1])/2)>.064
        ii,jj=ii[keep],jj[keep]
        minimum=np.inf
        if len(ii):
            aa,bb,cc,dd=a[ii],b[ii],a[jj],b[jj]
            def endpoint_distance(point,start,end):
                v=end-start;t=np.clip(np.sum((point-start)*v,axis=1)/np.sum(v*v,axis=1),0,1)
                return np.linalg.norm(point-start-t[:,None]*v,axis=1)
            distance=np.minimum.reduce([endpoint_distance(aa,cc,dd),endpoint_distance(bb,cc,dd),endpoint_distance(cc,aa,bb),endpoint_distance(dd,aa,bb)])
            u=bb-aa;v=dd-cc;w=aa-cc
            A=np.sum(u*u,axis=1);B=np.sum(u*v,axis=1);C=np.sum(v*v,axis=1);D=np.sum(u*w,axis=1);F=np.sum(v*w,axis=1);den=A*C-B*B
            s=(B*F-C*D)/np.maximum(den,1e-30);t=(A*F-B*D)/np.maximum(den,1e-30)
            interior=(den>1e-20)&(s>=0)&(s<=1)&(t>=0)&(t<=1)
            distance[interior]=np.minimum(distance[interior],np.linalg.norm((w+s[:,None]*u-t[:,None]*v)[interior],axis=1))
            minimum=float(distance.min())
        overlap=minimum<.032
        local=bool(np.max(np.linalg.norm(q[:,1:3],axis=1)/(self.l*(1+q[:,3])))*.016>=1)
        span=np.ptp(xy,axis=0)*1000+32
        eigen=None
        if stability:
            h=np.empty((self.ndof,self.ndof));step=2e-5
            for j in range(self.ndof):
                dz=np.zeros(self.ndof);dz[j]=step
                h[:,j]=(self.evaluate(z+dz,T)[1]-self.evaluate(z-dz,T)[1])/(2*step)
            rest=d['rope_lengths']/(1+np.asarray(T)/p.rope_ea);active=np.asarray(T)>1e-7
            J=d['rope_jac'][active];h+=J.T@((p.rope_ea/rest[active])[:,None]*J)
            eigen=float(eigvalsh((h+h.T)/2,subset_by_index=[0,0])[0])
        return dict(tensions_n=list(map(float,T)),total_tension_n=float(np.sum(T)),front_up_projected_deg=up,front_side_projected_deg=side,
          front_total_bend_deg=turn,head_x_mm=float(xy[-1,0]*1000),head_y_mm=float(xy[-1,1]*1000),head_z_mm=float(xy[-1,2]*1000),
          max_core_stress_mpa=stress,passes_reference_yield=stress<=205,passes_self_envelope_screen=not(overlap or local),
          minimum_nonlocal_clearance_mm=None if not np.isfinite(minimum) else minimum*1000,local_capsule_curvature_exceeded=local,
          horizontal_span_mm=float(span[0]),vertical_span_mm=float(span[1]),lateral_span_mm=float(span[2]),
          passes_empty_box=bool(span[0]<=1600 and span[1]<=300 and span[2]<=830),
          max_axial_compression=float(max(0,-q[:,3].min())),max_axial_extension=float(max(0,q[:,3].max())),
          equilibrium_residual=self.residual(g),minimum_fixed_length_eigenvalue=eigen,
          stable_spatial=None if eigen is None else eigen>=-1e-7,rope_lengths_mm=(d['rope_lengths']*1000).tolist()),d
