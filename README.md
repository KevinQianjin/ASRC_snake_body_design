# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 9 November 2026

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

## Reports

- [**Latest report — 8 November 2026**](Report_2026_11_08.pdf): M module stiffness requirement, NiTi backbone concept, straightening and steering with the backbone, test plan and updated next decisions. Built by [`build_report_2026_11_08.py`](ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_08.py).
- [Report — 6 November 2026](Report_2026_11_06.pdf): design concept, active straightening, tank entry and steering with the current M module; unresolved issues.
- [Report — 5 November 2026](Report_2026_11_05.pdf): earlier design and analysis.

## Current status (8 November 2026)

| Item | 6 November baseline | With 1.8 mm NiTi backbone in M (simulation) |
|---|---|---|
| U4+M2 straightening at 20°, at or below 5% strain | 94.7 mm offset, 61.3°: fails | 1.7 mm, 4.0°, 0.10% strain: **passes** |
| Same at 15° and 25° | Fails | **Passes** |
| Yaw with head held at 20° elevation | No solution found | **0–180°** in 5° steps, **7–15 N** peak tendon (minimum-force, smooth allocation) |
| 3D lateral stability | — | Needs **≥ 1 N pretension on every rope**; all results rechecked with it |
| Full 3D tank check (all tank solids from the STEP file) | Five 2D sections only | Entry clears by 47 / 65 / 19 mm (15/20/25°); at 20° with clamp s = 0–30 mm the **whole yaw sweep clears by ≥ 12.6 mm**; 25° fails at the roof |
| Tank entry screen at ≤ 5% strain (front-only, saved sections) | All low-strain shapes hit the tank | U4+M2 **passes** at 15/20/25° (44 / 64 / 17 mm min gap) |
| U6+M3, U8+M4 straightening | Fail | Still fail with ≤ 3 anchor sets |
| Evidence | Database module properties | Rod properties **calculated only**; module tests next |

**Decision:** develop U4+M2 with a central 1.8 mm NiTi backbone in each M module. Build and test the backbone M module before further simulation refinement.

## Latest studies (8 November 2026)

### M module stiffness requirement

[Study README and files](ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108)

This study scales only M axial stiffness (EA, ×1–×1000) and bending stiffness (EI, ×1–×5) for U4+M2 at 20°.

- Raising EA alone straightens the front, but leaves a **7.1° tangent-error floor**. Between anchor disks, the head weight bends each M module, and that bending is set by M EI.
- The first combination that passes all checks is **EA ×5 (about 830 N) with EI ×1.25 (about 0.055 N·m²)**, anchors [4,5,6]. This is confirmed at 16 cells per module.

![M stiffness requirement](ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108/results/m_stiffness_requirement.png)

### NiTi backbone: straightening, steering and test plan

[Study README and files](ASRC_kevin/telescopic_planar_study/backbone_20261108) · [Build and test plan](ASRC_kevin/telescopic_planar_study/backbone_20261108/M_BACKBONE_TEST_PLAN.md)

A central Ø1.8 mm NiTi rod is added to each M module, including its mass. It is modelled at E = 40 and 75 GPa, giving M EA of 102–191 kN and EI of 0.065–0.083 N·m².

- **U4+M2 passes every straightness check at 15°, 20° and 25°**, with about 1–2 mm offset and about 0.1% strain.
- **U6+M3 and U8+M4 still fail** with ≤ 3 anchor sets. This includes an exhaustive search of every three-set layout.
- **Spatial steering (8 cells per module):** at 20°, yaw reaches the 180° search cap with world head elevation held within 20 ± 5°.
- **Minimum-force follow-up (9 November):** a continuous sweep from 0° to 175° with the head held at exactly 20° needs only **about 7–15 N** peak tendon force (anchors [4,5,6]). The 8 November allocations needed 46–98 N because they maximised angle only.
- **Every rope needs ≥ 1 N pretension.** Without it, the straightened front is laterally unstable in 3D, a mode the 2D model cannot detect. Straightening and tank entry were rechecked with the pretension and still pass.
- **Test plan** covers: rod material, axial and bending stiffness, rod buckling at a 24 mm guide spacing, tendon-driven bending, fatigue, and an integrated U4+M2 check.

