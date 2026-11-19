# Full 500 g yaw and vertical-pitch cycle

The prescribed sequence is loaded startup and straightening, insertion, right turn to +175° and return, left turn to −175° and return, pitch to +90° and return, pitch to −90° and return, and withdrawal. Pitch is measured from laboratory horizontal. The return pose points 20° upward at zero yaw. The clamp is 15 mm inside the opening during steering. A pull on one rope changes the loads in all three anchor groups.

[Engineering report](../../../../reports/daily/Yaw_Pitch_Closeout_2026_11_19.md) · [Both vertical poses with labelled loads](results/yaw_pitch/pitch_poles.svg) · [Twelve-rope event table and plot](results/yaw_pitch/ROPE_TENSIONS.md) · [Interactive 3-D rope viewer](results/yaw_pitch/motion_viewer.html) · [Every accepted motion step](results/yaw_pitch/rope_tensions_every_step.csv.gz)

## Read the tension at a specific pose

Open the HTML viewer file on GitHub, choose **Download raw file**, then open the saved file in a browser. Choose a phase endpoint or move the step slider. Select a value in the force table to highlight that rope along its actual routed path and label its anchor with the current tension. “Follow highest tension” tracks the most heavily loaded rope at each step. Each body-fixed channel keeps its label as the head rotates. The displayed pose and all twelve load readings use the same motion-step index. The files use newtons for tension, millimetres for length and degrees for attitude. Playback time is independent of simulated motion step number.

| Group | Physical anchor | Lane radius | CSV channels (N) |
|---|---|---:|---|
| A | End of U4 | 21 mm | A_up, A_right, A_down, A_left |
| B | End of M5 | 24 mm | B_up, B_right, B_down, B_left |
| C | End of M6 | 28 mm | C_up, C_right, C_down, C_left |

In the module CAD cross-section, up is +Y, right is −X, down is −Y and left is +X. For example, C up uses the lane centred at (0, +28) mm and C down uses (0, −28) mm, measured from the M6 centre. These labels stay with the same holes throughout a turn. [CAD ray directions](../../../../cad/lanes_u4m2/end_bellmouth_v1/design.json)

Some inherited solver arrays name these anchors `a4`, `a5` and `a6` respectively. In the step CSV, `_N` gives the nominal frictionless, uniform rope tension. `_command_mm` is the commanded total unstretched length including a 1 m free span. `_internal_path_mm` is the geometric route between the module entrance and the indicated anchor. The dataset also gives the target, actual camera-axis elevation and yaw, head axis, quaternion in x/y/z/w order, head centreline endpoint, clamp position, local tangent eigenvalue and allowance-adjusted clearance. Step zero is the loaded pre-control state. A winch force and the tension at a real distal anchor can differ on a sliding or sticking rope.

[Full-precision turning points](results/yaw_pitch/rope_tensions_at_events.csv) · [Range and peak step for each rope](results/yaw_pitch/rope_tensions_full_range.csv) · [Per-rope phase minima and maxima](results/yaw_pitch/rope_tensions_by_phase.csv) · [Actual controller commands, equilibria and tensions](results/yaw_pitch/controller_states.npz) · [Nominal engineering checks](results/yaw_pitch/summary.json)

## Plant and controller

The working plant uses eight rod cells per module, six 96 mm modules, a 500 g head including the adapter, two Ø1.8 mm M-module NiTi rods, Ø2 mm ropes and the actual free C-rope path across the M5/M6 common bore. The two M5 ±12 mm retained assemblies replace the original station masses. The machined body reduction is also counted. The other six stations retain the published V3 CAD and its masses. The existing homogenized module stiffness, ideal winches, point guides and externally prescribed rear support remain assumptions. The closed loop uses head orientation and each of the twelve rope tensions. The simulation time axis is a sequence of quasi-static equilibria.

The 1,200-target comparison replays the established yaw route with the revised plant. The second run preserves the entire executed prefix through the neutral return from the left turn. The continuation restores the simulated rod equilibrium, all twelve applied commands and controller offsets, damping and clamp position. It inserts four pitch phases, then executes withdrawal from the resulting state. At the vertical poles the head direction is unique while azimuth is indeterminate. Pitch control uses lateral tilt and signed pitch in the fixed forward/up plane and independently scores the three-dimensional angle to the requested direction. Each pitch reference is spaced by 2°. The actual commands are subdivided at a maximum nominal 0.25 mm per rope and checked for a 4.5 mm node step.

The pitch reference model uses the prior fixed-centre bellmouth law and its archived mass. One set of 35 up and 55 down references gives height retention high weight. A second constrained allocation uses the redundant winches to reduce antagonistic tension at the same pitch increment. Both solve all 90 outward references. The selected second set gives an upper/lower planning peak of 21.03/16.98 N versus 250.00/247.25 N for the height-priority plan. The smaller loads change the head path. The minimum modelled upper/lower tank clearance after allowance changes from 59.69/63.25 to 21.19/35.12 mm. Only the selected allocation enters the full feedback run. [Height-priority references](results/pitch_reference/) · [Selected references](results/pitch_reference_minimum_tension/) · [Yaw-only comparison](results/summary.json)

## Supporting tests

