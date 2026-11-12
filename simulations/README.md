# Simulation index

[Project home](../README.md) · [Current design](../docs/current_design.md) · [Repository map](../docs/repository_map.md)

This is the simulation navigation entry. Existing code and data paths are retained in this organisation stage because the active model imports earlier study modules. Dates identify research provenance, not whether a module is still required.

## Active studies

| Study | Source and results | Purpose |
|---|---|---|
| U4+M2 NiTi backbone | [Backbone study](../ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md) | Active front model, steering, tank screening and winch control |
| Closed-loop round trip | [English report](../ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/REPORT.md) · [Controller](../ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_cycle.py) | Head-angle and tendon-tension feedback; latest numerical study |
| Stable startup and 3 N pretension | [Study section 10](../ASRC_kevin/telescopic_planar_study/backbone_20261108/README.md#10-round-trip-cycle-with-3-n-pretension-and-a-stable-startup-2026-11-11) | Open-loop reference for the feedback study |
| Tank and rear deployment | [Telescopic study](../ASRC_kevin/telescopic_planar_study/README.md) | Tank geometry, front clearance and rear support |

## Reference studies and shared dependencies

| Study | Role |
|---|---|
| [6 November planar model](../ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106/README.md) | Baseline results and code still used by the active model |
| [6 November spatial model](../ASRC_kevin/telescopic_planar_study/steering_63mm_20261106/README.md) | Spatial rod implementation imported by the active model |
| [M axial stiffness sweep](../ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108/README.md) | Backbone design rationale and shared rod implementation |
| [Model input sheet](../ASRC_kevin/telescopic_planar_study/backbone_20261108/model_data/MODEL_DATA.md) | Model dimensions, assumptions and data provenance |
| [Module stiffness database](../ASRC_kevin/module_stiffness.sqlite3) | Shared material/module properties; retain study-specific snapshots |

## Historical studies

These use earlier configurations or assumptions. Their inputs and outputs are retained for reproducibility; they are not interchangeable with the current U4+M2 baseline.

- [H8U12 rear with a 500 g head](../ASRC_kevin/h8u12_front5to8_payload500g/README.md).
- [Four-rope inverse study, 5–11 front modules](../ASRC_kevin/four_rope_inverse_5_to_11/README.md).
- [Front module count sweep](../ASRC_kevin/front_sweep_5_to_11/README_front_sweep.md).
- [Passive reach and extension study](../reach_extension_results/README.md).
- Earlier [rope models](../ASRC_kevin/README_ropes.md), [rear backbone model](../ASRC_kevin/README_rear_backbone.md), [sag model](../ASRC_kevin/README_pla_sag.md) and [horizontal inverse study](../ASRC_kevin/README_horizontal_inverse.md).

## Run and verify the closed-loop study

Use a Python environment with the model dependencies installed. The study uses NumPy, SciPy, Numba, Matplotlib, Pillow, trimesh, VTK and CAD support from cadquery-ocp; MP4 rendering also requires FFmpeg. Existing dependency lists include [rope requirements](../ASRC_kevin/requirements_ropes.txt) and [CAD requirements](../ASRC_kevin/telescopic_planar_study/requirements-cad.txt). These lists are not yet a single locked environment for all studies.

From the repository root, verify the saved study and controller:

```bash
cd ASRC_kevin/telescopic_planar_study/backbone_20261108
python -m unittest test_closed_loop.py -v
python validate_closed_loop_results.py
```

To regenerate the reference gains and a case:

```bash
python closed_loop_cycle.py --prepare
python closed_loop_cycle.py --case nominal
```

Other cases are `E75`, `payload550g`, `free1500mm` and `ropeEA80pct`. Full runs can take substantial time. See the [report reproduction instructions](../ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/REPORT.md#reproduction) before regenerating data or animations. Re-running a case writes its result files.
