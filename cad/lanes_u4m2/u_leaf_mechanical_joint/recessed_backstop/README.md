# U1 single-leaf joint with recessed proximal backstop

The updated shoe transfers compression from the NiTi heel into the PA12 lip on its own end disk. The underlying U1 lane-routed body, all four NiTi leaves and the U1 mating base supply the fit geometry. Only the positive-X, positive-Y leaf gets two mechanical seats in this trial. The distal key and blind floor follow the first fit design. The changed proximal dimensions and geometry are specific to this trial.

[Proximal CAD sections](results/U1_compression_sections.png) · [Bench fixture layout](results/U1_bench_fixture.png) · [Nominal fit checks](results/verification.json) · [500 g mission assessment](../../../../simulations/u4m2/lanes_20261113/closeout_20261128/README.md)

## Mechanical changes and measured CAD clearances

The proximal screw and nut move from y = 21.12 to 20.10 mm at x = 6.40 mm. The shoe has a 0.80 mm thick bridge and a relieved retainer eye. The wings engage the flanks of the PA12 lip. The screw remains engaged with the shoe and key laterally through the available axial play. Its countersunk head seats in the PA12. The outside disk surface is d = 0 and d increases into the module. Proximal z = −48 + d and distal z = +48 − d in the U module frame.

| Nominal straight CAD check | Result |
|---|---:|
| NiTi heel to proximal shoe, followed by shoe to lip | 0.060 + 0.050 mm |
| Outward travel of the shoe before it reaches the seated head | 0.160 mm |
| Outward travel of the shoe before it reaches either tested mating face | 0.140 mm |
| Recess at first lip contact, also the gap to a flush mating disk | 0.090 mm |
| Shortest gap to the seated head at first lip contact | 0.07776 mm |
| Nominal backed area of the shoe wings on the lip | 13.417 mm² |
| Nominal near-end reversal / both ends in an aligned series | 0.360 / 0.610 mm |
| Lateral movement before the seated shank captures the key / loaded shoe | 0.1001 / 0.1103 mm |
| Minimum gap from changed proximal solids to reserved straight Ø2 mm ropes | 2.710 mm |

The previous seated-head trial engaged the head at zero shoe stroke. If the head was replaced by a fixture pin, the same shoe touched the mating face after 0.080 mm, ahead of the PA12 lip at 0.120 mm. The stated gaps in the table include the revised compression stop in both the actual U1 base and the orientation of a preceding unmodified U distal face. Twenty-five aligned axial contact states showed no penetration above 0.00001 mm³. The U1 and U4 proximal insertion sweeps also cleared the other leaves and the reserved rope and bore volumes. The original inboard route was screened for cutting. [First trial](../README.md) · [Earlier reversal study](../bench_reversal/README.md)

The central bridge addresses contact order and fit. Edge loading, lip bending, pretension, PA12 creep, retained torque, fretting and accumulated play can change the order under load. The two sub-0.1 mm gaps must be checked on the printed and machined parts. U4 clearance is a proximal donor/access comparison.

## Print and buy for one fit assembly

| Item | Qty | Preparation |
|---|---:|---|
| [Recessed proximal PA12 coupon](results/U1_proximal_recessed_coupon.stl) and [distal PA12 coupon](results/U1_distal_coupon.stl) | 1 each | Print with the intended PA12 process, print orientation and conditioning. Clean transverse slots and both test-flange holes. Measure lip and rail before use. |
| [Complete U1 body STL](results/U1_one_leaf_trial_body.stl) | 1 optional | Print separately for nominal body/base stack fit after the coupon check. The small local features are used on one leaf only. |
| [Proximal shoulder key STEP](results/proximal_shoulder_key.step) | 1 | Prototype machining with a smooth R0.25 mm working edge. Preserve the edge radius during deburring. |
| [Proximal shoe STEP](results/proximal_backstop.step) | 1 | Prototype machining of the one-piece relieved shoe. Verify the 0.80 mm bridge, lip-side bearing faces and the head relief. |
| [Distal shoulder key STEP](../results/shoulder_key.step) | 1 | Use the original distal key. Its retainer screw offset differs from the updated proximal key. |
| [Original NiTi leaf STEP](../../../manufacturing_setup/U_leaf_spring_02.step) | 1 | Form the original 94 mm leaf, source solid 3. Rotate +90° about X then −45° about Z to compare with the selected corner of the [clocked assembly](../../guides_v2/U_leaf_springs.stl). |
| Countersunk screw and square nut | 2 sets | Trial envelopes use M1.6 × 8, Ø3.20 × 0.80 mm head with a nominal 90° countersink, and 3.20 mm square × 1.30 mm nut. Check usable thread engagement, actual head shape and seat depth against the supplier drawing. |
| Fixture components | 1 set | Two registered plates, rigid base, anti-rotation linear carriage with push/pull actuation, bidirectional load cell, displacement indicator for spacing and independent optical tracking across the local joint. Use interchangeable proximal relief plate and solid mating-face witness. |

