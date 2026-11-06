# Reach and extension screening study

This study compares the existing 31-module reference layout with longer layouts and different allocations of flexible front modules and rear backbone stiffness. It is a passive, planar gravity equilibrium calculation using the project's rear-backbone beam solver.

## Main result

The nominal module pitch is assumed to be 48 mm, so a straight 1600 mm path requires at least 34 modules (1632 mm nominal length). In the sweep of 33,760 configurations, 2,641 configurations with no tip payload pass the model's reach, height, width, and reference backbone-yield screens. None of the 500 g tip-payload configurations pass all four screens.

One illustrative unloaded candidate is 34 modules, H1/U29/D2/L2, four flexible front modules, and a 6 mm 304 backbone. The model predicts a 1615 mm horizontal tip reach, 228 mm capsule vertical span, 156 MPa backbone stress, and 455 g total system mass. This is a screening candidate, not a validated design. Its four-module flexible front section may not provide enough articulation for the real route.

For comparison, the existing 31-module H8/U12/D8/L3 reference with a 4.2 mm backbone predicts 1107 mm tip reach, 620 mm capsule vertical span, 180 MPa stress, and 235 g mass without a tip payload. The selected longer candidate gains about 507 mm of horizontal reach but nearly doubles modeled system mass and reduces the flexible front section from 8 modules to 4.

## Figures

- `reach_vs_length.png`: best reach by total module count and backbone diameter among designs that pass the passive yield and height screens; includes the existing reference point and target lines.
- `reach_sag_tradeoff.png`: reach versus sag for the unloaded design sweep, with the reach and height boundaries.
- `reference_stack_extension.png`: adds modules to the existing H8/D8/L3 composition to show whether simply lengthening that stack solves reach.
- `payload_effect_on_candidates.png`: compares representative unloaded candidate poses with their 500 g loaded predictions.
- `reach_target_screen_counts.png`: number of configurations passing the reach screen by payload.

## Data and reproduction

- `all_configurations.csv`: every solved configuration and its predicted metrics/screens.
- `summary_by_length_front_core.csv`: grouped summary.
- `target_feasible_candidates.csv`: configurations passing the unloaded reach target screen.
- `reference_stack_candidates.csv`: cases that retain the reference H/D/L composition.
- `study_summary.json`: sweep scope, boundaries, and aggregate counts.

Run `python reach_extension_study.py` from the repository root to reproduce the CSVs and figures, using the project's NumPy, SciPy, and Matplotlib environment. Add `--no-plots` to update the numerical outputs only.

## Limits

These results do not model tendon actuation, actual entry position, wall contact, friction, collision clearance, 3D routing, or dynamic motion. The “reach target” screen assumes the base may remain outside the 1600 mm area; the “whole-body box” screen separately requires the entire modeled chain envelope to fit within the box. The 500 g tip load is a comparison case, not a confirmed payload specification. The 205 MPa 304 yield value is a reference screen, not a measured hardware limit. Validate promising designs with the real geometry, loads, cable routing, and contact constraints before fabrication.
