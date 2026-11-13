# Lane-routed U4+M2 modules (newest design, 13 Nov 2026)

These are the 3D modules for the current design: continuous 96 mm modules
U1–U4, M5, M6 (no pin joint, no gap), three rope sets on their own radial lanes,
and a 1.8 mm NiTi backbone through M5 and M6. They are built from the uploaded
STEP meshes in `../previews/u4m2/`, which are left untouched, by
`build_lane_modules.py`. Open `lane_assembly.scad` in OpenSCAD with the STL files beside it
(`explode = 20` separates the modules so the end disks are visible).
`lane_disks.png` shows the end-disk faces.

| File | Used as | Lane holes | Anchor | Centre hole |
|---|---|---|---|---|
| `U_lane_pass.stl` | U1, U2, U3 | A, B, C | – | none (filled; no rod in U) |
| `U4_lane_anchorA.stl` | U4 | A, B, C | A at the distal disk | none (filled) |
| `M5_lane_anchorB.stl` | M5 | B, C | B at the distal disk | **1.85 mm bore for the 1.8 mm rod** |
| `M6_lane_anchorC.stl` | M6 | C | C at the distal disk (head side) | **1.85 mm bore** |
| `U_leaf_springs.stl` | the 4 NiTi leaf springs of every U | – | – | – |

Frame: Z is the module axis (proximal → distal), +Y is up, +X is left and −X is right.
Every lane is on the up, left, down and right rays. Lane radii: A 21 mm, B 24 mm, C 27 mm.

## What changed from the STEP bodies

1. **Re-clocking (required).** In both STEP bodies the spring strips sit on the
   0/90/180/270° rays, which is exactly where the ropes have to run. Without re-clocking,
   every lane runs through material (clearance −0.02 to −0.04 mm, `lane_design.json`).
   The fix is to rotate each body about its axis: U by −45° and M by −22.5°. After that,
   every straight rope between two disks has a clear corridor:

   | Lane | U, left/right rays | U, up/down rays | M, all rays |
   |---|---|---|---|
   | A 21 mm | 11.5 mm | 4.6 mm | 5.5 mm |
   | B 24 mm | 14.5 mm | 4.1 mm | 6.7 mm |
   | C 27 mm | 16.6 mm | 4.1 mm | 7.8 mm |

   Rotating U by −45° also puts its leaf-spring diagonal, which is its stiff
   direction, on ±Y. That gives the high vertical bending stiffness the simulation
   assumes. Check this against the U designer's intent.
2. **Solid end disks (13 Nov, later).** Every 3 mm end disk is now a full round plate (r 31.45 mm). All the STEP notches, the 2 mm-deep blind slots (curved strip-root reliefs, U diagonal slots) and the unused 8.4 mm U centre hole are filled. The only holes left are: lane holes, anchor grooves + return holes, the M backbone bore, the 4 joint holes, and the U leaf-spring pockets (re-cut to the exact spring shape). U1–U3 disk: 12 lane + 4 joint holes + 4 spring pockets. U4 distal: the same plus 4 return holes and grooves. M5 distal: 8 lane + 4 return + 4 joint + bore. M6 distal: 4 lane + 4 return + 4 joint + bore. Filling the strip-root reliefs bonds each strip root to the disk over 3 mm instead of 1 mm, which may stiffen the module slightly near its ends. This is untested: compare one printed module with the stiffness database before relying on the simulation numbers.
3. **Rope pads.** The end disks are notched exactly where the corridors are, so each ray gets a
   3 mm pad in the notch (radial 18.5–29.5 mm, 7 mm wide). Lane holes are Ø2.5 mm (2 mm rope +
   0.5 mm) with 0.5 mm entry chamfers. Holes exist only for the sets that still pass through
   that module.
4. **Backbone hole sized to the rod.** In M5 and M6 the 8.4 mm passage is plugged (Ø8.6) and bored
   Ø1.85 mm for the Ø1.8 mm NiTi rod. A Ø6 × 12 mm sleeve inside each end disk gives the rod
   15 mm of support per end. A 3 mm disk alone cannot clamp the rod in rotation, so without the
   sleeve the rod would add little bending stiffness. The interior is free up to r ≈ 8 mm
   there, so the sleeve touches no strip. The U centre hole is filled because no rod runs
   there; head wiring has to run outside the modules or through a hole added later.
5. **Anchor blocks.** On the distal disk of U4 (A), M5 (B) and M6 (C), the pad is 7 mm deep:
   the 3 mm disk plus 4 mm of free space inside the module. It has a groove and a return hole,
   described below.
6. **Joint holes.** 4 × Ø2.2 mm at r = 12.5 mm on the four rays, through both disks. These
   are free inside both bodies for the nut and screw head.

