// Experimental M5/M6 internal rope-guide spider.
// Not a released/print-approved part: guide-to-body clearance and friction remain
// to be checked against deformed module geometry and a physical sample.
//
// Export one guide: set guide_kind to "M5" or "M6", press F6, then export STL.
// M5 routes B/C (r=24/27 mm); M6 routes C (r=27 mm).
// The guide is a thin cross-guide clipped around four existing inner M-body webs.

guide_kind = "M5"; // [M5,M6]
rope_hole_d = 2.6;         // 2.0 mm rope with 0.3 mm radial running clearance
plate_thickness = 1.2;
arm_width = 4.0;
root_inner_radius = 8.8;
root_outer_radius = 10.2;
web_center_radius = 6.9; // measured from the M-body STEP cross-section
web_clip_outer_d = 6.4;
web_clip_inner_d = 5.2;
web_clip_gap = 1.2;
web_angles = [-22.5, 67.5, 157.5, 247.5];
arm_tip_radius = 28.7;
show_rope_preview = false;
guide_pitch = 24; // maximum unsupported rope span in the modeled layout
show_guide_array = false;

module web_clip() {
    difference() {
        cylinder(d=web_clip_outer_d, h=plate_thickness, center=true, $fn=64);
        cylinder(d=web_clip_inner_d, h=plate_thickness+1, center=true, $fn=48);
        // Mouth faces inward, toward the module axis.
        translate([-web_clip_outer_d/2,0,0])
            cube([web_clip_outer_d,web_clip_gap,plate_thickness+1],center=true);
    }
}

module one_guide(kind="M5") {
    radii = kind == "M5" ? [24, 27] : [27];
    difference() {
        union() {
            difference() {
                cylinder(r=root_outer_radius, h=plate_thickness, center=true, $fn=96);
                cylinder(r=root_inner_radius, h=plate_thickness+1, center=true, $fn=96);
            }
            for (a = [0:90:270])
                rotate([0,0,a])
                    translate([(root_inner_radius + arm_tip_radius)/2,0,0])
                        cube([arm_tip_radius-root_inner_radius,arm_width,plate_thickness], center=true);
            for (a = web_angles)
                translate([web_center_radius*cos(a),web_center_radius*sin(a),0])
                    rotate([0,0,a]) web_clip();
        }
        for (a = [0:90:270])
            for (r = radii)
                rotate([0,0,a])
                    translate([r,0,0])
                        cylinder(d=rope_hole_d, h=plate_thickness+1, center=true, $fn=48);
    }
}

if (show_guide_array) {
    for (z = [-24,-12,12,24])
        translate([0,0,z]) one_guide(guide_kind);
} else if (show_rope_preview) {
    color([0.45,0.48,0.52]) one_guide(guide_kind);
    for (a = [0:90:270])
        for (r = (guide_kind == "M5" ? [24,27] : [27]))
            rotate([0,0,a])
                translate([r,0,0])
                    color([0.88,0.55,0.08])
                        cylinder(d=2,h=guide_pitch*2,center=true,$fn=32);
} else {
    one_guide(guide_kind);
}
