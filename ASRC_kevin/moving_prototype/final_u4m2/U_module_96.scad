// Single full-detail UniDirectional module from the uploaded STEP assembly.
// The source STEP axis is local Y; this places the 96 mm module along +Z with
// its lower end at Z=0 for straightforward inspection and slicing.
translate([0, 0, 48])
    rotate([90, 0, 0])
        import("UniDirectional_96.stl", convexity = 12);
