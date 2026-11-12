# Repository map

[Project home](../README.md) · [Simulation index](../simulations/README.md) · [Reports](../reports/README.md)

The root README retains its complete pre-organisation content and section order. Its file links and path references now point to the relocated files. This page describes the new physical layout.

## Folder layout

| Location | Contents |
|---|---|
| [simulations/u4m2](../simulations/u4m2/) | Active U4+M2 studies, baseline models, saved numerical results and closed-loop animations |
| [simulations/shared](../simulations/shared/README.md) | Shared H8U12 kernel and legacy rod models, with their configurations, input snapshots and reference runs |
| [cad/modules](../cad/modules/) | Original U/M STEP source files |
| [cad/tank](../cad/tank/) | Tank STEP and reference images |
| [cad/previews/u4m2](../cad/previews/u4m2/) | STEP-derived SCAD/STL preview; keep each assembly with its mesh files |
| [data/materials](../data/materials/README.md) | Shared material catalogue, SQLite databases and prior stiffness snapshot |
| [reports/daily](../reports/daily/) | Daily PDF and Word reports |
| [reports/weekly](../reports/weekly/) | Presentations |
| [reports/builders](../reports/builders/README.md) | PDF/PPTX generators and their figure/chart inputs |
| [archive/legacy_studies](../archive/README.md) | Earlier four-rope, front-count and reach-extension studies |
| [archive/superseded_cad](../archive/superseded_cad/) | Superseded prototype geometry, its warnings and cleanup review |
| [archive/utilities](../archive/utilities/) | Historical upload helper scripts; retained as references |
| [docs](.) | Design notes, limitations, roadmap, history and migration documentation |

Study-local results remain beside their source. In particular, the [closed-loop report](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md), CSV/JSON/NPZ data and animations have one canonical location. Frozen input snapshots and recorded provenance retain their historical contents; paths recorded inside old JSON/logs describe the original execution environment.

## Path changes

| Previous location | Current location |
|---|---|
| `ASRC_kevin/telescopic_planar_study/` | `simulations/u4m2/` |
| `ASRC_kevin/telescopic_planar_study/reports/` | `reports/builders/`; published Word reports are in `reports/daily/` |
| `ASRC_kevin/h8u12_front5to8_payload500g/` | `simulations/shared/h8u12_front5to8_payload500g/` |
| Root-level models, configurations and result folders in `ASRC_kevin/` | `simulations/shared/legacy_models/` |
| `ASRC_kevin/four_rope_inverse_5_to_11/` | `archive/legacy_studies/four_rope_inverse_5_to_11/` |
| `ASRC_kevin/front_sweep_5_to_11/` | `archive/legacy_studies/front_sweep_5_to_11/` |
| `reach_extension_study.py`, `reach_extension_results/` | `archive/legacy_studies/reach_extension/`, with outputs in `results/` |
| `robot_3d_viewer.html` | `simulations/shared/legacy_models/robot_3d_viewer.html` |
| `CAD/` | `cad/modules/` |
| `ASRC_kevin/telescopic_planar_study/inputs/tank-v2.step` | `cad/tank/tank-v2.step` |
| `ASRC_kevin/moving_prototype/final_u4m2/` | `cad/previews/u4m2/` |
| `ASRC_kevin/moving_prototype/full_length/` | `archive/superseded_cad/full_length/` |
| Shared material files and `stiffness_update/` | `data/materials/`, with the previous database under `history/` |
| Root `Report_*.pdf` and `Weekly_report_*.pptx` | `reports/daily/` and `reports/weekly/` |

The [complete file-by-file path map](path_migration.csv) covers the moved files, including the earlier report relocation. This organisation changes paths and navigation, not scientific conclusions. Source paths are updated where needed for execution; historical simulation data, CAD and published report bytes are preserved.

## Execution and provenance

The active model resolves shared inputs through [project_paths.py](../simulations/u4m2/project_paths.py). It still uses the same H8U12 rod kernel and stiffness database. Shared legacy rod scripts resolve the central material catalogue from their new location. See the [simulation commands](../simulations/README.md#run-and-verify-the-closed-loop-study) and [report builder instructions](../reports/builders/README.md).

The archived full-length CAD is still **not the simulated design**. Its [warning](../archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md) and [cleanup review](../archive/superseded_cad/full_length/CLEANUP_REVIEW_CONFIRMATION.md) remain with it. Archiving preserves those records; it does not validate or replace the geometry.
