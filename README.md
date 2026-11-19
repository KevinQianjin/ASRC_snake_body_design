# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 19 November 2026, full yaw and vertical-pitch cycle with twelve-rope tension

Times in reports, updates and scheduled handoffs use **US Eastern Time
(America/New_York)** and include the equivalent **UTC** timestamp. Use EST
(UTC−05:00) or EDT (UTC−04:00) according to the date; see
[time and provenance conventions](docs/time_conventions.md).

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

## Daily updates

The latest update is detailed below. Earlier dates have short summaries and links to the full reports and research history. All results described here are simulations unless explicitly stated otherwise.

### 19 November 2026 — 500 g full cycle with +90° and −90° pitch

The 500 g U4+M2 simulation executed **1,380 targets and 3,405 motion states** through loaded straightening, insertion, +175°/−175° yaw, **+90°/−90° pitch**, neutral returns and withdrawal. The upward and downward endpoint pointing errors were **0.081° and 0.079°**. The eight-cell operating assessment passed, with 0 failed motion substeps and 0 unsettled or failed targets.

- The trace contains all **40,860 rope tensions**, corresponding winch lengths, head pose and clearance. The ideal force range was **2.901–21.554 N**, and adjusted body clearance stayed at or above **8.056 mm**. Select any of the twelve ropes in the 3-D viewer to see its path and load.
- At +90° the C-up rope carried 21.20 N. At −90° the C-down rope carried 16.81 N. In a separate steady-sliding comparison at assumed μ = 0.15, the weakest distal rope across the four turning commands reached 1.15 N. The measured coefficient and force through reversal are still needed. [Winch-side and distal forces](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/sliding_turn_tensions.csv)
- At unchanged actual commands, refining to sixteen cells changed the up/down pointing directions by 0.00017/0.00051°. Finite rope/end CAD, six guide stations, the actual adapter and directional friction have separate checks. As-built friction, guide stiffness and the sensor housing still limit hardware validation.
- The P3 coupon fixture reduces locating-pilot free reversal from 0.05964 to 0.01966 mm. The measurement log is still empty. [Fixture CAD and test evidence](simulations/u4m2/lanes_20261113/p3_pin_fixture_20261119/README.md)

