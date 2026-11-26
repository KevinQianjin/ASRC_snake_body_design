# Engineering reports and presentations

The [free-space steering, fracture and repeat-duty report](projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) contains the latest 500 g results from 20 November 2026. The [daily timeline](../README.md#daily-updates) summarises results, and the [project index](../docs/project_index.md) links each report to its CAD, simulation and data.

## Project reports

| Project | Reports |
|---|---|
| Extreme tests and service life | [Free-space limits, repeated service and 25 Nov component-demand sensitivity](projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md#component-demand-and-threshold-sensitivity-sweep-25-november-2026) · [Round 2 at 500 g](projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) · [Round 1 results and methods](../simulations/u4m2/extreme_tests/round1_20261119/README.md) |
| Motion control | [Full yaw and ±90° pitch cycle, 19 November](projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md) · [Twelve-rope tension supplement](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) |
| Rope routing | [M5 seat and shared M5/M6 bore, 19 November](projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md) |
| M5 structure | [Retained-seat design and assembly, 18 November](projects/m5_structure/M5_Retained_Seat_2026_11_18.md) · [Large-rotation joint tests, 18 November](projects/m5_structure/M5_Joint_Test_2026_11_18.md) |

## Daily editions

Scheduled morning and evening editions share a row for each reporting date. These publication files stay in [daily](daily/). The 14 November validation is published with its simulation archive.

| Date in 2026 | Subject | Read |
|---|---|---|
| 24 November | Whole-body solid M6 model: stiffness validated, bond demand 1–3.5 MPa mean, solid-arm clearance at 0.2° tilt | [Evening Report](daily/Evening_Report_2026_11_24.md) |
| 23 November | Local solid M6 strut model; rod-map boundary conditions shown over-constrained | [Evening Report](daily/Evening_Report_2026_11_23.md) |
| 22 November | Crowned M6 bond-layer tractions and bond motion with 0.2° tilt | [Evening Report](daily/Evening_Report_2026_11_22.md) |
| 21 November | Full-mission crowned M6 certification, nominal and 0.2° tilt | [Evening Report](daily/Evening_Report_2026_11_21.md) |
| 20 November | Crowned M6 bond land and tilt tolerance | [Evening Report](daily/Evening_Report_2026_11_20.md) |
| 19 November | Wider M6 bonded sockets and assembly tilt | [Evening Report](daily/Evening_Report_2026_11_19.md) |
| 18 November | Rotating guide seats and real web contact | [Evening Report](daily/Evening_Report_2026_11_18.md) |
| 17 November | Rib-level guide joint and stiffness | [Evening Report](daily/Evening_Report_2026_11_17.md) |
| 16 November | Guide/web compatibility and constrained bellmouth paths | [Evening Report](daily/Evening_Report_2026_11_16.md) · [Morning Report](daily/Morning_Report_2026_11_16.md) |
| 15 November | Finite-rope end exits and V3 saddle refinement | [Evening Report](daily/Evening_Report_2026_11_15.md) · [Morning Report](daily/Morning_Report_2026_11_15.md) · [Original report address](daily/Report_2026_11_15.md) |
| 14 November | Guided 500 g cycle, mounting and end-routing failures | [Guided validation](../simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) |
| 13 November | Separate rope lanes, bend limits and original module CAD | [PDF](daily/Report_2026_11_13.pdf) |
| 12 November | Tension-aware closed-loop round trip and exact 20° reference | [PDF](daily/Report_2026_11_12.pdf) · [Controller study](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) |
| 11 November | Stable startup, 3 N operating pretension and model input sheet | [PDF](daily/Report_2026_11_11.pdf) · [Input sheet](../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) |
| 10 November | Coordinated winches and position-error sensitivity | [PDF](daily/Report_2026_11_10.pdf) |
| 9 November | Tank entry, pretension, three-dimensional clearance and yaw | [PDF](daily/Report_2026_11_09.pdf) |
| 8 November | M-module stiffness and NiTi backbone sizing | [PDF](daily/Report_2026_11_08.pdf) |
| 6 November | Loaded straightening and steering of the original M module | [PDF](daily/Report_2026_11_06.pdf) · [Word review](daily/ASRC_Latest_Simulation_Review_2026_11_06.docx) |
| 5 November | Original design and analysis | [PDF](daily/Report_2026_11_05.pdf) · [Word review](daily/ASRC_Simulation_Review_2026_11_05.docx) |

## Weekly presentations and motion replays

- **10 November 2026.** The weekly deck covers the steering problem, the NiTi backbone and the winch studies. [PowerPoint](weekly/Weekly_report_2026_11_10.pptx)
- **19 November 2026.** The interactive replay includes upward and downward pitch and all twelve rope forces. [3D replay](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/motion_viewer.html) · [Replay and tension instructions](../simulations/u4m2/lanes_20261113/cycle_closeout_20261119/README.md)
- **12 November 2026.** Earlier closed-loop visualisations remain with their model. [Full-cycle MP4](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_full_cycle.mp4) · [Steering GIF](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_steering.gif) · [Historical payload-sensitivity animation](../simulations/u4m2/backbone_20261108/closed_loop_results/payload550g_feedback_convergence.gif)

## Regenerating daily reports

The [report builders and their instructions](builders/README.md) specify Python, ReportLab and the Carlito fonts for the dated PDFs. For example, run `python reports/builders/build_report_2026_11_11.py` from the repository root. Use the [time conventions](../docs/time_conventions.md) for new morning and evening editions.
