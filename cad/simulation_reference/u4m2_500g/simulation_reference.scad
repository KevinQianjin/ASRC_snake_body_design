// Generated from baseline.json. Simulation reference only; not fabrication CAD.
module_length=96.0;
interface_length=20.0;
envelope_radius=31.5;
rod_diameter=1.8;
rope_diameter=2.0;
module_starts=[20.0, 116.0, 212.0, 308.0, 404.0, 500.0];
module_ends=[116.0, 212.0, 308.0, 404.0, 500.0, 596.0];
offsets=[[24.0, 0.0], [0.0, 24.0], [-24.0, 0.0], [0.0, -24.0]];
anchor_ends=[404.0, 500.0, 596.0];
rod_starts=[404.0, 500.0];
rod_ends=[500.0, 596.0];
payload_x=596.0;
pitch_deg=20;

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
