# Current limitations

[Project home](../README.md) · [Current design](current_design.md) · [Roadmap](roadmap.md)

The design has not passed an integrated, hardware-validated deployment cycle. The latest [closed-loop report](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) distinguishes settled-state success from failures before feedback correction. Earlier findings are preserved in [research history](history.md).

| Limitation | Current evidence | Work required |
|---|---|---|
| Tension during command transitions | **Addressed in simulation (12 Nov, v2):** with a 3 N correction target, tension-aware arrival and refined transitions, every recorded state of all five cases stays at ≥ 2.62 N ([section 12](../simulations/u4m2/backbone_20261108/README.md#12-closed-loop-round-trip-v2-operating-pretension-and-refined-path-closed_loop_v2py-2026-11-12)). Peak tension rises to 25–27 N. | Verify on hardware with measured rope and winch behaviour. |
| Transient angle error at large yaw with a heavier head | **Reference fixed (12 Nov, v3):** with an exact 20° reference, four of five cases pass every check in every recorded state (angle error during motion ≤ 0.61°, step move ≤ 2.5 mm). The 550 g head still has about 115 recorded states above 1° at 155–175° yaw (up to 3.1°) because the nominal gains have the wrong sign there; correction during moves made it worse ([section 13](../simulations/u4m2/backbone_20261108/README.md#13-exact-20-reference-and-correction-during-moves-closed-loop-v3-2026-11-12)). | Update the controller gains online from measured responses; test with independent payload and stiffness cases. |
| Controller convergence | All five cases meet the 1-degree settled-angle criterion; one 550 g sample reaches 16 corrections at 0.699-degree yaw error. | Improve convergence and test independent uncertainty cases. |
| Idealised dynamics and sensing | Simulations are quasi-static, with ideal measurements and no motor dynamics, delay or sensor noise. | Verify sampled dynamic control and actuator limits. |
| Unmeasured mechanical properties | Friction, backlash, NiTi hysteresis, fatigue, guide buckling and interface slip are not validated. | Test assembled modules, ropes and winches; calibrate the models. |
| Provisional head and cables | Clearance uses a 63 mm envelope and nominal 500 g payload rather than the complete head and cable geometry. | Integrate actual CAD, centre of mass and cable routing. |
| Incomplete CAD integration | The STEP-derived preview does not establish M-backbone integration, module connections or tendon continuity. The old full-length prototype is marked as not the simulated design. | Review interfaces before fabrication; follow the existing cleanup record. |
| Restricted workspace and system scope | Prior tank studies restrict installation and insertion depth; longer fronts, rear deployment, storage and inspection coverage remain unproven. | Verify the complete mechanism and usable inspection coverage. |

The 5% strain threshold and 250 N tendon bound are numerical diagnostics, not validated hardware ratings. Positive fixed-winch tangent stiffness does not establish dynamic closed-loop stability. The 1.5 mm mesh/sampling allowance is not a certified global clearance bound.

## Rope routing inside the modules (13 November 2026)

- Ropes are modelled as straight chords between module end disks. That is accurate for the U modules (≤ 7.3° bend, chords within 0.2 mm of the lane). In M5, chords leave the lane by 4 mm at the 0° hold, and by 7–33 mm when steering beyond 15° yaw (M5 bends up to 103°). They would then touch the M spring strips (5.5–7.8 mm corridor clearance in `cad/lanes_u4m2`). Results beyond about 15° yaw assume rope paths that the current M body cannot provide without intermediate guides.
- The lane-routed CAD (`cad/lanes_u4m2`) is checked geometrically only, in the straight pose: corridor clearance, 0.5 mm minimum wall between lane holes, free space for the anchor blocks, sleeves and joint screws. Part strength, rope friction and the stiffness of the re-clocked bodies are untested.
