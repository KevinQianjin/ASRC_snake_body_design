// Installed 96 mm U module. Use F5 for the material colours.
// Keep this file beside the original body and spring STLs. Coordinates are mm.
module_body = "U1-U3"; // [U1-U3, U4]
show_part = "assembly"; // [assembly, body, springs]

assert(module_body == "U1-U3" || module_body == "U4", "Select U1-U3 or U4");
assert(show_part == "assembly" || show_part == "body" || show_part == "springs",
       "Select assembly, body or springs");

if (show_part != "springs") {
    color("#a8b4bf")
        if (module_body == "U4")
            import("U4_lane_anchorA.stl", convexity = 12);
        else
            import("U_lane_pass.stl", convexity = 12);
}

// This single reference mesh contains two pairs, with two NiTi strips per pair.
if (show_part != "body")
    color("#543398") import("U_leaf_springs.stl", convexity = 8);
