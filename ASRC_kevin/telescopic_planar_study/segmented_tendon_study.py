"""Planar, head-load compensation using multiple tendon anchor stations.

Every tendon starts at the front base and follows the actual module disks up to
its anchor. Thus distal tendons also compress proximal modules. No imaginary
decoupling sheath or lateral support is added. Only top tendons are optimized.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json,sys,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import minimize,LinearConstraint
from front_solver import FrontRod,patched_source,KERNEL_PATH,HERE,write_csv
from refine_front import geometry_screen,finer_seed

def replace_once(text,old,new):
 if text.count(old)!=1:raise RuntimeError('Read-only kernel patch mismatch')
 return text.replace(old,new)

s=replace_once(patched_source,'tensions=np.asarray(tensions,dtype=float)',
 '''tensions=np.asarray(tensions,dtype=float)
        controls=tensions.reshape(len(self.anchors),4)
        tensions=controls.T@self.routes''')
s=replace_once(s,'rope_lengths=np.zeros(4);G=np.zeros((4,self.ndof))',
 '''rope_lengths=np.zeros(4);G=np.zeros((4,self.ndof))
        anchor_lengths=np.zeros((len(self.anchors),4))
        anchor_jac=np.zeros((len(self.anchors),4,self.ndof))''')
s=replace_once(s,'energy+=tensions[rope]*ll.sum();gmod+=tensions[rope]*grad;hmod+=tensions[rope]*hess',
 '''energy+=float(tensions[rope]@ll);gmod+=tensions[rope,:,None]*grad;hmod+=tensions[rope,:,None,None]*hess
            anchor_lengths[:,rope]=self.routes@ll
            for anchor_index,route in enumerate(self.routes):
                anchor_jac[anchor_index,rope]=self.assemble_g(grad*route[:,None])''')
s=replace_once(s,"rope_jac=G,head_jac=head_jac,guide_points=points[::self.sub],cell_displacements=v)",
 "rope_jac=G,head_jac=head_jac,guide_points=points[::self.sub],cell_displacements=v,anchor_lengths=anchor_lengths,anchor_jac=anchor_jac)")
ns={'__file__':str(KERNEL_PATH),'__name__':'_segmented_readonly_kernel'}
exec(compile(s,str(KERNEL_PATH),'exec'),ns)

class SegmentedRod(FrontRod):
 evaluate=ns['PlanarRod'].evaluate
 def __init__(self,n_uni,anchors,pitch_deg=20,sub=4):
  self.anchors=tuple(anchors)
  super().__init__(n_uni,pitch_deg,sub,.5)
  self.routes=np.array([np.arange(10)<a for a in self.anchors],dtype=float)
  # Count four physical tendons per anchor set, routed from base to anchor.
  extra_mass=(self.routes.sum(axis=0)-1)*4*self.rope_density*.048
  self.mass+=np.repeat(extra_mass/sub,sub)
  self.weight_after=np.cumsum(self.mass[::-1])[::-1]-self.mass+self.payload_kg
 def control_matrix(self,D):
  T=np.zeros((len(self.anchors),4));T[:,0]=D;return T
 def solve(self,D,seed,gravity=9.81):
  return self.solve_force(self.control_matrix(D),seed,gravity,maxiter=180)
 def free(self):
  seed=self.straight_seed()
  for g in np.linspace(9.81/25,9.81,25):
   q=self.solve(np.zeros(len(self.anchors)),seed,g)
   if q is None:
    seed=self.straight_seed();seed[::2]=np.linspace(self.root_pitch,-np.pi/2,self.m)
    q=self.solve(np.zeros(len(self.anchors)),seed,g)
   if q is None:return None
   seed=q
  return seed
 def dense_h(self,H):
  A=np.diag(H[0]);n=self.ndof
  for k in range(1,self.bandwidth+1):
   i=np.arange(n-k);A[i+k,i]=H[k,:n-k];A[i,i+k]=H[k,:n-k]
  return A
 def ideal_controls(self):
  # Approximate module-midpoint gravity moments in an undeformed front.
  length=np.arange(10)*.048+.024
  mass=self.mass.reshape(10,self.sub).sum(axis=1)
  moment=np.array([9.81*np.cos(self.root_pitch)*(.5*(.480-x)+sum(mass[j]*max(0.,length[j]-x) for j in range(10))) for x in length])
  starts=np.r_[0,np.array(self.anchors[:-1])].astype(int)
  effective=np.array([moment[a:b].mean()/self.r for a,b in zip(starts,self.anchors)])
  return np.maximum(effective-np.r_[effective[1:],0],0)
 def optimize(self,seed,D0,max_strain=.3):
  n=self.ndof;k=len(self.anchors);calls={}
  def state(u):
   key=u.tobytes()
   if calls.get('key')!=key:
    E,g,H,d=self.evaluate(u[:n],self.control_matrix(u[n:]*100),detail=True)
    calls.update(key=key,g=g,H=H,data=d)
   return calls
  def obj(u):
   q=u[:n];a=q[::2]-self.root_pitch;e=q[1::2]
   return .5*np.mean(a*a)+.1*np.mean(e*e)+1e-7*np.sum(u[n:]**2)
  def jac(u):
   v=np.zeros_like(u);v[:n:2]=(u[:n:2]-self.root_pitch)/self.m
   v[1:n:2]=.2*u[1:n:2]/self.m;v[n:]=2e-7*u[n:];return v
  # Moment and strain energy scales are fixed, so the equality is unchanged.
  scale=np.ones(n);scale[1::2]=1/(self.EA*self.l)
  def con(u):return state(u)['g']*scale
  def cjac(u):
   st=state(u);G=st['data']['anchor_jac'][:,0,:].T*100
   return np.c_[self.dense_h(st['H']),G]*scale[:,None]
  u=np.r_[seed,np.asarray(D0)/100]
  bounds=[(self.root_pitch-np.pi,self.root_pitch+np.pi) if j%2==0 else (-max_strain,min(max_strain,.15)) for j in range(n)]+[(0,2.5)]*k
  B=np.zeros((self.m,n+k))
  for i in range(self.m):
   B[i,2*i]=1
   if i:B[i,2*i-2]=-1
  lo=np.full(self.m,-.55);hi=np.full(self.m,.55);lo[0]+=self.root_pitch;hi[0]+=self.root_pitch
  opt=minimize(obj,u,jac=jac,bounds=bounds,constraints=[{'type':'eq','fun':con,'jac':cjac},LinearConstraint(B,lo,hi)],method='SLSQP',options={'maxiter':180,'ftol':1e-11})
  x=opt.x[:n];D=opt.x[n:]*100
  return x,D,dict(optimizer_success=bool(opt.success),message=opt.message,iterations=int(opt.nit),objective=float(opt.fun))
 def metrics2(self,x,D):
  _,g,H,d=self.evaluate(x,self.control_matrix(D),detail=True)
  offset=.02*np.array([np.cos(self.root_pitch),np.sin(self.root_pitch)])
  p=np.vstack((np.zeros(2),d['points']+offset))
  t=np.array([np.cos(self.root_pitch),np.sin(self.root_pitch)]);normal=np.array([-t[1],t[0]])
  A=self.dense_h(H);G=d['anchor_jac'][:,0];T=np.asarray(D);active=T>1e-7
  rest=d['anchor_lengths'][:,0]/(1+T/self.rope_ea)+1.
  A+=G[active].T@((self.rope_ea/rest[active])[:,None]*G[active])
  scal=1/np.sqrt(np.maximum(abs(np.diag(A)),1e-10));eig=float(np.linalg.eigvalsh(A*scal[:,None]*scal[None,:])[0])
  deviation=float(np.max(abs(p@normal)))*1000;projection=float(p[-1]@t)*1000
  angle=float(np.max(abs(d['theta']-self.root_pitch)))*180/np.pi;strain=float(np.max(abs(d['eps'])))
  metric=dict(configuration=self.label,anchors=list(self.anchors),anchor_set_count=len(self.anchors),top_tensions_n=np.asarray(D).tolist(),
   effective_top_force_by_module_n=(np.asarray(D)@self.routes).tolist(),equilibrium_residual=self.residual(g),
   maximum_axis_deviation_mm=deviation,axial_projection_mm=projection,maximum_tangent_error_deg=angle,
   max_abs_axial_strain=strain,stable_with_1m_extra_free_rope=bool(eig>=-1e-7),minimum_scaled_eigenvalue=eig,
   provisional_straight_geometry=bool(deviation<=10 and projection>=475 and angle<=5),low_strain_diagnostic=bool(strain<=.05),
   added_ropes_included_in_mass=True,anchor_hardware_and_sheath_mass_not_included=True)
  metric.update(geometry_screen(p,d,self));return metric,p,d

def validate():
 r=SegmentedRod(8,[4,8,10],sub=2);rng=np.random.default_rng(42);x=r.straight_seed()+rng.normal(size=r.ndof)*.01;x[1::2]*=.02
 D=np.array([30.,20.,5.]);T=r.control_matrix(D);v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
 E,g,H,d=r.evaluate(x,T,detail=True)
 fd=(r.evaluate(x+h*v,T)[0]-r.evaluate(x-h*v,T)[0])/(2*h)
 hv=(r.evaluate(x+h*v,T)[1]-r.evaluate(x-h*v,T)[1])/(2*h)
 np.testing.assert_allclose(fd,g@v,atol=1e-7);np.testing.assert_allclose(hv,r.dense_h(H)@v,atol=2e-6)
 dd=np.array([.2,-.3,.4]);gg=(r.evaluate(x,r.control_matrix(D+h*dd))[1]-r.evaluate(x,r.control_matrix(D-h*dd))[1])/(2*h)
 np.testing.assert_allclose(gg,d['anchor_jac'][:,0].T@dd,atol=1e-7)
 one=SegmentedRod(8,[10],sub=2);old=FrontRod(8,20,sub=2)
 np.testing.assert_allclose(one.evaluate(x[:old.ndof],[ [8,0,0,0] ])[1],old.evaluate(x[:old.ndof],[8,0,0,0])[1],atol=1e-12)
 return dict(gradient_error=float(abs(fd-g@v)),hessian_vector_error=float(np.max(abs(hv-r.dense_h(H)@v))),
   control_gradient_checked=True,single_anchor_matches_original=True,actual_prefix_routing_and_extra_rope_mass=True)

def run():
 out=HERE/'results';checks=validate();rows=[];arr={};attempts=[]
 for u in [8,9]:
  for name,anchors in [('single',[10]),('two',[u,10]),('three',[4,u,10]),('per_module',list(range(1,11)))]:
   r=SegmentedRod(u,anchors);free=r.free()
   if free is None:raise RuntimeError('Free seed failed')
   seeds=[(free,np.zeros(len(anchors)),'sag')]
   ideal=r.ideal_controls();seed=r.straight_seed()
   for g in np.linspace(9.81/30,9.81,30):
    q=r.solve(ideal*g/9.81,seed,g)
    if q is None:break
    seed=q
   else:seeds.append((seed,ideal,'gravity_compensation'))
   candidates=[]
   for x,D,label in seeds:
    xx,DD,info=r.optimize(x,D);m,_,_=r.metrics2(xx,DD)
    attempts.append(dict(configuration=r.label,architecture=name,seed=label,**info,residual=m['equilibrium_residual']))
    if m['equilibrium_residual']<2e-7:candidates.append((info['objective'],xx,DD))
   if not candidates:
    xx,DD=free,np.zeros(len(anchors));status='optimizer_did_not_find_equilibrium'
   else:_,xx,DD=min(candidates,key=lambda a:a[0]);status='best_local_stationary_solution'
   m,_,_=r.metrics2(xx,DD);fine=SegmentedRod(u,anchors,sub=8)
   xf=fine.solve(DD,finer_seed(xx,r,fine));sid=f'{name}_u{u}'
   if xf is not None:
    fm,fp,fd=fine.metrics2(xf,DD);fm.update(architecture=name,status=status,fine_converged=True,coarse_maximum_axis_deviation_mm=m['maximum_axis_deviation_mm'])
    arr[sid+'_points_m']=fp;arr[sid+'_x']=xf;arr[sid+'_top_tensions_n']=DD;rows.append(fm)
   else:m.update(architecture=name,status=status,fine_converged=False);rows.append(m)
   print(r.label,name,'offset',round(rows[-1]['maximum_axis_deviation_mm'],2),'strain',round(rows[-1]['max_abs_axial_strain']*100,1),'force',np.round(DD,1).tolist(),flush=True)
 write_csv(out/'segmented_tendon_comparison.csv',rows);write_csv(out/'segmented_tendon_optimizer_attempts.csv',attempts)
 (out/'segmented_tendon_comparison.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');np.savez_compressed(out/'segmented_tendon_states.npz',**arr)
 (out/'segmented_tendon_validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
 render(rows,arr,out)
 print(json.dumps(checks,indent=2))

def render(rows,z,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.text import Text
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.unicode_minus':False})
 fig,axs=plt.subplots(1,2,figsize=(11,5.5));colors=['#246b9d','#c86431','#587b52','#80648a'];names=['single','two','three','per_module']
 for name,c in zip(names,colors):
  r=next(q for q in rows if q['configuration']=='U9-M1' and q['architecture']==name)
  if r['fine_converged']:
   p=z[f'{name}_u9_points_m']*1000;a=np.radians(20);p=p@np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
   axs[0].plot(p[:,0],p[:,1],lw=2,color=c,label=f'{r["anchor_set_count"]} anchor set(s)')
  for u,marker in [(8,'o'),(9,'s')]:
   q=next(q for q in rows if q['configuration']==f'U{u}-M{10-u}' and q['architecture']==name)
   axs[1].scatter(q['max_abs_axial_strain']*100,q['maximum_axis_deviation_mm'],color=c,marker=marker,s=55)
   right=q['max_abs_axial_strain']*100>25
   axs[1].annotate(f'{u}U, {q["anchor_set_count"]} sets',(q['max_abs_axial_strain']*100,q['maximum_axis_deviation_mm']),xytext=(-5 if right else 5,5),ha='right' if right else 'left',textcoords='offset points',fontsize=9)
 axs[0].axhline(0,color='#596570',ls='--',lw=1);axs[0].set(xlabel='Projection along insertion axis (mm)',ylabel='Offset from insertion axis (mm)',title='U9-M1: optimized loaded shapes\n500 g head; 20 deg root pitch');axs[0].grid(alpha=.15);axs[0].legend(fontsize=9)
 axs[1].axvline(5,color='#596570',ls='--',lw=1);axs[1].axhline(10,color='#596570',ls=':',lw=1);axs[1].set(xlabel='Maximum absolute axial strain (%)',ylabel='Maximum axis deviation (mm)',title='Shape improvement versus axial strain\nCircle: U8-M2; square: U9-M1',xlim=(0,33),ylim=(-5,460));axs[1].grid(alpha=.15)
 fig.tight_layout(rect=(0,.11,1,1));fig.text(.5,.015,'All tendons run from base to their anchor: proximal compression and added rope mass are included.\nLocal optimum only; 5% is a diagnostic threshold. More anchor sets require new routing hardware. No deployment approval.',ha='center',fontsize=9)
 for t in fig.findobj(Text):assert all(ord(c)<128 for c in t.get_text())
 fig.savefig(out/'segmented_tendon_comparison.png',dpi=170,bbox_inches='tight');plt.close(fig)

def run_low_strain():
 rows=[]
 for name,anchors in [('single',[10]),('two',[9,10]),('three',[4,9,10]),('per_module',list(range(1,11)))]:
  r=SegmentedRod(9,anchors);free=r.free();D=np.zeros(len(anchors));D[-1]=8
  seed=r.solve(D,free)
  if seed is None:seed=free;D[:]=0
  x,T,info=r.optimize(seed,D,max_strain=.05);m,_,_=r.metrics2(x,T)
  m.update(architecture=name,optimizer=info,coarse_strain_bound=.05)
  fine=SegmentedRod(9,anchors,sub=8);xf=fine.solve(T,finer_seed(x,r,fine))
  if xf is not None:
   fm,_,_=fine.metrics2(xf,T);m.update(fine_metrics=fm,fine_converged=True)
  else:m['fine_converged']=False
  rows.append(m);print(name,'residual',m['equilibrium_residual'],'offset',m['maximum_axis_deviation_mm'],'strain',m['max_abs_axial_strain'],flush=True)
 (HERE/'results/segmented_low_strain.json').write_text(json.dumps(rows,indent=2))
 return rows

if __name__=='__main__':
 if '--low-strain' in sys.argv:run_low_strain()
 else:run()
