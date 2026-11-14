// V2 engineering candidate. Bent-pose mount interference is unresolved.
$fn=64;
module station(kind,z) {
  translate([0,0,z]) {
    color("orange") import(str(kind,"_z",z>0?"+":"",z,"_guide.stl"));
    color("gold") import(str(kind,"_z",z>0?"+":"",z,"_caps.stl"));
    color("silver") import(str(kind,"_z",z>0?"+":"",z,"_wire_envelope.stl"));
  }
}
module m(kind) {
  color([.55,.65,.72,.25]) import(kind=="M5"?"M5_lane_anchorB.stl":"M6_lane_anchorC.stl");
  for(z=[-24,-12,12,24]) station(kind,z);
  color("royalblue") cylinder(d=1.8,h=96,center=true);
  for(r=kind=="M5"?[24,28]:[28],a=[0,90,180,270])
    color(r==24?"green":"red") rotate([0,0,a]) translate([r,0,0]) cylinder(d=2,h=96,center=true);
}
m("M5");
translate([80,0,0]) m("M6");
