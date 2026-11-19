# M5 seat validation on a common guide and a matching bench coupon

This study covers the two ±12 mm M5 stations. Four bearing sites share one rigid guide pose at each station in a nonlinear rib-shell model. A separate bench fixture holds one piece of the real M5 web, with the production pin and cap, under prescribed rotations and signed force ramps. The 500 g head, 21/24/28 mm lanes, 2 mm ropes and independent Ø1.8 mm NiTi backbone are retained. The other guide stations and M6 have their own geometry. [Engineering report](../../../../reports/daily/M5_Seat_and_Shared_Bore_2026_11_19.md) · [Coupon CAD and assembly](../../../../cad/lanes_u4m2/m5_seat_bench_20261119/README.md) · [Candidate hub](../../../../cad/lanes_u4m2/m5_hub_relief_20261119/README.md)

## Run the physical coupon test

1. Characterize the bare fixture under reference loads using a rigid dummy and register the fixed pin and moving carrier coordinate frames. Record the load-cell calibration, displacement and rotation uncertainties and setup ID. Enter the measured free span, web dimensions, Ø0.60 shaft, bore waist, crown, minimum side ligament and the two thrust radii in [metrology_measurements.csv](metrology_measurements.csv). Measure the minimum ligament on an actual section or a calibrated scan. The nominal opening follows the intersection of the face and bore profiles. Preserve raw scans, calibration records and the print orientation in the laboratory record.
2. The [66-row load program](results/load_program.csv) gives six cycles. P1 pairs the 24.05 N force with the 157.5° web orientation in the 67.5° fixture bend. P2 is the 20.59 N, 6.565°-tilt site on a different web in that bend. P3 reproduces the 14.84 N, 3.066°-tilt seat in the 500 g return hold 146. The reverse branch applies the equal and opposite load as a laboratory challenge. The archived simulation supplied only the source direction. Use all four XYZW quaternion components. P1 has appreciable rotation in the plane despite zero shaft tilt.
3. Each cycle starts at a +1 N reference in the source direction, goes through zero, 25%, 50%, 75% and 100% of the signed load, then unloads and returns to the same +1 N reference. Hold until settled and retain the complete time history. Use the opposite force on the coupon carrier to produce the tabulated pin-on-web force. Express both measured force and translation in the fixed pin frame. Set the load limit from the specimen and fixture capacity. Stop and inspect a cracked or slipping specimen and keep its incomplete record.
4. Enter a time-ordered observation for each phase in [coupon_measurements.csv](coupon_measurements.csv). Each row includes the calibration ID, force vector, measured coupon-to-pin quaternion, translation at the registered pivot, vector measurement uncertainties and visible damage. Time may reset between cycles. Use the same datum in both directions. Compare the two peak positions for reversal travel. Compare the pre/post reference positions for residual displacement. A zero-load position alone cannot distinguish permanent set from bearing free play.
5. Compare matched specimens from the same print lot and direction. Use additional matched pairs to assess specimen-to-specimen variation. The elastic model does not predict damage, wear, real hysteresis or fatigue life. An unresolved change smaller than instrument uncertainty does not quantify service life. [Fine-mesh force ramps](results/coupon_fine.json) · [Load and displacement figure](results/coupon_travel.svg)

## Measure the assembled M5 cage

Use one complete trial ID per build and the actual tool used to deliver torque. For each ±12 mm station enter the following observations in [cage_measurements.csv](cage_measurements.csv). Each row names its feature, units, uncertainty and the predeclared requirement source. Store the actual torque traces and pull-test traces with the lab record.

