# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 10 November 2026

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

## Reports and presentation

- [**Daily report — 10 November 2026**](Report_2026_11_10.pdf): coordinated winch control between the 5° poses (smooth, stable, reversible; winch command tables) and winch position error sensitivity (about ±0.2–0.5 mm per winch for ±1°; head-angle feedback recommended). Built by [`build_report_2026_11_10.py`](ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_10.py).
- [Daily report — 9 November 2026](Report_2026_11_09.pdf): tank entry with the low-strain shape, 3D stability and pretension, minimum tendon force for held-elevation yaw, full 3D tank clearance, and horizontal flexibility (side-rope pull). Built by [`build_report_2026_11_09.py`](ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_09.py).
- [**Presentation — latest results, 9 November 2026**](ASRC_Presentation_2026_11_09.pptx): slide deck summarising the problem, the NiTi backbone fix and all results to date.
- [Report — 8 November 2026](Report_2026_11_08.pdf): M module stiffness requirement, NiTi backbone concept, straightening and steering with the backbone, and the module test plan.
- [Report — 6 November 2026](Report_2026_11_06.pdf): design concept, active straightening, tank entry and steering with the current M module; unresolved issues.
- [Report — 5 November 2026](Report_2026_11_05.pdf): earlier design and analysis.

## Current status (10 November 2026)

All results below are simulations for **U4+M2 with a central 1.8 mm NiTi rod in each M module**, compared with the 6 November design. Rod properties are calculated, not yet measured.

| Check | 6 November design (current M) | With 1.8 mm NiTi rod |
|---|---|---|
| Straightening at ≤ 5% strain, 15–25° | 90–99 mm offset: **fails** | 1.2–2.0 mm offset, about 0.1% strain: **passes** |
| Tank entry, 2D sections and full 3D | Every low-strain shape hits the tank | **Passes**: 47 / 65 / 19 mm minimum clearance at 15 / 20 / 25° |
| 3D lateral stability | — | Needs **≥ 1 N pretension on every rope**; with it, all cases are stable |
| Yaw with the head held at 20° | No solution found | **0–175°** in smooth 5° steps at **7–15 N** peak rope force |
| Coordinated winch (rope-length) control between poses | — | **Smooth, stable and reversible** over 0–175° at 19.2–20.1° elevation; no slack rope; winch travel ≤ 69 mm |
| Winch position error | — | ±1° head angle needs about **±0.2–0.5 mm on every winch** (±0.16 mm near 175°); the 4 tip winches dominate; rope EA ±10% gives ≤ 0.4°. Stable in all cases, but 1 N pretension ropes go slack beyond about 0.15 mm error: **use head-angle feedback** |
| Yaw sweep inside the full 3D tank | — | At 20° with the clamp 0–30 mm past the opening: **clear by ≥ 12.6 mm**; 25° hits the roof |
| One side rope pulled (winch control) | — | About **1.25° yaw per mm**, smooth and stable; holds 20 ± 5° elevation only to **about ±20°** |
| Tension-only rope control | — | Straight front **snaps** (258 mm jump at +0.5 N): **use rope-length control** |
| Longer fronts U6+M3, U8+M4 | Fail | Still fail with ≤ 3 anchor sets |

**Decisions:** develop U4+M2 with the 1.8 mm NiTi backbone. Install at **20°**, steer with the clamp **0–30 mm** past the opening, keep **≥ 1 N** on every rope, and drive the ropes by **length (winch position)**, coordinating the up and side ropes to hold the working elevation. Build and test the backbone M module next.

## Latest studies

### 10 November 2026: coordinated winch control and winch accuracy

