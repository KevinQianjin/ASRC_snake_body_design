// Exact end-disk fit coupon sliced from the STEP-derived M-module mesh.
// Open this SCAD in the same folder as Medium_Stiffness_96.stl.
// The coupon is the source M end face, 3 mm thick, with its actual central
// 8.4 mm passage and surrounding STEP geometry. It does NOT add an anchor.
// Use it to check proposed rod-end hardware against the real end-face shape.

source_mesh = "Medium_Stiffness_96.stl";
end_z = -48;          // M STEP/STL axis is Z, full length is -48..+48 mm
end_disk_thickness = 3; // verified end section is z=-48..-45 mm
crop_size = 80;       // >63 mm OD, leaves the whole end-disk section intact
show_rod_preview = false;
rod_diameter = 1.8;

module end_disk_coupon() {
    // Crop the source mesh at its actual end. Move the coupon bottom to Z=0.
    translate([0,0,-end_z])
        intersection() {
            import(source_mesh, convexity=16);
            translate([-crop_size/2,-crop_size/2,end_z])
                cube([crop_size,crop_size,end_disk_thickness]);
        }
}

if (show_rod_preview) {
    color([0.72,0.78,0.84]) end_disk_coupon();
    // Preview only. The wire is not part of the printable coupon.
    color([0.88,0.68,0.18])
        translate([0,0,-3]) cylinder(d=rod_diameter,h=end_disk_thickness+6,$fn=48);
} else {
    end_disk_coupon();
}

// Export with show_rod_preview=false. No ferrule, clamp, adhesive, or anchor
// is modeled yet; choose the retention concept separately, then add it here.

