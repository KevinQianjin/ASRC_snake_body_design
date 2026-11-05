"""Recompute consequential geometry and numerical consistency checks."""
from pathlib import Path
import sys,json,hashlib,math
import numpy as np
from scipy.optimize import brentq
from planar_clearance import load_geometry,HERE
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from front_solver import FrontRod,KERNEL_PATH
from rear_beam import solve_beam,segments_for

def run():
 out=HERE/'results';cad,obs,cavity,xs,floor,roof=load_geometry()
 assert len(cad['sections'])==5
 assert all(s['validation']['union_valid'] and not s['validation']['boolean_or_discretization_failures'] for s in cad['sections'])
 entry=np.array([449.,np.interp(449.,xs,floor)])
 aperture_distance=obs[648.].distance(Point(entry));assert 249<aperture_distance<251
 fo=unary_union([obs[k] for k in [632.,648.,664.]])
 ro=unary_union([obs[k] for k in [628.,648.,668.]])
 # A deliberately imposed geometric case must be checked separately from force equilibrium.
 a=np.radians(15);v=np.array([np.cos(a),np.sin(a)]);root=entry+400*v
 imposed=LineString([root,root+500*v]);guide=entry-200*v
 assert imposed.distance(fo)>=21 and cavity.covers(imposed.buffer(21))
 assert LineString([guide,root]).distance(ro)>=25
 z=np.load(out/'front_refined_states.npz');p=z['r004_points_m']*1000
 rod=FrontRod(3,20,sub=8);T=np.array([8.,0,0,0]);m,points,_,_=rod.metrics(z['r004_x'],T)
 assert np.max(abs(points*1000-p))<1e-8 and m['equilibrium_residual']<1e-8
 v=np.array([np.cos(np.radians(20)),np.sin(np.radians(20))])
 def distance(s):return LineString(p+entry+s*v).distance(fo)-21
 lo=brentq(distance,883,884,xtol=1e-6);hi=brentq(distance,884,885,xtol=1e-6)
 mid=(lo+hi)/2;line=LineString(p+entry+mid*v)
 assert 0<hi-lo<1 and cavity.covers(line.buffer(21))
 assert distance(lo-.1)<0 and distance(hi+.1)<0
 beam=solve_beam(segments_for('stepped_40_30',1.084),np.radians(20),m['vertical_reaction_n'],m['gravity_moment_about_interface_nm'],numerical_check=True)
 assert beam['root_moment_integration_abs_difference_nm']<1e-10
 validation=dict(cad_sections_valid=True,opening_center_distance_to_solid_mm=aperture_distance,
  imposed_geometric_case_checked=True,fine_loaded_state_residual=m['equilibrium_residual'],
  narrow_window_lower_mm=lo,narrow_window_upper_mm=hi,narrow_window_width_mm=hi-lo,
  boundary_cases_checked=True,kernel_sha256=hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest(),
  input_step_sha256=hashlib.sha256((HERE/'inputs/tank-v2.step').read_bytes()).hexdigest(),
  english_only_figure_text_enforced_by_renderer=True,
  conclusion='No complete installation feasibility claim: static fit is narrow and frozen-shape deployment collides.')
 (out/'study_validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
 (out/'candidate_detail.json').write_text(json.dumps(dict(narrow_window_lower_mm=lo,narrow_window_upper_mm=hi,narrow_window_width_mm=hi-lo,
  front_load_vertical_n=m['vertical_reaction_n'],front_gravity_moment_nm=m['gravity_moment_about_interface_nm'],rear_nominal_beam=beam,
  caveat='Rear gravity-only beam deflection is separate, not an iteratively coupled front/rear solution; joints not included.'),indent=2),encoding='utf-8')
 print(json.dumps(validation,indent=2))
 return validation

if __name__=='__main__':run()