For a first comparison make three near/far coupon pairs, one extra proximal coupon and one rigid dummy link for fixture calibration. Where repeated or destructive tests are planned use separate specimens. All STL and STEP dimensions are in millimetres. The metal surface STLs are alignment/inspection aids. The native STEP files govern the quote.

## Assembly and low-force measurement

1. Align both PA12 coupon faces 96.00 mm apart in a common x/y frame. The two Ø3.2 mm holes are at x = 1.2 and 11.5 mm, y = 12.5 mm. Keep the clamp plates clear of the shoe and the load line through the leaf end centres (x ≈ 7.5 mm, y ≈ 26.4 mm). Leave side access for the key and shoe at +Y and the nut at +X.
2. With both keys, the shoe and the screws removed, feed the leaf through the near coupon to the distal seat. Confirm its keyed shoulder and its clocking with the section drawing. Slide the keys in from +Y, working edges facing the thin span. Insert the proximal shoe from +Y, bridge facing the outside plane and wings captured in the pocket.
3. Slide the nuts in from +X. Install the recessed screws from the outside and confirm seating, thread engagement, tool access and installed gaps. At zero load place a straightedge over each disk face and measure head and shoe recess. Repeat with the mating CAD witness or the real base in place. Measure the as-built parts before assuming the nominal reserve.
4. Remove the face witness for initial optical access. Calibrate the displacement and force channels with the rigid link, aiming for ≤0.005 mm and ≤0.05 N resolution. With tension positive and displacement control active, screen three slow reversals at ±2 N and re-inspect. If the displacement loop and engagement are repeatable, run three more at ±5 N. Record force, face spacing, both blade ends, shoe, screw and lip position referenced to each coupon. Watch for permanent set, PA12 lip opening, leaf bowing and loose hardware. Stop on a force excursion or visible damage.
5. In compression the heel should move the shoe until it stops on the PA12 lip. At that load the head and the mating face should retain positive gaps. Include a second low-load check with the actual mating face installed once the free-fit motion has been measured. Use the tension and compression intercepts of the measured force–displacement ramps to estimate backlash and the slopes to estimate branch stiffness. Include resolution, repeats and fixture compliance in the reported uncertainty.

[Specimen and fit worksheet](results/u1_specimen_blank.csv) · [Raw force and motion worksheet](results/u1_trace_blank.csv)

The archived roughly 214 N reaction is from a different blade clocking and from a specific restraint model. Use the low-force trial to establish the actual load path before specifying a separate supported single-end strength specimen or cycling under service loads. The full U1 joint law requires the as-built backlash, stiffness, creep, torque retention and mass. The geometry screen supports printing the trial coupons.

## Reproduce

The U1 CAD uses the repository inputs at `d9347e87ab3612342962125580187523a0b42fd5`. Run `python build_recessed.py` then `python draw_fixture.py` in this directory with Python 3.12, NumPy, manifold3d, trimesh, CadQuery and Matplotlib. The builder checks STL watertightness and native STEP solid validity. The shoulder key and shoe STEP volume differences from the faceted checks are 0.00093 and 0.00242 mm³, respectively.
