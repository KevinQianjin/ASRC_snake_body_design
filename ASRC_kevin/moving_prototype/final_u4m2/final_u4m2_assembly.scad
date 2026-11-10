/*
 * Full-scale U4+M2 assembly from the uploaded Shapr3D STEP models.
 *
 * OpenSCAD cannot import STEP, so the two source assemblies are triangulated
 * into companion STL files in this folder. The STEP files remain the editable
 * design sources; these meshes are display/print-export derivatives.
 *
 * STEP frame notes:
 *   U model: 96 mm long on local Y, so rotate +90 degrees about X to align Z.
 *   M model: 96 mm long on local Z, already aligned with the assembly axis.
 */

view_mode = "assembly"; // [assembly, exploded, U_only, M_only, selected_only]
selected_module = 0;    // [0:5] 0..3 = U1..U4, 4..5 = M1..M2
module_gap_mm = 0;      // Keep 0 for end-to-end nominal assembly
explode_gap_mm = 18;    // Separation added only in exploded view

module_length_mm = 96;
module_order = ["U", "U", "U", "U", "M", "M"];

function module_center_z(i, gap) = i * (module_length_mm + gap) + module_length_mm / 2;

module draw_module(kind) {
    if (kind == "U") {
        color([0.12, 0.48, 0.86])
            rotate([90, 0, 0])
                import("UniDirectional_96.stl", convexity = 12);
    } else {
        color([0.95, 0.48, 0.12])
            import("Medium_Stiffness_96.stl", convexity = 12);
    }
}

module placed_module(kind, center_z) {
    translate([0, 0, center_z]) draw_module(kind);
}

if (view_mode == "assembly" || view_mode == "exploded") {
    for (i = [0 : len(module_order) - 1]) {
        gap = view_mode == "exploded" ? explode_gap_mm : module_gap_mm;
        placed_module(module_order[i], module_center_z(i, gap));
    }
} else if (view_mode == "U_only") {
    placed_module("U", module_length_mm / 2);
} else if (view_mode == "M_only") {
    placed_module("M", module_length_mm / 2);
} else if (view_mode == "selected_only") {
    assert(selected_module >= 0 && selected_module < len(module_order), "selected_module must be 0..5");
    placed_module(module_order[selected_module], module_length_mm / 2);
} else {
    assert(false, "Unknown view_mode. Use assembly, exploded, U_only, M_only, or selected_only.");
}
