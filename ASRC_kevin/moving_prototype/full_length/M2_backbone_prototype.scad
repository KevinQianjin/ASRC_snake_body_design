// M-section proof-of-concept with a central, non-printed 1.8 mm NiTi rod.
// The shell follows module_common.scad's dimensions and M6 interface.
// The diagonal spiders are printed with the shell; the rod is preview-only
// and must be made as a separate metal part.
// This is a fit/assembly concept, not a validated load-bearing design.

include <module_common.scad>;

show_tendons = true;
show_backbone = true;
show_supports = true;
export_shell_only = false;

rod_diameter = 1.8;
rod_clearance = 0.35;       // diametral clearance around rod
support_thickness = 3.0;    // axial thickness of each guide spider
support_radius = 29.5;      // extend into the shell wall so guide webs fuse to it
support_web_width = 2.4;
support_hub_diameter = 6.0;
support_positions = [26, 50, 74]; // global Z; 24 mm spacing inside shell z=6..90

module rod_guide_spider() {
    // Two diagonal webs support the rod. Their ends avoid the four tendon
    // bores, which sit on the cardinal axes at a 24 mm radius.
    difference() {
        union() {
            cylinder(d=support_hub_diameter, h=support_thickness, center=true);
            for (a=[45,135])
                rotate([0,0,a])
                    cube([2*support_radius, support_web_width,
                          support_thickness], center=true);
        }
        cylinder(d=rod_diameter+rod_clearance,
                 h=support_thickness+0.4, center=true);
        for (a=[0:90:270])
            translate([guide_radius*cos(a),guide_radius*sin(a),0])
                cylinder(d=guide_hole_d+0.8,
                         h=support_thickness+0.4, center=true);
    }
}

module M2_shell_with_guides() {
    union() {
        module_link("M",6,false,true,show_tendons && !export_shell_only);
        if (show_supports)
            for (z=support_positions)
                translate([0,0,z]) color([0.12,0.48,0.39]) rod_guide_spider();
    }
}

module backbone_preview() {
    // Rendered in a contrasting color to show the assembly. Turn this off
    // before exporting the printable shell.
    color([0.86,0.72,0.25])
        translate([0,0,6]) cylinder(d=rod_diameter,h=84);
}

if (export_shell_only) {
    M2_shell_with_guides();
} else {
    M2_shell_with_guides();
    if (show_backbone) backbone_preview();
}
