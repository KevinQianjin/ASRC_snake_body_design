# ASRC Project Index

ASRC is a fuel-tank inspection robot with a tendon-driven front on a supported telescopic rear. The current U4+M2 front uses four U modules, two M modules and twelve Ø2 mm ropes. The six 96 mm modules span 576 mm and are about 63 mm across. The camera and induction-thermography head has a **500 g total mass budget including its adapter**.

[Prototype installation guide](docs/installation_guide.md) · [Full-cycle engineering report](reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [Next steps](nextstep/README.md) · [Repository map](docs/repository_map.md)

## Daily updates

### 19 November 2026 — first extreme tests at 500 g

At the M6 left-turn witness the guide/web gap fell from **0.08438 mm straight to 0.02093 mm bent**. A 0.025 mm rigid shift toward the web produced contact. On the +69° pitch return, B-down crossed the 2.5 N operating floor between assumed friction coefficients **0.16 and 0.17**. Four-blade U1 analysis located the largest trial tensile strain at the distal tab. The unknown compliance of this bond affects the predicted force. [First-round results, critical sites and twelve-rope figures](simulations/u4m2/lanes_20261113/extreme_round1_20261119/README.md)

### 19 November 2026 — 500 g full cycle with +90° and −90° pitch

The nominal quasi-static closed-loop simulation completed **1,380 of 1,380 targets**, from loaded straightening and insertion through two yaw turns, two pitch turns, each return to neutral and final withdrawal. It recorded **3,405 states and 40,860 individual rope tensions**, with zero failed operating substeps. Neutral is 0° yaw and +20° elevation. Pitch is measured from horizontal.

| Turn | Command | Achieved | 3-D pointing error | Highest endpoint rope tension | Body-to-tank gap after allowance |
|---|---|---|---:|---|---:|
| Right | +175° yaw at +20° elevation | +175.002° yaw, +20.001° elevation | 0.002° | B-up, 17.61 N | 11.581 mm |
| Left | −175° yaw at +20° elevation | −175.172° yaw, +19.940° elevation | 0.173° | B-up, 17.70 N | 24.522 mm |
| Up | +90° elevation | +89.919° elevation | 0.081° | C-up, 21.20 N | 21.146 mm |
| Down | −90° elevation | −89.921° elevation | 0.079° | C-down, 16.81 N | 35.129 mm |

- **Across the whole cycle, including loaded startup**, ideal rope tension ranged from **2.901 to 21.554 N**. C-up reached the peak near +69° pitch on both the outward and return moves. The smallest body-to-tank gap was **8.056 mm** after the 1.5 mm allowance. Refining from eight to sixteen cells per module changed the up/down endpoint directions by 0.00017°/0.00051° at the same winch commands.
- **What still needs a bench test.** At the four turning commands, a separate steady-sliding calculation with assumed friction coefficient μ = 0.15 put the weakest distal rope at **1.152 N**, below the 2.5 N operating floor. The closest selected full-mesh guide/web gap was **0.02047 mm** at M6, z = −12 mm. The P3 coupon fixture reduces calculated reversal play from 0.05964 to 0.01966 mm. Its specimen log is empty. Friction on reversal, as-built fit and the actual head and harness envelope remain open.

[Full report](reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [All twelve forces at each turn](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [Step-by-step data](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/rope_tensions_every_step.csv.gz) · [Interactive 3-D replay — download the HTML and open it locally](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) · [Simulation and reproduction commands](simulations/u4m2/lanes_20261113/cycle_closeout_20261119/README.md)

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

The first bench build consists of the **M5 retained-seat coupon and P3 fixture** and an **M6 guide fit at −12 mm**. The installation guide also gives the complete six-module parts list, supplier geometry, rope routes and assembly order. Use these trials to measure fit and force transmission before ordering the full front.

[First test parts](docs/installation_guide.md#first-test-parts) · [Full-front print list and STL files](docs/installation_guide.md#full-front-print-list) · [Purchasing list](docs/installation_guide.md#materials-and-hardware) · [Assembly sequence](docs/installation_guide.md#assembly) · [Commissioning checks](docs/installation_guide.md#commissioning)

To see the U module with its two leaf-spring pairs fitted, open the [illustrated spring installation](docs/installation_guide.md#2-install-the-u-module-leaf-springs) or the [rotatable U1–U4 assembly view](cad/lanes_u4m2/guides_v2/U_spring_assembly.scad).

## Next steps

The extreme-test programme keeps the head and adapter at 500 g. It covers usable motion and recovery, component damage and rupture, single faults, fatigue life and safety factors. The first round uses the full-cycle loads to test M6 clearance, M5 seat reactions, U spring end loads and force transmission at the two +69° pitch crossings.

[Extreme-test plan](nextstep/README.md) · [Complete plan (PDF)](nextstep/U4M2_Extreme_Test_Plan_2026_11_19.pdf) · [First-round results and reproduction](simulations/u4m2/lanes_20261113/extreme_round1_20261119/README.md)

<a id="geometry-and-input-data"></a><a id="earlier-studies"></a>

## Project references

[500 g validation plan](docs/500g_validation_plan.md) · [Current design](docs/current_design.md) · [Limitations](docs/limitations.md) · [CAD sources](cad/README.md) · [Tank STEP](cad/tank/tank-v2.step) · [Module stiffness data](data/materials/module_stiffness.sqlite3)

[All daily reports](reports/daily/) · [Weekly presentations](reports/weekly/) · [Research history](docs/history.md) · [Earlier studies](archive/README.md) · [Report times in US Eastern and UTC](docs/time_conventions.md)
