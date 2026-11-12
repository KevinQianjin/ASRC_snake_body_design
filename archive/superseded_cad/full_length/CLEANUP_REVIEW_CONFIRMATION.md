# Cleanup review confirmation (no removals yet)

Date: 2026-11-12

This folder remains marked as **not the simulated design**. The files below are confirmed cleanup candidates for later archiving or removal, but **nothing is deleted in this change**.

## Confirmed archive/removal review list

- `00_full_assembly.scad`
- `00_full_assembly_standalone.scad`
- `01_U1_base.scad` through `08_head_placeholder.scad`
- `U4M2_backbone_assembly.scad`
- `M2_backbone_prototype.scad`
- `module_common.scad`
- `BUILD_AND_PRINT_GUIDE.md`
- `BOM_AND_BUILD_STEPS.md`
- `09_backbone_anchor_coupon.scad`
- `BACKBONE_ANCHOR_LAYOUT_FIRST_PROTOTYPE.md`
- `backbone_layout_screening/`
- `simulate_backbone_layout.py`
- `../tendon_joint_prototype.scad` (review whether it still has value as a standalone demo)

## Keep for now

- `../../../cad/modules/UniDirectional_96.step`
- `../../../cad/modules/Medium_Stiffness_96.step`
- `../final_u4m2/`
- [Daily reports](../../../reports/README.md) (PDFs relocated to `../../../reports/daily/`)
- Existing simulation data and source files (research provenance)
- `NOT_THE_SIMULATED_DESIGN.md` (keep until replacement cad/modules/guide are ready)

## Removal order (after replacements exist)

1. Build and review the correct 96 mm continuous-module SCAD from current STEP files and model data.
2. Replace the incorrect BOM/print guide with guidance matched to that geometry.
3. Archive/remove the listed placeholder files after preserving useful history and updating links.

References:

- `../../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md`
- `NOT_THE_SIMULATED_DESIGN.md`
