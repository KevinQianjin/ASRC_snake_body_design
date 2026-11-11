// IGNORE (marked 2026-11-11): does not match the simulated design. This placeholder uses 84 mm shells + 12 mm pin joints;
// the design uses continuous 96 mm modules with a full-length 1.8 mm NiTi rod in each M module. See NOT_THE_SIMULATED_DESIGN.md.
// NON-FINAL PLACEHOLDER: generic rigid shells and pin joints, not the soft U/M body.
// Do not treat this model or its STL exports as the final robot design.
// Self-contained copy of the six-module assembly preview.
// Shared geometry is included below so this file can be downloaded and opened by itself.

// Shared geometry library for the numbered full-length proof-of-motion parts.
// Module pitch matches the study's 96 mm; printed shell is 84 mm with a 12 mm
// joint allowance between successive pin centers. These are generic shells,
// not mechanically equivalent replicas of the simulated PA12/NiTi modules.

module_pitch = 96;
shell_length = 84;
body_diameter = 63;
shell_wall = 4;
end_plate = 4;
guide_radius = 24;
guide_hole_d = 3.2;
pivot_hole_d = 3.4; // M3 pin/bolt clearance
head_ring_length = 16;
head_placeholder_length = 80; // envelope only; actual head CAD is unknown

$fn = 56;

function rotate_x_point(p,a) = [p[0],p[1]*cos(a)-p[2]*sin(a),p[1]*sin(a)+p[2]*cos(a)];

module axial_hole(x,y,d,h,z0) {
    translate([x,y,z0]) cylinder(d=d,h=h);
}

module guide_holes(z0,h) {
    for (a=[0:90:270])
        axial_hole(guide_radius*cos(a),guide_radius*sin(a),guide_hole_d,h,z0);
}

module cable_segment(a,b,d=1.2,c=[0.82,0.52,0.12]) {
    v=[b[0]-a[0],b[1]-a[1],b[2]-a[2]];
    len=norm(v);
    if (len>0.01)
        color(c) translate(a)
            rotate([0,acos(v[2]/len),atan2(v[1],v[0])]) cylinder(d=d,h=len);
}

module cable_run_in_link(z0=6,z1=90,show_tendons=true) {
    if (show_tendons)
        for (a=[0:90:270]) {
            col=(a==90)?[0.82,0.52,0.12]:[0.30,0.34,0.40,0.72];
            cable_segment([guide_radius*cos(a),guide_radius*sin(a),z0],
                          [guide_radius*cos(a),guide_radius*sin(a),z1],1.2,col);
        }
}

module joint_cable_bridge(angle_deg=0,show_tendons=true) {
    // Bridges the 12 mm joint allowance between the adjacent module guide exits.
    if (show_tendons)
        for (a=[0:90:270]) {
            p0=[guide_radius*cos(a),guide_radius*sin(a),-6];
            p1=rotate_x_point([guide_radius*cos(a),guide_radius*sin(a),6],angle_deg);
            col=(a==90)?[0.82,0.52,0.12]:[0.30,0.34,0.40,0.72];
            cable_segment(p0,p1,1.2,col);
        }
}

module shell_body(label="U") {
    difference() {
        cylinder(d=body_diameter,h=shell_length);
        translate([0,0,end_plate])
            cylinder(d=body_diameter-2*shell_wall,h=shell_length-2*end_plate);
        axial_hole(0,0,14,shell_length+0.2,-0.1);
        guide_holes(-0.1,shell_length+0.2);
        translate([-12,-2,shell_length-0.8])
            linear_extrude(height=1) text(label,size=5,halign="center",valign="center");
    }
}

