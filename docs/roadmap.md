# Engineering roadmap

[Project home](../README.md) · [Current design](current_design.md) · [Limitations](limitations.md)

1. **Enforce transition tension and refine the trajectory.** Guard feedforward and feedback commands against the selected operating pretension requirement; subdivide the corrected path below the 5 mm sampling bound.
2. **Add dynamic control verification.** Include actuator travel, speed and saturation, sampling time, sensing noise and delay. Repeat the round trip and uncertainty cases.
3. **Measure the backbone M module and interfaces.** Follow the [test plan](../ASRC_kevin/telescopic_planar_study/backbone_20261108/M_BACKBONE_TEST_PLAN.md) for EA, EI, guide buckling and attachment slip; update the model from measurements.
4. **Calibrate ropes and winches.** Identify friction, backlash and hysteresis, and verify pretension margins against slack.
5. **Integrate tank-aware motion and actual hardware geometry.** Add the real head, cables, sleeve contact and rear storage/retraction; check twist and inspection coverage.
6. **Validate the integrated prototype.** Demonstrate loaded startup, insertion, steering, return and withdrawal experimentally.

Completed numerical milestones include coordinated winch control, the stable-startup 3 N open-loop cycle and the [quasi-static closed-loop study](../ASRC_kevin/telescopic_planar_study/backbone_20261108/closed_loop_results/REPORT.md). They do not replace physical validation.
