# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 15 November 2026

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

## Daily updates

The latest update is detailed below. Earlier dates have short summaries and links to the full reports and research history. All results described here are simulations unless explicitly stated otherwise.

### 15 November 2026 (latest): refined CAD checks and V3 saddle development

The head remains **500 g**. Today's work separates numerical collision error from actual mounting problems, and produces reproducible V3 CAD, updated mass equilibria and a detailed English report.

- **Corrected CAD deformation:** the source STL has triangles spanning 24.6 mm axially. Conforming surface refinement reduces the V2 175° maximum overlap from 31.10 to **5.97 mm³**; remaining contact lies at the outer saddles in the three checked holds. This reduction corrects the measurement rather than proving a mechanical improvement.
- **V3 geometry:** flared outer sockets retain a true **0.5 mm land**, a 0.15 mm central gap and **1.5:1 mouth relief**. Explicit loft breakpoints fix an error that otherwise distorted the land and could split caps. All eight straight assemblies pass; **112 exported-STL gap measurements** agree with the design. Rope lanes/stations and the independent NiTi backbone are retained; no end ferrule is added.
- **Expanded validation:** **217 re-solved records / 199 unique geometries**, including 36 additional unseen motion geometries, receive **1736 guide-part checks**. **55 records still have guide contact**, maximum **0.008959 mm³**. The earlier three-pose pass missed intermediate-angle failures; this remains a development candidate.
- **Rope and force evidence:** minimum sampled middle-flexure clearance **4.890 mm**, peak hole load **5.522 N**. **57/217 records** still contain end-region rope-centre penetration, maximum **0.2406 mm**.
- **Verification and limits:** 30 distinct tests and 11 configuration checks pass; all 24 V2 guide/cap/wire STLs reproduce exactly with relief disabled. The final nominal bonding area is only about **5.67 mm² per outer saddle**. Joint strength, mounting stiffness and finite rope contact remain unresolved; **not released for manufacture**, and no new full closed-loop replay is claimed. A 0.25 mm refinement attempt exceeded the 8 GiB memory limit; the completed contact results use 0.5 mm resolution.

[Full English daily report](reports/daily/Report_2026_11_15.md) · [V3 CAD and installation limits](cad/lanes_u4m2/guides_v3/README.md) · [Evidence and reproduction](simulations/u4m2/lanes_20261113/guided_refinement_20261115/README.md) · [Comparison figure](simulations/u4m2/lanes_20261113/guided_refinement_20261115/comparison.png)

### 14 November 2026: guided 500 g paths and a rejected rigid-mount candidate

Validated ideal guided startup and a complete 500 g closed-loop cycle, corrected archive coverage, and produced the V2 mounting CAD and guide loads. Physical mounting and finite end routing failed their separate checks. The 15 November update refines the coarse CAD collision screen; retain the older numbers as a dated snapshot.

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

The [V3 guide candidate](cad/lanes_u4m2/guides_v3/README.md) is the latest mounting experiment and reuses V2 module bodies. It remains unqualified for manufacture; see the latest daily report.

**Ignore `archive/superseded_cad/full_length/` (marked 11 November 2026).** It uses 84 mm shells with 12 mm pin joints and two separate backbone rods with a free joint. The design and all simulations use continuous 96 mm modules with one Ø1.8 mm NiTi rod along the full length of each M module; see [model data](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) and [why the folder is marked](archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md). The uploaded U/M STEP files have a STEP-derived OpenSCAD viewing package in [`cad/previews/u4m2/`](cad/previews/u4m2). **The newest modules (rope lanes, anchors, backbone bore, joints) are in [`cad/lanes_u4m2/`](cad/lanes_u4m2).**

The U STEP contains one full-envelope body solid (96 mm long, about 63.24 mm across) and four separate leaf-spring solids (about 94 mm long). The M STEP contains one full-envelope body solid. The STEP product tree lists wing and disk items, but not as separate solid meshes; the full-envelope body geometry means that alone does not show the module body is missing. The STEP files do not encode material labels. The intended split is U body in PA12 with four NiTi spring elements, and M body in PA12. The current M study adds a separate Ø1.8 mm NiTi backbone to each M module.

The original SCAD preview arranges the six modules in a straight line without the backbone or inter-module connection; `cad/lanes_u4m2/` adds both. Confirm material assignments and connection details before ordering a full print.

- [Original U STEP](cad/modules/UniDirectional_96.step) · [Original M STEP](cad/modules/Medium_Stiffness_96.step).
- [Preview instructions](cad/previews/u4m2/README.md) · [Complete OpenSCAD/STL bundle](cad/previews/u4m2/final_u4m2_openSCAD_bundle.zip).
- [Backbone module test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md) · [Superseded CAD cleanup review](archive/superseded_cad/full_length/CLEANUP_REVIEW_CONFIRMATION.md).

## Next steps

1. Resolve the remaining guide/land contact with an explicit local structural/contact model and a defensible bonded, articulated or compliant attachment. Include the effect on M-module stiffness and guide position.
2. Revise finite end-hole/anchor routing and check the full 2 mm rope envelope, material bridges and contact/friction.
3. With a physically compatible candidate, update mass/stiffness and replay the complete **500 g** closed-loop path, including finer equilibrium meshes and uncertainty cases.
4. Qualify printed parts, adhesive, lockwire, assembly access and cyclic wear using the simultaneous exported guide loads.
5. Add measured friction/backlash/hysteresis, actuator/sensor dynamics, actual head/harness geometry and rear deployment hardware.

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
