"""Small dependency-free follow-up: more U modules and active insertion tension.

No CAD runtime is required. This tests front equilibria, not a changing-shape
deployment trajectory, and writes a separate compact result set.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import json,csv
import numpy as np
from front_solver import FrontRod,HERE,write_csv
from refine_front import finer_seed,geometry_screen,stiffness_with_extra_rope

def extra_metrics(rod,x,T):
 m,p,_,d=rod.metrics(x,T)
 a=rod.root_pitch;t=np.array([np.cos(a),np.sin(a)]);n=np.array([-np.sin(a),np.cos(a)])
 projection=float(p[-1]@t)*1000;dev=float(np.max(abs(p@n)))*1000
 ang=float(np.max(abs(d['theta']-a)))*180/np.pi
 strain=float(np.max(abs(d['eps'])))
 m.update(axial_projection_mm=projection,maximum_axis_deviation_mm=dev,maximum_tangent_error_deg=ang,
   max_abs_axial_strain=strain,score_mm=dev+max(0.,500-projection)*.5,
   provisional_straight_test=bool(dev<=10 and ang<=5 and projection>=475 and strain<=.05),
   screen_definition='10mm maximum offset; 5deg tangent error; 475mm projection; 5% diagnostic strain, not approved acceptance criteria')
 return m,p,d

def run():
 out=HERE/'results';rows=[];attempts=[];chosen=[];arrays={}
 forces=np.r_[np.arange(0.,31.,1.),40.,48.,64.,96.,128.,160.,200.]
 for u in [7,8,9,10]:
  for pitch in [15,20,25]:
   rod=FrontRod(u,pitch,sub=4);free=rod.free_state();local=[]
   if free is None:raise RuntimeError('No gravity seed')
   for common in [0.,2.]:
    prev=free
    for f in forces:
     T=rod.sweep_tensions(float(f),common)
     got=rod.solve_force(T,prev,maxiter=120)
     if got is None:got=rod.solve_force(T,rod.straight_seed(),maxiter=120)
     attempts.append(dict(n_uni=u,n_medium=10-u,pitch_deg=pitch,top_extra_n=float(f),common_per_rope_n=common,converged=got is not None))
     if got is None:continue
     prev=got;m,p,d=extra_metrics(rod,got,T)
     m.update(top_extra_n=float(f),common_per_rope_n=common,all_U_upper_bound_only=u==10)
     rows.append(m);local.append((m,got,T))
   eligible=[q for q in local if q[0]['stable_in_plane'] and q[0]['max_abs_axial_strain']<=.05]
   if not eligible:continue
   m,x,T=min(eligible,key=lambda q:q[0]['score_mm'])
   fine=FrontRod(u,pitch,sub=8);xf=fine.solve_force(T,finer_seed(x,rod,fine),maxiter=180)
   record=dict(configuration=rod.label,pitch_deg=pitch,selected_top_extra_n=m['top_extra_n'],selected_common_per_rope_n=m['common_per_rope_n'],all_U_upper_bound_only=u==10,fine_converged=xf is not None)
   if xf is not None:
    fm,fp,fd=extra_metrics(fine,xf,T);sid=f'u{u}_p{pitch}'
    fm.update(geometry_screen(fp,fd,fine));record.update(fm,state_id=sid,
       tip_refinement_change_mm=float(np.linalg.norm(fp[-1]-extra_metrics(rod,x,T)[1][-1]))*1000,
       stability_with_one_m_extra_rope=stiffness_with_extra_rope(fine,xf,T))
    arrays[sid+'_points_m']=fp;arrays[sid+'_theta_rad']=fd['theta'];arrays[sid+'_strain']=fd['eps'];arrays[sid+'_x']=xf
   chosen.append(record)
   print(rod.label,pitch,'best top',m['top_extra_n'],'proj',round(m['axial_projection_mm'],1),'offset',round(m['maximum_axis_deviation_mm'],1),flush=True)
 write_csv(out/'insertion_tension_equilibria.csv',rows);write_csv(out/'insertion_tension_attempts.csv',attempts)
 write_csv(out/'insertion_tension_best.csv',chosen)
 (out/'insertion_tension_best.json').write_text(json.dumps(chosen,indent=2),encoding='utf-8')
 np.savez_compressed(out/'insertion_tension_best_states.npz',**arrays)
 summary=dict(attempted=len(attempts),converged=len(rows),uni_counts=[7,8,9,10],pitches_deg=[15,20,25],
  payload_kg=.5,high_U_EI_vertical_nm2=.061,high_U_EI_other_plane_nm2=.0057,medium_EI_nm2=.0046,
  provisional_straight_cases=sum(r['provisional_straight_test'] for r in rows),
  fine_best_records=len(chosen),
  limitations=['U10/M0 is an upper-bound control, not the requested mixed design.',
   '5% is a diagnostic strain threshold, not measured failure.',
   'No CAD clearance or time-varying insertion trajectory recomputed.',
   'All four tendons anchor to head; only top differential and 0/2N common tension searched.',
   'Force search bounds are not actuator or tendon ratings.'])
 render(chosen,arrays,out)
 summary['total_new_result_bytes']=sum(p.stat().st_size for p in out.glob('insertion_tension_*'))
 (out/'insertion_tension_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2))

def render(rows,z,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.text import Text
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.unicode_minus':False})
 fig,axs=plt.subplots(1,2,figsize=(11,5.2));colors=['#246b9d','#c86431','#587b52','#80648a']
 for u,c in zip([7,8,9,10],colors):
  r=next(q for q in rows if q['configuration']==f'U{u}-M{10-u}' and q['pitch_deg']==20 and q['fine_converged']);p=z[r['state_id']+'_points_m']*1000
  a=np.radians(20);local=p@np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
  axs[0].plot(local[:,0],local[:,1],color=c,lw=2,label=f'U{u}/M{10-u}, top {r["selected_top_extra_n"]:.0f} N')
  axs[1].bar(str(u),r['maximum_axis_deviation_mm'],color=c)
  axs[1].text(str(u),r['maximum_axis_deviation_mm']+5,f'{r["maximum_axis_deviation_mm"]:.0f}',ha='center')
 axs[0].axhline(0,color='#596570',ls='--',lw=1);axs[0].set(xlabel='Projection along insertion axis (mm)',ylabel='Offset from insertion axis (mm)',title='Best tested low-strain front shapes\n20 deg root pitch; 500 g head')
 axs[0].set_aspect('equal');axs[0].grid(alpha=.15)
 axs[1].axhline(10,color='#596570',ls='--',lw=1);axs[1].set(xlabel='Number of U modules (10 modules total)',ylabel='Maximum axis deviation (mm)',title='Increasing U: stiff bending plane\naligned against gravity',ylim=(0,470));axs[1].text(.98,13,'10 mm provisional target',transform=axs[1].get_yaxis_transform(),ha='right',va='bottom',fontsize=9,bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
 fig.tight_layout(rect=(0,.18,1,1));fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.145),ncol=4,fontsize=9)
 fig.text(.5,.015,'Active tension, 480 mm modules + 20 mm interface; fine mesh. Selection minimizes offset and loss of projection.\nU10/M0 is a comparison only. 5% strain is a diagnostic screen; no deployment or material approval.',ha='center',fontsize=9)
 for t in fig.findobj(Text):assert all(ord(c)<128 for c in t.get_text())
 fig.savefig(out/'insertion_tension_comparison.png',dpi=170,bbox_inches='tight');plt.close(fig)

if __name__=='__main__':run()
