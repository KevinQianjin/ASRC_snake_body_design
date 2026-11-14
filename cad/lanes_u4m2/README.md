# Lane-routed U4+M2 front (newest design, 13 Nov 2026)

**14 November validation update:** the [V2 guide candidate](guides_v2/README.md) fixes unsupported inner clips at the ±12 mm stations, widens the B–C lane spacing and includes CAD-estimated masses in a new 500 g simulation. Its straight assembly passes, but rigid guide/web interference in bent poses prevents manufacturing release. See the [full validation report](../../simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md). The build guide below describes the earlier geometry and is not a release approval for V2.

**To build it, follow [`BUILD_GUIDE.md`](BUILD_GUIDE.md).** It covers printing, purchased parts, springs, backbone, joints, rope threading and anchoring, tensioning and the checks before first use.

This folder has every part needed for the U4+M2 front:
- continuous 96 mm modules U1–U4, M5, M6, with no pin joint and no gap;
- three rope sets on their own radial lanes;
- a 1.8 mm NiTi backbone through M5 and M6;
- the base interface and the head adapter.

The modules are built by `build_lane_modules.py` from the uploaded STEP meshes in `../previews/u4m2/`, which are left untouched. `build_ends_and_check.py` builds the two end parts and checks the whole assembly; the result is in `assembly_check.json` (all pass). `lane_assembly.scad` shows the full stack in OpenSCAD (`explode = 20` separates the parts). `lane_disks.png` and `end_parts.png` show the faces.

| File | Qty | Used as | Lane holes | Anchor | Centre |
|---|---:|---|---|---|---|
| `base_interface.stl` | 1 | 20 mm block between the rear beam and U1 | A, B, C | – | solid |
| `U_lane_pass.stl` | 3 | U1, U2, U3 | A, B, C | – | solid (no rod in U) |
| `U4_lane_anchorA.stl` | 1 | U4 | A, B, C | A, distal disk (radial loop) | solid (rod end stop) |
| `M5_lane_anchorB.stl` | 1 | M5 | B, C | B, distal disk | **Ø1.85 bore for the Ø1.8 rod** |
| `M6_lane_anchorC.stl` | 1 | M6 | C | C, distal disk | **Ø1.85 bore** |
| `head_adapter.stl` | 1 | 6 mm plate between M6 and the head | – | closes the C anchors | 1 mm rod-end relief |
| `U_leaf_springs.stl` | reference | the 4 NiTi springs of one U (16 in total) | | | |

Frame: Z is the module axis (proximal → distal), +Y is up, +X is left and −X is right. Every lane lies on one of the four rays (up, right, down, left). Lane radii: A 21 mm, B 24 mm, C 27 mm.

## What changed from the STEP bodies

1. **Re-clocking (required).** In both STEP bodies the spring strips sit on the
   0/90/180/270° rays, which is exactly where the ropes have to run. Without re-clocking,
   every lane runs through material (clearance −0.02 to −0.04 mm, `lane_design.json`).
   The fix is to rotate each body about its axis: U by −45° and M by −22.5°. After that,
   every straight rope between two disks has a clear corridor:

   | Lane | U, left/right rays | U, up/down rays | M, all rays |
   |---|---|---|---|
   | A 21 mm | 11.5 mm | 4.6 mm | 5.5 mm (A does not run in M) |
   | B 24 mm | 14.5 mm | 4.1 mm | 6.7 mm |
   | C 27 mm | 16.6 mm | 4.1 mm | 7.8 mm |

   Rotating U by −45° also puts its leaf-spring diagonal, which is its stiff
   direction, on ±Y. That gives the high vertical bending stiffness the simulation
   assumes. Check this against the U designer's intent.
2. **Solid end disks (13 Nov, later).** Every 3 mm end disk is now a full round plate (r 31.45 mm). All the STEP notches, the 2 mm-deep blind slots (curved strip-root reliefs, U diagonal slots) and the unused 8.4 mm U centre hole are filled. The only holes left are: lane holes, anchor grooves + return holes, the M backbone bore, the 4 joint holes, and the U leaf-spring pockets (re-cut to the exact spring shape). U1–U3 disk: 12 lane + 4 joint holes + 4 spring pockets. U4 distal: the same plus 4 return holes and grooves. M5 distal: 8 lane + 4 return + 4 joint + bore. M6 distal: 4 lane + 4 return + 4 joint + bore. Filling the strip-root reliefs bonds each strip root to the disk over 3 mm instead of 1 mm, which may stiffen the module slightly near its ends. This is untested: compare one printed module with the stiffness database before relying on the simulation numbers.
3. **Rope pads.** The end disks were notched exactly where the corridors are, so each ray has a
   3 mm pad (radial 18.5–29.5 mm, 7 mm wide); since the disks are now solid, the pads only matter
   for the anchor blocks. Lane holes are Ø2.5 mm (2 mm rope + 0.5 mm) with 0.25 mm entry chamfers,
   which keeps a wall between lanes at the 3 mm pitch. Holes exist only for the sets that still
   pass through that module.
4. **Backbone hole sized to the rod.** In M5 and M6 the 8.4 mm passage is plugged (Ø8.6) and bored
   Ø1.85 mm for the Ø1.8 mm NiTi rod. A Ø6 × 12 mm sleeve inside each end disk gives the rod
   15 mm of support per end. A 3 mm disk alone cannot clamp the rod in rotation, so without the
   sleeve the rod would add little bending stiffness. The interior is free up to r ≈ 8 mm
   there, so the sleeve touches no strip. The U centre hole is filled because no rod runs
   there; head wiring has to run outside the modules or through a hole added later.