![Backbone results](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/backbone_results.png)

![Entry screen](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/entry_screen.png)

![Minimum tendon force](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/minforce_results.png)

*Minimum peak tendon force with the head held at the base pitch while sweeping yaw (9 November).*

![3D tank clearance](ASRC_kevin/telescopic_planar_study/backbone_20261108/results/tank3d_sweep.png)

*Full 3D tank clearance during the held-elevation yaw sweep at 20°, by clamp depth (9 November).*

*Tank entry screen (9 November): the straight rod shape (0.10% strain) feeds through the bottom opening with at least 64 mm clearance at 20°. The current-M low-strain shape hits the tank.*

*Left: U4+M2 actively straightened at 20°, with and without the rod. Right: steering endpoints at 20°; filled markers hold head elevation within 20 ± 5°.*

The 5% strain threshold, 250 N tendon bound and 180° angle cap are numerical diagnostics or search bounds, not validated hardware ratings.

## Next steps

1. Build and test the backbone M module ([test plan](ASRC_kevin/telescopic_planar_study/backbone_20261108/M_BACKBONE_TEST_PLAN.md)), then re-run the backbone studies with measured EA and EI.
2. ~~Minimum-force tendon allocations and path continuity~~ — done on 9 November: about 7–15 N peak, smooth 5° steps from 0° to 175°, and ≥ 1 N pretension needed for 3D stability ([results](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#5-minimum-tendon-force-for-held-elevation-yaw-min_force_sweeppy-2026-11-09)). Open: acceptability of 30–55° twist.
3. ~~Full 3D tank check~~ — done on 9 November: entry and the full yaw sweep clear the 3D tank at 20° with the clamp at s = 0–30 mm. Deeper clamp positions and 25° hit the roof ([results](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#6-full-3d-tank-clearance-tank3d_screenpy-2026-11-09)).
4. ~~Re-run the tank entry screen with the new low-strain straight shape~~ — done on 9 November: U4+M2 with the rod passes at 15–25°, and 20° has the best margin ([results](ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#3-tank-entry-screen-with-the-straight-low-strain-shape-entry_screenpy-2026-11-09)). Next: design entry, storage, sleeve contact and the sensor head envelope (full-width 3D clearance is now covered by item 3).
5. Rear mechanism selection, followed by an integrated 3D tank validation.

## Previous baseline studies (6 November 2026, current M module)

- [Active straightening and tank entry](ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106): U4+M2, U6+M3 and U8+M4 with database properties. Near-straight shapes need 17–28% axial strain. The front-only tank entry screen passes only for high-strain shapes.
- [Spatial steering and tendon forces](ASRC_kevin/telescopic_planar_study/steering_63mm_20261106): U4+M2 reaches about 179° yaw at low strain, but with head elevation at −65.7°. No held-elevation (20 ± 5°) solution was found.

These studies are the controls for the 8 November work. Their no-rod results are reproduced exactly by the new scripts.

## Geometry and input data

- [Telescopic rear and tank geometry study](ASRC_kevin/telescopic_planar_study): tank sections, rear beam calculations and deployment screening. Its top-level README includes earlier geometry assumptions.
- [Module stiffness database](ASRC_kevin/module_stiffness.sqlite3): module mass, EA, EI and torsional stiffness. Use each study's saved input snapshot when reproducing its results.

## Earlier studies

- [H8U12 rear and 500 g head](ASRC_kevin/h8u12_front5to8_payload500g): comparison of 5–8 front modules.
- [Four tendon inverse study](ASRC_kevin/four_rope_inverse_5_to_11): methods, frozen inputs and results.
- [Front module count sweep](ASRC_kevin/front_sweep_5_to_11): comparison of 5–11 front modules.
- [Reach and extension screening](reach_extension_results): earlier passive reach study with different dimensional assumptions.

Start with the 8 November report and the two studies dated 20261108. Earlier results use different geometry or material assumptions and should not be combined directly with the latest baseline.