**Winch accuracy** ([section 9](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#9-winch-position-error-and-rope-stretch-sensitivity-winch_sensitivitypy-2026-11-10)):

- One winch off by 1 mm moves the head 1.3–3.2°. All 12 winches off by up to ±1 mm at random give up to 1.9–6.3° (99%).
- Holding ±1° open-loop needs about ±0.2–0.5 mm per winch. The four tip (anchor 6) winches matter most, and rope stiffness calibration hardly matters.
- Every perturbed state stays stable, but 1 N pretension ropes can go slack. Head-angle feedback and a higher pretension are recommended.

![Winch sensitivity](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/winch_sensitivity.png)

**Coordinated winch control:**

[Study README, section 8](ASRC_kevin/telescopic_planar_study/backbone_20261108)

All 12 winches follow the rope lengths of the 5° minimum-force poses together, in 20 sub-steps per segment.

- The head moves smoothly from 0° to 175° (40 GPa rod) or 180° (75 GPa rod) while staying at 19.2–20.1° elevation.
- Every one of the 701 / 721 states is stable, no rope goes slack, and the motion is identical forward and backward.
- The in-between states clear the 3D tank by at least 12.6 mm.
- The largest winch travel is 69 mm, and the anchor-4 ropes barely move.
- Winch command tables are saved as CSV.

![Coordinated winch](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/coordwinch.png)

### 9 November 2026: entry, stability, tendon force, 3D tank and horizontal flexibility

[Study README, sections 3–7](ASRC_kevin/telescopic_planar_study/backbone_20261108)

- **Tank entry:** the straight low-strain rod shape feeds through the bottom opening at 15–25°, re-checked at 16 cells per module. The current-M low-strain shape hits the tank.

  ![Entry screen](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/entry_screen.png)

- **3D stability:** with only the up ropes pulled, the straight front is laterally unstable in 3D. A 1 N pretension on every rope stabilises it, and straightening and entry still pass.
- **Minimum tendon force:** holding the head at 20° while sweeping yaw needs about 7–15 N peak (anchors [4,5,6]), against 46–98 N for the 8 November allocations. With smoothing, no rope changes by more than about 5 N per 5° step. Beyond about 90° the front curls up and back over itself, and it uses 30–55° of twist at mid yaw.

  ![Minimum tendon force](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/minforce_results.png)

- **Full 3D tank:** all 362 tank solids were meshed from the STEP file, which agrees with the saved 2D sections within 0.23 mm. Entry is confirmed across the full front width. At 20° with the clamp 0–30 mm past the opening, the whole yaw sweep clears the tank by at least 12.6 mm on both sides.

  ![3D tank clearance](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/tank3d_sweep.png)

- **Horizontal flexibility:** reeling in only the tip's right rope turns the head about 1.25° per mm. The head droops beyond about 20° of yaw unless the up ropes are reeled in together with it. Anchors 4 and 5 hardly turn the head. Tension-only control makes the straight front snap.

  ![Side pull](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/sidepull.png)

### 8 November 2026: M stiffness requirement and NiTi backbone

- [M stiffness requirement sweep](ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108):
  - Raising M axial stiffness alone leaves a 7.1° tangent-error floor.
  - The first passing combination is **EA ×5 (about 830 N) with EI ×1.25 (about 0.055 N·m²)**, anchors [4,5,6].
- [NiTi backbone study](ASRC_kevin/telescopic_planar_study/backbone_20261108) and [build and test plan](ASRC_kevin/telescopic_planar_study/backbone_20261108/M_BACKBONE_TEST_PLAN.md):
  - The Ø1.8 mm rod gives M an EA of 102–191 kN and an EI of 0.065–0.083 N·m² (E = 40–75 GPa).
  - With it, U4+M2 passes straightening at 15–25° and reaches 180° yaw at held elevation.

![M stiffness requirement](ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108/results/m_stiffness_requirement.png)

![Backbone results](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/backbone_results.png)

The 5% strain threshold, 250 N tendon bound and 180° angle cap are numerical diagnostics or search bounds, not validated hardware ratings.

## Next steps

1. **Build and test the backbone M module** ([test plan](ASRC_kevin/telescopic_planar_study/backbone_20261108/M_BACKBONE_TEST_PLAN.md)): EA, EI, rod buckling at the guide spacing and rod joint slip. Then re-run the studies with the measured values.
2. ~~Coordinated winch-control test~~ — done on 10 November: smooth, stable and reversible ([results](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#8-coordinated-winch-control-between-poses-coordinated_winchpy-2026-11-10)). Winch accuracy studied on 10 November: about ±0.2–0.5 mm per winch for ±1° open-loop, so add head-angle feedback ([results](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#9-winch-position-error-and-rope-stretch-sensitivity-winch_sensitivitypy-2026-11-10)). Next: test 3–5 N pretension against rope slack, and add friction to the rope model.
3. **Tank-aware steering:** optimise postures with the 3D tank as a constraint, and check the 30–55° twist against hardware limits.
4. **Entry, storage and sensor head:** real head CAD and cable envelopes, sleeve contact, rear storage and retraction.
5. **Rear mechanism and integrated validation.**

## Previous baseline studies (6 November 2026, current M module)

- [Active straightening and tank entry](ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106): near-straight shapes need 17–28% axial strain, and only high-strain shapes pass the entry screen.
- [Spatial steering and tendon forces](ASRC_kevin/telescopic_planar_study/steering_63mm_20261106): U4+M2 reaches about 179° yaw at low strain, but with head elevation at −65.7°. No held-elevation solution was found.

These studies are the controls for the 8–9 November work, and their results are reproduced exactly by the new scripts.

## Geometry and input data

- [Telescopic rear and tank geometry study](ASRC_kevin/telescopic_planar_study): tank sections, rear beam calculations and deployment screening. The 3D tank model is `ASRC_kevin/telescopic_planar_study/inputs/tank-v2.step`.
- [Module stiffness database](ASRC_kevin/module_stiffness.sqlite3): module mass, EA, EI and torsional stiffness. Use each study's saved input snapshot when reproducing its results.

## Earlier studies

- [H8U12 rear and 500 g head](ASRC_kevin/h8u12_front5to8_payload500g): comparison of 5–8 front modules.
- [Four tendon inverse study](ASRC_kevin/four_rope_inverse_5_to_11): methods, frozen inputs and results.
- [Front module count sweep](ASRC_kevin/front_sweep_5_to_11): comparison of 5–11 front modules.
- [Reach and extension screening](reach_extension_results): earlier passive reach study with different dimensional assumptions.

Start with the 10 November report, the 9 November report and the presentation. Earlier results use different geometry or material assumptions and should not be combined directly with the latest baseline.
