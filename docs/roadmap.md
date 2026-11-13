# Engineering roadmap

[Project home](../README.md) · [Current design](current_design.md) · [Limitations](limitations.md)

1. ~~**Enforce transition tension and refine the trajectory.**~~ Done in simulation on 12 November (`closed_loop_v2.py`): every recorded state ≥ 2.62 N, largest node move ≤ 4.5 mm. The 17° insertion reference was then fixed (v3, four of five cases pass every check). Remaining: transient angle error at 155–175° yaw with a 550 g head; next, an online gain update from measured responses ([section 12](../simulations/u4m2/backbone_20261108/README.md#12-closed-loop-round-trip-v2-operating-pretension-and-refined-path-closed_loop_v2py-2026-11-12)).
2. **Rope guides inside M5/M6 (13 November).** With separate rope lanes ([lane study](../simulations/u4m2/lanes_20261113/README.md)) everything passes, but ropes guided only at the end disks leave the M strip-free corridor beyond about 15° yaw. Add intermediate guides, route the ropes through them in the model, and re-run with the printed part masses.
3. **Build and test the lane-routed front.** Follow the [build guide](../cad/lanes_u4m2/BUILD_GUIDE.md): one U and one M module first (stiffness, 0.5 mm walls, anchor at 50 N, rope friction).
4. **Add dynamic control verification.** Include actuator travel, speed and saturation, sampling time, sensing noise and delay. Repeat the round trip and uncertainty cases.
5. **Measure the backbone M module and interfaces.** Follow the [test plan](../simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md) for EA, EI, guide buckling and attachment slip; update the model from measurements.
6. **Calibrate ropes and winches.** Identify friction, backlash and hysteresis, and verify pretension margins against slack.
7. **Integrate tank-aware motion and actual hardware geometry.** Add the real head, cables, sleeve contact and rear storage/retraction; check twist and inspection coverage.
8. **Validate the integrated prototype.** Demonstrate loaded startup, insertion, steering, return and withdrawal experimentally.

Completed numerical milestones include coordinated winch control, the stable-startup 3 N open-loop cycle and the [quasi-static closed-loop study](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md). They do not replace physical validation.
