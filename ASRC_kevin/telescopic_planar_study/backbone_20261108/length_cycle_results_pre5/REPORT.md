# U4+M2 Length-Controlled Round Trip: 5 N pretension and stable startup

Rest-length commands for 12 ropes are derived from E40, 20-degree, anchor [4,5,6] reference states with a **5 N minimum on every rope** (`minforce_niti18_E40_p20_a456_pre5_exact_smooth1_fromstartup_states.npz`) and a **stable startup** (`startup_niti18_E40_p20_pre5_states.npz`), at eight cells per module. Model parameters: `model_data/MODEL_DATA.md`. Each commanded state is then solved forward from the preceding equilibrium, rather than replaying the stored posture.

## Engineering interpretation

Numerical completion does not establish an executable trajectory. Negative tangent eigenvalues identify equilibria that cannot be treated as stable quasi-static motion.

- Nominal case: 1165 samples; 48 fail at least one check. Failure counts overlap: Yaw error above 1 deg: 48 samples; Pretension below 0.95 N: 16 samples.
- Maximum steering/elevation error: 1.289 / 4.657 deg. Peak rope force: 22.94 N.
- Minimum sampled tank clearance: 24.75 mm; 23.25 mm after the 1.5 mm sampling/mesh allowance.
- Outbound sample prefixes passing all checks from zero yaw: Right sweep: 51.6667 deg; Left sweep: 51.6667 deg. These are not continuous safety guarantees or geometric limits.
- Minimum straightening tangent eigenvalue: 0.6295. The startup raises the head from natural sag (all ropes at 5 N) to 20 degrees through held-elevation states.
- Insertion: 0 of 261 samples fail; minimum rope force 5.000 N; minimum stability eigenvalue 0.6541.
- Right sweep: 12 of 143 samples fail; minimum rope force 0.819 N; minimum stability eigenvalue 0.2010.
- Return from right: 12 of 143 samples fail; minimum rope force 0.819 N; minimum stability eigenvalue 0.2010.
- Left sweep: 12 of 143 samples fail; minimum rope force 0.819 N; minimum stability eigenvalue 0.2010.
- Return from left: 12 of 143 samples fail; minimum rope force 0.819 N; minimum stability eigenvalue 0.2010.
- Withdrawal: 0 of 259 samples fail; minimum rope force 5.000 N; minimum stability eigenvalue 0.6541.

- Sensitivities replay the same open-loop commands. Changes in backbone stiffness or payload affect posture; rope stiffness and free length also affect pretension. Good angular tracking alone is insufficient.
- This run implements the pretension margin (5 N floor in the reference poses) and the redesigned startup. Remaining failures in the sensitivity cases are open-loop calibration effects (posture tracking, or rope tension with a longer free rope).

## Results

| Case | Numerical cycle completed | All checks pass | Samples | Minimum tank clearance (mm) | Minimum stability eigenvalue | Peak force (N) | Maximum yaw error (deg) |
|---|---|---|---:|---:|---:|---:|---:|
| Backbone modulus 75 GPa | Yes | No | 1145 | 20.82 | 0.291 | 24.41 | 5.72 |
| Free rope length 1.5 m | Yes | No | 1167 | 24.04 | 0.1903 | 20.49 | 1.27 |
| Nominal | Yes | No | 1165 | 24.75 | 0.201 | 22.94 | 1.29 |
| Payload 550 g | Yes | No | 1157 | 22.45 | 0.1019 | 23.74 | 8.20 |
| Rope axial stiffness -20% | Yes | No | 1166 | 24.22 | 0.1931 | 21.07 | 1.26 |

Completion means stationary solutions were obtained throughout the numerical cycle. Failed samples are retained to locate limitations; their presence does not authorize execution of the commands.

### Backbone modulus 75 GPa

- Samples failing one or more checks: 408.
- Failure counts: Yaw error above 1 deg: 376 samples; Elevation error above 5 deg: 148 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 20 deg; Left sweep: 20 deg; not a continuous safety guarantee.
- First failure locations: see `E75.json` and `comparison.json`.

### Free rope length 1.5 m

- Samples failing one or more checks: 52.
- Failure counts: Yaw error above 1 deg: 52 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 51.2963 deg; Left sweep: 51.2963 deg; not a continuous safety guarantee.
- First failure locations: see `free1500mm.json` and `comparison.json`.

### Nominal

