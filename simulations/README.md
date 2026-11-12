# Simulation index

[Project home](../README.md) · [Current design](../docs/current_design.md) · [Repository map](../docs/repository_map.md)

Active U4+M2 studies are in `u4m2/`; shared dependencies and their reference runs are in `shared/`. Superseded studies are in `../archive/legacy_studies/`. Study-local inputs and results remain beside their source. Dates identify research provenance, not whether a module is still required.

## Active studies

| Study | Source and results | Purpose |
|---|---|---|
| U4+M2 NiTi backbone | [Backbone study](u4m2/backbone_20261108/README.md) | Active front model, steering, tank screening and winch control |
| Closed-loop round trip v3 | [Study section 13](u4m2/backbone_20261108/README.md#13-exact-20-reference-and-correction-during-moves-closed-loop-v3-2026-11-12) · [Results](u4m2/backbone_20261108/closed_loop_v3_results/) | Exact 20° reference; four of five cases pass every check; latest numerical study |
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
