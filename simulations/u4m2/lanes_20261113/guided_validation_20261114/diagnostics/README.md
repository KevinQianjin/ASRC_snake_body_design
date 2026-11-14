# Exploratory diagnostics

These are intermediate runs, not the final validation datasets.

- `candidate_nominal_mass_partial`: the 21/24/28 mm lane candidate before CAD-estimated masses were added. The coarse-seed sweep was interrupted after an unsuccessful large-angle refinement. It is superseded by `../candidate/`.
- `baseline_partial_startup_audit` and `baseline_partial_hold_audit`: earlier per-hole force and unsigned flexure-distance screens. They do not contain the final full-path closed-solid/end-region classification. Use `../baseline/path_audit/` for reported results.

The baseline inverse folder retains its original unsuccessful coarse sweep records alongside the accepted NPZ, `sweep_repairs.json` and `fine_continuation.json`. The original optimisation JSON is not rewritten to imply that rejected seeds passed. Full trajectory coverage is checked independently by the strict archive reader and the reference-generation guard.
