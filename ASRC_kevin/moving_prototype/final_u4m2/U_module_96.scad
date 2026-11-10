// UniDirectional module from the uploaded STEP assembly.
// The source STEP axis is local Y; this places the 96 mm module along +Z with
// its lower end at Z=0. The source assembly contains five separate solids.
// Set component_to_show to 1..5 to inspect/export one solid at a time; 0 shows
// the complete positioned module assembly.

component_to_show = 0; // [0:5]

module u_component(part_number) {
    translate([0, 0, 48])
        rotate([90, 0, 0])
            import(str("UniDirectional_96_part_0", part_number, ".stl"), convexity = 12);
}

assert(component_to_show >= 0 && component_to_show <= 5, "component_to_show must be 0..5");
if (component_to_show == 0) {
    for (part_number = [1 : 5]) u_component(part_number);
} else {
    u_component(component_to_show);
}
