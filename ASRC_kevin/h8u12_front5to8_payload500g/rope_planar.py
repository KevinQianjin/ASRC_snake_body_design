"""Planar extensible rod with four actual-disk tendon routes.

Unknowns are absolute nodal pitch and constant axial strain in each FE cell.
Rotation is interpolated linearly; the centreline is integrated by Gauss
quadrature. Disk guides exist only at real 48 mm module boundaries, independent
of refinement. Four frictionless, head-anchored tendons follow straight chords
between disk guides. The two side tendons have identical planar paths.

All energies use reference material coordinates. EI/EA and module masses are
unscaled original paper values. Rear core is linear elastic, rear only.
The four rope reference masses are distributed uniformly along the rod;
their symmetric offset gravity moments cancel in this planar approximation.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import sys,json
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.linalg import solveh_banded, solve_banded, eigvalsh

HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE/'inputs'))
import craft_data as D


class PlanarRod:
    def __init__(self,counts,sub=4,*,rope_mass=True,extensible=True):
        self.counts=tuple(map(int,counts));self.sub=int(sub)
        self.n=sum(self.counts);self.m=self.n*self.sub;self.ndof=2*self.m
        self.rear=sum(self.counts[:2]);self.b=self.rear*self.sub
        kinds=np.repeat(np.arange(4),self.counts)
        names=['high','unidirectional','directional','low']
        ei=np.array([D.MODULES[n]['EI_y' if i in [1,2] else 'EI_x'] for i,n in enumerate(names)])
        ea=np.array([D.MODULES[n]['EA'] for n in names])
        masses=np.array([(D.MODULES[n]['pc_g']+D.MODULES[n]['pla_g'])/1000 for n in names])
        catalog=json.loads((HERE/'inputs/rope_materials.json').read_text())
        self.steel=next(x for x in catalog['materials'] if x['id']=='ss304_annealed')
        self.rope=next(x for x in catalog['materials'] if x['id']=='nylon_pa6_reference')
        self.area=np.pi*.0042**2/4;self.I=np.pi*.0042**4/64
        self.core_ei=self.steel['young_modulus_pa']*self.I
        self.core_ea=self.steel['young_modulus_pa']*self.area
        self.r=.013;self.diameter=.032
        self.rope_ea=self.rope['young_modulus_pa']*np.pi*.002**2/4
        self.rope_density=self.rope['density_kg_m3']*np.pi*.002**2/4
        core=np.arange(self.n)<self.rear
        self.EI=np.repeat(ei[kinds]+core*self.core_ei,sub)
        self.EA=np.repeat(ea[kinds]+core*self.core_ea,sub)
        self.module_EI=ei[kinds]
        self.module_EA=ea[kinds]
        if not extensible:self.EA=np.full_like(self.EA,1e14)
        mass=masses[kinds]+core*self.steel['density_kg_m3']*self.area*.048
        if rope_mass:mass=mass+4*self.rope_density*.048
        self.mass=np.repeat(mass/sub,sub)
        self.l=.048/sub
        self.weight_after=np.cumsum(self.mass[::-1])[::-1]-self.mass
        z,w=leggauss(4);self.u=(z+1)/2;self.w=w/2
        self.aa=1-self.u;self.bb=self.u
        self.p=1+2*sub
        starts=np.arange(self.n)*sub
        self.indices=np.c_[2*starts-2,2*starts[:,None]+np.arange(2*sub)]
        self.valid=self.indices>=0
        self.ia=np.array([0 if k==0 else 2*k-1 for k in range(sub)])
        self.ib=1+2*np.arange(sub);self.ie=2+2*np.arange(sub)
        ii=np.broadcast_to(self.indices[:,:,None],(self.n,self.p,self.p))
        jj=np.broadcast_to(self.indices[:,None,:],(self.n,self.p,self.p))
        mask=(ii>=0)&(jj>=0)&(ii>=jj)
        self.hmask=mask;self.hrow=(ii-jj)[mask];self.hcol=jj[mask]
        self.bandwidth=2*sub+1
        self.gidx=self.indices[self.valid]
        self._side=np.array([0,0,0,0])

    @property
    def label(self):return '-'.join(f'{a}{b}' for a,b in zip('HUDL',self.counts))

    def assemble_g(self,g):
        a=np.zeros(self.ndof);np.add.at(a,self.gidx,g[self.valid]);return a

    def assemble_h(self,h):
        a=np.zeros((self.bandwidth+1,self.ndof));np.add.at(a,(self.hrow,self.hcol),h[self.hmask]);return a

    def evaluate(self,x,tensions=(0,0,0,0),gravity=9.81,*,detail=False):
        x=np.asarray(x);eps=x[1::2];lam=1+eps
        theta=np.r_[0.,x[::2]];a,b=theta[:-1],theta[1:]
        q=b-a;th=a[:,None]*self.aa+b[:,None]*self.bb
        tang=np.stack((np.cos(th),np.sin(th)),axis=-1)
        norm=np.stack((-np.sin(th),np.cos(th)),axis=-1)
        def integ(v,weights=None):
            ww=self.w if weights is None else self.w*weights
            return np.einsum('cqi,q->ci',v,ww)
        v=self.l*lam[:,None]*integ(tang)
        ja=self.l*lam[:,None]*integ(norm,self.aa)
        jb=self.l*lam[:,None]*integ(norm,self.bb)
        je=self.l*integ(tang)
        haa=-self.l*lam[:,None]*integ(tang,self.aa**2)
        hab=-self.l*lam[:,None]*integ(tang,self.aa*self.bb)
        hbb=-self.l*lam[:,None]*integ(tang,self.bb**2)
        hae=self.l*integ(norm,self.aa);hbe=self.l*integ(norm,self.bb)
        J=np.zeros((self.n,2,self.p));Hv=np.zeros((self.n,2,self.p,self.p))
        vr=v.reshape(self.n,self.sub,2).sum(axis=1)
        for k in range(self.sub):
            A,B,E=self.ia[k],self.ib[k],self.ie[k]
            for col,arr in [(A,ja),(B,jb),(E,je)]:J[:,:,col]+=arr[k::self.sub]
            for i,j,arr in [(A,A,haa),(A,B,hab),(B,A,hab),(B,B,hbb),
                            (A,E,hae),(E,A,hae),(B,E,hbe),(E,B,hbe)]:
                Hv[:,:,i,j]+=arr[k::self.sub]
        gmod=np.zeros((self.n,self.p));hmod=np.zeros((self.n,self.p,self.p))
        K=self.EI/self.l;A=self.EA*self.l
        energy=.5*np.sum(K*q*q+A*eps*eps)
        coef=gravity*self.l*self.w*(self.weight_after[:,None]+self.mass[:,None]*(1-self.u))
        grav_s=np.sum(coef*np.sin(th),axis=1)
        energy+=np.sum(lam*grav_s)
        ga=lam*np.sum(coef*np.cos(th)*self.aa,axis=1)
        gb=lam*np.sum(coef*np.cos(th)*self.bb,axis=1)
        gaa=-lam*np.sum(coef*np.sin(th)*self.aa**2,axis=1)
        gab=-lam*np.sum(coef*np.sin(th)*self.aa*self.bb,axis=1)
        gbb=-lam*np.sum(coef*np.sin(th)*self.bb**2,axis=1)
        gae=np.sum(coef*np.cos(th)*self.aa,axis=1)
        gbe=np.sum(coef*np.cos(th)*self.bb,axis=1)
        for k in range(self.sub):
            ids=slice(k,None,self.sub);aa,bb,ee=self.ia[k],self.ib[k],self.ie[k]
            gmod[:,aa]+=-K[ids]*q[ids]+ga[ids]
            gmod[:,bb]+= K[ids]*q[ids]+gb[ids]
            gmod[:,ee]+= A[ids]*eps[ids]+grav_s[ids]
            hmod[:,aa,aa]+=K[ids]+gaa[ids];hmod[:,bb,bb]+=K[ids]+gbb[ids]
            hmod[:,aa,bb]+=-K[ids]+gab[ids];hmod[:,bb,aa]+=-K[ids]+gab[ids]
            hmod[:,ee,ee]+=A[ids]
            for i,j,arr in [(aa,ee,gae),(ee,aa,gae),(bb,ee,gbe),(ee,bb,gbe)]:hmod[:,i,j]+=arr[ids]
        tensions=np.asarray(tensions,dtype=float)
        rope_lengths=np.zeros(4);G=np.zeros((4,self.ndof))
        t0=np.stack((np.cos(theta[::self.sub][:-1]),np.sin(theta[::self.sub][:-1])),axis=-1)
        t1=np.stack((np.cos(theta[::self.sub][1:]),np.sin(theta[::self.sub][1:])),axis=-1)
        n0=np.stack((-t0[:,1],t0[:,0]),axis=-1);n1=np.stack((-t1[:,1],t1[:,0]),axis=-1)
        end_angle=self.ib[-1]
        for rope,offset in enumerate([self.r,0.,-self.r,0.]):
            d=vr+offset*(n1-n0)
            ll=np.linalg.norm(d,axis=1)
            if np.any(ll<1e-9):raise ValueError('collapsed tendon chord')
            unit=d/ll[:,None];jj=J.copy();hh=Hv.copy()
            jj[:,:,0]+=offset*t0;jj[:,:,end_angle]-=offset*t1
            hh[:,:,0,0]+=offset*n0;hh[:,:,end_angle,end_angle]-=offset*n1
            grad=np.einsum('ni,nip->np',unit,jj)
            hess=(np.einsum('nip,niq->npq',jj,jj)-np.einsum('np,nq->npq',grad,grad))/ll[:,None,None]
            hess+=np.einsum('ni,nipq->npq',unit,hh)
            rope_lengths[rope]=ll.sum();G[rope]=self.assemble_g(grad)
            energy+=tensions[rope]*ll.sum();gmod+=tensions[rope]*grad;hmod+=tensions[rope]*hess
        grad=self.assemble_g(gmod);H=self.assemble_h(hmod)
        if not detail:return energy,grad,H
        points=np.vstack((np.zeros(2),np.cumsum(v,axis=0)))
        head_jac=np.stack((self.assemble_g(J[:,0]),self.assemble_g(J[:,1])))
        return energy,grad,H,dict(theta=theta,eps=eps,points=points,rope_lengths=rope_lengths,
              rope_jac=G,head_jac=head_jac,guide_points=points[::self.sub],cell_displacements=v)

    def solve_h(self,H,rhs):
        try:return solveh_banded(H,rhs,lower=True,check_finite=False)
        except np.linalg.LinAlgError:
            w=self.bandwidth;n=self.ndof
            ab=np.zeros((2*w+1,n));ab[w]=H[0]
            for k in range(1,w+1):
                ab[w+k,:n-k]=H[k,:n-k]
                ab[w-k,k:]=H[k,:n-k]
            return solve_banded((w,w),ab,rhs,check_finite=False)

    def residual(self,g):
        return max(float(np.max(np.abs(g[::2]))),float(np.max(np.abs(g[1::2]/self.l)))*.01)

    def target(self,data,kind,sense=1,goal=None):
        if kind=='level':return data['points'][-1,1]-(0. if goal is None else goal),data['head_jac'][1]
        jac=np.zeros(self.ndof);jac[2*self.m-2]=1;jac[2*self.b-2]=-1
        return data['theta'][-1]-data['theta'][self.b]-(sense*np.pi if goal is None else goal),jac

    @staticmethod
    def tensions(D,common=0):return np.array([max(D,0),common/2,max(-D,0),common/2])

    def inverse(self,kind,sense=1,common=0,*,initial=None,gravity=9.81,maxiter=40,goal=None):
        if initial is None:x=np.zeros(self.ndof);D0=0.
        else:x=np.array(initial[0],copy=True);D0=float(initial[1])
        def merit(g,h):return self.residual(g)+abs(h)*(10 if kind=='level' else .1)
        for iteration in range(maxiter):
            T=self.tensions(D0,common)
            try:E,g,H,data=self.evaluate(x,T,gravity,detail=True)
            except ValueError:return None
            h,A=self.target(data,kind,sense,goal)
            if self.residual(g)<2e-8 and abs(h)<(2e-7 if kind=='level' else 2e-6):
                return x,D0,dict(iterations=iteration,residual=self.residual(g),target_error=h)
            sign=1 if D0>=0 else -1
            B=data['rope_jac'][0] if sign==1 else -data['rope_jac'][2]
            try:
                uv=self.solve_h(H,np.c_[g,B]);u,v=uv.T
                av=A@v
                if abs(av)<1e-13:return None
                dD=(h-A@u)/av;dx=-u-v*dD
            except (np.linalg.LinAlgError,ValueError):return None
            old=merit(g,h);accepted=False
            alpha=1.
            for _ in range(22):
                xx=x+alpha*dx;dd=D0+alpha*dD
                if np.max(np.abs(xx[1::2]))>.85 or abs(dd)>300:
                    alpha*=.5;continue
                try:
                    _,gg,_,dt=self.evaluate(xx,self.tensions(dd,common),gravity,detail=True)
                    hh,_=self.target(dt,kind,sense,goal)
                except ValueError:alpha*=.5;continue
                if merit(gg,hh)<old*(1-1e-4*alpha) or merit(gg,hh)<2e-8:
                    x,D0=xx,dd;accepted=True;break
                alpha*=.5
            if not accepted:return None
        return None

    def load_inverse(self,kind,sense=1,common=0,*,initial=None):
        if initial is not None:
            got=self.inverse(kind,sense,common,initial=initial)
            if got is not None:return got
        if kind=='level':
            result=(np.zeros(self.ndof),0.,{})
            for gravity in np.linspace(9.81/8,9.81,8):
                got=self.inverse(kind,sense,common,initial=result,gravity=gravity)
                if got is None:return None
                result=got
            return result
        # A circular seed is only an initial guess; no shape is enforced in equilibrium.
        th=np.zeros(self.m+1)
        rear_flex=self.rear*.048/self.core_ei
        mod_ei=self.EI[self.b:]
        compliance=np.sum(self.l/mod_ei)
        moment=sense*np.pi/compliance
        th[:self.b+1]=np.linspace(0,moment*rear_flex,self.b+1)
        th[self.b+1:]=th[self.b]+np.cumsum(moment*self.l/mod_ei)
        x=np.zeros(self.ndof);x[::2]=th[1:]
        result=(x,moment/self.r,{})
        got=self.inverse(kind,sense,common,initial=result,gravity=0.)
        if got is None:return None
        for gravity in np.linspace(9.81/8,9.81,8):
            got=self.inverse(kind,sense,common,initial=got,gravity=gravity)
            if got is None:return None
        return got

    def free_equilibrium(self,gravity=9.81,initial=None):
        x=np.zeros(self.ndof) if initial is None else np.array(initial,copy=True)
        for load in np.linspace(gravity/8,gravity,8):
            for _ in range(60):
                E,g,H=self.evaluate(x,gravity=load)
                if self.residual(g)<1e-9:break
                try:step=-self.solve_h(H,g)
                except (ValueError,np.linalg.LinAlgError):return None
                alpha=1.
                for _ in range(25):
                    trial=x+alpha*step
                    en,_,_=self.evaluate(trial,gravity=load)
                    if en <= E+1e-4*alpha*(g@step)+1e-14:break
                    alpha*=.5
                x=trial
        return x if self.residual(self.evaluate(x,gravity=gravity)[1])<1e-8 else None

    def lift_from_sag(self,common=0):
        if common:
            return self.load_inverse('level',common=common)
        x=self.free_equilibrium()
        if x is None:return None
        h0=self.evaluate(x,detail=True)[3]['points'][-1,1]
        got=(x,0.,{})
        for goal in np.linspace(h0,0.,17)[1:]:
            trial=self.inverse('level',common=common,initial=got,goal=goal,maxiter=50)
            if trial is None:return None
            got=trial
        return got

    def shape_metrics(self,x,D0,common=0):
        T=self.tensions(D0,common)
        E,g,H,data=self.evaluate(x,T,detail=True)
        xy=data['points'];th=data['theta'];eps=data['eps'];current=self.l*(1+eps)
        front_length=float(current[self.b:].sum());sense=1 if th[-1]-th[self.b]>=0 else -1
        phase=np.r_[0,np.cumsum(current[self.b:])]/front_length*np.pi
        local=(xy[self.b:]-xy[self.b])@np.array([[np.cos(th[self.b]),-np.sin(th[self.b])],
                                                               [np.sin(th[self.b]),np.cos(th[self.b])]])
        arc=front_length/np.pi*np.c_[np.sin(phase),sense*(1-np.cos(phase))]
        dev=np.linalg.norm(local-arc,axis=1)*1000
        curvature=np.diff(th)/self.l
        axialstress=self.steel['young_modulus_pa']*eps[:self.b]
        bendstress=self.steel['young_modulus_pa']*.0042/2*curvature[:self.b]
        cell_stress=float(np.max(np.abs(axialstress)+np.abs(bendstress)))/1e6
        # Recover end-section actions from distal weight + tendon-cut balance.
        # This avoids underestimating root stress by using first-cell average curvature.
        a,b=th[:-1],th[1:]
        tq=a[:,None]*self.aa+b[:,None]*self.bb
        centroids=xy[:-1]+(1+eps)[:,None]*self.l*np.c_[
            np.sum(self.w*(1-self.u)*np.cos(tq),axis=1),np.sum(self.w*(1-self.u)*np.sin(tq),axis=1)]
        mass_after=np.r_[np.cumsum(self.mass[::-1])[::-1],0.]
        mx_after=np.r_[np.cumsum((self.mass*centroids[:,0])[::-1])[::-1],0.]
        gravity_moment=9.81*(mx_after-xy[:,0]*mass_after)
        disks=xy[::self.sub];angle=th[::self.sub]
        normals=np.c_[-np.sin(angle),np.cos(angle)]
        tangents=np.c_[np.cos(angle),np.sin(angle)]
        lengths=[];unit=[]
        for r in [self.r,0.,-self.r,0.]:
            vv=np.diff(disks+r*normals,axis=0)
            ll=np.linalg.norm(vv,axis=1);lengths.append(ll);unit.append(vv/ll[:,None])
        unit=np.asarray(unit)
        recovered=[]
        for j in range(self.rear+1):
            sides=[]
            if j<self.rear:sides.append((j,j))
            if j>0:sides.append((j-1,j-1))
            for segment,module in sides:
                force=np.sum(T[:,None]*unit[:,segment],axis=0)+np.array([0.,9.81*mass_after[j*self.sub]])
                axial=-float(force@tangents[j])
                offsets=np.array([self.r,0.,-self.r,0.])[:,None]*normals[j]
                moment=-gravity_moment[j*self.sub]-float(np.sum(T*(offsets[:,0]*unit[:,segment,1]-offsets[:,1]*unit[:,segment,0])))
                nc=axial*self.core_ea/(self.core_ea+self.module_EA[module])
                mc=moment*self.core_ei/(self.core_ei+self.module_EI[module])
                recovered.append(abs(nc)/self.area+abs(mc)*.0021/self.I)
        stress=max(cell_stress,max(recovered)/1e6)
        length=data['rope_lengths']
        rest=length/(1+T/self.rope_ea)
        # Zero-force ropes receive 1 mm slack; their command is nonunique.
        commanded_rest=rest+np.where(T>1e-7,0.,.001)
        takeup=(self.n*.048-commanded_rest)*1000
        span=(xy.max(axis=0)-xy.min(axis=0))*1000+32
        return dict(tensions_n=T.tolist(),total_tension_n=float(T.sum()),D_n=D0,common_n=common,
             head_x_mm=float(xy[-1,0]*1000),head_y_mm=float(xy[-1,1]*1000),head_z_mm=0.,
             front_angle_deg=float(np.degrees(th[-1]-th[self.b])),rear_angle_deg=float(np.degrees(th[self.b])),
             front_current_length_mm=front_length*1000,semicircle_max_error_mm=float(dev.max()),semicircle_rms_error_mm=float(np.sqrt(np.mean(dev**2))),
             max_module_axial_compression=float(max(0,-eps.min())),max_module_axial_extension=float(max(0,eps.max())),
             max_core_stress_mpa=stress,core_reference_yield_ratio=stress/205,
             horizontal_span_mm=float(span[0]),vertical_span_mm=float(span[1]),
             passes_empty_box=bool(span[0]<=1600 and span[1]<=300),passes_reference_yield=stress<=205,
             rope_path_lengths_mm=(length*1000).tolist(),rope_strains=(T/self.rope_ea).tolist(),
             take_up_mm=takeup.tolist(),slack_ropes=[bool(t<=1e-7) for t in T],
             axial_strain_exceeds_5_percent=bool(np.max(np.abs(eps))>.05),
             equilibrium_residual=self.residual(g)),data,H

    def stability(self,H,data,T):
        n=self.ndof;mat=np.diag(H[0])
        for k in range(1,self.bandwidth+1):
            a=np.arange(n-k);mat[a+k,a]=H[k,:n-k];mat[a,a+k]=H[k,:n-k]
        rest=data['rope_lengths']/(1+T/self.rope_ea)
        active=np.asarray(T)>1e-7
        G=data['rope_jac'][active]
        if len(G):mat+=G.T@((self.rope_ea/rest[active])[:,None]*G)
        scale=1/np.sqrt(np.maximum(np.abs(np.diag(mat)),1e-10))
        ev=eigvalsh(mat*scale[:,None]*scale[None,:],subset_by_index=[0,0],check_finite=False)[0]
        return float(ev)
