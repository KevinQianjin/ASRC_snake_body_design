> **IGNORE — does not match the simulated design (marked 11 November 2026).** The files in `moving_prototype/full_length/` use 84 mm shells with 12 mm pin joints and, for the backbone, two separate rods with a free joint. The design and all simulations use **continuous 96 mm modules with no pin joint, and one Ø1.8 mm NiTi rod along the full 96 mm of each M module**. Use [`simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md`](../../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) for the model parameters. See [`NOT_THE_SIMULATED_DESIGN.md`](NOT_THE_SIMULATED_DESIGN.md).

# Backbone anchor layout: first prototype decision

## Layout to evaluate

- Use two separate 1.8 mm backbone rods: one inside M1 and one inside M2.
- Retain each rod at the two ends of its own M module (four retention points total).
- Keep the three intermediate guide holes in each module as sliding guides; they center the rod but do not clamp it.
- Leave the 12 mm articulated gap between M1 and M2 free of backbone rod. Do not connect the rods across the joint.

The assembly preview in `U4M2_backbone_assembly.scad` displays red markers at the proposed rod-end retention locations. These markers are conceptual only; they are not printable anchors, material selections, or evidence of strength.

## Why this is the first layout to test

The current chain allows the M1–M2 interface to rotate. A single continuous rod across that joint would resist the joint bend. Separate rods let each M module provide its own backbone action while leaving the interface articulated. Using guides that slide avoids clamping the rod at multiple points along its length.

## Prototype sequence

1. Print one M-module shell with its three guides. Confirm that the 1.8 mm rod passes through all guides without binding.
2. Make a short end-retention coupon with the same end-plate thickness and center passage as the module. Try replaceable metal ferrules/collars captured at the ends; do not rely on printed threads or a guessed press fit.
3. Check that retention prevents axial slip while the rod still bends, and inspect the PA12 around both ends for cracks, crushing, or permanent deformation.
4. Repeat on one complete M module, then on the pair with the joint bent. Apply only a measured, low test load first and record load, displacement, and joint angle.

The existing model gives a 1.8 mm rod and module geometry envelope, but does not define exact end disk geometry, NiTi grade/condition, anchor dimensions, friction, or a measured service load. Therefore this layout is a testable starting point, not a validated or load-rated design. Do not use the earlier 248 N value as an anchor design load unless the team confirms it applies to this specific rod-end connection.

