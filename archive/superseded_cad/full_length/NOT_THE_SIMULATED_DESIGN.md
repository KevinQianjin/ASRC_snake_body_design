# Ignore this folder for design decisions

Marked 11 November 2026.

Everything in `archive/superseded_cad/full_length/` was built on a placeholder layout:

- 84 mm module shells with a 12 mm pin joint (M3 bolts) between modules;
- for the backbone, two separate rods (about 150 mm, one per M module), retained at the shell ends, with the M1–M2 joint left free;
- `backbone_layout_screening/` compares bending the rod over 84 mm against bending it across the 12 mm gap.

**This is not the design.** The design, and every simulation from 6 to 11 November 2026, uses:

- continuous 96 mm modules (U1–U4, M1–M2) with no pin joint or gap;
- one Ø1.8 mm NiTi rod in each M module, running its full 96 mm length, fixed to both M end disks and guided laterally.

The model parameters are listed in [`../../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md`](../../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md).

The files are kept for reference only. Do not print, order or test from them, and do not use the layout screening stresses. The anchor fit coupon (`09_backbone_anchor_coupon.scad`) only checks how a ferrule seats in PA12; any reuse must first be checked against the 96 mm continuous-module design.

For the confirmed cleanup proposal list (with no deletions applied yet), see [`CLEANUP_REVIEW_CONFIRMATION.md`](CLEANUP_REVIEW_CONFIRMATION.md).
