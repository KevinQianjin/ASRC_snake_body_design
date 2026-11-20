# ASRC Project Index

ASRC is a fuel-tank inspection robot with a tendon-driven front on a supported telescopic rear. The current U4+M2 front uses four U modules, two M modules and twelve Ø2 mm ropes. The six 96 mm modules span 576 mm and are about 63 mm across. The camera and induction-thermography head has a **500 g total mass budget including its adapter**.

[Second-round extreme-test report](reports/daily/Extreme_Simulation_Round_2_2026_11_19.md) · [Prototype installation guide](docs/installation_guide.md) · [Full-cycle engineering report](reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [Next steps](nextstep/README.md) · [Repository map](docs/repository_map.md)

## Daily updates

### 19 November 2026 — second extreme-test round at 500 g

The 0.25 mm M6 guide candidate clears the actual body triangles at both stations in all **3,405** mission states. The minimum guide gaps are **0.0667 mm at −12 mm** and **0.0824 mm at +12 mm**. An elastic support calculation at the critical yaw poses moves the C-rope bores **2.07–2.18 mm** relative to their ideal positions. Re-equilibrating with the original winch lengths gives **1.51°–1.56°** pointing error. Bounded feedback recovers **0.028°–0.197°** across the six tested holds.

- **Rope reversal.** With assumed friction 0.15 and 0.10 mm drum play, the original commands reach a minimum distal force of **1.444 N**. Holding the pose while the drum takes up the friction reversal gives **2.901 N** over 7,084 freely equilibrated substeps with matched model parameters. With estimated friction 0.12 against a 0.15 plant, the minimum is **2.622 N** and the largest pointing error is **0.819°** (0 substeps over 1°). The archive includes both ends of all twelve ropes. [Tension figure](simulations/u4m2/lanes_20261113/extreme_round2_20261119/results/twelve_rope_forces.png) · [Free-rod replay](simulations/u4m2/lanes_20261113/extreme_round2_20261119/results/takeup_plant_mu0.12.json)
- **Structural limits.** The U cage and four movable blade tabs balance the critical U1 axial load under the stated stiffness assumptions. The M5 local pin reaches **372.6 MPa** bending stress at the more severe service event and **739.2 MPa** at twice that event's pin load. The steel grade, printed PA12 resistance and installed bond strength still require measurement. [U assembly](simulations/u4m2/lanes_20261113/extreme_round2_20261119/results/u_assembly.json) · [M5 proof loads](simulations/u4m2/lanes_20261113/extreme_round2_20261119/results/proof_loads.json)
- **Usable motion and life.** The installed map follows 22 combined yaw/pitch branches at three clamp coordinates, including the return and withdrawal connection. The service spectrum records 46 signed channels from one mission. Physical lifetime and safety factors require measured resistance and fatigue curves. [Motion map](simulations/u4m2/lanes_20261113/extreme_round2_20261119/results/combined_motion.png) · [Life and resistance requirements](reports/daily/Extreme_Simulation_Round_2_2026_11_19.md#fatigue-wear-and-safety-factors)

[Full engineering report](reports/daily/Extreme_Simulation_Round_2_2026_11_19.md) · [Simulations, data and reproduction](simulations/u4m2/lanes_20261113/extreme_round2_20261119/README.md) · [Next decisions](nextstep/README.md)

### 19 November 2026 — Evening Report: wider M6 guide bond gap

The 0.25 mm M6 sockets improved rigid-location margin over the 0.15 mm land. Tilt became the controlling assembly tolerance in the sampled configurations. [Evening Report](reports/daily/Evening_Report_2026_11_19.md) · [Candidate M6 parts](cad/lanes_u4m2/m6_bond_gap_20261119/README.md)

### 19 November 2026 — first extreme tests at 500 g

The first round identified the critical M6 gap, M5 pin and remote web hotspots, U1 distal tab and the weak B-down return at +69° pitch. [First-round results](simulations/u4m2/lanes_20261113/extreme_round1_20261119/README.md)

### 19 November 2026 — 500 g full cycle with +90° and −90° pitch

The nominal quasi-static controller completed 1,380 targets through loaded straightening, insertion, ±175° yaw, ±90° pitch and withdrawal. The archive contains 40,860 individual rope tensions. [Full-cycle report](reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [Twelve-rope results](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [Interactive 3-D replay](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html)

### Earlier results

- **19 November, earlier work.** The M5 coupon and hub relief were developed, and the four C ropes gained lateral freedom at the M5/M6 interface.<br>
  [Seat and shared-bore report](reports/daily/M5_Seat_and_Shared_Bore_2026_11_19.md)
- <a id="18-november-2026--evening-report-retained-rotating-seat"></a><a id="18-november-2026--validation-test-plan-for-the-500-g-front"></a>**18 November.** Loaded web tests informed the rotating M5 seat, retained hardware, fork clearance and driver-access checks.<br>
  [Retained-seat CAD and tests](reports/daily/M5_Retained_Seat_2026_11_18.md) · [Evening Report](reports/daily/Evening_Report_2026_11_18.md) · [Large-rotation joint test](reports/daily/M5_Joint_Test_2026_11_18.md)
- <a id="17-november-2026--evening-report-latest-rib-level-model-of-the-guide-joint"></a>**17 November.** A model of eight actual M5 ribs quantified the effect of bonded guides on bending and torsional stiffness.<br>
  [Evening Report](reports/daily/Evening_Report_2026_11_17.md)
- **16 November.** The solver connected end fillets to guide centres. The evening study screened guide/web compatibility across the saved holds.<br>
  [Evening Report](reports/daily/Evening_Report_2026_11_16.md) · [Morning Report](reports/daily/Morning_Report_2026_11_16.md)
- **15 November.** The V3 saddles and refined surface checks exposed remaining contact. Bellmouth exits were developed for the full Ø2 mm rope.<br>
  [Evening Report](reports/daily/Evening_Report_2026_11_15.md) · [Morning Report](reports/daily/Morning_Report_2026_11_15.md)
- **14–13 November.** Separate rope lanes and anchors led to a guided 500 g cycle. Bent guide mounts and rope/end contact drove the next changes.<br>
  [14 Nov guided validation](simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) · [13 Nov report](reports/daily/Report_2026_11_13.pdf)
- <a id="closed-loop-simulation-update-12-november-2026"></a>**12–11 November.** A stable 3 N startup and a 20° reference supported the first closed-loop round trips.<br>
  [12 Nov report](reports/daily/Report_2026_11_12.pdf) · [Controller study](simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) · [11 Nov report](reports/daily/Report_2026_11_11.pdf)
- **10–8 November.** Winch accuracy, tank entry and M-module stiffness studies established the case for a NiTi backbone in each M module.<br>
  [10 Nov report](reports/daily/Report_2026_11_10.pdf) · [9 Nov report](reports/daily/Report_2026_11_09.pdf) · [8 Nov report](reports/daily/Report_2026_11_08.pdf)
- <a id="previous-baseline-studies-6-november-2026-current-m-module"></a>**6–5 November.** Initial studies documented the loaded-steering limits of the original M module.<br>
  [6 Nov report](reports/daily/Report_2026_11_06.pdf) · [5 Nov report](reports/daily/Report_2026_11_05.pdf)

<a id="prototype-cad-status"></a>

## Prototype

The first bench build consists of the **M5 retained-seat coupon and P3 fixture** and an **M6 guide fit at −12 mm**. For that fit, the [0.25 mm bond-gap M6 parts](cad/lanes_u4m2/m6_bond_gap_20261119/README.md) are the current candidate. Measure the bonded plate tilt: the modelled margin is used up at about 0.2°. The installation guide also gives the complete six-module parts list, supplier geometry, rope routes and assembly order. Use these trials to measure fit and force transmission before ordering the full front.

[First test parts](docs/installation_guide.md#first-test-parts) · [Full-front print list and STL files](docs/installation_guide.md#full-front-print-list) · [Purchasing list](docs/installation_guide.md#materials-and-hardware) · [Assembly sequence](docs/installation_guide.md#assembly) · [Commissioning checks](docs/installation_guide.md#commissioning)

To see the U module with its two leaf-spring pairs fitted, open the [illustrated spring installation](docs/installation_guide.md#2-install-the-u-module-leaf-springs) or the [rotatable U1–U4 assembly view](cad/lanes_u4m2/guides_v2/U_spring_assembly.scad).

## Next steps

Measure the M6 bore motion and bonded tilt, identify rope friction and drum play on reversal, then measure U tab stiffness and M5 pin/web response under the recovered loads. Matched material tests will turn the published service spectrum into a first-damage, rupture and fatigue-life rating.

[Extreme-test programme and next decisions](nextstep/README.md) · [Complete plan (PDF)](nextstep/U4M2_Extreme_Test_Plan_2026_11_19.pdf) · [Second-round evidence](reports/daily/Extreme_Simulation_Round_2_2026_11_19.md)

<a id="geometry-and-input-data"></a><a id="earlier-studies"></a>

## Project references

[500 g validation plan](docs/500g_validation_plan.md) · [Current design](docs/current_design.md) · [Limitations](docs/limitations.md) · [CAD sources](cad/README.md) · [Tank STEP](cad/tank/tank-v2.step) · [Module stiffness data](data/materials/module_stiffness.sqlite3)

[All daily reports](reports/daily/) · [Weekly presentations](reports/weekly/) · [Research history](docs/history.md) · [Earlier studies](archive/README.md) · [Report times in US Eastern and UTC](docs/time_conventions.md)