[Full engineering report](reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [Both vertical poses and loads](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/pitch_poles.svg) · [Twelve-rope event table and curves](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [3-D rope viewer](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) · [Data and commands](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/README.md)

### 19 November 2026 — M5 seat bench fixture, coupled guide and shared rope bore

The paired-load fixture and coupon established the bench procedure. A 0.15 mm hub-edge chamfer left at least 0.0629 mm in six selected M5 bent endpoints. All 217 fixed-winch holds converged after the four C ropes gained lateral freedom at the M5/M6 interface. The predicted minimum tank gap after allowance was 7.737 mm. [Detailed report](reports/daily/M5_Seat_and_Shared_Bore_2026_11_19.md) · [Fixture and forms](simulations/u4m2/lanes_20261113/m5_seat_bench_20261119/README.md) · [Hub CAD](cad/lanes_u4m2/m5_hub_relief_20261119/README.md) · [Shared-bore routing](simulations/u4m2/lanes_20261113/shared_bore_20261119/README.md)

### 18 November 2026 — M5 retained-seat CAD and loaded contact checks

Created the retained M5 seat, trimmed the fork after uncovering a returning-web collision and identified a 0.044 mm nominal rib-to-hub gap. A low side-drive exterior cleared the 16 hub screws in CAD. The 19 November work adds a coupon, a shared-guide model and a hub edge change.

[Full English test report](reports/daily/M5_Retained_Seat_2026_11_18.md) · [CAD, exploded view and sections](cad/lanes_u4m2/retained_seat_20261118/README.md) · [Results and reproduction](simulations/u4m2/lanes_20261113/m5_retained_seat_20261118/README.md)

<a id="18-november-2026--evening-report-retained-rotating-seat"></a>

### 18 November 2026 — Evening Report: sizing the M5 rotating seat

The six-case shell study found that the original V3 land interferes with a rotating web. A pivot-centred bow-tie cavity, a 0.20 mm running gap and an ideal spherical pin release gave +0.058 to +0.107 mm of local wall clearance. This provided the sizing inputs for the later physical-CAD follow-up.

[Full English Evening Report](reports/daily/Evening_Report_2026_11_18.md) · [Evening evidence](simulations/u4m2/lanes_20261113/evening_20261118/README.md) · [Evening handoff](simulations/u4m2/lanes_20261113/evening_20261118/HANDOFF.md)

<a id="18-november-2026--validation-test-plan-for-the-500-g-front"></a>

### 18 November 2026 — Large-rotation test of the M5 guide joint (test 1)

A geometrically nonlinear shell model of the actual M5 ribs compared bare ribs, a bonded guide and a rotating seat. At 96.19° the holding couples were 743.3, 761.5 and 808.2 N·mm (the seat is 5.8% below the bond). The seat land force of 24.78 N is 4.67× the linear estimate. The saved holds 146, 141, 47 and 64 give up to 15.40 N, 5.03° and 0.330 mm socket travel. The same day the five-test validation plan was added.

[Full English test report](reports/daily/M5_Joint_Test_2026_11_18.md) · [Curves, reactions and reproduction commands](simulations/u4m2/lanes_20261113/m5_large_rotation_20261118/README.md) · [Five-test validation plan](docs/500g_validation_plan.md) · [Current limitations](docs/limitations.md)

<a id="17-november-2026--evening-report-latest-rib-level-model-of-the-guide-joint"></a>

### 17 November 2026 — Evening Report on the M5 guide joint

The model built from the eight actual ribs predicts that rigid bonding increases M5 body bending stiffness by 10.4% and torsional stiffness by 11.8%. A seat that allows rotation has a smaller effect on bending but needs about 12.5 degrees of travel. The linear result at the most bent hold calls for a large-rotation check.

[Full English Evening Report](reports/daily/Evening_Report_2026_11_17.md) · [Evidence and commands](simulations/u4m2/lanes_20261113/evening_20261117/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261117/HANDOFF.md) · [Summary figure](simulations/u4m2/lanes_20261113/evening_20261117/rib_joint_3d/rib_joint_summary.png)

### 16 November 2026 — Evening Report: full-coverage guide/web compatibility and a 0.25 mm bond-gap candidate

Start/cutoff **20:02:13 EST (17 November 01:02:13 UTC)**. A calibrated signed-distance screen of all **217 holds × 8 guides** found V3 body contact in **59/217** records (worst −0.0211 mm). A **0.25 mm** land bond gap cleared all 1736 checks and the Booleans. Its homogenised bond-shear estimate (35%) is superseded by the 17 November rib-level model above.

[Full English Evening Report](reports/daily/Evening_Report_2026_11_16.md) · [Evidence and commands](simulations/u4m2/lanes_20261113/evening_20261116/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261116/HANDOFF.md) · [Comparison figure](simulations/u4m2/lanes_20261113/evening_20261116/compatibility_comparison.svg)

### 16 November 2026 — Morning Report: bellmouth routing in the equilibrium solver

Start/cutoff **07:19:33 EST (12:19:33 UTC)**. Connected the bellmouth geometry to rope energy and loads with endpoint-consistent paths: **217/217** fixed-winch holds solve, head change up to **3.479 mm / 1.147° yaw**, and **0/5208** finite-rope end failures. Simultaneous guide load tables were exported. Six targeted V3 mount contacts persisted at 0.25 mm; the Evening Report above extends that check to every hold.

[Full English Morning Report](reports/daily/Morning_Report_2026_11_16.md) · [Evidence and commands](simulations/u4m2/lanes_20261113/morning_20261116/README.md) · [Morning handoff](simulations/u4m2/lanes_20261113/morning_20261116/HANDOFF.md) · [Pose comparison](simulations/u4m2/lanes_20261113/morning_20261116/path_comparison/pose_changes.svg)

### 15 November 2026 — Evening Report: finite-rope exits and bellmouth CAD

Added the full 2 mm rope envelope and M5/M6 bellmouth bodies. Constructed rigid-end paths passed 5208 end checks, but had not been integrated into the equilibrium solver. The 16 November Morning Report adds endpoint-consistent paths and re-solved holds while retaining physical contact limitations.

[Full Evening Report](reports/daily/Evening_Report_2026_11_15.md) · [Bellmouth CAD](cad/lanes_u4m2/end_bellmouth_v1/README.md) · [Archived evidence](simulations/u4m2/lanes_20261113/evening_20261115/README.md)

### 15 November 2026 — Morning Report: refined CAD screening and V3 saddles

Corrected coarse-surface collision measurements and developed V3 flared sockets. All straight checks passed, but guide/body contact remained in 55/217 selected records; joint strength and finite rope routing were unresolved.

[Full Morning Report](reports/daily/Morning_Report_2026_11_15.md) · [V3 CAD](cad/lanes_u4m2/guides_v3/README.md) · [Archived evidence](simulations/u4m2/lanes_20261113/guided_refinement_20261115/README.md)

### 14 November 2026: guided 500 g paths and a rejected rigid-mount candidate

Validated ideal guided startup and a complete 500 g closed-loop cycle, corrected archive coverage, and produced the V2 mounting CAD and guide loads. Physical mounting and finite end routing failed their separate checks. The 15 November Morning Report refines the coarse CAD collision screen; retain the older numbers as a dated snapshot.

[Full validation report](simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) · [V2 CAD](cad/lanes_u4m2/guides_v2/README.md) · [Archived evidence](simulations/u4m2/lanes_20261113/guided_validation_20261114/)

### 13 November 2026: separate rope lanes and build package

Separated the three rope sets onto 21/24/27 mm lanes, regenerated the module bodies, end disks, anchors, backbone supports and interfaces, and documented assembly. Endpoint-only simulations passed their settled checks, but large M-module bends exposed rope/strip interference and motivated intermediate guides. These are historical results; see the 14 November update for guided simulations and mounting limitations.

[Daily report](reports/daily/Report_2026_11_13.pdf) · [Lane study](simulations/u4m2/lanes_20261113/README.md) · [Original lane CAD](cad/lanes_u4m2/README.md) · [Original build guide](cad/lanes_u4m2/BUILD_GUIDE.md)

### 12 November 2026: exact 20° reference — four of five cases pass every check

Corrected the low-yaw elevation references to 20°. Nominal, 75 GPa rod, 1.5 m free-rope and rope-stiffness −20% cases then passed every recorded check. The 550 g case retained transient large-yaw errors despite settling successfully. These tests used the earlier routing, before the four-station guide validation.

[Daily report](reports/daily/Report_2026_11_12.pdf) · [Detailed results](simulations/u4m2/backbone_20261108/README.md#13-exact-20-reference-and-correction-during-moves-closed-loop-v3-2026-11-12) · [Data and figures](simulations/u4m2/backbone_20261108/closed_loop_v3_results/)

### 12 November 2026 (later): operating pretension enforced and refined closed-loop path

Added a 3 N tension target, tension-aware command preparation and subdivided moves. All five earlier-routing cases stayed above 2.5 N and below the 5 mm step limit; transient angle errors remained and motivated the exact-reference update above.

[Controller and detailed results](simulations/u4m2/backbone_20261108/README.md#12-closed-loop-round-trip-v2-operating-pretension-and-refined-path-closed_loop_v2py-2026-11-12) · [Saved results](simulations/u4m2/backbone_20261108/closed_loop_v2_results/)

<a id="closed-loop-simulation-update-12-november-2026"></a>

### 12 November 2026: closed-loop control, 3D visualisation and repository organisation

Implemented head-angle and tendon-tension feedback for the insertion/right/left/return/withdrawal cycle. All five original cases passed settled-state checks, while motion traces exposed tension and sampling failures subsequently addressed by v2. Added 3D animations and reorganised CAD, simulations, reports and historical files with updated links.

[Full original closed-loop report](simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) · [3D steering animation](simulations/u4m2/backbone_20261108/closed_loop_results/E75_steering.gif) · [Repository map](docs/repository_map.md) · [File migration record](docs/path_migration.csv)

### 11 November 2026: stable startup and 3 N pretension

A stable startup and 3 N pretension reference made the nominal open-loop round trip pass all 1,069 samples, with minimum tendon tension of 2.74 N. The rope-stiffness -20% case also passed; the 75 GPa, 550 g and 1.5 m free-rope cases still exposed open-loop calibration limits. The model input sheet and prototype review were documented.

[Daily report](reports/daily/Report_2026_11_11.pdf) · [Detailed study](simulations/u4m2/backbone_20261108/README.md#10-round-trip-cycle-with-3-n-pretension-and-a-stable-startup-2026-11-11) · [Model data sheet](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) · [Earlier 1 N findings](docs/history.md#original-1-n-cycle-limitations-11-november-2026).

### 10 November 2026: coordinated winch control and accuracy

Coordinated rope-length commands produced smooth, stable and reversible steering while maintaining working elevation. Winch-position sensitivity showed that roughly ±0.2–0.5 mm accuracy was needed for ±1° open-loop head-angle accuracy, motivating angle feedback and additional pretension margin.

[Daily report](reports/daily/Report_2026_11_10.pdf) · [Weekly presentation](reports/weekly/Weekly_report_2026_11_10.pptx) · [Detailed results and figures](docs/history.md#10-november-2026-coordinated-winch-control-and-winch-accuracy).

### 9 November 2026: tank entry, stability and steering

Screened loaded entry, fixed-winch stability, tendon forces and clearance against the full 3D tank. A 20° installation with limited insertion depth supported the tested steering envelope; pulling only one side rope lost working elevation beyond about ±20° yaw.

[Daily report](reports/daily/Report_2026_11_09.pdf) · [Detailed results and figures](docs/history.md#9-november-2026-entry-stability-tendon-force-3d-tank-and-horizontal-flexibility).

### 8 November 2026: M stiffness requirement and NiTi backbone

Identified insufficient M-module stiffness and evaluated a central Ø1.8 mm NiTi backbone. The revised U4+M2 model passed the studied straightening and held-elevation steering checks; the module test plan defines the measurements still required.

[Daily report](reports/daily/Report_2026_11_08.pdf) · [Backbone results](docs/history.md#8-november-2026-m-stiffness-requirement-and-niti-backbone) · [Build and test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md).

<a id="previous-baseline-studies-6-november-2026-current-m-module"></a>

### 6 November 2026: original M-module baseline

The original M-module model required excessive strain for straightening and did not achieve loaded steering at the required head elevation. These results became the control cases for the later backbone studies.

[Daily report](reports/daily/Report_2026_11_06.pdf) · [Baseline studies](docs/history.md#previous-baseline-studies-6-november-2026-current-m-module).

### 5 November 2026: initial design and analysis

Established the earlier design and analysis baseline for the subsequent stiffness, deployment and tendon-control investigations.

[Daily report](reports/daily/Report_2026_11_05.pdf).


<a id="prototype-cad-status"></a>

## Prototype

The [V3 guide candidate](cad/lanes_u4m2/guides_v3/README.md) uses the V2 module bodies. Its 0.15 mm bond gap produced unintended contact in 59/217 holds. A [0.25 mm bond gap](simulations/u4m2/lanes_20261113/evening_20261116/README.md) cleared the earlier beam-based screen with 0.0182 mm to spare. The [large-rotation M5 test](reports/daily/M5_Joint_Test_2026_11_18.md) now predicts 24.78 N at an individual rotating support in the reference pure bend. A physical retainer, as-printed clearance and material strength still need verification.

**Ignore `archive/superseded_cad/full_length/` (marked 11 November 2026).** It uses 84 mm shells with 12 mm pin joints and two separate backbone rods with a free joint. The design and all simulations use continuous 96 mm modules with one Ø1.8 mm NiTi rod along the full length of each M module; see [model data](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) and [why the folder is marked](archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md). The uploaded U/M STEP files have a STEP-derived OpenSCAD viewing package in [`cad/previews/u4m2/`](cad/previews/u4m2). **The newest modules (rope lanes, anchors, backbone bore, joints) are in [`cad/lanes_u4m2/`](cad/lanes_u4m2).**

The U STEP contains one full-envelope body solid (96 mm long, about 63.24 mm across) and four separate leaf-spring solids (about 94 mm long). The M STEP contains one full-envelope body solid. The STEP product tree lists wing and disk items, but not as separate solid meshes; the full-envelope body geometry means that alone does not show the module body is missing. The STEP files do not encode material labels. The intended split is U body in PA12 with four NiTi spring elements, and M body in PA12. The current M study adds a separate Ø1.8 mm NiTi backbone to each M module.

The original SCAD preview arranges the six modules in a straight line without the backbone or inter-module connection; `cad/lanes_u4m2/` adds both. Confirm material assignments and connection details before ordering a full print.

- [Original U STEP](cad/modules/UniDirectional_96.step) · [Original M STEP](cad/modules/Medium_Stiffness_96.step).
- [Preview instructions](cad/previews/u4m2/README.md) · [Complete OpenSCAD/STL bundle](cad/previews/u4m2/final_u4m2_openSCAD_bundle.zip).
- [Backbone module test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md) · [Superseded CAD cleanup review](archive/superseded_cad/full_length/CLEANUP_REVIEW_CONFIRMATION.md).

## Next steps

Start with large-rotation bending of M5 at its ±12 mm guide stations. The result sets the rotation and clearance a retained saddle must provide. The plan then covers the full rope diameter, printed-module measurements and the complete 500 g control path. [Test cases, measurements and acceptance criteria](docs/500g_validation_plan.md)

[Detailed roadmap](docs/roadmap.md) · [Current limitations](docs/limitations.md) · [Module test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md).

## Geometry and input data

- [Telescopic rear and tank geometry study](simulations/u4m2): tank sections, rear beam calculations and deployment screening. The 3D tank model is `cad/tank/tank-v2.step`.
- [Module stiffness database](data/materials/module_stiffness.sqlite3): module mass, EA, EI and torsional stiffness. Use each study's saved input snapshot when reproducing its results.

## Earlier studies

- [H8U12 rear and 500 g head](simulations/shared/h8u12_front5to8_payload500g): comparison of 5–8 front modules.
- [Four tendon inverse study](archive/legacy_studies/four_rope_inverse_5_to_11): methods, frozen inputs and results.
- [Front module count sweep](archive/legacy_studies/front_sweep_5_to_11): comparison of 5–11 front modules.
- [Reach and extension screening](archive/legacy_studies/reach_extension/results): earlier passive reach study with different dimensional assumptions.

Start with the latest daily update above. Earlier results use different geometry or material assumptions and should not be combined directly with the latest baseline.
