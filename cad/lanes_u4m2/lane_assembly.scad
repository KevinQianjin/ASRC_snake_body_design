use <internal_rope_guide.scad>;

// Lane-routed U4+M2 assembly (newest design, 13 Nov 2026). Built by build_lane_modules.py.
// Parts: base_interface + U1..U3 (U_lane_pass) + U4 + M5 + M6 + head_adapter, 16 leaf springs, rod, 12 ropes.
// Frame: Z axial (proximal -> distal), +Y up, +X left, -X right. Straight pose, no pitch.
// Keep the STL files beside this file. Bodies are the STEP meshes re-clocked (U -45 deg, M -22.5 deg)
// with rope pads, lane holes, anchor blocks, the 1.85 mm backbone bore and joint holes added.
show_ropes = true;
show_rod = true;
show_springs = true;
show_ends = true;     // base interface (z -20..0) and head adapter (z 576..582)
show_guides = false;  // experimental M5/M6 internal guide spiders (4 per M module)
explode = 0;          // mm between modules, e.g. 20 to see the end disks
$fn = 32;
L = 96;
lanes = [21, 24, 27];                 // A (ends at U4), B (ends at M5), C (ends at M6)
anchor_end = [4*L, 5*L, 6*L];         // distal disk of U4, M5, M6
rays = [0, 90, 180, 270];             // left, up, right, down
parts = ["U_lane_pass.stl", "U_lane_pass.stl", "U_lane_pass.stl", "U4_lane_anchorA.stl", "M5_lane_anchorB.stl", "M6_lane_anchorC.stl"];
function zc(i) = i*(L+explode) + L/2;
for (i = [0:5]) translate([0, 0, zc(i)]) {
    color(i < 4 ? [0.12, 0.48, 0.86] : [0.95, 0.48, 0.12]) import(parts[i], convexity = 12);
    if (show_springs && i < 4) color([0.6, 0.6, 0.6]) import("U_leaf_springs.stl", convexity = 6);
    if (show_guides && i == 4) for (g = [-36, -12, 12, 36]) translate([0,0,g]) color([0.15,0.8,0.85]) one_guide("M5");
    if (show_guides && i == 5) for (g = [-24, 0, 24]) translate([0,0,g]) color([0.15,0.8,0.85]) one_guide("M6");
}
if (show_rod) color([0.3, 0.3, 0.3]) translate([0, 0, 4*(L+explode)]) cylinder(d = 1.8, h = 2*L + explode);
if (show_ropes) for (s = [0:2]) for (a = rays)
    color([[0.95, 0.6, 0.02], [0.02, 0.65, 0.2], [0.8, 0.05, 0.4]][s])
        translate([lanes[s]*cos(a), lanes[s]*sin(a), -20]) cylinder(d = 2, h = anchor_end[s] + 20 + (s+3)*explode);
if (show_ends) {
    color([0.35, 0.35, 0.4]) translate([0, 0, -explode]) import("base_interface.stl", convexity = 8);
    color([0.8, 0.1, 0.1]) translate([0, 0, 6*(L+explode)]) import("head_adapter.stl", convexity = 8);
}
