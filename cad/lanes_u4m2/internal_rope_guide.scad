// Experimental M5/M6 internal rope-guide spider.
// Not a released/print-approved part: guide-to-body clearance and friction remain
// to be checked against deformed module geometry and a physical sample.
//
// Export one guide: set guide_kind to "M5" or "M6", press F6, then export STL.
// M5 routes B/C (r=24/27 mm); M6 routes C (r=27 mm).
// The guide is a thin cross spider supported on the central Ø1.8 mm backbone.

guide_kind = "M5"; // [M5,M6]
rope_hole_d = 2.6;         // 2.0 mm rope with 0.3 mm radial running clearance
backbone_hole_d = 2.1;     // 1.8 mm NiTi backbone
plate_thickness = 1.2;
hub_length = 8.0;          // bonded sleeve length on the backbone at each guide station
arm_width = 4.0;
root_inner_radius = 8.5; // clears the four inner M flexure webs at the guide plane
root_outer_radius = 10.0;
arm_tip_radius = 28.7;
show_rope_preview = false;
guide_pitch = 24; // maximum pitch between interior guide stations
show_guide_array = false;

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
        }
        for (a = [0:90:270])
            for (r = radii)
                rotate([0,0,a])
                    translate([r,0,0])
                        cylinder(d=rope_hole_d, h=plate_thickness+1, center=true, $fn=48);
    }
}

if (show_guide_array) {
    for (z = [-36,-12,12,36])
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
