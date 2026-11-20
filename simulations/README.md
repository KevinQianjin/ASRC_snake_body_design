# Simulation index

Use the [engineering project index](../docs/project_index.md) for links across CAD, code, results and reports. Each study keeps the solver and data needed to interpret its saved run.

## Current 500 g studies

| Study | What to open |
|---|---|
| Extreme tests | [Both rounds and result folders](u4m2/extreme_tests/README.md) · [Round 1 critical poses](u4m2/extreme_tests/round1_20261119/README.md) · [Round 2 validation and reproduction](u4m2/extreme_tests/round2_20261119/README.md#reproduction) |
| Controlled yaw, pitch, return and withdrawal | [Full mission](u4m2/lanes_20261113/cycle_closeout_20261119/README.md) · [Twelve-rope tensions](u4m2/lanes_20261113/cycle_closeout_20261119/results/yaw_pitch/ROPE_TENSIONS.md) · [Installed motion map](u4m2/extreme_tests/round2_20261119/results/motion_limits/combined_motion.png) |
| M5 seats, hub, pin and coupon | [Large-rotation shell](u4m2/lanes_20261113/m5_large_rotation_20261118/README.md) · [Retained seats](u4m2/lanes_20261113/m5_retained_seat_20261118/README.md) · [Coupon test](u4m2/lanes_20261113/m5_seat_bench_20261119/README.md) · [P3 fixture and forms](u4m2/lanes_20261113/p3_pin_fixture_20261119/README.md) |
| M6 fixed guides | [Bond-gap comparison](u4m2/lanes_20261113/evening_20261119/README.md) · [Full-mission CAD gaps and support motion](u4m2/extreme_tests/round2_20261119/results/m6_guides/) |
| Rope routing and drive | [Bellmouth holds](u4m2/lanes_20261113/morning_20261116/README.md) · [Shared bore](u4m2/lanes_20261113/shared_bore_20261119/README.md) · [Twelve-rope reversal histories](u4m2/extreme_tests/round2_20261119/results/rope_control/) |
| U structure and fatigue | [Four blades and cage](u4m2/extreme_tests/round2_20261119/results/u_structure/) · [Mission spectrum and material requirements](u4m2/extreme_tests/round2_20261119/results/fatigue_and_strength/) |

The current 21/24/28 mm rope radii and eight guide stations are documented in the [installation guide](../docs/installation_guide.md#build-configuration). For the staged transition from the original lane geometry, see the [14 November validation](u4m2/lanes_20261113/GUIDED_VALIDATION.md) and [15 November saddle refinement](u4m2/lanes_20261113/guided_refinement_20261115/README.md).

## Earlier controller and lane studies

| Study | Source and results | Purpose |
|---|---|---|
| U4+M2 NiTi backbone | [Backbone study](u4m2/backbone_20261108/README.md) | NiTi-backed front model and early winch-control studies |
| Separate rope lanes (13 Nov) | [Lane study](u4m2/lanes_20261113/README.md) · [3D modules](../cad/lanes_u4m2/README.md) | 13 November baseline with 21/24/27 mm lanes and M5 rope-chord checks |
| Closed-loop round trip v3 | [Study section 13](u4m2/backbone_20261108/README.md#13-exact-20-reference-and-correction-during-moves-closed-loop-v3-2026-11-12) · [Results](u4m2/backbone_20261108/closed_loop_v3_results/) | Exact 20° reference; four of five cases pass every check |
| Closed-loop round trip v2 | [Study section 12](u4m2/backbone_20261108/README.md#12-closed-loop-round-trip-v2-operating-pretension-and-refined-path-closed_loop_v2py-2026-11-12) · [Controller](u4m2/backbone_20261108/closed_loop_v2.py) | 3 N operating tension enforced, tension-aware arrival, refined path |
| Closed-loop round trip | [English report](u4m2/backbone_20261108/closed_loop_results/REPORT.md) · [Controller](u4m2/backbone_20261108/closed_loop_cycle.py) | Head-angle and tendon-tension feedback (v1) |
| Stable startup and 3 N pretension | [Study section 10](u4m2/backbone_20261108/README.md#10-round-trip-cycle-with-3-n-pretension-and-a-stable-startup-2026-11-11) | Open-loop reference for the feedback study |
| Tank and rear deployment | [Telescopic study](u4m2/README.md) | Tank geometry, front clearance and rear support |

## Reference studies and shared dependencies

| Study | Role |
|---|---|
| [6 November planar model](u4m2/stiffness_63mm_20261106/README.md) | Baseline results and code still used by the active model |
| [6 November spatial model](u4m2/steering_63mm_20261106/README.md) | Spatial rod implementation imported by the active model |
| [M axial stiffness sweep](u4m2/m_axial_sweep_20261108/README.md) | Backbone design rationale and shared rod implementation |
| [Model input sheet](u4m2/backbone_20261108/model_data/MODEL_DATA.md) | Model dimensions, assumptions and data provenance |
| [Module stiffness database](../data/materials/module_stiffness.sqlite3) | Shared material/module properties; retain study-specific snapshots |

## Historical studies

These use earlier configurations or assumptions. Their inputs and outputs are retained for reproducibility; they are not interchangeable with the current U4+M2 baseline.

- [H8U12 rear with a 500 g head](shared/h8u12_front5to8_payload500g/README.md).
- [Four-rope inverse study, 5–11 front modules](../archive/legacy_studies/four_rope_inverse_5_to_11/README.md).
- [Front module count sweep](../archive/legacy_studies/front_sweep_5_to_11/README_front_sweep.md).
- [Passive reach and extension study](../archive/legacy_studies/reach_extension/results/README.md).
- Earlier [rope models](shared/legacy_models/README_ropes.md), [rear backbone model](shared/legacy_models/README_rear_backbone.md), [sag model](shared/legacy_models/README_pla_sag.md) and [horizontal inverse study](shared/legacy_models/README_horizontal_inverse.md).

## Run and verify the closed-loop study

Use a Python environment with the model dependencies installed. The study uses NumPy, SciPy, Numba, Matplotlib, Pillow, trimesh, VTK and CAD support from cadquery-ocp; MP4 rendering also requires FFmpeg. Existing dependency lists include [rope requirements](shared/legacy_models/requirements_ropes.txt) and [CAD requirements](u4m2/requirements-cad.txt). These lists are not yet a single locked environment for all studies.

From the repository root, verify the saved study and controller:

```bash
cd simulations/u4m2/backbone_20261108
python -m unittest test_closed_loop.py -v
python validate_closed_loop_results.py
```

To regenerate the reference gains and a case:

```bash
python closed_loop_cycle.py --prepare
python closed_loop_cycle.py --case nominal
```

Other cases are `E75`, `payload550g`, `free1500mm` and `ropeEA80pct`. Full runs can take substantial time. See the [report reproduction instructions](u4m2/backbone_20261108/closed_loop_results/REPORT.md#reproduction) before regenerating data or animations. Re-running a case writes its result files.
