# Next-run handoff — from the 23 November 2026 Evening Report

Prepared at about **2026-11-23 20:55 EST (2026-11-24 01:55 UTC)** by the evening run. That run started at **2026-11-23 20:01:55 EST (2026-11-24 01:01:55 UTC)**, and its budget deadline is **22:01:55 EST (03:01:55 UTC)**. The final pushed revision is reported in the completion message, which this pre-publication file cannot contain. Checkpoint `caa7ea7` holds the code and results.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_23.md) · [Evidence](README.md) · [Previous handoff (22 Nov evening)](../evening_20261122/HANDOFF.md) · [Round 2 rib/plate model](../rib_joint_3d.py) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (linear solid FE; no hardware)

- **A verified P2 solid FE tool now exists**, with a TetGen mesher and an exact structured prism mesher for the strut ([`strut_fe.py`](strut_fe.py), [`coupled_land.py`](coupled_land.py)).
  - Patch tests pass to 3·10⁻⁸ or better.
  - The bond-point field is mesh-converged to 0.14%.
  - Coupled-station wrench closure is 10⁻¹¹.
  - The 22 November `rod` and `rigidland` rows are reproduced exactly.
- **Driving a single strut at its cut faces with the rod map is over-constrained.** The eight driven struts carry 30–35× the rod model's cell bending moment (19.7 vs 0.65 N·m at step 1,709, z = −12 mm). Free-strut and coupled-station tractions (126 MPa peak, 44 MPa area-mean axial shear; 1.2° guide rotation) are **not** design values.
- **Topology:** each bonded 8.0 mm² strut is the arm of a zig-zag rib. It runs from the hub disk (z ≈ −5.5 mm) to a knee at r ≈ 30.6 mm, z ≈ −20.3 mm, and continues through a 4.89 mm² member towards z ≈ −35 mm (mirrored at +12 mm). The arm's outer end is not a rigid section.
- **The rod map distorts the arm walls around the guide** by 0.050–0.054 mm inside the land and 0.30–0.37 mm at the ±1.62 mm socket ends (67.5° and 247.5° arms). Those are 2× and 10× the crowned-land clearance margins of 0.0284 / 0.0424 mm.

- **Clearance bracket (tonight, [`rigid_arm_probe.py`](rigid_arm_probe.py)).** With an undeformed body around the guide, the worst gap at 0.2° tilt is 0.0789 mm (uncrowned) and 0.0804 mm (crowned) at both stations. Against the rod-mapped body it was 0.0007 / 0.0283 mm (z = −12 mm) and 0.0172 / 0.0440 mm (z = +12 mm). The crown's benefit is a rod-map effect.

## Priorities

1. **Solid rib-lattice model between the Round 2 masters, validated first (simulation, one full run).**
   *Why:* only this model can decide the bond demand (`rigidland` 2–4 MPa vs kinematic tens to hundreds of MPa), and only it can say whether the 0.028 mm clearance margin is real.
   *How:*
   - Solid-mesh one complete M6 rib (all members of one angular rib, from D0 to the R1 disk, or the whole half-module) using the masters of [`rib_joint_3d.setup`](../rib_joint_3d.py):
     - D0: z ≤ −45 mm, or r < 3.3 mm with z < −30 mm;
     - hub rings R_k: r < 8.6 mm at z ∈ [−20, −16.95] and [−6.5, −3.45] mm.
   - Treat the masters as rigid. The Round 2 rings are free; the disks follow the rod map.
   - First stage, before any tractions: reproduce the plate model's bare-body EI (46,700 N·mm², Round 2 `m6_support.json`) and the rod cell stiffness (5.394 N·m/rad per 12 mm cell, so EI ≈ 64,700 N·mm²). If the solid and plate stiffness disagree by more than about 30%, resolve that first.
   - A P2 mesh of the whole module lattice (about 13,000 mm³ outside the end disks) is too large for SuperLU in one run. Use one rib with cyclic or plane-symmetry conditions, or condense each rib, or use an iterative solver (`scipy.sparse.linalg.cg` with an AMG preconditioner such as `pyamg`).
   - Then bond the guide with the distributed crowned layer of [`coupled_land.py`](coupled_land.py), which can be reused.
   *Acceptance:*
   - Body EI within 30% of the plate model.
   - Mesh-converged area-mean and land-edge tractions at step 1,709 (and 1,885) at G = 500 / 1,500 MPa.
   - The guide motion and rotation relative to its land.
   - A statement of which 22 November mismatch model the result is closest to.
2. **Re-check the crowned clearance against a solid-arm geometry (simulation, about 30–40 min once item 1 exists).**
   *Why:* the 0.0284 / 0.0424 mm certified margins sit below the rod map's own non-rigid distortion of the arm walls (0.05 mm in the land, 0.37 mm at the socket ends).
   *How:* replace `deformed_body` (rod map) around the guide with the item-1 solid displacement of the arm, then rerun [`../evening_20261122/bond_tilt_probe.py`](../evening_20261122/bond_tilt_probe.py) at steps 1,709, 1,710 and 1,885. Both brackets already exist: the undeformed body (tonight, about 0.079–0.080 mm) and the rod map (archived, 0.0007–0.044 mm).
   *Acceptance:* the minimum gap at 0.2° tilt at both stations with the solid arm, compared with both brackets. State whether the crown is still needed.
3. **Bench (hardware, unchanged from the 21 and 22 November handoffs).**
   *Acceptance:*
   - Tilt ≤ 0.20° and offset ≤ 0.025 mm at both stations, with the land profile measured to 0.01 mm.
   - A lap-shear coupon of the chosen adhesive on PA12 at a 0.25–0.31 mm gap.
   - **Add:** a strain gauge or DIC on one M6 arm next to the land while the module is bent to the step-1,709 curvature (about 6–8° per 12 mm cell). This directly separates the rod map from real arm deformation.

   Do not report this item as completed in simulation.

The previous item 3 (mission-wide first-contact tilt at 5° axis spacing) is **deferred**. It still relies on the rod-mapped arm geometry that item 2 questions.

## Blockers and resources

- 4 cores and 15 GB of memory. One P2 strut at about 50–75k DOF factorises in about 10–60 s with SuperLU (`MMD_AT_PLUS_A`). A 4-strut coupled station with 45k layer points per land took about 6 min. The h = 0.45 mm TetGen struts (about 74k DOF) used several GB while eight were held.
- `tetgen` 0.8.4 segfaults when given a background sizing mesh (`bgmesh` with `pyvista` 0.49.2). Use the structured prism mesher, or uniform `a` volume switches.
- Install with `python -m pip`. On top of the 22 November list you need `tetgen`, `triangle`, `numba` (needed by the replay import chain) and, optionally, `pyvista`. `pillow` needs `--ignore-installed` over the broken system PIL.
- `codex/m5-active-reset-load-export` is still unmerged and has no committed results. It was not duplicated.
- The adhesive, as-printed land, bonded tilt and bond strength are unmeasured. The crowned candidate is not a manufacturing release.
