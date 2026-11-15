# 15 November 2026 — guided CAD refinement and V3 development

[Full daily report](../../../../reports/daily/Report_2026_11_15.md)
· [Final candidate CAD](../../../../cad/lanes_u4m2/guides_v3/README.md)
· [Machine-readable final summary](validated_summary.json)
· [Consolidated selected poses](selected_pose_metrics.csv.gz)
· [Numerical/design comparison](comparison.png)
· [Next-run handoff](HANDOFF.md)

**No manufacturing release.** Positive guide/land contact and finite end-region
rope penetration remain blockers. This folder distinguishes numerical checks,
rejected geometry variants, selected ideal equilibria and physical limitations.

## Evidence map

| Path | Meaning |
|---|---|
| `run_context.json`, `environment.json` | Reporting interval, deadline, checked revisions and dependency versions |
| `mount_convergence_float64/` | Final complete-body V2 Boolean study: original/2/1/0.5 mm CAD surface resolution, 0°/90°/175° holds |
| `mount_convergence/`, `probe/` | Earlier diagnostic comparisons using the recorded legacy Boolean adapter |
| `held_path_1mm/`, `held_path_0p5mm/` | Independent 36-hold rope/flexure/end-region resolution comparison |
| `variants/` | Parameter, geometry-check and mass snapshots for the explored relief variants; experimental STLs are retained as `.stl.gz` files |
| `v3_mount/`, `slope_0p6_mount/`, `slope_1p0_mount/` | Early three-pose screens at slopes 0.3, 0.6 and 1.0 |
| `contact_subset/`, `v3_mass_holds/`, `v3_contact/`, `v3_path/` | Initial 181-record experiment using the early slope 1.0 CAD; 17 records have guide contact |
| `slope_1p5_recheck/` | Contact-only check of an **invalid disconnected-cap** variant; zero overlap does not validate those parts |
| `slope_1p5_land_recheck/` | Corrected-land check at previously failing records; residual contact is concentrated near the fixed land |
| `contact_subset_final/` | 217 selected records, including 36 additional distinct motion geometries; full source provenance and deterministic seed |
| `v3_final_mass_holds/` | Final mass re-solves and exact baseline/candidate mass snapshots |
| `v3_final_contact/` | Final 0.5 mm complete-body guide checks, with no body cropping |
| `diagnostics/v3_final_contact_partial/`, `v3_final_contact_completion/` | Preserved interrupted main checkpoint and sequential completion of missing poses; final summary validates input hashes and unique coverage |
| `v3_final_resolution_spotcheck/`, `diagnostics/memory_limit_event.json` | **Incomplete:** attempted 0.25 mm check returned no results after an 8 GiB memory-limit event; not convergence evidence |
| `v3_final_path/` | Final sampled rope clearance, finite end-region penetrations and per-hole loads |
| `v3_final_design_loads.json` | Preliminary load multipliers/arm comparison; not a strength pass |
| `socket_gap_verification.json` | 112 actual-STL gap measurements validating the explicit land/relief |
| `v2_reproduction.json`, `published_candidate_match.json` | V2 byte-for-byte reproduction and identity of published vs simulated candidate inputs |
| `diagnostics/`, `logs/` | Rejected/aborted attempts and successful final checks, labelled separately |

The final CAD has an actual 0.5 mm land and a relief slope of 1.5. Early variants
used nine loft planes and missed the land boundaries; their metadata described
an intended land that the STL did not exactly provide. Do not use their old
full-depth bonding-area fields as final joint sizing. The corrected geometry
uses explicit ±0.25 mm planes and reports the short-land nominal area.

Diagnostic and experimental STL exports are compressed without changing their
bytes. [The mesh manifest](diagnostics/mesh_export_manifest.json) records source
names and SHA-256 hashes. Redundant large deformed-body exports are omitted;
the original and 1 mm probe bodies remain compressed, and every body can be
regenerated from its saved pose, source CAD and recorded refinement. Published
V3 CAD remains directly readable as STL. Historical evidence is unchanged.

`selected_pose_metrics.csv.gz` reports internal geometric rope paths, tensions,
head pose/material frames, guide overlaps and rope contact by selected record.
It does not contain a newly executed closed-loop command sequence. Repeated
archive records are retained for provenance; unique-geometry counts are separate.
The final selection adds 36 geometries with seed 20261115 before final checking;
it does not certify every intermediate pose or a probabilistic reliability level.

## Reproduce

Use the versions in [environment.json](environment.json), including the
Manifold build supporting `Mesh64`. Run the following from the parent
`simulations/u4m2/lanes_20261113` folder. Choose a **new output root** for new
experiments; these dated outputs are the evidence for this report.

```bash
python ../../../cad/lanes_u4m2/guides_v3/build.py
python ../../../cad/lanes_u4m2/guides_v3/verify_socket_land.py --out /tmp/socket-gap-check.json
python select_contact_states.py guided_validation_20261114/candidate --out /tmp/asrc-selection --extra-motion-samples 36
python candidate_mass_holds.py /tmp/asrc-selection/selected_states.npz --baseline-mass ../../../cad/lanes_u4m2/guides_v2/mass_model.json --candidate-mass ../../../cad/lanes_u4m2/guides_v3/mass_model.json --out /tmp/asrc-mass-holds --max-seconds 600
python mount_refinement_study.py /tmp/asrc-mass-holds/mass_holds_states.npz --cad ../../../cad/lanes_u4m2/guides_v2 --guide-cad ../../../cad/lanes_u4m2/guides_v3 --out /tmp/asrc-contact --resolutions 0.5 --all-states --max-seconds 1200
python guide_path_audit.py /tmp/asrc-mass-holds/mass_holds_states.npz --cad ../../../cad/lanes_u4m2/guides_v2 --radii 21 24 28 --cad-max-axial-span-mm 0.5 --out /tmp/asrc-rope-path
python guide_load_design.py /tmp/asrc-rope-path --out /tmp/asrc-design-loads.json
python -m unittest -v test_guides test_cad_surface_refinement
```

For the V2 surface study, use its saved inverse-state archive with
`mount_refinement_study.py --resolutions 0 2 1 0.5`, the V2 CAD folder and the
default three labels. `--legacy-float32` reproduces the earlier trimesh adapter.
The final study reuses native complete-body solids and keeps float64 transfer;
it does not use the rejected slab-cropping shortcut.

Generate an early variant in a separate temporary folder with, for example,
`python ../../../cad/lanes_u4m2/guides_v3/build.py --slope 1.0 --legacy-nine-sections --out /tmp/asrc-early-variant`.
The legacy option intentionally reproduces the old land construction and must
not be mistaken for the final candidate. The invalid early slope 1.5 generation
fails its component-count check, as recorded in its log.

`finalize_guided_refinement.py` checks completed final artifacts, input identity
and counts before regenerating this dated report's pose table, figure and
README entry. It is specific to this study; do not use it to overwrite the next
day's report. `SHA256SUMS` records the retained dated evidence after publication
preparation, excluding itself.

## Interpretation and next work

The CAD mapping follows ideal rod material frames and is not solid/contact FEA.
The physical joint is still missing from the homogenised stiffness model. A
0.5 mm bonding land is not a validated articulation; wire retention is not
proven axial holding. Prioritise a local joint/contact model and finite end-hole
rope routing before claiming full-motion compatibility or printing a final set.
The payload remains 500 g; no 550 g run or new hardware measurements are included.
