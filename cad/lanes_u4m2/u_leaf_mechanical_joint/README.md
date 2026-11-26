# U leaf mechanical joint: first fit coupons

This candidate captures the shaped ends of one original NiTi leaf with PA12 seats, a removable shoulder key and a proximal backing shoe. It replaces the two adhesive interfaces on the selected leaf. The deliverables are suitable for a fit trial and planning instrumented loads. Load capacity, installed stiffness, endurance and the full 500 g mission with these joints remain open.

## Parts for one near/far trial

| Item | Quantity | Use |
|---|---:|---|
| [Proximal PA12 coupon](results/U1_proximal_coupon.stl) and [distal PA12 coupon](results/U1_distal_coupon.stl) | One of each | Print in the intended production PA12 process, orientation and conditioning. Each STL is one watertight solid with a fixture flange. Keep the two test holes accessible. Remove powder from transverse slots before fitting. |
| [Shoulder key STEP](results/shoulder_key.step) | 2 | One per end. Quote a smooth metal prototype; a polymer mock-up can check fit. Preserve the R0.25 working edge and deburr the edges facing NiTi. The projected dimensions and screw hole are in the STEP. |
| [Proximal backstop STEP](results/backstop.step) | 1 | A one-piece stepped metal shoe. The asymmetrical side wings enter grooves behind the outer-face lips. The central bridge is 0.80 mm thick. Obtain machining and inspection feedback on the thin webs before a loaded test. |
| Original 94 mm NiTi leaf | 1 | Use [leaf 02 STEP](../../manufacturing_setup/U_leaf_spring_02.step), source solid 3. Rotating the source +90° about X then −45° about Z puts it at +X,+Y in the [clocked four-leaf CAD](../guides_v2/U_leaf_springs.stl). The two short `leaf_reference` STLs are section gauges for orientation. |
| Screw and square nut | 2 sets | Trial envelope for an M1.6 × 8 countersunk screw, 90° head, Ø3.20 mm head, and a 3.20 mm square × 1.30 mm nut. Match actual supplier drawings and check seating before machining or loading. The assembly model uses unthreaded envelopes. Torque, thread retention and vibration resistance require tests. |

[Near-end sections](results/U1_proximal_sections.png) · [Far-end sections](results/U1_distal_sections.png) · [U4 anchor overlay](results/U4_anchor_access.png) · [Machine-readable verification](results/verification.json)

All STLs and STEPs use mm. The mating face of each coupon is at depth **d = 0** and depth increases into the module. For a module-frame location use z = −48 + d at the proximal end and z = +48 − d at the distal end. Local x and y retain the published module clocking. A slicer may recenter individual files. Keep native coordinates to inspect the assembly; orient individual fabrication jobs separately.

## Retention and assembly

1. Align the two datum faces 96 mm apart in a straight fixture with a common x/y origin. Clamp the test flanges independently. The two Ø3.2 mm fixture holes are at x = 1.2 and 11.5 mm, y = 12.5 mm. Gripping loads enter through a test-only flange outside the joint. Coupon restraint differs from that of a complete disk.
2. With both keys and the backstop out, feed the full blade axially from the proximal side until its distal heel seats against the original blind floor. At d = 2 mm the selected end lies at x = 5–10 mm, y = 23.405–29.405 mm. The single working shoulder faces the key; use the sections to check the blade handedness.
3. Slide each key from +Y toward −Y behind the shoulder, rounded working edge toward the thin span. At the proximal end insert the backing shoe from the same side, bridge toward the mating face and wings beneath the disk lips. The shoe bears against outward motion of the heel. The blind floor performs this function at the far end.
4. Slide each square nut from +X into its pedestal. Insert the screw from the outer disk face while the module is accessible. The preformed nut slot restrains rotation. The same screw blocks lateral withdrawal of the key and, at the near end, the shoe. Confirm that the head seats below the datum face, the bit engages and the nut has full usable thread engagement. Characterise preload and loss of retention on samples.
5. Measure the force–displacement loop in both directions and axial end play before applying the service load. Backlash is material to control accuracy. The blade-to-key gap is 0.13 mm, the key has 0.12 mm travel to the rail, and the near heel-to-shoe and shoe-to-lip gaps are each 0.12 mm. A freely floating, unpreloaded proximal joint can have approximately **0.49 mm reversal travel** between the two bearing limits. The distal blind heel seats at nominal zero. Head preload, friction, tolerance and load sharing can change these values. Measure each joint and a complete U before accepting this boundary condition in the robot model.

Under pull, the intended bearing path is NiTi shoulder → key → PA12 rail → end disk. Under push, the proximal heel loads the bridge, wings and disk lips, while the distal heel loads the blind floor. Actual screw loading depends on fit and preload. All checks below use the straight, unloaded geometry.

## Geometry and U4 clearance

Baseline engineering revision `8ef0fe02d19fe0358ddea9709e895a1b0dc63b4a`. The builder directly reads both lane-routed body STLs, the clocked NiTi STL and the lane definitions. It crops each coupon from its own modified end and adds a test-only gripping flange. Assembly and U4 access checks use full bodies without the flange. Only the +X,+Y leaf has modified seats. The other three leaves are present as obstacles. The archived CAD, free span, 21/24/28 mm lane centres and head payload remain the reference for this trial.

