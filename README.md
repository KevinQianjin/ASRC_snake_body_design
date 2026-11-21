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
| [Extreme tests, strength and service life](docs/project_index.md#extreme-tests-strength-and-service-life) | [Free-space and repeated-duty results](reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) · [Download the free-space 3D replay (ZIP)](simulations/u4m2/extreme_tests/free_space_20261120/results/replay/ASRC-500g-3D-Replay.zip?raw=true) · [Extreme-test index](simulations/u4m2/extreme_tests/README.md) |
| [Prototype fabrication and assembly](docs/project_index.md#prototype-fabrication-and-assembly) | [Print list](docs/installation_guide.md#full-front-print-list) · [Purchasing list](docs/installation_guide.md#materials-and-hardware) · [Assembly order](docs/installation_guide.md#assembly) |

The [full project index](docs/project_index.md) links CAD, simulation code, result files and reports for each project. The [repository map](docs/repository_map.md) lists the physical folders and relocated paths.

<a id="daily-updates"></a>

## 20 November 2026

<a id="20-november-2026--evening-report-crowned-m6-bond-land"></a>

**Evening Report — crowned M6 bond land.** The 0.25 mm M6 outer-socket candidate cleared the body over the whole mission, but plate tilt still governed its margin. The bonded land edge sits about 21 mm from the axis, and Round 2 found contact when a 0.025 mm offset was combined with 0.2° tilt. This run kept the 0.25 mm bond datum at mid-land and crowned the 0.5 mm land quadratically to 0.31 mm at its edges. The rope bores, stations, webs, masses (−0.0021 g per station) and solver inputs are unchanged. [Evening Report](reports/daily/Evening_Report_2026_11_20.md) · [Study and commands](simulations/u4m2/lanes_20261113/evening_20261120/README.md) · [Crowned-land CAD](cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Next-run handoff](simulations/u4m2/lanes_20261113/evening_20261120/HANDOFF.md)

| Rigid CAD check at the governing left-yaw steps | 0.25 mm candidate | 0.06 mm crown |
|---|---:|---:|
| Smallest first-contact tilt, in-plane axes every 15°, z = −12 / +12 mm | 0.207° / 0.258° | **0.289° / 0.340°** |
| Smallest translation allowance at 0.2° tilt, z = −12 / +12 mm | 0.0013 / 0.0176 mm | **0.0290 / 0.0443 mm** |
| Mission screen, 787 + 430 low-margin steps, all 11 phases | 0.0667 / 0.0824 mm, 0 contacts | **0.0945 / 0.1089 mm, 0 contacts** |

These are rigid-body results. Bond deformation, as-printed form and bonded tilt are unmeasured, and a 0.06 mm crown is below typical PA12 print resolution.

The [free-space steering, fracture and service-life study](reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) extends the 500 g U4+M2 front beyond its original ±175° yaw and ±90° pitch mission. It keeps the actual guide geometry and the twelve Ø2 mm rope routes. Only the external tank constraint was removed.

| Engineering question | Latest result | Evidence |
|---|---|---|
| How far can the head steer and return? | On the 8-cell rod with sampled guide and rope CAD, right/left yaw reached **+296° / -296°** at +20° elevation. The zero-yaw pitch endpoints were **+215° / -149°**, referenced to horizontal. The 16-cell, 0.25 mm fixed-command checks reached +297° / -297° in yaw and +215° / -149° in pitch. | [Directional boundaries](simulations/u4m2/extreme_tests/free_space_20261120/results/strength/limits.json) · [All twelve forces and commands](simulations/u4m2/extreme_tests/free_space_20261120/results/angles/) · [Fine-grid limits](simulations/u4m2/extreme_tests/free_space_20261120/results/mesh/refined_transitions.json) |
| When can a structural part fail? | The M5 +12 mm pin at the 67.5° rib crossed a 205 MPa reference yield between -109.688° and -110.625° on left-out motion. The installed pin grade and fracture strain remain unmeasured. Trial installed rope capacities and printed-web strain thresholds are mapped to their first sampled crossings. | [Pin and web response](simulations/u4m2/extreme_tests/free_space_20261120/results/strength/pin_area_0.1_fine.json) · [Rope capacity lookup](simulations/u4m2/extreme_tests/free_space_20261120/results/strength/pull_capacity_lookup.csv.gz) |
| Does normal duty repeat, and how much fatigue resistance is required? | Simply reversing the matched startup gave a second-block minimum of **2.305 N**. Active friction take-up during reset gave **2.901 N** and **0** tension-floor violations. For a design duty of 10,000 blocks, the slope-5 axial-force model requires **5.722 N** alternating amplitude at one million cycles on C_up at the winch end. Actual working life requires matched endurance and wear tests. | [Repeated duty and endurance](simulations/u4m2/extreme_tests/free_space_20261120/results/fatigue/life.json) · [Phase loads and sliding travel](simulations/u4m2/extreme_tests/free_space_20261120/results/fatigue/phase_exposure.csv.gz) |

Earlier on 20 November, Round 2 verified the 0.25 mm M6 guide candidate over the archived mission, analysed M5 proof loads and U-module load sharing, and compared reversal commands. [Earlier Round 2 report](reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) · [Methods and grouped evidence](simulations/u4m2/extreme_tests/round2_20261119/README.md)

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
