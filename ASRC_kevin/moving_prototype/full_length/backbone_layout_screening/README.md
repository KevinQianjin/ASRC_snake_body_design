> **IGNORE — does not match the simulated design (marked 11 November 2026).** The files in `moving_prototype/full_length/` use 84 mm shells with 12 mm pin joints and, for the backbone, two separate rods with a free joint. The design and all simulations use **continuous 96 mm modules with no pin joint, and one Ø1.8 mm NiTi rod along the full 96 mm of each M module**. Use [`ASRC_kevin/telescopic_planar_study/backbone_20261108/model_data/MODEL_DATA.md`](../../../telescopic_planar_study/backbone_20261108/model_data/MODEL_DATA.md) for the model parameters. See [`NOT_THE_SIMULATED_DESIGN.md`](../NOT_THE_SIMULATED_DESIGN.md).

# Backbone layout screening

This is a simple elastic Euler-Bernoulli beam estimate, not finite-element analysis. It compares bending a 1.8 mm rod over the 84 mm M-module body with forcing the same angle change across the 12 mm articulated gap. The assumed NiTi modulus is swept from 30 to 70 GPa because the actual grade/phase data are not yet supplied.

At 40 GPa and 25 degrees, estimated moment/stress are 107.1 N mm / 187 MPa over one module, versus 749.5 N mm / 1309 MPa across the gap. The simple curvature estimate is 7.0 times higher for the short gap.

This supports keeping the two M-module rods separate across their hinge. It does not select an end-anchor design: no anchor geometry, contact, friction, pullout, PA12 failure, NiTi superelastic response, or measured service force is included. Euler buckling loads in the CSV are ideal pin-ended estimates and should be treated only as a warning scale. Print a fit/retention coupon and test it with a force gauge before any payload or high-tension test.

Files: `layout_screening.csv` contains the calculation table; `layout_stress_comparison.png` plots estimated bending stress. Run with `python simulate_backbone_layout.py`.

