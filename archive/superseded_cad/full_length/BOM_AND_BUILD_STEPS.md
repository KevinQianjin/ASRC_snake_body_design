> **IGNORE — does not match the simulated design (marked 11 November 2026).** The files in `moving_prototype/full_length/` use 84 mm shells with 12 mm pin joints and, for the backbone, two separate rods with a free joint. The design and all simulations use **continuous 96 mm modules with no pin joint, and one Ø1.8 mm NiTi rod along the full 96 mm of each M module**. Use [`simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md`](../../../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) for the model parameters. See [`NOT_THE_SIMULATED_DESIGN.md`](NOT_THE_SIMULATED_DESIGN.md).

# U4+M2 moving prototype: what to print, buy, and assemble

This is a fit-and-motion prototype, not a load-rated aircraft inspection robot. The anchor coupon helps compare fit and retention geometry; it does not establish a safe service load. Do not attach the inspection payload or apply high tendon forces until the assembly is physically tested and reviewed.

## Print

For the complete six-module body, export and print these from `U4M2_backbone_assembly.scad` one at a time:

- U1, U2, U3, U4: one of each.
- M1, M2: one of each, with the central rod guides included.
- Base interface: one, if mounting to a test stand.
- Head placeholder: optional sizing mock-up only; it is not the camera mount.
- `09_backbone_anchor_coupon.scad`: one PA12 coupon to check collar/ferrule pocket fit at 6, 8, and 10 mm nominal diameters.

The coupon is a material/process test and should use the same material and print orientation intended for the M-module end features. Export it with `export_printable_coupon=true`. The rod and grey ferrule previews are not part of the STL.

## Buy or source

| Item | Quantity / starting specification | Notes |
|---|---:|---|
| Straight NiTi backbone wire | 2 pieces, Ø1.8 mm, about 150 mm each | One independent rod per M module; confirm grade, transformation/phase condition, and allowable bend with supplier/team before load testing. |
| Rod end collars or ferrules | 4, compatible with Ø1.8 mm wire | Two per rod. Select after checking the coupon and how the supplier permits this wire to be retained; do not assume a generic 2 mm shaft collar fits. |
| PA12 printed modules | Six module bodies, plus coupon | Request exact PA12 grade/process from the print service. The current coupon sizes are screening values, not approved final dimensions. |
| M3 joint fasteners | 5 sets: bolts/pins plus lock nuts or retainers | One set at each of the five module joints. Confirm usable length against printed joint thickness. |
| Braided tendon cord | 4 runs, about 1 m each to start | Route through four guide paths; trim after assembly. Nominal 2 mm cord is the current fit assumption. |
| M4 fixture bolts | 2 | For fastening the coupon to a rigid pull-test fixture; fixture is not included. |
| Force gauge / spring scale | 1, suitable low range | Use to record force during retention checks. Do not jump to high loads. |

No servos are needed for the first manually pulled motion test. They can be selected after tendon force and travel are measured.

## Assembly and test sequence

1. Print one coupon in PA12 and measure the three pockets. Obtain the intended collar/ferrule sample and confirm which station seats it without looseness or cracking. The selected metal part must actually grip the rod; the coupon only captures its outer shoulder.
2. Print one M module and pass a Ø1.8 mm sample rod through the three intermediate guides. It should move freely; the guides are not clamps.
3. Fit a retention feature at each end of the rod inside that M module. Pull axially with a force gauge at a low force, record any slip, and inspect the end plates and rod for damage. Increase force gradually only after inspection.
4. Repeat for the second M module. Keep the two rods separate across the M1–M2 articulated joint.
5. Assemble the body with M3 joints and four tendons. Start with manual, low-force bending and no payload. Record tendon pull, joint angle, rod movement, and any damage.
6. Only after the first module and paired-module tests pass should the team decide whether to print/assemble the remaining full-length set and specify actuators.

## Important limits

The beam screening assumes an elastic rod with an assumed modulus range. It does not model ferrule gripping, PA12 strength, NiTi superelasticity, fatigue, joint contact, or a measured aircraft-inspection load. The 248 N value mentioned in earlier project material is not adopted here as a safe anchor test load. Confirm the service load and NiTi specification before defining an acceptance load. The red anchor markers in the assembly are diagrammatic only; the coupon is a test aid, not final anchor CAD.

