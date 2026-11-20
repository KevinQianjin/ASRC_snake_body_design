# ASRC snake-body design

ASRC is a tendon-driven robot for fuel-tank inspection. The front has four U modules, two M modules and twelve Ø2 mm ropes. Its six 96 mm modules span 576 mm. The mass budget for the inspection head **including its adapter is 500 g**.

[Latest engineering results](#20-november-2026) · [Prototype and assembly](#prototype) · [Bench tests to run next](nextstep/README.md) · [Reports and presentations](reports/README.md)

## Project index

| Project | Where to start |
|---|---|
| [U modules and NiTi springs](docs/project_index.md#u-modules-and-niti-springs) | [Spring installation](docs/installation_guide.md#2-install-the-u-module-leaf-springs) · [U cage and blade loads](simulations/u4m2/extreme_tests/round2_20261119/results/u_structure/u_assembly.json) |
| [M5 structure and rotating seats](docs/project_index.md#m5-structure-and-rotating-seats) | [Retained-seat CAD](cad/lanes_u4m2/retained_seat_20261118/README.md) · [Pin and web results](simulations/u4m2/extreme_tests/round2_20261119/results/m5_structure/) |
| [M6 guides and bonded mounts](docs/project_index.md#m6-guides-and-bonded-mounts) | [0.25 mm candidate CAD](cad/lanes_u4m2/m6_bond_gap_20261119/README.md) · [Clearance and bore motion](simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/) |
| [Rope routing and winch transmission](docs/project_index.md#rope-routing-and-winch-transmission) | [Shared-bore routing](reports/projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md) · [Reversal tests](simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/) |
| [Motion control and tank clearance](docs/project_index.md#motion-control-and-tank-clearance) | [Full-cycle report](reports/projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md) · [12-rope tension lookup](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [3D replay](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) |
| [Extreme tests, strength and service life](docs/project_index.md#extreme-tests-strength-and-service-life) | [Round 1 and Round 2](simulations/u4m2/extreme_tests/README.md) · [Fatigue and strength data](simulations/u4m2/extreme_tests/round2_20261119/results/fatigue_and_strength/) |
| [Prototype fabrication and assembly](docs/project_index.md#prototype-fabrication-and-assembly) | [Print list](docs/installation_guide.md#full-front-print-list) · [Purchasing list](docs/installation_guide.md#materials-and-hardware) · [Assembly order](docs/installation_guide.md#assembly) |

The [full project index](docs/project_index.md) links CAD, simulation code, result files and reports for each project. The [repository map](docs/repository_map.md) lists the physical folders and relocated paths.

<a id="daily-updates"></a>

## 20 November 2026

The second extreme-test report was compiled at **00:27 EST (05:27 UTC)** after the study opened on 19 November. It used the 500 g mission and the 0.25 mm M6 guide candidate. The documentation now groups its evidence by engineering project. [Full report](reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) · [Methods and reproduction](simulations/u4m2/extreme_tests/round2_20261119/README.md)

| Engineering question | Result | Evidence |
|---|---|---|
| Do the M6 guides clear the bending body? | Across all 3,405 mission states, minimum rigid guide-to-body gaps were **0.0667 mm** at −12 mm and **0.0824 mm** at +12 mm. With elastic supports the C-rope bores moved **2.07–2.18 mm** at three loaded poses. Feedback reduced the resulting pointing error from **1.51–1.56°** to **0.028–0.197°** in six hold cases. | [Station gaps](simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/m6_full.json) · [Displaced bores](simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/m6_bores.json) · [Corrected holds](simulations/u4m2/extreme_tests/round2_20261119/results/motion_limits/disturbed_holds.json) |
| Can all twelve ropes maintain tension on reversal? | Original commands reached **1.444 N**, below the 2.5 N floor. Taking up drum motion before reversing kept the minimum at **2.901 N** across **7,084** substeps with matched parameters. With friction and drum play underestimated, the minimum was **2.622 N** across **10,102** substeps. Maximum pointing errors were **0.507°** and **0.819°**, respectively. | [Twelve-rope force plot](simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/twelve_rope_forces.png) · [Matched replay](simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/takeup_plant_mu0.15.json) · [Mismatched replay](simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/takeup_plant_mu0.12.json) |
| Which parts need a physical strength test first? | The modelled M5 pin reached **372.6 MPa** in bending at the higher service event and **739.2 MPa** at twice its pin load. The U cage and four movable blade tabs balanced the critical U1 axial load under the assumed stiffnesses. The pin grade, printed web resistance and tab stiffness still need measurement. | [M5 proof loads](simulations/u4m2/extreme_tests/round2_20261119/results/m5_structure/proof_loads.json) · [U load sharing](simulations/u4m2/extreme_tests/round2_20261119/results/u_structure/u_assembly.json) |
| What motion and lifetime can be supported? | The installed motion study followed **22** combined yaw/pitch branches at **three** clamp coordinates and checked their return and withdrawal connections. One complete mission supplied **46** signed fatigue channels. A physical life or safety-factor rating still requires measured material and joint resistance. | [Motion map](simulations/u4m2/extreme_tests/round2_20261119/results/motion_limits/combined_motion.png) · [Withdrawal checks](simulations/u4m2/extreme_tests/round2_20261119/results/motion_limits/pose_boundary_checks.json) · [Fatigue and safety factors](reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md#fatigue-wear-and-safety-factors) |

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

Start with the **M5 retained-seat coupon and P3 fixture** and an **M6 guide fit at −12 mm**. The 0.25 mm M6 socket is the current fit-test candidate. The model uses up its local clearance with about 0.2° adverse tilt under the studied assembly offset. The installation guide identifies each print, purchased part and rope termination, including both pairs of NiTi leaf springs in every U module. [First test parts](docs/installation_guide.md#first-test-parts) · [Illustrated assembly guide](docs/installation_guide.md) · [Rotatable U-module assembly](cad/lanes_u4m2/guides_v2/U_spring_assembly.scad)

<a id="geometry-and-input-data"></a><a id="earlier-studies"></a>

## Project references

[Current design](docs/current_design.md) · [Limitations](docs/limitations.md) · [500 g validation plan](docs/500g_validation_plan.md) · [Research history](docs/history.md) · [Earlier studies](archive/README.md) · [Report times in US Eastern and UTC](docs/time_conventions.md)