- **Numerical convergence.** The achieved up/down commands are held fixed while the updated rod is re-equilibrated at 16 cells per module. This compares numerical sensitivity with the 8-cell controller stopping threshold. [Vertical endpoint comparison](results/yaw_pitch/mesh_poles.json)
- **Sensitivity to material stiffness.** At both vertical holds, test the same feedback gains with a 75 GPa M backbone or 20% lower rope axial stiffness. A separate check for softer ropes uses the nominal stretched path length divided by `1 + T / EA` to calculate the unstretched winch length for each desired nominal force `T`. It solves each length increment, including any tension-floor violations. This check assumes known rope stiffness and a stationary clamp. [Per-rope loads and correction attempts](results/yaw_pitch/perturbed_poles.json)
- **Forces on guides.** The vector sum and moment of simultaneous forces at all eight M guide stations are recorded at every accepted step. Hole and joint reactions use the deformed CAD axes. The published inner-M5 shell/contact study used a subset of load cases. [Eight station resultants by step](results/yaw_pitch/guide_station_loads.csv.gz) · [Per-hole forces and moments](results/yaw_pitch/guide_hole_loads.npz)
- **Rope transmission.** Convert each turn in each full routed rope into a capstan sensitivity for both limiting directions of full sliding. The archived 217 holds and the executed motion get separate outputs. The coefficient is unmeasured and the screening geometry is frozen. At the four actual mission turns, all twelve rope laws are re-equilibrated at the same commands with approach/departure sliding signs and two assumed coefficients. A separate one-rope calculation re-equilibrates three high-wrap archived commands. [Distal force bounds at every step for each rope](results/yaw_pitch/rope_winch_distal_envelopes.csv.gz) · [Motion sensitivity](results/yaw_pitch/transmission_motion.json) · [Archived hold sensitivity](results/transmission_holds.json) · [Winch and distal tension for each cable at the four turns](results/yaw_pitch/sliding_turn_tensions.csv) · [Coupled sliding cases](results/yaw_pitch/sliding_turns.json) · [Re-equilibrated one-rope cases](results/sliding.json)
- **End-region and tank geometry.** At phase endpoints and force extrema, compare the full rope radius with the actual M5 and M6 rigid end meshes. Eight end checks use the free common passage. The other sixteen retain the finite fillet construction. The actual 6 mm adapter plate is checked at every motion pose against the tank triangles. A conservative displacement bound covers linear translation and shortest-arc plate rotation between poses. [Rope/end witnesses](results/yaw_pitch/rope_end_events.json) · [Adapter clearance](results/yaw_pitch/adapter_clearance.json)
- **Guide/body compatibility.** Screen the six existing V3 stations outside the two retained inner-M5 stations against the actual M5 and M6 body meshes. Record the sample positions, bounds and representative states. For a body point at axial distance d within either cell adjacent to the guide node, the displacement bound is d|Δε| + (r d / L + (1 + max|ε|)d² / (2L))‖Δφ‖. L is cell length, r is the largest sampled radius, ε is axial strain and φ is the cell rotation vector. A signed distance is 1-Lipschitz. Reuse is allowed only within the prescribed displacement and when the lower bound stays positive. Targeted refined whole-body triangle distances at the controlling step of each station check thin features that point sampling can miss. Neither method predicts adhesively mounted web deformation. [Saved-hold screen](results/station_holds.json) · [Motion screen](results/yaw_pitch/station_motion.json) · [Whole-body motion witnesses](results/yaw_pitch/solid_motion_0p5.json)
- **Data integrity.** Independent checks recalculate forces, equilibrium residual and head frame at selected witnesses. They match all per-step tension and length labels to solver arrays and verify the vertical endpoints and the preserved yaw prefix. [Validation record](results/validation.json) · [Input provenance](results/provenance.json)

## Reproduce

Use Python with the [shared-bore simulation dependencies](../shared_bore_20261119/README.md) plus Matplotlib and python-fcl. Run in this directory. A new output path preserves the published results. Single-threaded BLAS avoids resource contention on the two-core reference host.

```bash
out=$(mktemp -d)
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
holds=../shared_bore_20261119/results/rebalanced_states.npz
python replay.py --out "$out"
python pitch_reference.py --out "$out/pitch_reference" --allocation height-priority --height-weight .035
python pitch_reference.py --out "$out/pitch_reference_minimum_tension" --allocation minimum-tension --height-weight .01
motion="$out/yaw_pitch"
python pitch_cycle.py --plan "$out/pitch_reference_minimum_tension" --base "$out" --out "$motion"
python tension_report.py --source "$motion"
python viewer.py --source "$motion"
python mesh_poles.py --source "$motion"
python perturb_poles.py --source "$motion" --plan "$out/pitch_reference_minimum_tension"
python end_events.py --source "$motion"
python adapter.py --source "$motion"
python station_loads.py --source "$motion"
python transmission.py --kind holds --source "$holds" --out "$out"
python transmission.py --kind motion --source "$motion/controller_states.npz" --out "$motion"
python sliding.py --out "$out/sliding.json"
python sliding_turns.py --source "$motion"
python stations.py --kind holds --source "$holds" --spacing .12 --out "$out"
python solid_stations.py --kind holds --source "$holds" --resolution .5 --out "$out"
python stations.py --kind motion --source "$motion/controller_states.npz" --spacing .15 --reuse-bound .004 --out "$motion"
python solid_stations.py --kind motion --source "$motion/controller_states.npz" --resolution .5 --out "$motion"
python -m unittest -v test_cycle
python validate_closeout.py --out "$out"
```