| Nominal quantity | Result |
|---|---:|
| NiTi shoulder bearing area on key / key bearing area on rail | 19.63 / 17.02 mm² |
| Near heel area on bridge / wing area backed by PA12 lips | 28.82 / 13.42 mm² |
| Slot side wall / rail roof at the documented section | 0.70 / 1.61 mm |
| Web between key and nut slot / roof over nut slot | 1.50 / 0.82 mm |
| Near shoe outer lip / original distal blind floor | 1.48 / 1.00 mm |
| New PA12 net volume, proximal / distal, one attachment each | +146.79 / +215.09 mm³ |
| U4 distal, modified solids to protected A-anchor block / swept access to block | 0.650 / 0.700 mm |
| U4 distal, modified solids to Ø3 mm bore-mouth envelopes / Ø2 mm straight ropes | 2.650 / 3.150 mm |
| U4 distal, modified solids to Ø3.5 × 6 mm axial tail-sleeve envelope | 2.506 mm |

The support widths above are section or projected-area measurements. The builder ray-tests these specific chords. They do not define a minimum thickness everywhere. The 0.70 mm side wall and 0.82 mm nut-slot roof are candidates for printing and depowdering trials. In the first layout the A-anchor reserve gap was only 0.18 mm and the shoe wings were backed over 7.01 mm². Moving the boss boundary away from the anchor, lengthening the key rail and widening the inner portion of the shoe wing produced the reported geometry.

For U1 and U4 the builder tests continuous, straight insertion sweeps of the complete blade, keys, shoe, nut and screw, plus a Ø4.4 mm axial bit approach. Convex component sweeps conservatively bound solid travel; the blade hull includes the space between its two thick ends. Designed tangencies at the distal heel and countersink are allowed. Penetration above 0.00001 mm³ fails the run. Separate virtual over-travel checks confirm that the shoulder engages the key, the key engages the rail and both compressive stops engage. These are geometric witnesses. The four U4 anchor blocks are reserved in full, including the material around the groove and return hole. Tail sleeves are screened as axial cylinders at the return bores. Lateral crimp motion, actual driver tip and handle, crimp pliers, misaligned installation, deformed bodies and simultaneous modifications to the other leaves require additional checks.

## Load tests and decision points

The archived maximum **213.616 N** is a resultant reaction at one blade end in the U1 step 1,510 restraint sweep (sampled blade index 2, tab stiffness 10,000 N/mm, cage fraction 1). Its axial component is +212.842 N. That index identifies the archived load case; applying it to this +X,+Y coupon is an envelope test. [Assembly and tab reactions](../../../simulations/u4m2/extreme_tests/round2_20261119/results/u_structure/u_assembly.json) · [Published target table](../../../simulations/u4m2/extreme_tests/design_limit_sweep_20261122/component_stress_sweep.csv)

| Isolated axial bearing screen | At 213.6 N | At 320.4 N | At 427.2 N |
|---|---:|---:|---:|
| NiTi shoulder on key, 19.63 mm² | 10.9 MPa | 16.3 MPa | 21.8 MPa |
| Key on rail, 17.02 mm² | 12.6 MPa | 18.8 MPa | 25.1 MPa |
| Backstop wings on proximal lips, 13.42 mm² | 15.9 MPa | 23.9 MPa | 31.8 MPa |

These values simply divide an assumed axial force by projected area in the applicable load direction. Edge contact, eccentricity, bending, lip breakout, nut-pocket damage, PA12 creep and NiTi fretting can govern earlier. No strength factor or life has been demonstrated.

- **Fit test:** inspect actual wall thickness, edge radius, debris, clearance and shoulder coverage. Document insertion in both coupons without forced blade straightening, flush screw heads, repeatable seating and clean withdrawal after unloading.
- **Single-end static test:** use actual NiTi and machined candidate retainers. Use separate specimens for the two load directions and for overload. Begin below service, then test the archived load orientation and bending moment once recovered from the matching frame. A pure axial pull/push is a fixture shakedown. Record head/rail/lip motion and permanent set after unloading; stop on cracking, disengagement or a migrating retainer. Investigate 320.4 N and 427.2 N only after reviewing the preceding level. Measure the failure load on a dedicated specimen as appropriate.
- **Reversal and dwell:** use independently printed specimens in the intended orientation/condition. Record joint stiffness, backlash, wear at the shoulder, preload loss and residual slip with calibrated displacement measurement. Establish allowable play from the head-direction and tension error budget; the nominal 0.49 mm stack makes that check especially important.
- **Before four-leaf or whole-robot adoption:** measure free span, bending stiffness in both axes and zero return on one fully assembled U. Map all eight seats per module, check tool access with neighbouring hardware, use actual masses and measured joint laws in the controller/clearance replay across the 3,405 states. A 500 g head is the retained payload constraint. Weigh the additional retainers and body material separately.

## Reproduction

Run Python 3.12 from this study directory with the packages in [verification.json](results/verification.json) and the four published input files in the sibling `guides_v2` directory. Use `python build.py` and allow about one to two minutes on two CPU cores. The script rebuilds all geometry, writes the three figures, tests engagement and insertion, and reopens each STL and both analytic STEPs. The input SHA-256 checksums identify the exact meshes and lane configuration used. The metal STEP round-trip volumes agree with their respective faceted screening shapes to within 0.003 mm³. Inspect the console exit status together with the JSON when reproducing this study.