| Observation | Feature and measurement |
|---|---|
| `bent_gap_mm` | Inspect `rib7_hub0` and `nearest_local_fork_or_gate` in the registered 96.19° bend about the 67.5° axis. In the prior +12 mm guide coordinates the rib/hub approach was near (7.638, −1.539, +1.620) mm, and at −12 mm near (7.638, −1.539, −1.621) mm. Record a third feature, `bend0_closest_pair`, under the 96.19° bend about the 0° axis. This tests the limiting fork after the rim change. Record a signed gap, optical uncertainty and any required manufacturing allowance. |
| `lap_torque_Nmm` | Features `lap_0` through `lap_7`, in 45° order starting at 22.5°. Demonstrate the tightening stroke and measured torque inside the actual cage with the low side driver. The previous exterior was Ø2.50 × 1.15 mm with a Ø0.80 mm lateral shaft. Lower and upper torque limits must come from a qualified joint or fastener specification. |
| `cap_install_torque_Nmm`, `cap_engagement_mm`, `cap_retention_N`, `both_pin_ends_accessible` | Each of `seat_0` through `seat_3` in the archived fork order −22.5°, 67.5°, 157.5°, 247.5°. Record engagement, measured retention load and whether both ends can be held simultaneously. Record access as 1 or 0. Use a sacrificial assembly where a destructive pull is necessary. |
| `guide_mass_g`, `bore_position_error_mm` | Weigh `assembled_station`. Register all eight B and C hole centres in the common guide frame and record position error norms, e.g. `B_0`, `C_90`. The cardinal azimuths are CAD angles. |

Register a probe or camera in the station frame. The following positions are the midpoints between the closest nominal mesh surfaces with the chamfered hub. They locate the inspection region. Their extra digits in the raw CAD output describe the numerical calculation.

| Bend axis | Station | Closest pair | Local probe region (x, y, z), mm | Nominal gap (mm) |
|---|---:|---|---|---:|
| 67.5° | -12 mm | rib 1 to fork 1 | (8.70, 17.90, 0.67) | 0.07472 |
| 67.5° | +12 mm | rib 5 to fork 3 | (-6.50, -18.81, -0.67) | 0.07483 |
| 0° | -12 mm | rib 7 to fork 0 | (17.91, -8.70, 0.67) | 0.06286 |
| 0° | +12 mm | rib 7 to fork 0 | (17.90, -8.70, -0.67) | 0.06364 |

Use calibrated expanded uncertainties or bounds consistently. The scorer uses the sum of the two position bounds for a reference drift comparison and the full measurement bound at each torque limit. Blank torque or drawing limits leave the observation pending. A complete record describes that measured trial. The four header-only forms across the seat and rope studies contain zero physical observations. [Hardware status](results/hardware_status.json) · [Rope pull-through procedure](../shared_bore_20261119/README.md)

## Common-guide mechanics

The global model uses the previous large-rotation M5 shell and simultaneous guide loads and disk boundary conditions from the same saved endpoint. The shell transmits the eight integrated ring forces into the eight finite 3-D web patches. For each patch, the shell position and director at both cut faces provide its rotation and non-rigid boundary displacements. Static elastic extension lifts these displacements into the solid before unilateral shaft/shoulder contact is solved. Matching the resulting cut-frame translation avoids adding the bulk web compliance a second time. Each guide and its four local rings exchange equal and opposite bearing moments. The transfer moves each force's moment reference to the displaced ring centre.

Translation and moment residuals are updated together until every site is within 0.001 mm and 0.020 N·mm, the local force residual is below 0.005 N and the global equilibrium has settled. The criterion concerns the numerical interface. On the two ribs in the exact reflection plane of the 67.5° pure bend, the normal translation follows that plane and the normal contact reaction is recovered and compared with the shell. A force-only pilot stalled at a 0.0102 mm mismatch because near-zero thrust left the axial position undetermined inside the two free gaps. [Pilot history](results/force_only_pilot.json) · [Middle shell and solid](results/coupled_middle/) · [Fine shell and solid](results/coupled_fine/)

For the off-axis fine-mesh hold 47, the force-controlled thrust contact did not settle at an intermediate global iterate. The [original attempt](results/recovery/47_force_control.json) retains its history. In the mixed formulation each solid follows the shell's displacement along the pin. The outer solve adjusts the ring position until the recovered normal force agrees with the shell. The two in-plane directions stay force-controlled. The 0.02 mm/N scaling is an iteration parameter. Every site still has to satisfy the original 0.001 mm, 0.020 N·mm and 0.005 N limits. The same contact law is checked in a tilted coupon by prescribing its force-solved normal position and recovering the original reaction.

