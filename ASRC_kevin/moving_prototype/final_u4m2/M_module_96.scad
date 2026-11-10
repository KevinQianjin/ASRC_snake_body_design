// Single full-detail Medium Stiffness module from the uploaded STEP assembly.
// The source STEP axis is already Z; this places the 96 mm module with its
// lower end at Z=0 for straightforward inspection and slicing.
translate([0, 0, 48])
    import("Medium_Stiffness_96.stl", convexity = 12);
