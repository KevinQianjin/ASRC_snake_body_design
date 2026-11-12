# Repository map

[Project home](../README.md) · [Simulation index](../simulations/README.md) · [Reports](../reports/README.md)

## Current organisation

| Location | Role | Status |
|---|---|---|
| [docs](.) | Current design, limitations, roadmap and dated research history | Active documentation |
| [reports/daily](../reports/daily/) | Dated PDF reports | Reference publications |
| [reports/weekly](../reports/weekly/) | Weekly presentations | Reference publications |
| [Simulation index](../simulations/README.md) | Active and historical study navigation, execution commands | Active entry point |
| [Backbone study](../ASRC_kevin/telescopic_planar_study/backbone_20261108/) | U4+M2 model, controller, saved results and animations | Active research |
| [Telescopic study](../ASRC_kevin/telescopic_planar_study/) | Tank, rear support and model dependencies | Active/reference research |
| [Original STEP modules](../CAD/) | Editable U/M source geometry | Source CAD |
| [Tank STEP](../ASRC_kevin/telescopic_planar_study/inputs/tank-v2.step) | Tank geometry used by clearance checks | Source CAD |
| [U4+M2 preview](../ASRC_kevin/moving_prototype/final_u4m2/) | STEP-derived SCAD/STL viewing package; keep files together | Geometry preview, not validated assembly |
| [Old full-length prototype](../ASRC_kevin/moving_prototype/full_length/) | Incorrect 84 mm shell / 12 mm pin-gap representation | Superseded; not the simulated design |
| [Earlier studies](../simulations/README.md#historical-studies) | Older model configurations and frozen inputs/results | Historical reference |

The closed-loop report, CSV/JSON/NPZ data and animations have one canonical location beside their simulation source. The reports index links there without duplicating them.

## Path changes

The first organisation stage moved publications and split the root documentation. Simulation code, databases, CAD and numerical results keep their existing paths.

| Previous location | New location |
|---|---|
| `Report_2026_11_05.pdf` | [reports/daily/Report_2026_11_05.pdf](../reports/daily/Report_2026_11_05.pdf) |
| `Report_2026_11_06.pdf` | [reports/daily/Report_2026_11_06.pdf](../reports/daily/Report_2026_11_06.pdf) |
| `Report_2026_11_08.pdf` | [reports/daily/Report_2026_11_08.pdf](../reports/daily/Report_2026_11_08.pdf) |
| `Report_2026_11_09.pdf` | [reports/daily/Report_2026_11_09.pdf](../reports/daily/Report_2026_11_09.pdf) |
| `Report_2026_11_10.pdf` | [reports/daily/Report_2026_11_10.pdf](../reports/daily/Report_2026_11_10.pdf) |
| `Report_2026_11_11.pdf` | [reports/daily/Report_2026_11_11.pdf](../reports/daily/Report_2026_11_11.pdf) |
| `Weekly_report_2026_11_10.pptx` | [reports/weekly/Weekly_report_2026_11_10.pptx](../reports/weekly/Weekly_report_2026_11_10.pptx) |
| Root README: design, closed-loop update, CAD and input data | [Current design](current_design.md) |
| Root README: current blockers | [Current limitations](limitations.md) |
| Root README: next steps | [Roadmap](roadmap.md) |
| Root README: dated findings, earlier limitations and studies | [Research history](history.md) |
| Root README: reports and presentation | [Report index](../reports/README.md) |
| Tracked `ASRC_kevin/__pycache__/craft_data.cpython-312.pyc` and `craft_data.cpython-314.pyc` | Removed from version control; generated caches are ignored |

Original report filenames are retained. The PDF/PPTX contents are unchanged, and the four existing daily-report builders now target `reports/daily/`.

## Subsequent organisation stage

A later migration can group model code under `simulations/u4m2/` and `simulations/shared/`, source geometry under `cad/`, shared materials under `data/materials/`, and superseded work under `archive/`. That migration requires dependency and path updates: the active backbone model still imports the 6 November planar/spatial models and the M stiffness sweep.

Preserve frozen study inputs, scientific results and source histories. Follow the [existing CAD cleanup review](../ASRC_kevin/moving_prototype/full_length/CLEANUP_REVIEW_CONFIRMATION.md) when replacing the superseded prototype; its warning and review record remain in place.
