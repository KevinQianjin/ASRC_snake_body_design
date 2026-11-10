// NON-FINAL PLACEHOLDER: generic rigid shells and pin joints, not the soft U/M body.
// Do not treat this model or its STL exports as the final robot design.
include <module_common.scad>;
base_pitch = 20;
show_tendons = true;
joint_1 = 0; // [-25:1:25]
joint_2 = 0; // [-25:1:25]
joint_3 = 0; // [-25:1:25]
joint_4 = 0; // [-25:1:25]
joint_5 = 0; // [-25:1:25]
module at_next_link(angle_deg, show_tendons=true) {
 translate([0,0,module_pitch]) { joint_cable_bridge(angle_deg,show_tendons); rotate([angle_deg,0,0]) children(); }
}
module full_chain() {
 module_link("U",1,true,false,show_tendons);
 at_next_link(joint_1,show_tendons) {
  module_link("U",2,false,false,show_tendons);
  at_next_link(joint_2,show_tendons) {
   module_link("U",3,false,false,show_tendons);
   at_next_link(joint_3,show_tendons) {
    module_link("U",4,false,false,show_tendons);
    at_next_link(joint_4,show_tendons) {
     module_link("M",5,false,false,show_tendons);
     at_next_link(joint_5,show_tendons) {
      module_link("M",6,false,true,show_tendons);
      translate([0,0,90+head_ring_length]) head_placeholder();
     }
    }
   }
  }
 }
}
rotate([-base_pitch,0,0]) { translate([0,0,-20]) base_interface(); full_chain(); }
