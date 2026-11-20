# Repository map

[Project home and daily timeline](../README.md) · [Find a component or study](project_index.md) · [Report catalogue](../reports/README.md)

## Folder layout

| Location | What belongs here |
|---|---|
| [cad/lanes_u4m2](../cad/README.md) | Routed bodies, M5/M6 guide revisions, A/B/C end geometry, the U spring assembly and bench fixtures. Open the [print list](installation_guide.md#full-front-print-list) for station-specific selections. |
| [cad/modules](../cad/modules/) and [cad/tank](../cad/tank/) | Original U/M STEP files, tank geometry and reference images |
| [cad/previews](../cad/previews/u4m2/README.md) and [cad/simulation_reference](../cad/simulation_reference/u4m2_500g/README.md) | STEP-based previews and the annotated 500 g simulation reference |
| [simulations/u4m2/extreme_tests](../simulations/u4m2/extreme_tests/README.md) | The first two extreme-test rounds and the [free-space and repeated-duty study](../simulations/u4m2/extreme_tests/free_space_20261120/README.md). Results are grouped by component and test. |
| [simulations/u4m2/lanes_20261113](../simulations/u4m2/lanes_20261113/README.md) | Source lane solvers and dated guide, seat, bore and full-motion studies, with their local evidence and handoffs |
| [Other U4+M2 simulations](../simulations/README.md) and [shared models](../simulations/shared/README.md) | Backbone, tank, rear deployment, earlier controllers, common kernels and model dependencies |
| [data/materials](../data/materials/README.md) | Material properties, current stiffness database and historical inputs |
| [reports/projects](../reports/projects/) | Technical reports grouped by [M5 structure](../reports/projects/m5_structure/), [rope routing](../reports/projects/rope_routing/), [motion control](../reports/projects/motion_control/) and [extreme tests](../reports/projects/extreme_tests/) |
| [reports/daily](../reports/daily/), [weekly](../reports/weekly/) and [builders](../reports/builders/README.md) | Dated morning and evening editions, earlier PDF and Word reports, weekly presentations and their generators |
| [nextstep](../nextstep/README.md) | Current test programme, priorities and measurement criteria |
| [docs](.) | Project index, installation guide, design status, limitations, history and time conventions |
| [scripts](../scripts/) and [workflows](../.github/workflows/) | Repository-level configuration, publication and automated checks |
| [archive](../archive/README.md) | Earlier design alternatives, superseded prototype geometry and historical utilities |

When adding a report, reuse the existing date heading on the [home page](../README.md#daily-updates) or add one level-two heading for a new date in descending order. Keep morning, evening and project work from the same day together. Link each new technical report from the [report catalogue](../reports/README.md) and the relevant [project entry](project_index.md).

## Extreme studies and project report moves

| Previous location | Current location |
|---|---|
| `simulations/u4m2/lanes_20261113/extreme_round1_20261119/` | [extreme_tests/round1_20261119](../simulations/u4m2/extreme_tests/round1_20261119/README.md) |
| `simulations/u4m2/lanes_20261113/extreme_round2_20261119/` | [extreme_tests/round2_20261119](../simulations/u4m2/extreme_tests/round2_20261119/README.md). Use the [result folder table](../simulations/u4m2/extreme_tests/README.md#round-2-result-folders) to locate the original filename. |
| `reports/daily/M5_Joint_Test_*` and `M5_Retained_Seat_*` | [reports/projects/m5_structure](../reports/projects/m5_structure/) |
| `reports/daily/M5_Seat_and_Shared_Bore_*` | [reports/projects/rope_routing](../reports/projects/rope_routing/) |
| `reports/daily/Yaw_Pitch_Closeout_*` | [reports/projects/motion_control](../reports/projects/motion_control/) |
| `reports/daily/Extreme_Simulation_Round_2_*` | [reports/projects/extreme_tests](../reports/projects/extreme_tests/) |

Paths recorded in archived data identify inputs at the stated source revision. The two rounds retain their original data files, hashes and CAD inputs.

## Earlier path changes

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

The [earlier file-by-file path map](path_migration.csv) covers this first migration, including the original report relocation.

## Execution and provenance

The active model resolves shared inputs through [project_paths.py](../simulations/u4m2/project_paths.py). It still uses the same H8U12 rod kernel and stiffness database. Shared legacy rod scripts resolve the central material catalogue from their new location. See the [simulation commands](../simulations/README.md#run-and-verify-the-closed-loop-study) and [report builder instructions](../reports/builders/README.md).

The archived full-length CAD is still **not the simulated design**. Its [warning](../archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md) and [cleanup review](../archive/superseded_cad/full_length/CLEANUP_REVIEW_CONFIRMATION.md) remain with it. Archiving preserves those records; it does not validate or replace the geometry.
