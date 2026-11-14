# Guided validation evidence — 14 November 2026

Read the [English engineering report](../GUIDED_VALIDATION.md) first. Both main cases use a **500 g head payload**. V2 rigid mounting is rejected by the bent-pose geometry screen; an ideal-guide simulation result does not override that failure.

| Folder / file | Meaning |
|---|---|
| `baseline/inverse/` | Guided 21/24/27 mm startup and held-yaw equilibria with nominal module mass; includes recorded seed recovery |
| `baseline/reference/` | Full open-loop length-command round trip |
| `baseline/closed_loop/` | Rebuilt gains, settled samples and accepted motion substeps |
| `baseline/path_audit/` | All five archives checked for per-hole loading and sampled rope/flexure clearance |
| `candidate/inverse/` | 21/24/28 mm, CAD-mass startup and direct eight-cell held-yaw continuation |
| `candidate/reference/` | Candidate open-loop round trip, including its failed angle checks |
| `candidate/closed_loop/` | Candidate gains and full closed-loop data |
| `candidate/path_audit/` | Per-hole forces, coverage, per-state clearances and peak locations |
| `candidate/mount_audit/` | Selected-pose rigid-guide/body Boolean intersections; not a full contact simulation |
| `candidate/mesh_convergence.json` | Fixed-tension 8→16 cell refinement at three holds |
| `candidate/design_loads.json` | Preliminary factor-three loading requirements; no strength acceptance |
| `candidate/path_overview.png` | Accepted motion sequence, not physical time |
| `diagnostics/` | Partial exploratory runs and earlier screens; not the final validation dataset |
| `legacy_reader_coverage.json` | Corrected coverage of the four historical archives, including an old 550 g case solely to test reading |
| `logs/` | Solver and test output retained for traceability |
| `environment.json` | Python and dependency versions |
| `validation.json` | Numerical tests and saved-result consistency checks |
| `SHA256SUMS` | Hashes of saved NPZ trajectories and relevant CAD/model inputs |

Recorded artifact paths are relative to the simulation folder; logs preserve the original execution paths.

The two cases each provide these formats:

- `inverse/*_states.npz`: paired `kN_z8`/`kN_T8` startup states or `yN_z8`/`yN_T8` yaw states.
- `reference/nominal_states.npz`: `z`, aligned with solved rows in `nominal.json`.
- `closed_loop/nominal_states.npz`: `closed`, aligned with settled rows in `nominal.json`.
- `closed_loop/nominal_trace_states.npz`: `z`, `rest_m` and `tensions_n`, aligned with **every** row of `nominal_trace.json`, including the initial state.
- `closed_loop/nominal_motion.csv.gz`: one row per accepted trace state, with all rope commands, internal path lengths, tensions, head pose, clearance and stability. Unstretched command lengths include 1 m of free rope; internal geometric path lengths exclude it.
- `path_audit/hole_loads.csv.gz`: 48 guide-hole force records per state: 32 in M5 and 16 in M6. Forces use local rod x axial, y up and z right. The station identifier uses CAD local z in millimetres.

The stored rod vector has 192 scaled degrees of freedom (6 modules ×8 cells ×4 strains). It must be decoded using the matching model scale; it is not a Cartesian coordinate array. The path audit includes overlaps between inverse, reference, settled and trace records and separately reports the exact unique geometry count.

Reproduction commands and acceptance limits are in the [report](../GUIDED_VALIDATION.md). The [V2 CAD README](../../../../cad/lanes_u4m2/guides_v2/README.md) describes actual attachment features and unresolved physical installation issues.
