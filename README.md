# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 14 November 2026

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

## Daily updates

The latest update is detailed below. Earlier dates have short summaries and links to the full reports and research history. All results described here are simulations unless explicitly stated otherwise.

### 14 November 2026 (latest): guided 500 g paths and a rejected rigid-mount candidate

The guide study now reads every saved state format, records closed-loop motion states, and uses the four actual guide stations at **−24, −12, +12 and +24 mm** on both the eight- and sixteen-cell meshes. The old archive reader silently missed matrix-form results; coverage of the four supplied historical archives is corrected from **68 to 2,270 states**.

- **500 g validation:** rerun startup, 0–175° held-elevation steering and the complete insertion/right/left/return/withdrawal cycle with ideal guides. Export every guide-hole load and screen the moving ropes against beam-mapped M-body flexures. The V2 comparison includes CAD-estimated module, guide, cap and retaining-wire masses.
- **A real mounting error found:** the previous ±12 mm clips had no inner web to grip. V2 uses actual inner webs at ±24 mm and actual outer webs at ±12 mm, with eight distinct CAD-derived socket frames.
- **V2 CAD:** A/B/C radii become **21/24/28 mm**, with regenerated matching disks and anchors. Ø2.6 mm bores, Ø3.0 mm rounded entries and a 3.2 mm guide thickness leave 1.4 mm at the B–C bore bridge and 1.0 mm at the mouth. Removable caps, retaining-wire envelopes and an adhesive gap define the proposed attachment.
- **Release decision:** all eight frames pass straight assembly and mesh checks, but rigid guide mounting intersects the M body in bent poses, and some rope spans penetrate end-region material. The mounting is **not ready for manufacture**. The ideal guided-rope simulation does not include that contact or the extra stiffness imposed by the mounts.
- **Verification:** nine new archive/geometry/mass/load tests and fourteen existing numerical/control tests pass. The report distinguishes simulation checks, preliminary sizing requirements and unresolved physical behaviour.

<!-- GUIDED_METRICS -->
V2 recorded **1,200 settled samples** and **2,526 motion trace states**. Control and envelope failures (settled / motion): **0 / 0**. Motion tension range: **3.00–18.06 N**. The sampled rope/flexure clearance bound is **4.92 mm**; the largest single-hole load is **5.52 N**. **985 audited records** also contain rope-centre penetration of end-region material. The ideal-guide results do not resolve the rigid mounting or finite end-hole contact problems.
<!-- END_GUIDED_METRICS -->

[Full English validation report](simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) · [V2 CAD and installation concept](cad/lanes_u4m2/guides_v2/README.md) · [Results and load exports](simulations/u4m2/lanes_20261113/guided_validation_20261114/) · [Current limitations](docs/limitations.md)

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

**Ignore `archive/superseded_cad/full_length/` (marked 11 November 2026).** It uses 84 mm shells with 12 mm pin joints and two separate backbone rods with a free joint. The design and all simulations use continuous 96 mm modules with one Ø1.8 mm NiTi rod along the full length of each M module; see [model data](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) and [why the folder is marked](archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md). The uploaded U/M STEP files have a STEP-derived OpenSCAD viewing package in [`cad/previews/u4m2/`](cad/previews/u4m2). **The newest modules (rope lanes, anchors, backbone bore, joints) are in [`cad/lanes_u4m2/`](cad/lanes_u4m2).**

The U STEP contains one full-envelope body solid (96 mm long, about 63.24 mm across) and four separate leaf-spring solids (about 94 mm long). The M STEP contains one full-envelope body solid. The STEP product tree lists wing and disk items, but not as separate solid meshes; the full-envelope body geometry means that alone does not show the module body is missing. The STEP files do not encode material labels. The intended split is U body in PA12 with four NiTi spring elements, and M body in PA12. The current M study adds a separate Ø1.8 mm NiTi backbone to each M module.

The original SCAD preview arranges the six modules in a straight line without the backbone or inter-module connection; `cad/lanes_u4m2/` adds both. Confirm material assignments and connection details before ordering a full print.

- [Original U STEP](cad/modules/UniDirectional_96.step) · [Original M STEP](cad/modules/Medium_Stiffness_96.step).
- [Preview instructions](cad/previews/u4m2/README.md) · [Complete OpenSCAD/STL bundle](cad/previews/u4m2/final_u4m2_openSCAD_bundle.zip).
- [Backbone module test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md) · [Superseded CAD cleanup review](archive/superseded_cad/full_length/CLEANUP_REVIEW_CONFIRMATION.md).

## Next steps

1. ~~Enforce operating pretension throughout the control sequence and refine the corrected path below the 5 mm sampling bound~~ — done in simulation on 12 November (v2). The 17° insertion reference was then fixed (v3); four of five cases pass every check. Next: online gain update for the 550 g large-yaw transient.
2. Add intermediate rope guides to the M modules and route the ropes through them in the model (per-cell chords); without them the M5 ropes rub the spring strips beyond about 15° yaw (13 November).
3. Re-run the lane pipeline with the printed part masses, then print one U and one M module and test them ([build guide](cad/lanes_u4m2/BUILD_GUIDE.md), section 10).
4. Add actuator dynamics, sensing noise/delay and calibrated friction, backlash and hysteresis.
5. Test the backbone module and interfaces, then integrate the actual head, cables and rear deployment mechanism.

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
