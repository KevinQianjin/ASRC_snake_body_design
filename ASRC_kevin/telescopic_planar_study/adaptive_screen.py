"""Adaptive follow-up for narrow static fit windows missed by the coarse grid."""
from pathlib import Path
import sys,json,math
import numpy as np
from scipy.optimize import minimize_scalar
from planar_clearance import load_geometry,self_screen,save_csv,HERE
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import shapely as sh

def run():
 out=HERE/'results';_,obs,cavity,xs,floor,roof=load_geometry()
 ro=unary_union([obs[k] for k in (628.,648.,668.)]);fo=unary_union([obs[k] for k in (632.,648.,664.)])
 cases=[]
 coarse=json.loads((out/'front_equilibria.json').read_text());z=np.load(out/'front_states.npz')
 for r in coarse:
  if r['stable_in_plane'] and not r['axial_strain_exceeds_5_percent']:
   cases.append((r['state_id'],r['configuration'],r['pitch_deg'],r['tensions_n'],max(r['max_axial_compression'],r['max_axial_extension']),False,z))
 extended=json.loads((out/'front_angle_extension.json').read_text());ze=np.load(out/'front_angle_extension_states.npz')
 for r in extended:
  if r.get('stable_in_plane') and not r.get('axial_strain_exceeds_5_percent',True):
   cases.append((r['state_id'],r['configuration'],r['pitch_deg'],r['tensions_n'],max(r['max_axial_compression'],r['max_axial_extension']),r['record_type']=='best_refinement',ze))
 fine=json.loads((out/'front_refinements.json').read_text());zf=np.load(out/'front_refined_states.npz')
 for r in fine:
  if r['selection']=='best_forward' and r['refinement_converged']:
   cases.append((r['refined_state_id'],r['configuration'],r['pitch_deg'],r['tensions_n'],r['fine_max_abs_axial_strain'],True,zf))
 records=[];passed=[]
 ss=np.arange(0.,1000.001,.25)
 for sid,cfg,ang,T,strain,isfine,zz in cases:
  p=zz[sid+'_points_m']*1000;theta=zz[sid+'_theta_rad'];eps=zz[sid+'_strain']
  simple,clr,rk=self_screen(p,theta,eps);selfok=simple and clr>=-1e-6 and rk<1
  for port,x0 in [('A',449.),('B',1147.)]:
   entry=np.array([x0,np.interp(x0,xs,floor)])
   for direction in [-1,1]:
    a=math.radians(ang);v=np.array([direction*math.cos(a),math.sin(a)]);q=p*np.array([direction,1]);guide=entry-200*v
    def margin(s):
     w=entry+s*v+q
     return float(np.min(np.r_[w[:,1]-np.interp(w[:,0],xs,floor)-21,np.interp(w[:,0],xs,roof)-w[:,1]-21,w[:,0]-21,1600-w[:,0]-21]))
    opt=minimize_scalar(lambda s:-margin(s),bounds=(0,1000),method='bounded',options={'xatol':.001})
    m=margin(opt.x);valid=np.zeros(len(ss),dtype=bool)
    sleeveok=LineString([guide-300*v,guide]).distance(ro)>=30
    if m>=-.1 and selfok and sleeveok:
     roots=entry+ss[:,None]*v;lines=sh.linestrings(roots[:,None,:]+q[None,:,:])
     rear=sh.linestrings(np.stack((np.broadcast_to(guide,roots.shape),roots),axis=1))
     prelim=(sh.distance(lines,fo)>=21)&(sh.distance(rear,ro)>=25)
     for i in np.flatnonzero(prelim):valid[i]=cavity.covers(lines[i].buffer(21))
    hit=ss[valid]
    r=dict(state_id=sid,configuration=cfg,pitch_deg=ang,port=port,direction=direction,fine_mesh=isfine,tensions_n=T,max_abs_axial_strain=strain,
      self_screen_pass=selfok,best_necessary_vertical_margin_mm=m,optimized_insertion_mm=float(opt.x),
      static_fit_samples=int(valid.sum()),minimum_insertion_mm=float(hit.min()) if len(hit) else None,maximum_insertion_mm=float(hit.max()) if len(hit) else None)
    if len(hit):
     s=float(hit[len(hit)//2]);root=entry+s*v;w=root+q;ln=LineString(w)
     path_s=np.arange(-550.,s+.01,2.)
     paths=sh.linestrings((entry+path_s[:,None]*v)[:,None,:]+q[None,:,:])
     dd=sh.distance(paths,fo);clear=dd>=21
     r.update(selected_insertion_mm=s,exposed_rear_length_mm=s+200,interface_global_mm=root.tolist(),tip_global_mm=w[-1].tolist(),
       selected_front_obstacle_distance_mm=ln.distance(fo),selected_rear_obstacle_distance_mm=LineString([guide,root]).distance(ro),
       constant_shape_path_clear=bool(clear.all()),path_collision_samples=int((~clear).sum()),
       static_fit_window_span_mm=float(hit.max()-hit.min()),scope='static_fit_only_not_deployment_or_material_approval')
     passed.append(r)
    records.append(r)
 save_csv(out/'adaptive_low_strain_screen.csv',records)
 (out/'adaptive_static_fits.json').write_text(json.dumps(passed,indent=2),encoding='utf-8')
 summary=dict(eligible_front_states=len(cases),pose_families=len(records),fine_grid_step_mm=.25,
  static_fit_families=len(passed),fine_mesh_static_fit_families=sum(r['fine_mesh'] for r in passed),
  constant_shape_path_passes=sum(r['constant_shape_path_clear'] for r in passed),
  widest_fine_window_mm=max((r['static_fit_window_span_mm'] for r in passed if r['fine_mesh']),default=None),
  note='Adaptive search resolves narrow static windows missed by the 10 mm grid; no changing-shape insertion solved.')
 (out/'adaptive_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2));print(json.dumps([r for r in passed if r['fine_mesh']],indent=2))
 return records,passed

if __name__=='__main__':run()
