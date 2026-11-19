// M5 retained rotating guide prototype. Dimensions in mm, station plates centred at z = +/-12.
// Choose "module", "upper station", "lower station", or "single seat".
view = "module";
show_body = true;
mount = [-22.5, 67.5, 157.5, 247.5];
function side(z) = z > 0 ? "+12" : "-12";
module part(name, shade) {
    color(shade) import(str("parts/", name, ".stl"), convexity=20);
}
module screw_at(x,y) {
    translate([x,y,0]) part("hub_screw", "#415a71");
}
module seat(z) {
    part(str("fork_",side(z)), "#f2a840");
    part(str("gate_",side(z)), "#28a491");
    part("shoulder_pin", "#3876a4");
    part("threaded_cap", "#315874");
}
module station(z) {
    translate([0,0,z]) {
        for (i=[0:7]) {
            rotate([0,0,45*i]) part(i%2==0 ? "hub_upper_sector" : "hub_lower_sector", i%2==0 ? "#8da6b5" : "#b2c4ce");
            rotate([0,0,45*i+22.5]) translate([9.60,0,0]) part("lap_screw","#536679");
        }
        for (a=mount) rotate([0,0,a]) {
            seat(z);
            screw_at(9.68,-2.73);
        }
        for (a=[0:90:270]) rotate([0,0,a]) {
            part("rope_arm", "#db7148");
            screw_at(9.68,0);
        }
    }
}
if (view=="module") {
    if (show_body) part("M5_machined_body", "#dbd8d1");
    station(-12);
    station(12);
} else if (view=="upper station") {
    station(12);
} else if (view=="lower station") {
    station(-12);
} else if (view=="single seat") {
    seat(12);
}