Minimum wall between neighbouring lane holes is 0.5 mm (3 mm pitch − 2.5 mm hole).
No existing slot comes closer. 0.5 mm is thin for SLS PA12. If the printer cannot hold
it, use 2.3 mm holes (0.7 mm wall) or move the lanes to a 3.5 mm pitch (21/24.5/28 mm,
and re-run `lanes_study.py --radii 21 24.5 28`). All parts stay within the source
envelope (max radius 31.66 mm, the same as the STEP bodies).

## How to connect a rope to its module (anchor)

A crimp stop cannot sit on a lane. With only 3 mm between lanes, any ferrule or knot
wider than about 2.9 mm would break into the next lane's hole. So each rope ends with a
**loop through two holes**:

1. Thread the rope from the winch up its lane through every disk up to the anchor module's
   distal disk (U4 for A, M5 for B, M6 for C).
2. On the distal face, lay it in the tangential **groove** (2.2 mm wide × 2.2 mm deep, 5 mm long).
   It then sits flush, so the next module's disk can close over it.
3. Pass it back down the **return hole** (Ø2.5, 5 mm beside the lane) into the space inside
   the module.
4. On the inner face, crimp a stop (e.g. a Ø3.5 mm aluminium or copper ferrule for 2 mm rope).
   A stopper knot plus a drop of cyanoacrylate also works. Pre-stretch the PA6 rope first,
   then crimp at the 3 N pretension length.

The rope tension (up to 16.5 N in the cycles, 3 N minimum) is carried by the groove bridge
in bending and partly by friction. The crimp only sees what is left, and nothing sits in a
neighbouring lane. Fit-test one anchor block at 3× the peak load (~50 N) before trusting
the printed bridge.

## How to connect modules to each other

The joint is **rigid, end disk to end disk, no gap**, matching the continuous model:

- **Clocking/alignment:** the four joint holes and the lane holes line up by construction.
  Ream two opposite joint holes and fit Ø2 mm dowel pins (press in one module, slip in the
  other). They set the clocking, so the lane holes stay coaxial across the joint, and they
  take shear.
- **Clamping:** M2 socket screws through the other two holes, nuts on the inner face of the
  next module. Use thread-locker. For the joints that carry the largest bending moment (U4–M5
  and M5–M6), prefer four M2 screws plus two Ø2 dowels added on the 45° diagonals at r 12.5 mm
  (check these against the strips first; the build script only verifies the four ray positions). The joint must not open under the bending moment: a gap would change the rope
  lengths.
- **Backbone across M5–M6:** run one continuous 192 mm Ø1.8 NiTi rod through the M5 and M6
  bores, or one rod per module. Bond it in each 15 mm bore+sleeve with retaining compound or
  epoxy after roughening the NiTi; a cross-pinned collar also works. Keep it straight at
  assembly. Its proximal end stops in the U4/M5 joint (the U4 distal disk has the 8.4 mm hole).
- **Order:** assemble the six modules dry (pins + screws), then thread the ropes from the base,
  one set at a time (C first, being outermost and longest), and terminate at the anchors.
- Do not glue or bolt anything through the rope pads; keep the chamfered lane entries clean.

## Does it work? (checks done)

- Simulation with the lanes (`simulations/u4m2/backbone_20261108/lanes_study.py`): all 32
  startup states and all 36 yaw holds (0–175°) pass. The peak tension drops slightly
  (17.4 → 16.4 N) and stability margins rise slightly. The reference round trip passes every
  check: 1101 states, peak 16.5 N, minimum 2.73 N, clearance 20.1 mm. Closed loop: all five cases (nominal,
  E75, 550 g head, 1.5 m free rope, 80 % rope EA) complete and every settled sample passes. The 550 g
  head still has 48 transient states above 1° (max 2.32°, previously up to 3.8°) at 174–178° yaw
  (study README, section 14).
- **Limit found: rope chords in M5/M6 at large yaw.** The ropes are guided only at the end disks,
  so inside a bent module each rope is a straight chord. U modules bend ≤ 7.3°, so their chords
  stay within 0.2 mm of the lane. M5 bends 14° at the 0° hold, 25° at 15° yaw, 40–65° at 20–90° yaw
  and up to 103° at 175° yaw. M6 bends up to 40°. The chord leaves its lane by 4 mm at the hold,
  7 mm at 15° yaw, 11–18 mm at 20–90° yaw and 33 mm at 175° yaw. The M corridor clearance is
  5.5–7.8 mm, so the M5 ropes would rub the spring strips beyond roughly 15° yaw. The
  shared-hole layout has the same problem. To steer further, the M modules need intermediate
  rope guides (e.g. guide rings on the strips at the module's ¼, ½ and ¾ length). The model must
  then route the ropes through those guides instead of straight disk-to-disk chords.
  `rope_chord_check.py` measures this.
- NiTi rod strain at the largest M5 bend (103° over 96 mm, uniform curvature) is about 1.7%,
  within the superelastic range (~6%).
- Not checked: printed-part strength (pads, 0.5 mm walls, anchor bridges), friction at the
  chamfers, and real stiffness after re-clocking.
