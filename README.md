# ASRC snake-body design

ASRC is a tendon-driven robot for fuel-tank inspection. The front has four U modules, two M modules and twelve Ø2 mm ropes. Its six 96 mm modules span 576 mm. The mass budget for the inspection head **including its adapter is 500 g**.

## Interactive design handover

**[Open the 500 g design handover in your browser](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site)**. Anyone with the link can view the 21 November 2026 edition. In **Mission replay**, press **Play** or enter a step number to inspect one pose.

| What to inspect | Where to look |
|---|---|
| Rotate the CAD assembly and compare commanded and achieved head angles across 3,405 recorded states. The 11 phases cover loaded straightening, insertion, ±175° yaw, ±90° pitch, returns and withdrawal. | [Mission replay](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#mission) |
| At the same step, read the tension, commanded length and internal path length for each of the 12 ropes, plus the loads at eight guide stations. | [Ropes & loads](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#loads) |
| Check body and adapter clearance. The crowned M6 guide gaps are reported only at steps evaluated in CAD. | [Clearance](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#clearance) |
| Explore nine free-space steering routes, reference yield thresholds and fatigue estimates. Actual service life still requires hardware tests. | [Motion limits](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#limits) · [Strength & life](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#life) |
| Find the print list, purchased parts, rope routing and assembly sequence. | [Design & build](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#build) |
| Search 3,719 indexed source files, inspect available data tables and follow links to the exact GitHub revision. | [Evidence register](https://asrc-500g-design-handover.kevinqjchen.chatgpt.site/#evidence) |

[Archived single-file HTML (89.4 MiB)](https://github.com/KevinQianjin/ASRC_snake_body_design/blob/a1a3518c0746d4959204807147f7fe5f7bee9c54/reports/ASRC-500g-Design-Handover.html)

[Latest engineering results](#26-november-2026) · [Prototype and assembly](#prototype) · [Bench tests to run next](nextstep/README.md) · [Reports and presentations](reports/README.md)

## Project index

| Project | Where to start |
|---|---|
| [U modules and NiTi springs](docs/project_index.md#u-modules-and-niti-springs) | [Spring installation](docs/installation_guide.md#2-install-the-u-module-leaf-springs) · [U cage and blade loads](simulations/u4m2/extreme_tests/round2_20261119/results/u_structure/u_assembly.json) |
| [M5 structure and rotating seats](docs/project_index.md#m5-structure-and-rotating-seats) | [Retained-seat CAD](cad/lanes_u4m2/retained_seat_20261118/README.md) · [Pin and web results](simulations/u4m2/extreme_tests/round2_20261119/results/m5_structure/) |
| [M6 guides and bonded mounts](docs/project_index.md#m6-guides-and-bonded-mounts) | [0.25 mm candidate CAD](cad/lanes_u4m2/m6_bond_gap_20261119/README.md) · [Clearance and bore motion](simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/) |
| [Rope routing and winch transmission](docs/project_index.md#rope-routing-and-winch-transmission) | [Shared-bore routing](reports/projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md) · [Reversal tests](simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/) |
| [Motion control and tank clearance](docs/project_index.md#motion-control-and-tank-clearance) | [Full-cycle report](reports/projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md) · [12-rope tension lookup](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [3D replay](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) |
| [Extreme tests, strength and service life](docs/project_index.md#extreme-tests-strength-and-service-life) | [Free-space and repeated-duty results](reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) · [Download the free-space 3D replay (ZIP)](simulations/u4m2/extreme_tests/free_space_20261120/results/replay/ASRC-500g-3D-Replay.zip?raw=true) · [Extreme-test index](simulations/u4m2/extreme_tests/README.md) |
| [Prototype fabrication and assembly](docs/project_index.md#prototype-fabrication-and-assembly) | [Print list](docs/installation_guide.md#full-front-print-list) · [Purchasing list](docs/installation_guide.md#materials-and-hardware) · [Assembly order](docs/installation_guide.md#assembly) |

The [full project index](docs/project_index.md) links CAD, simulation code, result files and reports for each project. The [repository map](docs/repository_map.md) lists the physical folders and relocated paths.

<a id="daily-updates"></a>

## 26 November 2026

<a id="26-november-2026--m6-niti-backbone-hub-strain-and-stride-1-tilt-closeout"></a>

**Evening Report — M6 NiTi-backbone hub-strain convergence and stride-1 FCL tilt closeout.** Both simulation priorities from the 25 November handoff are closed out. Adding the Ø1.80 mm (`40 GPa`) NiTi backbone between the D0/D1 masters (not coupled to the Ø8.40 mm hub-ring bores, 3.30 mm radial clearance) under kinematic rod rotation gives a **75.2%–76.5% / 23.5%–24.8%** body/backbone moment split with guide wrenches, keeps all governing bending-plane land tractions within **1.2%–5.1%**, and converges the localized hub/arm corner strain (`q5 → q3 → q2.5/a0.25`, 1.34M reduced DOFs) to **4.196% / 4.169%** at steps 1,709 / 1,869 (**4.211%** mission max at step 1,884; 677 states > 3%; 0.5 / 1.0 mm finite-gauge averages **0.850% / 0.401%**). Compared with cited PA12 (HP MJF PA 12, EOS SLS PA 2200, and 15–18 MPa / ~1.0–1.2% fatigue endurance limits), the sharp corner exceeds fatigue limits and motivates a junction fillet plus hardware DIC/strain-gauge testing. For Priority 2, **776 exact FCL probes at stride 1** (±10 states around all 44 per-phase minima) confirm **0 contacts**, **0 states < 0.025 mm**, and a maximum drop vs stride-5 of **0.000097 mm** (`< 0.001 mm`, PASS: uncrowned **0.0752 / 0.0737 mm**, crowned **0.0789 / 0.0784 mm**). [Evening Report](reports/daily/Evening_Report_2026_11_26.md) · [Study and commands](simulations/u4m2/lanes_20261113/evening_20261126/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261126/HANDOFF.md)

## 25 November 2026

<a id="25-november-2026--evening-report-whole-mission-envelope"></a>

**Evening Report — whole-mission envelope of the bonded solid M6 model: bond demand closed out, no sampled 0.2° tilt failure, hub strain confirmed mission-wide.** The 24 November whole-body solid model was linear but had been evaluated at only two steps. This run factorised it once per adhesive case, solved 15 unit load cases and superposed them over **all 3,405 states** of the archived 500 g yaw/pitch mission (straighten → entry → right yaw and return → left yaw and return → pitch up/down and return → exit). The superposed fields reproduce the archived direct solves to < 10⁻⁸. No CAD, guide position, rope bore, mass or solver input changed. [Evening Report](reports/daily/Evening_Report_2026_11_25.md) · [Study and commands](simulations/u4m2/lanes_20261113/evening_20261125/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261125/HANDOFF.md)

| Check or result (G = 500 / 1,500 MPa assumed) | Mission envelope | Steps 1,709/1,885 (24 Nov) |
|---|---:|---:|
| **Area-mean axial bond shear** (q3, 1.08 M DOF) | **2.48 / 3.60 MPa** | 2.45 / 3.45 MPa |
| Land-edge peak axial shear, uncrowned / crowned | 9.0 / 16.8 · 7.8 / 14.5 MPa | 8.7 / 16.8 · 7.4 / 14.3 MPa |
| Peak normal traction, uncrowned | 21.2 / 36.4 MPa (at 1,709 / 1,885) | same |
| Mesh change q5 → q3 of the mission maxima | −3.9% to +4.7% | |
| **Worst gap at 26 rigid ±0.2° tilts, 689 sampled states**, uncrowned / crowned | **0.0737 / 0.0783 mm**; 0 states < 0.025 mm; 0 contacts | 0.0742 / 0.0785 mm |
| **Peak body strain** (no backbone; small-strain check fails) | **3.81% at step 1,869**; > 3% on 615 states | 3.74% |

Steps 1,709 / 1,885 were representative of the bond demand to within 5%. During right yaw the off-plane lands carry twice their step-1,709 load, but stay inside the envelope. Against the solid arm, the tilt clearance changes by only about 0.005 mm over the mission, so the 21 November uncrowned failure was a rod-map artefact across the sampled mission. The hub/arm strain above 3% is now a mission-wide finding and the top next-run item, with the NiTi backbone added. The adhesive, the bond strength, the as-printed land and the PA12 strain limit remain unmeasured, and the tilt sweep is sampled at every 5th state.

**Other repository updates (on `main`, 25 Nov):** a [NiTi manufacturing plan for PolyU IC](reports/niti_manufacturing_polyu_report.md); an [isolated U-leaf-spring geometry and wire-EDM CAM handoff](cad/manufacturing_setup/README.md) (STEP solids, audited profile DXF, Robofil job sheet; no machine code released); and a [U4+M2 component-demand and threshold sensitivity sweep](reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md#component-demand-and-threshold-sensitivity-sweep-25-november-2026). These are summarised in the Evening Report.

## 24 November 2026

<a id="24-november-2026--evening-report-whole-body-solid-m6-model"></a>

**Evening Report — whole-body solid M6 model.** The whole CAD lattice was meshed with quadratic tetrahedra and validated (bare EI 40,368–44,102 N·mm², within 1.4% of the database PA12 body). Both guides were bonded through the distributed crowned layer, and the rod's ~47° end rotation was applied only at the end masters. At steps 1,709 / 1,885 the bond demand is 1.0–3.5 MPa area-mean and 3.6–16.8 MPa land-edge peak (the `rod` model's 103–306 MPa ruled out), and both lands clear 0.2° tilt against the solid arm (0.074–0.079 mm). Peak hub strain is 3.7% (small-strain check fails; geometric nonlinearity about 1%). [Evening Report](reports/daily/Evening_Report_2026_11_24.md) · [Study](simulations/u4m2/lanes_20261113/evening_20261124/README.md) · [Handoff](simulations/u4m2/lanes_20261113/evening_20261124/HANDOFF.md)

## 23 November 2026

<a id="23-november-2026--evening-report-solid-m6-strut-model"></a>

**Evening Report — local solid model of the bonded M6 struts.** A verified quadratic-tetrahedron solver for the actual CAD struts showed that driving a strut's cut faces with the rod map is over-constrained. The struts carry 30–35× the rod model's cell moment, so the 126 MPa coupled-station traction is not physical. The rod map distorts the arm walls around the guide by more than the crowned land's clearance margin, and an undeformed body keeps about 0.08 mm at 0.2° tilt. [Evening Report](reports/daily/Evening_Report_2026_11_23.md) · [Study](simulations/u4m2/lanes_20261113/evening_20261123/README.md) · [Handoff](simulations/u4m2/lanes_20261113/evening_20261123/HANDOFF.md)

## 22 November 2026

<a id="22-november-2026--evening-report-crowned-m6-bond-layer"></a>

**Evening Report — crowned M6 bond layer: tractions, witness motion and bond motion with 0.2° tilt.** The 0.06 mm crowned M6 land (0.25 mm at mid-land, 0.31 mm at the edges) was modelled with a per-point bond thickness in the Round 2 bonded-land structure, at assumed adhesive moduli of 500 and 1,500 MPa. The guide motion relative to its witness web was then combined with 26 rigid ±0.2° tilts in an exact CAD clearance check at the governing steps 1,709, 1,710 and 1,885. The uncrowned two-point case reproduces Round 2 exactly. No CAD, guide position, rope bore, mass or solver input changed. [Evening Report](reports/daily/Evening_Report_2026_11_22.md) · [Study and commands](simulations/u4m2/lanes_20261113/evening_20261122/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261122/HANDOFF.md)

Bond motion plus 0.2° tilt left the crowned land 0.0284 / 0.0424 mm (z = −12 / +12 mm). The archived 63.96 MPa Round 2 traction turned out to be about 97% imposed rod kinematics; transmitted load alone gives 2–4 MPa.

## 21 November 2026

<a id="21-november-2026--evening-report-full-mission-crowned-m6-certification"></a>

**Evening Report — full-mission certification of the crowned M6 land.** Over all 3,405 steps, the crowned land had no contacts (minimum gaps 0.0945 / 0.1089 mm). It kept 0.0283 / 0.0440 mm at the worst of 26 rigid 0.2° tilts, with no step below the 0.025 mm probe offset. The uncrowned land fell below the offset at 665 / 317 yaw steps, and the crowned land contacts at 0.30°. The offline [500 g design handover](reports/ASRC-500g-Design-Handover.html) was also published (PR #41). [Evening Report](reports/daily/Evening_Report_2026_11_21.md) · [Study](simulations/u4m2/lanes_20261113/evening_20261121/README.md) · [Handoff](simulations/u4m2/lanes_20261113/evening_20261121/HANDOFF.md)

## 20 November 2026

<a id="20-november-2026--evening-report-crowned-m6-bond-land"></a>

**Evening Report — crowned M6 bond land.** A 0.06 mm crown on the 0.25 mm M6 outer-socket land raised the smallest first-contact rigid tilt at the governing left-yaw steps from 0.207° to 0.289° (z = −12 mm) and from 0.258° to 0.340° (z = +12 mm). It had zero contacts on 787 + 430 low-margin steps. [Evening Report](reports/daily/Evening_Report_2026_11_20.md) · [Study](simulations/u4m2/lanes_20261113/evening_20261120/README.md) · [Crowned-land CAD](cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Handoff](simulations/u4m2/lanes_20261113/evening_20261120/HANDOFF.md)

The [free-space steering, fracture and service-life study](reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) found the following on the 8-cell rod:

- yaw reached ±296° and pitch +215°/−149°;
- the M5 +12 mm pin crossed a 205 MPa reference yield near −110° of left-out motion;
- active reset gave 0 tension-floor violations;
- the reference fatigue amplitude is 5.722 N at one million cycles.

[Directional limits](simulations/u4m2/extreme_tests/free_space_20261120/results/strength/limits.json) · [Repeated duty](simulations/u4m2/extreme_tests/free_space_20261120/results/fatigue/life.json). Earlier that day, Round 2 verified the uncrowned 0.25 mm M6 candidate over the whole mission. [Round 2 report](reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md)

<a id="next-steps"></a>

The next bench measurements are M6 bore motion and bonded tilt under load, proximal and distal rope force on reversal, and pin, web and tab response at the archived service loads. [Test sequence and acceptance checks](nextstep/README.md)

<a id="earlier-results"></a>
<a id="19-november-2026--second-extreme-test-round-at-500-g"></a>
<a id="19-november-2026--evening-report-wider-m6-guide-bond-gap"></a>
<a id="19-november-2026--first-extreme-tests-at-500-g"></a>
<a id="19-november-2026--500-g-full-cycle-with-90-and-90-pitch"></a>

## 19 November 2026

- **Evening Report.** Wider M6 sockets improved nominal clearance. Bonded plate tilt remained the controlling assembly tolerance in the sampled configurations. [Evening Report](reports/daily/Evening_Report_2026_11_19.md)
- **Extreme tests.** Round 1 identified the critical M6 gap, M5 pin and web, U1 tab and weak B-down return near +69° pitch. Round 2 started that evening and finished the following morning. [Round 1 results](simulations/u4m2/extreme_tests/round1_20261119/README.md) · [Round 2 results](#20-november-2026)
- **Full motion cycle.** The nominal simulation completed 1,380 targets including loaded straightening, insertion, ±175° yaw, ±90° pitch and withdrawal. All 40,860 individual rope tensions are archived. [Cycle report](reports/projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md) · [Tensions at each step](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md)
- **Prototype and routing.** The M5 seat coupon, P3 fixture and hub relief were developed, and the four C ropes gained lateral freedom at the M5/M6 interface. [Seat and shared-bore report](reports/projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md) · [P3 fixture](cad/lanes_u4m2/p3_pin_fixture_20261119/README.md)

<a id="18-november-2026--evening-report-retained-rotating-seat"></a>
<a id="18-november-2026--validation-test-plan-for-the-500-g-front"></a>

## 18 November 2026

Loaded M5 web tests informed the rotating seat, retention hardware, fork clearance and driver access. [Evening Report](reports/daily/Evening_Report_2026_11_18.md) · [Large-rotation joint test](reports/projects/m5_structure/M5_Joint_Test_2026_11_18.md) · [Retained-seat report](reports/projects/m5_structure/M5_Retained_Seat_2026_11_18.md)

<a id="17-november-2026--evening-report-latest-rib-level-model-of-the-guide-joint"></a>

## 17 November 2026

A model of eight actual M5 ribs showed how a rigid bonded guide changes the module's bending and torsional stiffness. [Evening Report](reports/daily/Evening_Report_2026_11_17.md)

## 16 November 2026

The morning solver connected end fillets to guide centres for the full rope diameter. The evening study compared guide/web interference across the saved poses. [Evening Report](reports/daily/Evening_Report_2026_11_16.md) · [Morning Report](reports/daily/Morning_Report_2026_11_16.md)

## 15 November 2026

V3 saddles reduced guide/web interference, with residual contact in bent poses. The evening study introduced flared bellmouth exits for the Ø2 mm ropes. [Evening Report](reports/daily/Evening_Report_2026_11_15.md) · [Morning Report](reports/daily/Morning_Report_2026_11_15.md)

## 14 November 2026

The guided 500 g cycle exported hole loads and motion states. Separate CAD checks found interference at bent guide mounts and rope penetration in the end regions. [Guided validation](simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md)

## 13 November 2026

Separate 21/24/27 mm rope lanes were tested on the original lane-routed front. Large bends exposed a chord-routing limit in M5. Later designs moved the C lane to 28 mm. [Daily report](reports/daily/Report_2026_11_13.pdf) · [Original lane study](simulations/u4m2/lanes_20261113/README.md)

<a id="closed-loop-simulation-update-12-november-2026"></a>

## 12 November 2026

An exact 20° reference and tension-aware arrival improved the closed-loop round trip. Four of five parameter cases passed the recorded checks. [Daily report](reports/daily/Report_2026_11_12.pdf) · [Controller results](simulations/u4m2/backbone_20261108/closed_loop_v3_results/)

## 11 November 2026

A stable startup and 3 N operating pretension allowed the nominal open-loop round trip to meet its checks. The team also published the model inputs. [Daily report](reports/daily/Report_2026_11_11.pdf) · [Model data sheet](simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md)

## 10 November 2026

Coordinated winch commands connected the discrete steering poses. The sensitivity study quantified how winch position errors affect pointing. [Daily report](reports/daily/Report_2026_11_10.pdf) · [Weekly presentation](reports/weekly/Weekly_report_2026_11_10.pptx)

## 9 November 2026

The study checked three-dimensional tank entry, rope pretension and the force required to hold elevation while steering. [Daily report](reports/daily/Report_2026_11_09.pdf)

## 8 November 2026

The stiffness study sized a NiTi backbone for each M module and identified bending, axial and torsional tests for the physical module. [Daily report](reports/daily/Report_2026_11_08.pdf) · [Stiffness sweep](simulations/u4m2/m_axial_sweep_20261108/README.md)

<a id="previous-baseline-studies-6-november-2026-current-m-module"></a>

## 6 November 2026

Loaded straightening and tank-entry studies showed the limits of the original M module. [Daily report](reports/daily/Report_2026_11_06.pdf) · [Spatial steering study](simulations/u4m2/steering_63mm_20261106/README.md)

## 5 November 2026

The design review documented the early robot configuration and its simulation assumptions. [Daily report](reports/daily/Report_2026_11_05.pdf)

## 4 November 2026

The repository gained rear-backbone comparisons and a four-rope inverse study across five to eleven front modules. [Rear-backbone study](simulations/shared/legacy_models/README_rear_backbone.md) · [Four-rope study](archive/legacy_studies/four_rope_inverse_5_to_11/README.md)

## 3 November 2026

The initial uploads included the rope-driven model, material inputs and the 500 g tip-load comparison. [Original rope model](simulations/shared/legacy_models/README_ropes.md) · [Saved 500 g results](simulations/shared/legacy_models/rope_results_tip500g/)

<a id="prototype-cad-status"></a>

## Prototype

Start with the **M5 retained-seat coupon and P3 fixture** and an **M6 guide fit at −12 mm**. The 0.25 mm M6 socket is the current fit-test candidate. The model uses up its local clearance with about 0.2° adverse tilt under the studied assembly offset. A [crowned-land variant](cad/lanes_u4m2/m6_crowned_land_20261120/README.md) raises the rigid tilt to first contact to about 0.29°; print both and measure the land profile and bonded tilt. The installation guide identifies each print, purchased part and rope termination, including both pairs of NiTi leaf springs in every U module. [First test parts](docs/installation_guide.md#first-test-parts) · [Illustrated assembly guide](docs/installation_guide.md) · [Rotatable U-module assembly](cad/lanes_u4m2/guides_v2/U_spring_assembly.scad)

<a id="geometry-and-input-data"></a><a id="earlier-studies"></a>

## Project references

[Current design](docs/current_design.md) · [Limitations](docs/limitations.md) · [500 g validation plan](docs/500g_validation_plan.md) · [Research history](docs/history.md) · [Earlier studies](archive/README.md) · [Report times in US Eastern and UTC](docs/time_conventions.md)
