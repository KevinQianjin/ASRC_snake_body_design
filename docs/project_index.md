# Engineering project index

Use this page to find the geometry, code and evidence for a component or test. For a chronological account, open the [daily updates](../README.md#daily-updates). The [repository map](repository_map.md) explains where files live.

## U modules and NiTi springs

Each of U1–U4 has a printed body and two pairs of NiTi leaf springs. The four blades and the cage share load. Each M module instead carries its own Ø1.8 mm axial NiTi rod.

| Look for | Files |
|---|---|
| Original shape and installed blades | [Original U STEP](../cad/modules/UniDirectional_96.step) · [U1–U3 body](../cad/lanes_u4m2/guides_v2/U_lane_pass.stl) · [U4 body](../cad/lanes_u4m2/guides_v2/U4_lane_anchorA.stl) · [Rotatable body and spring assembly](../cad/lanes_u4m2/guides_v2/U_spring_assembly.scad) |
| Installation and backbone dimensions | [Illustrated U spring installation](installation_guide.md#2-install-the-u-module-leaf-springs) · [M rods and guides](installation_guide.md#4-fit-the-six-fixed-guides-and-the-two-backbones) · [Model data sheet](../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) |
| Loads, stiffness and slip | [Blade solver](../simulations/u4m2/extreme_tests/round1_20261119/u_springs.py) · [Four blades and cage](../simulations/u4m2/extreme_tests/round2_20261119/u_assembly.py) · [U results](../simulations/u4m2/extreme_tests/round2_20261119/results/u_structure/) · [Structural interpretation](../reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md#structural-load-sharing-and-overload) |

## M5 structure and rotating seats

At M5 ±12 mm, each rotating guide uses a retained seat on the actual web. The hub chamfer and the shoulder-pin coupon address different contact surfaces.

| Look for | Files |
|---|---|
| Parts, fixture and assembly | [Retained seats](../cad/lanes_u4m2/retained_seat_20261118/README.md) · [Relieved hub sectors](../cad/lanes_u4m2/m5_hub_relief_20261119/README.md) · [Web coupon](../cad/lanes_u4m2/m5_seat_bench_20261119/README.md) · [P3 pin fixture](../cad/lanes_u4m2/p3_pin_fixture_20261119/README.md) |
| Joint model and design reports | [Eight-rib model](../simulations/u4m2/lanes_20261113/evening_20261117/README.md) · [Large-rotation tests](../reports/projects/m5_structure/M5_Joint_Test_2026_11_18.md) · [Retained-seat design](../reports/projects/m5_structure/M5_Retained_Seat_2026_11_18.md) · [Pin-seat comparison](../simulations/u4m2/lanes_20261113/evening_20261118/README.md) |
| Pin stress, web loading and test records | [Shell and pin solver](../simulations/u4m2/extreme_tests/round2_20261119/m5_contact.py) · [Load cases and proof loads](../simulations/u4m2/extreme_tests/round2_20261119/results/m5_structure/) · [Bench load programme](../simulations/u4m2/lanes_20261113/m5_seat_bench_20261119/README.md) · [P3 measurement and scoring forms](../simulations/u4m2/lanes_20261113/p3_pin_fixture_20261119/README.md) |

## M6 guides and bonded mounts

The 0.25 mm candidate changes the bonded sockets at M6 ±12 mm. Distinguish the nominal adhesive gap at the land from the remaining clearance between the guide and the bending body.

| Look for | Files |
|---|---|
| CAD by revision | [V2 mounting baseline](../cad/lanes_u4m2/guides_v2/README.md) · [V3 saddles](../cad/lanes_u4m2/guides_v3/README.md) · [0.25 mm candidate and six exported parts](../cad/lanes_u4m2/m6_bond_gap_20261119/README.md) · [Crowned-land candidate (20 Nov evening)](../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) |
| Design progression | [Initial guided validation](../simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) · [V3 refinement](../simulations/u4m2/lanes_20261113/guided_refinement_20261115/README.md) · [Guide/web comparison](../simulations/u4m2/lanes_20261113/evening_20261116/README.md) · [Wider-socket study](../simulations/u4m2/lanes_20261113/evening_20261119/README.md) · [Crowned-land tilt study](../simulations/u4m2/lanes_20261113/evening_20261120/README.md) |
| Full mission and loaded support | [Body clearance solver](../simulations/u4m2/extreme_tests/round2_20261119/m6_full.py) · [Elastic support model](../simulations/u4m2/extreme_tests/round2_20261119/m6_support.py) · [Gaps, land loads and bore motion](../simulations/u4m2/extreme_tests/round2_20261119/results/m6_guides/) · [Engineering interpretation](../reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md#m6-guide-position-bond-and-rope-path) |

## Rope routing and winch transmission

The twelve Ø2 mm ropes end in sets of four at U4, M5 and M6. Their lane radii are 21, 24 and 28 mm. The finite-diameter routing studies use the disk exits, guide bores and shared M5/M6 interface.

| Look for | Files |
|---|---|
| Rope path and physical parts | [Routing and anchor sequence](installation_guide.md#5-stack-the-bodies-and-terminate-each-rope-while-its-distal-face-is-exposed) · [End-disk bellmouth CAD](../cad/lanes_u4m2/end_bellmouth_v1/README.md) · [Shared-bore design report](../reports/projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md) |
| Development and checks | [Exit diagnosis](../simulations/u4m2/lanes_20261113/evening_20261115/README.md) · [Fillet-to-guide path](../simulations/u4m2/lanes_20261113/morning_20261116/README.md) · [Shared-bore solver and pull-through protocol](../simulations/u4m2/lanes_20261113/shared_bore_20261119/README.md) |
| Forces and drum reversal | [Nominal twelve-rope lookup](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [Friction and drum-play solver](../simulations/u4m2/extreme_tests/round2_20261119/rope_history.py) · [Free-rod take-up replay](../simulations/u4m2/extreme_tests/round2_20261119/takeup_plant.py) · [Force traces and commands](../simulations/u4m2/extreme_tests/round2_20261119/results/rope_control/) |

## Motion control and tank clearance

The 500 g reference mission covers loaded straightening, insertion, right and left yaw, upward and downward pitch, return and withdrawal. The combined-motion study tests which branches can also be retraced at three clamp coordinates.

| Look for | Files |
|---|---|
| Geometry and nominal mission | [Tank STEP](../cad/tank/tank-v2.step) · [Current full-cycle report](../reports/projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md) · [Controller, input archives and reproduction](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/README.md) |
| Pose, tension and playback | [Interactive 3D replay](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) · [Tensions at each step](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/rope_tensions_every_step.csv.gz) · [Phase results](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/phase_results.csv) |
| Combined-motion and disturbance checks | [Motion map solver](../simulations/u4m2/extreme_tests/round2_20261119/pose_map.py) · [Return and withdrawal checks](../simulations/u4m2/extreme_tests/round2_20261119/pose_boundaries.py) · [Map, pose tables, disturbed holds and timed response](../simulations/u4m2/extreme_tests/round2_20261119/results/motion_limits/) |
| Earlier models | [Telescopic rear and tank study](../simulations/u4m2/README.md) · [NiTi backbone and winch studies](../simulations/u4m2/backbone_20261108/README.md) · [First guided motion archive](../simulations/u4m2/lanes_20261113/guided_validation_20261114/README.md) |

## Extreme tests, strength and service life

| Look for | Files |
|---|---|
| Programme and decisions | [Both extreme-test rounds](../simulations/u4m2/extreme_tests/README.md) · [Second-round engineering report](../reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) · [Prioritised test programme](../nextstep/README.md) |
| Candidate failure locations | [Round 1 critical sites and load cases](../simulations/u4m2/extreme_tests/round1_20261119/README.md) · [Round 2 structural and motion studies](../simulations/u4m2/extreme_tests/round2_20261119/README.md) |
| Free-space steering, conditional fracture and working life | [Engineering report](../reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) · [Directional boundaries, finite rope exits and repeat-duty spectra](../simulations/u4m2/extreme_tests/free_space_20261120/README.md) |
| Fatigue, proof loads and strength | [Mission duty spectrum](../simulations/u4m2/extreme_tests/round2_20261119/duty.py) · [Conditional strength calculations](../simulations/u4m2/extreme_tests/round2_20261119/strength.py) · [Rainflow counts and required resistance](../simulations/u4m2/extreme_tests/round2_20261119/results/fatigue_and_strength/) · [Conditional pin strength](../simulations/u4m2/extreme_tests/round2_20261119/results/m5_structure/conditional_pin_factor.json) |
| Reproduction and scope | [Round 1 verification](../simulations/u4m2/extreme_tests/round1_20261119/results/validation.json) · [Round 2 verification and input hashes](../simulations/u4m2/extreme_tests/round2_20261119/results/verification/validation.json) · [Outstanding measurements](limitations.md) |

## Prototype fabrication and assembly

| Look for | Files |
|---|---|
| First bench build | [Test parts and quantities](installation_guide.md#first-test-parts) · [M5 fixture geometry](../cad/lanes_u4m2/p3_pin_fixture_20261119/README.md) · [M6 fit-test parts](../cad/lanes_u4m2/m6_bond_gap_20261119/README.md) |
| Full six-module prototype | [Print list](installation_guide.md#full-front-print-list) · [Purchased materials and hardware](installation_guide.md#materials-and-hardware) · [Assembly sequence](installation_guide.md#assembly) · [Commissioning](installation_guide.md#commissioning) |
| Source and reference geometry | [CAD catalogue](../cad/README.md) · [500 g solver reference](../cad/simulation_reference/u4m2_500g/README.md) · [Shared material data](../data/materials/README.md) |

The [report catalogue](../reports/README.md) covers daily editions, project reports and weekly presentations. The [simulation catalogue](../simulations/README.md) also lists shared numerical dependencies and archived configurations.