module module_link(kind="U",number=1,base=false,tip=false,show_tendons=true) {
    module_color=(kind=="U")?[0.29,0.44,0.72]:[0.22,0.62,0.53];
    color(module_color) {
        // The shell spans z=6..90 in the 96 mm pivot-to-pivot module pitch.
        translate([0,0,6]) shell_body(kind);

        if (base) {
            // Flat base flange; holes are for a low-load test stand only.
            difference() {
                cylinder(d=body_diameter,h=6);
                axial_hole(0,0,14,6.2,-0.1);
                guide_holes(-0.1,6.2);
                for (a=[45:90:315]) axial_hole(18*cos(a),18*sin(a),3.4,6.2,-0.1);
            }
        } else {
            // Input tongue. It sits between the preceding link's clevis ears.
            difference() {
                union() {
                    translate([-6,-9,-6]) cube([12,18,12]);
                    translate([-6,-7,4]) cube([12,14,2]);
                }
                translate([-7,0,0]) rotate([0,90,0]) cylinder(d=pivot_hole_d,h=14);
            }
        }

        if (tip) {
            // Distal cord anchor ring at the terminal pivot.
            translate([0,0,90]) difference() {
                cylinder(d=body_diameter,h=head_ring_length);
                translate([0,0,-0.1]) cylinder(d=body_diameter-2*shell_wall,h=head_ring_length+0.2);
                axial_hole(0,0,14,head_ring_length+0.2,-0.1);
                guide_holes(-0.1,head_ring_length+0.2);
                for (a=[0:90:270])
                    translate([guide_radius*cos(a),guide_radius*sin(a),head_ring_length-3])
                        cube([5,5,4],center=true);
            }
        } else {
            // Output clevis, pin axis along X; it mates to the next link's tongue.
            for (x=[-9,9]) difference() {
                translate([x-3,-12,90]) cube([6,24,12]);
                translate([x-4,0,module_pitch]) rotate([0,90,0])
                    cylinder(d=pivot_hole_d,h=8);
            }
        }
    }
    cable_run_in_link(6,90,show_tendons);
    if (show_tendons && tip)
        for (a=[0:90:270])
            cable_segment([guide_radius*cos(a),guide_radius*sin(a),90],
                          [guide_radius*cos(a),guide_radius*sin(a),90+head_ring_length],1.2,
                          (a==90)?[0.82,0.52,0.12]:[0.30,0.34,0.40,0.72]);
}

module base_interface() {
    // 20 mm length from the study; outside shape is an envelope pending real CAD.
    difference() {
        cylinder(d=body_diameter,h=20);
        translate([0,0,-0.1]) cylinder(d=body_diameter-2*shell_wall,h=20.2);
        axial_hole(0,0,14,20.2,-0.1);
        guide_holes(-0.1,20.2);
        for (a=[45:90:315]) axial_hole(18*cos(a),18*sin(a),3.4,20.2,-0.1);
    }
}

module head_placeholder() {
    // Illustrative 63 mm envelope only; this does not represent the 500 g head CAD.
    difference() {
        cylinder(d=body_diameter,h=head_placeholder_length);
        translate([0,0,-0.1]) cylinder(d=body_diameter-2*shell_wall,h=head_placeholder_length+0.2);
        axial_hole(0,0,14,head_placeholder_length+0.2,-0.1);
    }
}


// ---- Full assembly preview ----
base_pitch = 20;
show_tendons = true;
joint_1 = 0; // [-25:1:25]
joint_2 = 0; // [-25:1:25]
joint_3 = 0; // [-25:1:25]
joint_4 = 0; // [-25:1:25]
joint_5 = 0; // [-25:1:25]
module at_next_link(angle_deg, show_tendons=true) {
 translate([0,0,module_pitch]) { joint_cable_bridge(angle_deg,show_tendons); rotate([angle_deg,0,0]) children(); }
}
module full_chain() {
 module_link("U",1,true,false,show_tendons);
 at_next_link(joint_1,show_tendons) {
  module_link("U",2,false,false,show_tendons);
  at_next_link(joint_2,show_tendons) {
   module_link("U",3,false,false,show_tendons);
   at_next_link(joint_3,show_tendons) {
    module_link("U",4,false,false,show_tendons);
    at_next_link(joint_4,show_tendons) {
     module_link("M",5,false,false,show_tendons);
     at_next_link(joint_5,show_tendons) {
      module_link("M",6,false,true,show_tendons);
      translate([0,0,90+head_ring_length]) head_placeholder();
     }
    }
   }
  }
 }
}
rotate([-base_pitch,0,0]) { translate([0,0,-20]) base_interface(); full_chain(); }
