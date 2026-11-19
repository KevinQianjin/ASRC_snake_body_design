// M5 seat coupon. All dimensions in mm. View "assembled" or "exploded".
view = "assembled";
explode = view == "exploded" ? 1 : 0;
$fn=64;

function along() = 1.4706/sqrt(1+1.4706*1.4706);
function rise() = 1/sqrt(1+1.4706*1.4706);
module delivered(name, shade) {
    color(shade) import(str("parts/",name,".stl"), convexity=16);
}
module production(name, shade, dz) {
    translate([0,0,dz*explode]) color(shade)
    multmatrix([[along(),0,rise(),-along()*19.229],[-rise(),0,along(),rise()*19.229],
                [0,-1,0,0],[0,0,0,1]])
    import(str("../retained_seat_20261118/parts/",name,".stl"),convexity=20);
}
translate([0,0,-6*explode]) delivered("coupon_carrier","#718893");
translate([0,0,5*explode]) {
    delivered("tab_cover","#8ba1ab");
    mirror([1,0,0]) delivered("tab_cover","#8ba1ab");
}
delivered("web_coupon","#e5a35a");
translate([0,-9*explode,0]) delivered("pin_carriage","#489c91");
production("shoulder_pin","#346fa0",12);
production("threaded_cap","#274b67",-12);
for (x=[-6.7,6.7]){
    translate([x,0,-4.70-4*explode]) color("#667783") cylinder(h=6,d=2);
    for(y=[-4.05,4.05]){
        color("#516371") translate([x,y,8*explode]){
            translate([0,0,-8]) cylinder(h=12,d=2);
            translate([0,0,4]) cylinder(h=2,d=3.80);
        }
        color("#516371") translate([x,y,-7.1-9*explode])
            difference(){cylinder(h=1.60,d=8/sqrt(3),$fn=6);translate([0,0,-0.1]) cylinder(h=1.8,d=2.03);}
    }
}