The shell/solid transfer enforces cut-frame translation, rotation and resultant force/moment. It does not iterate individual cut-face tractions or model the whole guide as an elastic solid. The machined hole and retained pin replace the ideal support locally. The finite patch uses isotropic small-strain PA12 with rigid frictionless metal contact. Bearing pressures and peak strains require convergence and material data before use as strength limits. The separate coupon holds the cut planes rigidly and has different local boundary conditions.

The CAD audit replaces the deformation inside each mounted web's local domain with the solid result, joining back to the shell over the last 0.18 mm of each cut face. It checks all eight local webs and the returning rib segments, ring and end-disk partitions against both stations. The other station's unmachined holes are conservatively filled in the nonlocal audit. Junction gaps and independently meshed intended steel/polymer overlap are reported separately. Comparing two hub options at identical equilibrium isolates the rigid geometry change. [Surface and mesh comparison](results/summary.json) · [Actual hub section and clearance figure](results/hub_clearance.svg)

## Reproduction

Use Python and the pinned scientific libraries in [provenance](results/provenance.json). Generate the pinned shell seed fields as described in the [retained-seat reproduction commands](../m5_retained_seat_20261118/README.md#reproduction) if they are absent. Start from the repository root. Use external scratch space for nodal fields and run fine shell or fine solid jobs sequentially on memory-limited machines.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
d=simulations/u4m2/lanes_20261113/m5_seat_bench_20261119
cad=cad/lanes_u4m2/m5_seat_bench_20261119
hub=cad/lanes_u4m2/m5_hub_relief_20261119
scratch_dir=/tmp/asrc-bench-reproduction
mkdir -p "$scratch_dir/results"
python "$cad/bench_cad.py" --out "$scratch_dir/coupon-parts"
python "$hub/relief.py" --size .15 --out "$scratch_dir/hub-parts"
for level in middle fine finer; do
  python "$d/bench_prediction.py" --level "$level" --out "$scratch_dir/results"
done
python "$d/fixture_check.py" --prediction "$scratch_dir/results/coupon_fine.json" --out "$scratch_dir/results/fixture_clearance.json"
python "$d/coupled.py" --cases bend67.5 146 64 141 47 bend0 --area .055 --level middle --seed "$scratch_dir/pinned055" --fields "$scratch_dir/middle" --out "$scratch_dir/results/coupled_middle" --iterations 26
python "$d/coupled.py" --cases bend67.5 146 64 141 47 bend0 --area .025 --level fine --seed "$scratch_dir/pinned025" --warm-interfaces "$scratch_dir/middle" --fields "$scratch_dir/fine" --out "$scratch_dir/results/coupled_fine" --iterations 26
# The preceding force-controlled fine run preserves its failed record and checkpoint for hold 47.
mkdir -p "$scratch_dir/results/recovery"
cp "$scratch_dir/results/coupled_fine/47.json" "$scratch_dir/results/recovery/47_force_control.json"
python "$d/coupled.py" --cases 47 --area .025 --level fine --mixed-thrust --seed "$scratch_dir/pinned025" --restart "$scratch_dir/fine" --fields "$scratch_dir/fine" --out "$scratch_dir/results/coupled_fine" --iterations 46
python "$d/hub_sweep.py" --cache "$scratch_dir/fields" --out "$scratch_dir/results/hub_sweep_original_pose.json"
python "$d/coupled_clearance.py" --fields "$scratch_dir/middle" --hub-parts "$scratch_dir/hub-parts" --cases bend67.5 146 --inner-edge .17 --outer-edge .30 --out "$scratch_dir/results/coupled_cad_middle_targets.json"
python "$d/coupled_clearance.py" --fields "$scratch_dir/fine" --hub-parts "$scratch_dir/hub-parts" --cases bend67.5 bend0 146 141 47 64 --inner-edge .15 --outer-edge .25 --out "$scratch_dir/results/coupled_cad_fine.json"
python "$d/score_bench.py" --coupon "$d/coupon_measurements.csv" --cage "$d/cage_measurements.csv" --metrology "$d/metrology_measurements.csv" --out "$scratch_dir/results/hardware_status.json"
python "$d/bench_figure.py" --assembly "$scratch_dir/fixture.png" --curves "$scratch_dir/results/coupon_travel.svg"
python -m unittest discover -s "$d" -p test_bench.py -v
```

Run the complete straight assembly and the tighter CAD sensitivity from the same repository root.

```sh
python simulations/u4m2/lanes_20261113/m5_retained_seat_20261118/straight.py --hub-parts "$scratch_dir/hub-parts" --out "$scratch_dir/straight"
cp "$scratch_dir/straight/straight.json" "$scratch_dir/results/straight_relieved.json"
python "$d/coupled_clearance.py" --fields "$scratch_dir/fine" --hub-parts "$scratch_dir/hub-parts" --cases bend67.5 146 --inner-edge .10 --outer-edge .18 --out "$scratch_dir/results/coupled_cad_refined_targets.json"
python "$d/coupled_clearance.py" --fields "$scratch_dir/fine" --hub-parts "$scratch_dir/hub-parts" --cases bend0 --inner-edge .10 --outer-edge .18 --out "$scratch_dir/results/coupled_cad_refined_transverse.json"
python "$d/summarize_bench.py" --results "$scratch_dir/results"
python "$d/result_figure.py" --source "$scratch_dir/results/coupled_cad_fine.json" --out "$scratch_dir/results/hub_clearance.svg"
```

The preceding source study's `recover_poses.py` produces the `fields` input for the four-size original-pose sweep. On a restarted common-guide job, `--restart` reads the last matching shell/solid field set and uses the same force and moment criteria. The previous rotating-band or pinned checkpoints seed the unmodified baseline, whose recovered reactions are checked against the archived source before coupling. The committed fixture checker uses the published four STLs. Use the checksums to compare a rebuilt set.


## Transfer the rebalanced rope loads to hold 146

Generate the [shared-bore states and per-hole forces](../shared_bore_20261119/README.md#reproduction). From the same repository root, point `rope_results` at that study's output. Both M5 inner guides receive their eight current B/C forces. The M5 end disk also follows the new local position and rotation. Before changing the loads the program recovers the original ideal-pin solution. It checks each transformed moment and independently reconstructs the new disk pose from the eight M5 rod cells. A subsequent ideal-pin solve at the updated boundaries supplies the reference for the local common-guide solve.

```sh
rope_results=/tmp/asrc-rope-reproduction/results
python "$d/coupled.py" --cases 146 --area .025 --level fine --seed "$scratch_dir/pinned025" --warm-interfaces "$scratch_dir/fine" --fields "$scratch_dir/shared146" --out "$scratch_dir/results/shared_load_case" --iterations 28 --shared-results "$rope_results"
python "$d/coupled_clearance.py" --fields "$scratch_dir/shared146" --hub-parts "$scratch_dir/hub-parts" --cases 146 --inner-edge .10 --outer-edge .18 --out "$scratch_dir/results/shared_load_case/cad_146.json"
python "$d/shared_load_comparison.py" --previous-fields "$scratch_dir/fine" --updated-fields "$scratch_dir/shared146" --results "$scratch_dir/results"
cp "$d/results/provenance.json" "$scratch_dir/results/provenance.json"
python "$d/validate_results.py" --seat "$scratch_dir/results" --ropes "$rope_results" --out "$scratch_dir/results/validation.json"
```

The [comparison](results/shared_load_case/comparison.json) registers the sixteen hole centres in the M5 proximal disk frame and compares closest CAD pairs at identical surface resolution before and after the load transfer. Feedback of the seat compliance into the whole arm requires an integrated structural model. The other five structural cases retain their original boundaries.
