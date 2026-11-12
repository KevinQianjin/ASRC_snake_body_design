# Current limitations

[Project home](../README.md) · [Current design](current_design.md) · [Roadmap](roadmap.md)

The design has not passed an integrated, hardware-validated deployment cycle. The latest [closed-loop report](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) distinguishes settled-state success from failures before feedback correction. Earlier findings are preserved in [research history](history.md).

| Limitation | Current evidence | Work required |
|---|---|---|
| Tension during command transitions | Seven feedforward arrival states fall below 0.95 N; the minimum is 0.568 N. The feedback target is 1.5 N, below the 3 N operating recommendation. | Increase pretension margin and guard or subdivide command transitions. |
| Motion sampling | The corrected path has a maximum 6.822 mm node step, above the previous 5 mm sampling bound. | Refine the path and check the swept envelope. |
| Controller convergence | All five cases meet the 1-degree settled-angle criterion; one 550 g sample reaches 16 corrections at 0.699-degree yaw error. | Improve convergence and test independent uncertainty cases. |
| Idealised dynamics and sensing | Simulations are quasi-static, with ideal measurements and no motor dynamics, delay or sensor noise. | Verify sampled dynamic control and actuator limits. |
| Unmeasured mechanical properties | Friction, backlash, NiTi hysteresis, fatigue, guide buckling and interface slip are not validated. | Test assembled modules, ropes and winches; calibrate the models. |
| Provisional head and cables | Clearance uses a 63 mm envelope and nominal 500 g payload rather than the complete head and cable geometry. | Integrate actual CAD, centre of mass and cable routing. |
| Incomplete CAD integration | The STEP-derived preview does not establish M-backbone integration, module connections or tendon continuity. The old full-length prototype is marked as not the simulated design. | Review interfaces before fabrication; follow the existing cleanup record. |
| Restricted workspace and system scope | Prior tank studies restrict installation and insertion depth; longer fronts, rear deployment, storage and inspection coverage remain unproven. | Verify the complete mechanism and usable inspection coverage. |

The 5% strain threshold and 250 N tendon bound are numerical diagnostics, not validated hardware ratings. Positive fixed-winch tangent stiffness does not establish dynamic closed-loop stability. The 1.5 mm mesh/sampling allowance is not a certified global clearance bound.
