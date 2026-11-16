# End-exit bellmouth candidate v1 (M5/M6) — 15 November 2026 evening run

**Engineering candidate; not released for manufacture.** Geometry only: no
printed tolerance, strength, wear, friction or rope-qualification evidence.

## What changed and why

The V2 lane holes in the rigid M5/M6 end regions are Ø2.5 mm bores (only
0.25 mm radial play for the Ø2 mm rope) that end at the inboard faces in a
0.25 mm × 45° chamfer:

| End region | Interface face | Inboard face | Rigid bore length |
|---|---:|---:|---:|
| Proximal disk | z = −48 mm | z = −45 mm | 3 mm |
| Distal anchor block + disk | z = +48 mm | z = +41 mm | 7 mm |

The rope cannot turn inside such a bore. It follows the bore axis across the
bolted joint and turns where it leaves the inboard face. Without a radius it
turns over the sharp 0.25 mm chamfer edge. This candidate adds an
**axisymmetric convex fillet (bellmouth)** to each inboard lane-hole exit. The
fillet is tangent to the bore at depth `h_b = R_w·sin(θ_d)` and reaches the
design wrap angle `θ_d` at the inboard face:

| Exit | Lanes | Fillet wall radius R_w | Rope centreline radius | Design wrap θ_d | Hole Ø at inboard face |
|---|---|---:|---:|---:|---:|
| M5 proximal (z −45) | B, C | 6.0 mm | 7.0 mm | 19° | 3.140 mm |
| M5 distal (z +41) | B, C | 3.9 mm | 4.9 mm | 29° | 3.456 mm |
| M6 proximal (z −45) | C | 7.0 mm | 8.0 mm | 18° | 3.172 mm |
| M6 distal (z +41) | C | 7.0 mm | 8.0 mm | 18° | 3.172 mm |

The wrap angles cover the largest exit deflection in the 217 saved 500 g V3
equilibria plus a 1° margin. The worst case is 27.09° at the M5 distal C/up
exit. This is the inner rope on the concave side, where the 17 mm span to the
+24 mm guide is short. The M5 distal radius is limited by the same-ray B (24 mm)
to C (28 mm) bridge. The minimum bridge falls from 1.058 mm with the chamfers
to **0.544 mm** at the inboard face (target ≥ 0.5 mm). This wall is as thin as
the existing 0.5 mm A–B disk wall, which still needs printer qualification.

Unchanged: lanes A/B/C 21/24/28 mm, rays, guide stations −24/−12/+12/+24 mm
and V3 guide parts, outer interface faces and their chamfers, return holes,
anchor grooves, backbone bores and supports, joint holes, outer envelope and
the 500 g head. No backbone end ferrule is added.

## Files

| File | Role |
|---|---|
| [design.json](design.json) | Exit parameters and assumptions |
| [build.py](build.py) | Cuts the fillets from `../guides_v2` bodies (manifold Boolean) and writes the checks |
| `M5_lane_anchorB.stl`, `M6_lane_anchorC.stl` | Candidate bodies; use with the V3 guide parts in [../guides_v3](../guides_v3/README.md) |
| [geometry_check.json](geometry_check.json) | Watertightness, component count, volume removed, section diameters and B–C bridges |

## Checks

- Both bodies are watertight, consistently wound and remain **one component**.
  Their bounds are identical to V2. The fillets remove 31.73 mm³ (M5) and
  14.87 mm³ (M6), about 0.05 g of PA12 in total. The mass model and solver mass
  inputs are **not** updated for this negligible change.
- Section diameters at 0.02 mm, mid-fillet and below the fillet match the
  nominal profile to ≤ 0.002 mm (128-sided cutter). Below the fillet, all lane
  bores remain Ø2.5 mm.
- Rejected construction: the first M6 trial used 12° and 10° wraps. Those
  fillets were smaller than the existing face chamfer and produced a
  non-watertight body with 33 components. The final M6 exits use 18°.

## Limitations

- The fillet is axisymmetric, so it also enlarges directions that need less
  wrap. An asymmetric or slotted exit could restore some B–C bridge.
- The rope centreline radius of 4.9–8 mm is a geometric choice. The repository
  rope is an uncalibrated PA6 surrogate, so no D/d rating, wear or capstan
  friction is claimed. Friction on the fillets is absent from the rod model.
- The rod solver still pivots the rope at the module interface. The exit-pivot
  path is 0.005–0.307 mm longer per rope across M5+M6. This mismatch must be
  added to the solver routing before a new closed-loop replay; see the
  [evening evidence](../../../simulations/u4m2/lanes_20261113/evening_20261115/README.md).
- U4 distal exits, where ropes B/C leave U4 towards M5, were not checked.
