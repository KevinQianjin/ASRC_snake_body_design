"""Generate a portable OpenSCAD view directly from baseline.json."""
from pathlib import Path
import json
p=Path(__file__).resolve().parent
b=json.loads((p/'baseline.json').read_text())
constants=dict(module_length=b['modules'][0]['length_mm'],interface_length=b['interface_length_mm'],
    envelope_radius=b['collision_diameter_mm']/2,
    rod_diameter=b['backbones'][0]['diameter_mm'],rope_diameter=b['tendons'][0]['diameter_mm'],
    module_starts=[m['start_mm'] for m in b['modules']],module_ends=[m['end_mm'] for m in b['modules']],
    offsets=[t['anchor_local_mm'][1:] for t in b['tendons'][:4]],
    anchor_ends=[t['anchor_local_mm'][0] for t in b['tendons'][::4]],
    rod_starts=[r['start_local_mm'][0] for r in b['backbones']],rod_ends=[r['end_local_mm'][0] for r in b['backbones']],
    payload_x=b['payload']['point_local_mm'][0],pitch_deg=b['installation']['pitch_deg'])
text='// Generated from baseline.json. Simulation reference only; not fabrication CAD.\n'
text+='\n'.join(k+'='+json.dumps(v)+';' for k,v in constants.items())+'\n'
text+='''
$fn=64;
show_envelopes=true;
show_source_cad=false; // Reference geometry exceeds nominal envelope; not conformed.
source_mesh_dir="../../previews/u4m2/"; // Portable ZIP uses "source_meshes/".
rope_group="ALL"; // [ALL,A,B,C,NONE] ALL intentionally contains coincident ropes.
world_pitch=false;
module line(a,b,r){v=b-a;translate(a) rotate(a=acos(v.z/norm(v)),v=cross([0,0,1],v)) cylinder(h=norm(v),r=r);}
module axis_ring(x,r){translate([x,0,0])rotate([0,90,0])difference(){cylinder(h=.3,r=r,center=true);cylinder(h=.5,r=r-.3,center=true);}}
module assembly(){
 if(show_envelopes){
  color([.45,.5,.55,.15])line([0,0,0],[interface_length,0,0],envelope_radius);
  for(i=[0:5])color(i<4?[.1,.4,.8,.12]:[.95,.4,.05,.12])line([module_starts[i],0,0],[module_ends[i],0,0],envelope_radius);
  color([.8,.1,.1,.1])translate([payload_x,0,0])sphere(r=envelope_radius);
 }
 for(x=concat([0,interface_length],module_ends))color([.3,.4,.5])axis_ring(x,envelope_radius);
 for(i=[0:1])color([.55,.6,.65])line([rod_starts[i],0,0],[rod_ends[i],0,0],rod_diameter/2);
 for(g=[0:2])if(rope_group=="ALL"||rope_group==["A","B","C"][g])for(o=offsets)
  color([[.95,.6,.02],[.02,.65,.2],[.8,.05,.4]][g])line([interface_length,o[0],o[1]],[anchor_ends[g],o[0],o[1]],rope_diameter/2);
 // Mathematical point-load marker; sphere size is only a display symbol.
 color([.8,.05,.05])translate([payload_x,0,0])sphere(r=2.5);
 if(show_source_cad)for(i=[0:5])translate([(module_starts[i]+module_ends[i])/2,0,0])rotate([0,90,0])
  if(i<4)rotate([90,0,0])for(j=[1:5])color([.6,.65,.7,.35])import(str(source_mesh_dir,"UniDirectional_96_part_0",j,".stl"),convexity=12);
  else color([.6,.65,.7,.35])import(str(source_mesh_dir,"Medium_Stiffness_96.stl"),convexity=12);
}
echo("SIMULATION REFERENCE: coincident ideal tendon paths; not a manufacturing release.");
rotate([0,0,world_pitch?pitch_deg:0])assembly();
'''
(p/'simulation_reference.scad').write_text(text)
print('Generated simulation_reference.scad from baseline.json')
