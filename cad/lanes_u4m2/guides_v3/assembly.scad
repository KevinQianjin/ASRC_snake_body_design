// V3 engineering candidate. Preview only; not released for manufacture.
// Body/disks/anchors are the unchanged V2 parts. Units: mm.
$fn=48;
show_body=true;
show_ropes=true;
show_backbone=true;
if(show_body) color([0.65,0.72,0.78,0.55])
    import("../guides_v2/M5_preview_cutaway.stl");
for(z=[-24,-12,12,24]) {
    tag=str("M5_z",z>0?"+":"",z);
    translate([0,0,z]) {
        color([1,0.60,0.12]) import(str(tag,"_guide.stl"));
        color([1,0.80,0.35]) import(str(tag,"_caps.stl"));
        color([0.3,0.35,0.4]) import(str(tag,"_wire_envelope.stl"));
    }
}
if(show_backbone) color([0.1,0.35,0.95]) cylinder(d=1.8,h=96,center=true);
if(show_ropes) for(a=[0,90,180,270]) rotate([0,0,a]) {
    color([0.1,0.8,0.4]) translate([24,0,0]) cylinder(d=2,h=96,center=true);
    color([0.95,0.2,0.3]) translate([28,0,0]) cylinder(d=2,h=96,center=true);
}