5. **Anchor blocks.** On the distal disk of U4 (A), M5 (B) and M6 (C), the pad is 7 mm deep: the
   3 mm disk plus 4 mm of free space inside the module. Each has a 2.2 × 2.2 mm groove on the
   distal face and a Ø2.5 return hole. For B and C the groove runs tangentially, with the return
   hole 5 mm beside the lane. For A it runs **radially inward**, with the return hole 3.5 mm inside
   the lane at r 17.5 mm. This keeps the U4 block narrow: a tangential block came within 0.3 mm of
   the leaf springs, the radial one leaves more than 1.5 mm.
6. **Joint holes.** 4 holes at r = 12.5 mm on the four rays, through both disks. The left/right
   holes are Ø1.9 pilots, reamed for Ø2 dowel pins: press fit on distal faces, slip fit on
   proximal faces. The up/down holes are Ø2.2 for M2 screws. An M2 nut fits on the inner face of
   every hole in every module (checked).
7. **Leaf-spring pockets.** Each pocket is the spring end shape + 0.1 mm per side (7.05 × 6.33 mm).
   It goes through the proximal disk, so the strip slides in from that face, and is a 2 mm blind
   pocket in the distal disk. The strip is bonded with epoxy at both ends.

Minimum wall between neighbouring lane holes is 0.5 mm (3 mm pitch − 2.5 mm hole).
No existing slot comes closer. 0.5 mm is thin for SLS PA12. If the printer cannot hold
it, use 2.3 mm holes (0.7 mm wall) or move the lanes to a 3.5 mm pitch (21/24.5/28 mm,
and re-run `lanes_study.py --radii 21 24.5 28`). All parts stay within the source
envelope (max radius 31.66 mm, the same as the STEP bodies).

## Rope anchors and module joints (summary; details in BUILD_GUIDE.md)

- **Rope anchor:** a crimp cannot sit on a lane, because 3 mm lane pitch leaves no room for a
  stop wider than about 2.9 mm. Each rope therefore comes up its lane, lies in the groove on the
  anchor disk's distal face (flush), goes back down the return hole, and is crimped (sleeve OD
  ≤ 3.5 mm) against the inner face. The groove bridge carries the load; fit-test one at 50 N.
- **Module joint:** rigid, end disk to end disk, no gap. 2 × Ø2 × 8 mm dowels (left/right) set the
  clocking so all rope holes line up; 2 × M2 × 10 screws (up/down) clamp, with nuts inside the
  module. The base interface and the head adapter use the same pattern, with counterbores for the
  screw heads.
- **Backbone:** one 192 mm Ø1.8 NiTi rod through M5 and M6, bonded over 15 mm at each module end
  (bore + sleeve). It stops against U4's solid distal centre and the head adapter's relief.
- **Mounting:** 4 × M3 heat-set inserts on the diagonals: base rear face at r 17 mm, head adapter
  front face at r 20 mm. These are placeholder patterns; match them to the real rear beam and head.

## Does it work? (checks done)

- Simulation with the lanes (`simulations/u4m2/lanes_20261113/lanes_study.py`): all 32
  startup states and all 36 yaw holds (0–175°) pass. The peak tension drops slightly
  (17.4 → 16.4 N) and stability margins rise slightly. The reference round trip passes every
  check: 1101 states, peak 16.5 N, minimum 2.73 N, clearance 20.1 mm. Closed loop: all five cases (nominal,
  E75, 550 g head, 1.5 m free rope, 80 % rope EA) complete and every settled sample passes. The 550 g
  head still has 48 transient states above 1° (max 2.32°, previously up to 3.8°) at 174–178° yaw
  (`simulations/u4m2/lanes_20261113/README.md`).
- **Intermediate M rope guides are now an experimental candidate.** A 24 mm maximum-span
  guide layout routes each M5/M6 rope through four internal guide stations at local z =
  −24, −12, +12 and +24 mm. The stations were selected by checking the guide mesh against both
  STEP-derived M body meshes; the generated guide meshes are watertight and have zero measured
  intersection at all four selected straight-pose locations. The stations at ±36 mm collide
  and are intentionally not used.
- On saved nominal, yaw, round-trip and 550 g payload bends, the idealized guided rope chord screen
  estimates a remaining lateral corridor margin of 3.8 mm (M5 B), 4.8 mm (M5 C) and 7.1 mm
  (M6 C). With no internal guides, the corresponding M5 estimates are about −25.5 mm, which means
  the chord model crosses the static corridor. These are geometric screening estimates; the guide
  mounts are not yet included in deformed-solid contact, friction, wear or stiffness simulations.
  The printable concept is in `internal_rope_guide.scad`; the mesh/station check is
  `build_rope_guides.py`. Treat it as an instrumented prototype, not an approved production part.
- NiTi rod strain at the largest M5 bend (103° over 96 mm, uniform curvature) is about 1.7%,
  within the superelastic range (~6%).
- Not checked: printed-part strength (0.5 mm walls, anchor bridges), rope friction, the
  stiffness after re-clocking and filling, and the extra part mass (M about +5 g each) in the
  simulation. See BUILD_GUIDE.md, sections 10–11.
