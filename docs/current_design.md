# Current design

[Project home](../README.md) · [Limitations](limitations.md) · [Roadmap](roadmap.md)

Fuel tank inspection robot: an externally supported telescopic rear with a 63 mm tendon-driven flexible front. The front has proximal U modules (PA12 + NiTi) and distal M modules (PA12), 96 mm each. It carries a 500 g camera and induction thermography head. Development targets are a 500 g payload, about 1.5 m reach and a diameter below 100 mm.

The active front is U4+M2: six continuous 96 mm modules, with a central 1.8 mm NiTi backbone along each M module. The tank-screening baseline installs the front at 20 degrees and steers with the clamp 0–30 mm past the opening. The 3 N operating pretension recommendation remains a development target; the exploratory feedback controller uses a lower 1.5 N target.

## Closed-loop simulation update (12 November 2026)

The [English closed-loop report](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) adds head-angle and 12-rope tension feedback to the latest stable-startup U4+M2 cycle. All five cases complete 1,069 reference samples and pass the chosen **settled-state** checks: yaw/elevation within 1 degree, tension bounds, positive fixed-winch tangent stiffness, geometry/strain and sampled tank clearance. The worst settled angular error is **0.699 degrees** in the 550 g case; the other four cases remain below 0.2 degrees. Controller gains use the nominal model, with output-based damping after measured error growth.

**The complete control sequence has not passed every requirement.** Some feedforward arrival states fall below 0.95 N before correction; the lowest is **0.568 N**. The feedback tension target is 1.5 N, so this exploratory controller does not enforce the project's 3 N operating pretension recommendation. The corrected path also exceeds the previous 5 mm sample-displacement bound at some transitions and needs refinement. No noise, latency, motor dynamics, friction or physical transient response is modelled.

- [3D full-cycle MP4](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_full_cycle.mp4): open-loop versus closed-loop settled shapes.
- [3D steering GIF](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_steering.gif).
- [Feedback correction GIF](../simulations/u4m2/backbone_20261108/closed_loop_results/payload550g_feedback_convergence.gif): measured-error damping at a fixed large-yaw reference.

## Prototype CAD status

**Ignore `archive/superseded_cad/full_length/` (marked 11 November 2026).** It uses 84 mm shells with 12 mm pin joints and two separate backbone rods with a free joint. The design and all simulations use continuous 96 mm modules with one Ø1.8 mm NiTi rod along the full length of each M module; see [model data](../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md) and [why the folder is marked](../archive/superseded_cad/full_length/NOT_THE_SIMULATED_DESIGN.md). The uploaded U/M STEP files have a STEP-derived OpenSCAD viewing package in [`cad/previews/u4m2/`](../cad/previews/u4m2).

The U STEP contains one full-envelope body solid (96 mm long, about 63.24 mm across) and four separate leaf-spring solids (about 94 mm long). The M STEP contains one full-envelope body solid. The STEP product tree lists wing and disk items, but not as separate solid meshes; the full-envelope body geometry means that alone does not show the module body is missing. The STEP files do not encode material labels. The intended split is U body in PA12 with four NiTi spring elements, and M body in PA12. The current M study adds a separate Ø1.8 mm NiTi backbone to each M module.

The SCAD preview arranges the six modules in a straight line. It does not model the M backbone or establish the inter-module connection. Confirm material assignments and connection details before ordering a full print.

## Geometry and input data

- [Telescopic rear and tank geometry study](../simulations/u4m2): tank sections, rear beam calculations and deployment screening. The 3D tank model is `cad/tank/tank-v2.step`.
- [Module stiffness database](../data/materials/module_stiffness.sqlite3): module mass, EA, EI and torsional stiffness. Use each study's saved input snapshot when reproducing its results.
