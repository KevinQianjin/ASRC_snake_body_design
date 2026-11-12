# U4+M2 Multi-Rope Length-Controlled Round-Trip Study

Rest-length commands for 12 ropes are derived from the existing E40, 20-degree, anchor [4,5,6] reference states at eight cells per module. Each commanded state is then solved forward from the preceding equilibrium, rather than replaying the stored posture.

## Engineering interpretation

Numerical completion does not establish an executable trajectory. Negative tangent eigenvalues identify equilibria that cannot be treated as stable quasi-static motion.

- Nominal case: 1033 samples; 56 fail at least one check. Failure counts overlap: Unstable equilibrium: 13 samples; Pretension below 0.95 N: 56 samples.
- Maximum steering/elevation error: 0.779 / 0.854 deg. Peak rope force: 14.89 N.
- Minimum sampled tank clearance: 17.48 mm; 15.98 mm after the 1.5 mm sampling/mesh allowance.
- Outbound sample prefixes passing all checks from zero yaw: Right sweep: 21.25 deg; Left sweep: 21.25 deg. These are not continuous safety guarantees or geometric limits.
- Minimum straightening tangent eigenvalue: -0.2296. Paying out the upper ropes by 10 mm is a specified initial condition for this study; failure here does not imply that every straightening procedure fails.
- Insertion: 0 of 260 samples fail; minimum rope force 1.000 N; minimum stability eigenvalue 0.7140.
- Right sweep: 9 of 123 samples fail; minimum rope force 0.713 N; minimum stability eigenvalue 0.1476.
- Return from right: 9 of 123 samples fail; minimum rope force 0.713 N; minimum stability eigenvalue 0.1485.
- Left sweep: 9 of 123 samples fail; minimum rope force 0.713 N; minimum stability eigenvalue 0.1476.
- Return from left: 9 of 123 samples fail; minimum rope force 0.713 N; minimum stability eigenvalue 0.1485.
- Withdrawal: 0 of 260 samples fail; minimum rope force 1.000 N; minimum stability eigenvalue 0.7140.

- Sensitivities replay the same open-loop commands. Changes in backbone stiffness or payload affect posture; rope stiffness and free length also affect pretension. Good angular tracking alone is insufficient.
- Next step: add pretension margin and stability constraints, redesign startup and rope-length commands, then repeat the sensitivity cases. These corrections have not been implemented in this study.

## Results

| Case | Numerical cycle completed | All checks pass | Samples | Minimum tank clearance (mm) | Minimum stability eigenvalue | Peak force (N) | Maximum yaw error (deg) |
|---|---|---|---:|---:|---:|---:|---:|
| Backbone modulus 75 GPa | Yes | No | 1019 | 10.83 | 0.01318 | 16.65 | 6.60 |
| Free rope length 1.5 m | Yes | No | 1023 | 17.42 | -0.2329 | 13.93 | 0.77 |
| Nominal | Yes | No | 1033 | 17.48 | -0.2296 | 14.89 | 0.78 |
| Payload 550 g | Yes | No | 1009 | 24.60 | -0.3738 | 15.70 | 9.85 |
| Rope axial stiffness -20% | Yes | No | 1020 | 17.43 | -0.2355 | 13.91 | 0.72 |

Completion means stationary solutions were obtained throughout the numerical cycle. Failed samples are retained to locate limitations; their presence does not authorize execution of the commands.

### Backbone modulus 75 GPa

- Samples failing one or more checks: 1019.
- Failure counts: Pretension below 0.95 N: 1019 samples; Yaw error above 1 deg: 336 samples; Elevation error above 5 deg: 204 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 0 deg; Left sweep: 0 deg; not a continuous safety guarantee.
- First failure locations: see `E75.json` and `comparison.json`.

### Free rope length 1.5 m

- Samples failing one or more checks: 1023.
- Failure counts: Unstable equilibrium: 14 samples; Pretension below 0.95 N: 1023 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 0 deg; Left sweep: 0 deg; not a continuous safety guarantee.
- First failure locations: see `free1500mm.json` and `comparison.json`.

### Nominal

- Samples failing one or more checks: 56.
- Failure counts: Unstable equilibrium: 13 samples; Pretension below 0.95 N: 56 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 21.25 deg; Left sweep: 21.25 deg; not a continuous safety guarantee.
- First failure locations: see `nominal.json` and `comparison.json`.

### Payload 550 g

- Samples failing one or more checks: 1009.
- Failure counts: Unstable equilibrium: 15 samples; Pretension below 0.95 N: 941 samples; Elevation error above 5 deg: 216 samples; Yaw error above 1 deg: 230 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 0 deg; Left sweep: 0 deg; not a continuous safety guarantee.
- First failure locations: see `payload550g.json` and `comparison.json`.

### Rope axial stiffness -20%

- Samples failing one or more checks: 1020.
- Failure counts: Unstable equilibrium: 14 samples; Pretension below 0.95 N: 1020 samples.
- Head position error after returning to zero yaw at equal clamp depth: 0.0000 mm.
- Outbound passing sample prefixes: Right sweep: 0 deg; Left sweep: 0 deg; not a continuous safety guarantee.
- First failure locations: see `ropeEA80pct.json` and `comparison.json`.

## Method and limitations

- Baseline: U4+M2, 20-degree installation, 500 g payload, E40 backbone, 1 m free rope length, database rope EA, eight cells per module.
- Initial condition: clamp at s=-750 mm outside the tank; the three upper ropes are paid out 10 mm from baseline. The initial payout transient is not simulated. Straightening reels in from the resulting stationary state, which may be unstable.
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
python length_cycle.py
python summarize_length_cycle.py
python -m unittest test_length_cycle.py -v
```

Dependencies: NumPy, SciPy, Numba, Matplotlib, cadquery-ocp, VTK, trimesh and rtree. The original STEP model and reference states are supplied by the repository.

## Figures

![Round-trip comparison](cycle_comparison.png)

![Nominal three-dimensional steering path](nominal_3d.png)
