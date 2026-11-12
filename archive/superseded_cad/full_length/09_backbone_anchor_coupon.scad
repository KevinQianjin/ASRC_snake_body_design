// IGNORE (marked 2026-11-11): does not match the simulated design. This placeholder uses 84 mm shells + 12 mm pin joints;
// the design uses continuous 96 mm modules with a full-length 1.8 mm NiTi rod in each M module. See NOT_THE_SIMULATED_DESIGN.md.
// Backbone end-retention fit coupon for the U4+M2 moving prototype.
// Print in the intended end-plate material (preferably PA12). This is a
// low-load test coupon, not a finished robot anchor or a rated fixture.
// The 1.8 mm rod and metal collars/ferrules are separate purchased parts.

$fn = 72;

rod_diameter = 1.8;
rod_clearance = 0.35;          // diametral fit allowance; verify by printed fit
ferrule_depth = 3.0;           // depth of capture pocket
ferrule_clearance = 0.30;      // radial allowance around collar/ferrule OD
ferrule_sizes = [6.0, 8.0, 10.0]; // test three retention-feature diameters
coupon_length = 54;
coupon_width = 30;
coupon_thickness = 8;
station_spacing = 17;
fixture_hole_d = 4.5;          // M4 fixture bolts; not part of robot interface
fixture_hole_spacing = 22;
show_rods = true;
show_ferrules = true;
export_printable_coupon = true;

module station_pocket(ferrule_d) {
    // Rod runs through the full coupon. A collar seated in the underside
    // counterbore bears against the coupon when the rod is pulled downward.
    translate([0,0,-0.1])
        cylinder(d=rod_diameter+rod_clearance,h=coupon_thickness+0.2);
    translate([0,0,-0.01])
        cylinder(d=ferrule_d+ferrule_clearance,
                 h=ferrule_depth+0.01);
}

module coupon_body() {
    difference() {
        translate([-coupon_length/2,-coupon_width/2,0])
            cube([coupon_length,coupon_width,coupon_thickness]);
        for (i=[0:2]) {
            x=(i-1)*station_spacing;
            translate([x,0,0]) station_pocket(ferrule_sizes[i]);
        }
        for (y=[-fixture_hole_spacing/2,fixture_hole_spacing/2])
            translate([0,y,-0.1])
                cylinder(d=fixture_hole_d,h=coupon_thickness+0.2);
    }
}

module preview_hardware() {
    // Illustrative only: actual ferrule OD/thickness and rod retention method
    // must match the purchased hardware and supplier guidance.
    if (show_rods)
        for (i=[0:2]) {
            x=(i-1)*station_spacing;
            translate([x,0,-4]) color([0.86,0.72,0.25])
                cylinder(d=rod_diameter,h=coupon_thickness+8);
        }
    if (show_ferrules)
        for (i=[0:2]) {
            x=(i-1)*station_spacing;
            translate([x,0,0]) color([0.55,0.58,0.62])
                difference() {
                    cylinder(d=ferrule_sizes[i],h=ferrule_depth);
                    translate([0,0,-0.1])
                        cylinder(d=rod_diameter+0.05,h=ferrule_depth+0.2);
                }
        }
}

if (export_printable_coupon) coupon_body();
else {
    color([0.22,0.62,0.53]) coupon_body();
    preview_hardware();
}

// Export the coupon alone with export_printable_coupon=true. The metal parts
// are preview aids only and must never be included in the printed STL.

