"""500 g head load extension; the inherited backbone remains rear only."""
import numpy as np
from rope_planar import PlanarRod

class PayloadPlanarRod(PlanarRod):
    def __init__(self,counts,sub=8,*,payload_kg=.5,antagonistic_common=0.,**kw):
        super().__init__(counts,sub,**kw)
        self.payload_kg=float(payload_kg)
        self.antagonistic_common=float(antagonistic_common)
        # The original exact-consistent gravity kernel uses distal nodal mass
        # in weight_after; adding a point mass here adds mg*y_head and all its
        # exact first/second derivatives, without smearing it into body mass.
        self.weight_after+=self.payload_kg

    def tensions(self,D,common=0):
        A=self.antagonistic_common
        return np.array([max(D,0)+A/2,common/2,max(-D,0)+A/2,common/2])

    def shape_metrics(self,x,D0,common=0):
        metrics,data,H=super().shape_metrics(x,D0,common)
        # Recover the loaded core stresses at real disk cuts. The inherited
        # cell stress already includes the load through the solved state.
        th=data['theta'];xy=data['points'];T=self.tensions(D0,common)
        disk=xy[::self.sub];angle=th[::self.sub]
        normal=np.c_[-np.sin(angle),np.cos(angle)]
        tangent=np.c_[np.cos(angle),np.sin(angle)]
        a,b=th[:-1],th[1:];tq=a[:,None]*self.aa+b[:,None]*self.bb
        centroids=xy[:-1]+(1+data['eps'])[:,None]*self.l*np.c_[
          np.sum(self.w*(1-self.u)*np.cos(tq),axis=1),np.sum(self.w*(1-self.u)*np.sin(tq),axis=1)]
        after=np.r_[np.cumsum(self.mass[::-1])[::-1],0.]+self.payload_kg
        mx=np.r_[np.cumsum((self.mass*centroids[:,0])[::-1])[::-1],0.]+self.payload_kg*xy[-1,0]
        moment_g=9.81*(mx-xy[:,0]*after)
        units=[]
        for radius in [self.r,0.,-self.r,0.]:
            vec=np.diff(disk+radius*normal,axis=0);units.append(vec/np.linalg.norm(vec,axis=1)[:,None])
        units=np.array(units);stress=[]
        for j in range(self.rear+1):
            for seg,mod in ([(j,j)] if j==0 else [(j-1,j-1)]+([(j,j)] if j<self.rear else [])):
                force=(T[:,None]*units[:,seg]).sum(axis=0)+np.array([0.,9.81*after[j*self.sub]])
                axial=-force@tangent[j]
                offset=np.array([self.r,0.,-self.r,0.])[:,None]*normal[j]
                moment=-moment_g[j*self.sub]-np.sum(T*(offset[:,0]*units[:,seg,1]-offset[:,1]*units[:,seg,0]))
                nc=axial*self.core_ea/(self.core_ea+self.module_EA[mod])
                mc=moment*self.core_ei/(self.core_ei+self.module_EI[mod])
                stress.append(abs(nc)/self.area+abs(mc)*.0021/self.I)
        eps=data['eps'][:self.b];curv=np.diff(th)[:self.b]/self.l
        cell=np.max(self.steel['young_modulus_pa']*(abs(eps)+.0021*abs(curv)))
        metrics['max_core_stress_mpa']=float(max(cell,max(stress))/1e6)
        metrics['core_reference_yield_ratio']=metrics['max_core_stress_mpa']/205
        metrics['passes_reference_yield']=metrics['max_core_stress_mpa']<=205
        metrics['payload_kg']=self.payload_kg
        return metrics,data,H
