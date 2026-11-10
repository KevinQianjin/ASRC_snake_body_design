// Medium Stiffness geometry from the uploaded STEP assembly.
// The source STEP axis is already Z; this places the 96 mm module with its
// lower end at Z=0 for inspection. The separate 1.8 mm NiTi backbone, guides,
// and end attachments from the current study are not included here.
translate([0, 0, 48])
    import("Medium_Stiffness_96.stl", convexity = 12);
