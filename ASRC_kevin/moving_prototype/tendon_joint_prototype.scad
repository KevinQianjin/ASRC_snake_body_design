/*
  First moving proof-of-concept for the snake front.
  This is a 1-axis, manually pulled tendon test article, not a faithful U/M
  stiffness replica and not rated for the 500 g simulated head load.
  Open in OpenSCAD. Set part="assembly" and change bend_angle to preview motion.
  Export parts separately by setting part to "proximal_link", "distal_link",
  or "head_ring". The pivot uses an M3 bolt/pin and nut (not included).
*/
part = "assembly"; // [assembly, proximal_link, distal_link, head_ring]
bend_angle = 0; // [-25:1:25]
show_tendons = true;
module_length = 96;
body_diameter = 63;
wall = 4;
end_plate = 4;
guide_radius = 24;
guide_diameter = 3.2;
pivot_diameter = 3.4;
head_ring_length = 16;
$fn = 64;
module axial_hole(x,y,d,h,z0=0) { translate([x,y,z0]) cylinder(d=d,h=h); }
module guide_holes(z0,h) { for (a=[0:90:270]) axial_hole(guide_radius*cos(a),guide_radius*sin(a),guide_diameter,h,z0); }
module module_shell(label="U") {
 difference() {
  union() { cylinder(d=body_diameter,h=module_length); translate([0,0,0]) cylinder(d=body_diameter,h=1.2); translate([0,0,module_length-1.2]) cylinder(d=body_diameter,h=1.2); }
  translate([0,0,end_plate]) cylinder(d=body_diameter-2*wall,h=module_length-2*end_plate);
  axial_hole(0,0,14,module_length+0.2,-0.1); guide_holes(-0.1,module_length+0.2);
  translate([-12,-2,module_length-0.8]) linear_extrude(height=1.0) text(label,size=5,halign="center",valign="center");
 }
}
module proximal_link() {
 color([0.29,0.44,0.72]) {
  module_shell("U");
  for (x=[-9,9]) difference() {
   translate([x-3,-12,module_length-6]) cube([6,24,22]);
   translate([x-4,0,module_length+6]) rotate([0,90,0]) cylinder(d=pivot_diameter,h=8);
  }
 }
}
module distal_link_local() {
 color([0.22,0.62,0.53]) {
  translate([0,0,6]) module_shell("M");
  difference() {
   union() { translate([-6,-9,-10]) cube([12,18,20]); translate([-6,-7,5]) cube([12,14,8]); }
   translate([-7,0,0]) rotate([0,90,0]) cylinder(d=pivot_diameter,h=14);
  }
 }
}
module head_ring() {
 color([0.72,0.31,0.29]) difference() {
  cylinder(d=body_diameter,h=head_ring_length);
  translate([0,0,-0.1]) cylinder(d=body_diameter-2*wall,h=head_ring_length+0.2);
  axial_hole(0,0,14,head_ring_length+0.2,-0.1); guide_holes(-0.1,head_ring_length+0.2);
  for (a=[0:90:270]) translate([guide_radius*cos(a),guide_radius*sin(a),head_ring_length-3]) cube([5,5,4],center=true);
 }
}
module tendon_segment(a,b,d=1.0) {
 v=[b[0]-a[0],b[1]-a[1],b[2]-a[2]]; len=norm(v);
 if (len>0.01) color([0.82,0.52,0.12]) translate(a) rotate([0,acos(v[2]/len),atan2(v[1],v[0])]) cylinder(d=d,h=len);
}
module assembly() {
 pivot_z=module_length+6;
 proximal_link(); rotate([bend_angle,0,0]) translate([0,0,pivot_z]) distal_link_local();
 rotate([bend_angle,0,0]) translate([0,0,pivot_z+6+module_length]) head_ring();
 if (show_tendons) for (a=[0:90:270]) {
  p0=[guide_radius*cos(a),guide_radius*sin(a),0]; p1=[guide_radius*cos(a),guide_radius*sin(a),module_length];
  entryLocal=[guide_radius*cos(a),guide_radius*sin(a),6]; endLocal=[guide_radius*cos(a),guide_radius*sin(a),6+module_length+head_ring_length/2];
  entryWorld=[entryLocal[0],entryLocal[1]*cos(bend_angle)-entryLocal[2]*sin(bend_angle),entryLocal[1]*sin(bend_angle)+entryLocal[2]*cos(bend_angle)+pivot_z];
  endWorld=[endLocal[0],endLocal[1]*cos(bend_angle)-endLocal[2]*sin(bend_angle),endLocal[1]*sin(bend_angle)+endLocal[2]*cos(bend_angle)+pivot_z];
  tendon_segment(p0,p1); tendon_segment(p1,entryWorld); tendon_segment(entryWorld,endWorld);
 }
}
if (part=="assembly") assembly();
else if (part=="proximal_link") proximal_link();
else if (part=="distal_link") distal_link_local();
else if (part=="head_ring") head_ring();