- Samples failing one or more checks: 48.
- Failure counts: Yaw error above 1 deg: 48 samples; Pretension below 0.95 N: 16 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 51.6667 deg; Left sweep: 51.6667 deg; not a continuous safety guarantee.
- First failure locations: see `nominal.json` and `comparison.json`.

### Payload 550 g

- Samples failing one or more checks: 310.
- Failure counts: Pretension below 0.95 N: 48 samples; Yaw error above 1 deg: 246 samples; Elevation error above 5 deg: 204 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 51.4815 deg; Left sweep: 51.4815 deg; not a continuous safety guarantee.
- First failure locations: see `payload550g.json` and `comparison.json`.

### Rope axial stiffness -20%

- Samples failing one or more checks: 48.
- Failure counts: Yaw error above 1 deg: 48 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 51.4815 deg; Left sweep: 51.4815 deg; not a continuous safety guarantee.
- First failure locations: see `ropeEA80pct.json` and `comparison.json`.

## Method and limitations

- Baseline: U4+M2, 20-degree installation, 500 g payload, E40 backbone, 1 m free rope length, database rope EA, eight cells per module.
- Initial condition: clamp at s=-750 mm outside the tank, front in natural sag with every rope at 5 N. Startup follows the held-elevation states of `startup_sweep.py` (head raised in 2.5 degree steps to 20 degrees, all ropes >= 5 N, each state stable at 8 cells).
- Cycle: straighten; insert to s=15 mm while holding posture; right sweep to 175 degrees; return; left sweep to -175 degrees; return; withdraw to s=-750 mm while holding posture.
- Reference poses are spaced by 5 degrees. Rest lengths are linearly interpolated with command increments no greater than 1 mm. Steps exceeding 5 mm displacement at any centreline node are recursively subdivided to depth nine; unresolved excess is a failure. This controls sampled resolution and does not prove continuous safety.
- Rope force: T = EA max(0, L + Lfree - R) / R. Stability uses the same rest lengths, rope stiffness and active-rope set in the elastic energy Hessian.
- Left commands swap the right/left rope channels. Both directions are forward-solved independently; the tank geometry is not mirrored.
- One-factor sensitivities replay identical open-loop commands without reoptimization: E75 backbone; 550 g payload; rope EA scaled by 0.8; free rope length 1.5 m, with a matching 0.5 m command-zero offset. These are assumed scenarios, not measured probability distributions.
- Tank screen: 362 solids, 0.5 mm mesh deflection; centreline distances sampled at about 2 mm spacing, minus a 31.5 mm envelope radius. A further 1.5 mm sampling/mesh allowance is subtracted. Mesh deflection is not a verified global error bound.
- Acceptance: clearance after allowance at least 5 mm; stability eigenvalue above 1e-7; existing self-collision/local-curvature constraints; axial strain at most 5%; each rope between 0.95 and 250 N; yaw error at most 1 degree; elevation within 20 +/- 5 degrees. Elevation/yaw tracking is not required during straightening. The 0.95 N threshold permits numerical tolerance around 1 N. The 250 N and 5% bounds are diagnostics, not hardware ratings.
- Excluded: dynamics, friction, backlash, NiTi hysteresis, actual sensor-head geometry, external cables, the rear telescopic mechanism, contact forces and recovery control. Withdrawal is rigid translation of the clamped front.
- Per-step output includes rest lengths, pull-in relative to baseline, forces for all 12 ropes, head position/orientation, clearance, geometry checks, equilibrium residual and stability. No time scale, motor speed or torque commands are provided.

## Reproduction

```bash
python length_cycle.py --source results/minforce_niti18_E40_p20_a456_pre5_exact_smooth1_fromstartup_states.npz --startup results/startup_niti18_E40_p20_pre5_states.npz --out length_cycle_results_pre5
python summarize_cycle_run.py length_cycle_results_pre5 --source results/minforce_niti18_E40_p20_a456_pre5_exact_smooth1_fromstartup_states.npz --startup results/startup_niti18_E40_p20_pre5_states.npz --pretension 5
python -m unittest test_length_cycle.py -v
```

Dependencies: NumPy, SciPy, Numba, Matplotlib, cadquery-ocp, VTK, trimesh and rtree. The original STEP model and reference states are supplied by the repository.

## Figures

![Round-trip comparison](cycle_comparison.png)

![Nominal three-dimensional steering path](nominal_3d.png)
