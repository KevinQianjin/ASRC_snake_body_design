# Backbone layout screening

This is a simple elastic Euler-Bernoulli beam estimate, not finite-element analysis. It compares bending a 1.8 mm rod over the 84 mm M-module body with forcing the same angle change across the 12 mm articulated gap. The assumed NiTi modulus is swept from 30 to 70 GPa because the actual grade/phase data are not yet supplied.

At 40 GPa and 25 degrees, estimated moment/stress are 107.1 N mm / 187 MPa over one module, versus 749.5 N mm / 1309 MPa across the gap. The simple curvature estimate is 7.0 times higher for the short gap.

This supports keeping the two M-module rods separate across their hinge. It does not select an end-anchor design: no anchor geometry, contact, friction, pullout, PA12 failure, NiTi superelastic response, or measured service force is included. Euler buckling loads in the CSV are ideal pin-ended estimates and should be treated only as a warning scale. Print a fit/retention coupon and test it with a force gauge before any payload or high-tension test.

Files: `layout_screening.csv` contains the calculation table; `layout_stress_comparison.png` plots estimated bending stress. Run with `python simulate_backbone_layout.py`.

