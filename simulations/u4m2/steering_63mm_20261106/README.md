# Spatial steering angles and tendon tensions

2026-11-06 · 63 mm outside diameter · 24 mm tendon guide radius · 500 g head


### Findings and interpretation

This is a bounded free-space spatial steering study of U4+M2, U6+M3 and U8+M4 carrying a 500 g point head at 20 degrees base pitch. Results are the largest refined endpoints found in documented local searches, not physical material or actuator ratings.

Unrestricted yaw must be read with head elevation. For U4+M2, the low-strain right/left yaw is 179.42 degrees, while world head elevation is -65.67 degrees. A downward-looking head can have large azimuth changes with much smaller true axis changes. This does not establish a constant-elevation or continuous 360 degree inspection sweep.

No tested configuration produced a low-strain candidate with world head elevation held at 20 +/- 5 degrees. The highest low-strain upward candidates remain below the base axis. For U4+M2 the signed upward candidate is -56.59 degrees relative to the base, and the downward endpoint is -117.77 degrees; peak tendon tensions are 250.00 and 250.00 N. The difference between endpoint angles is not a proven connected controllable range.

### Definitions and inputs

World X points horizontally forward, Y upward and Z right. The base is pitched 20 degrees in X-Y. Yaw is the signed endpoint tangent projection in world X-Z. Vertical turning is the unwrapped tangent projection in world X-Y minus base pitch. World elevation is separately measured against the horizontal plane and lies between +/-90 degrees. True 3D axis angle, material twist and head position are also saved. Projection norms below 0.1 are rejected as near singular. Negative signed Up means the head still points below the base; it is not a zero-degree upward maximum.

Every set is ordered **[up, right, down, left]**, in N. Peak individual tendon force and sum of all tendon forces are distinct columns. Natural loaded sag is a reference, not a required insertion or steering shape. Vertical recovery from natural sag is recorded separately.

The read-only source database supplies 96 mm modules. U is PA12+NiTi, 37.990 g, EA 128122 N, vertical EI 22.2052 N m² and horizontal EI 1.67184 N m². M is PA12, 23.948 g, EA 166.694 N and EI 0.0441178 N m² in all directions. Diameter is 63 mm and tendon radius 24 mm; no stiffness or mass scaling is applied. Flexible lengths are 576, 864 and 1152 mm, or 596, 884 and 1172 mm including a massless 20 mm interface. Both U and M length and weight change across configurations.

Whole-module torsion coefficients are U 4.70037 and M 0.437396 N m/rad. They are multiplied by 0.096 m to form the rod coefficient, preserving module twist energy under subdivision. No additional metal backbone is added. Positive/negative bending is assumed symmetric because asymmetric data were not supplied. EA/EI remain constant; NiTi transformation and local component failure are not modeled.

Four 2 mm tendons per anchor set use the prior solid PA6 proxy properties with no friction. Every tendon runs from the base through actual module disk guides to its anchor, so distal tendons still compress proximal modules. Routed rope mass and supplied module mass are included; new anchors, sheaths, wiring, head eccentricity and actual joint mass are unmeasured.

Layouts are head-only [N], two sets [U,N], three sets [U/2,U,N], and three sets [U,U+floor(M/2),N]. Left results are independently checked reflections of right states under the exact symmetric model, not additional independent optimization searches. Real manufacturing and friction may break this symmetry.

### Low-strain diagnostic endpoints

| Configuration | Direction | Angle deg | Peak tendon N | Max strain % | World elevation deg | 16 cell check |
|---|---|---|---|---|---|---|
| U4-M2 | Right | 179.42 | 146.48 | 4.83 | -65.67 | Pass |
| U4-M2 | Left | 179.42 | 146.48 | 4.83 | -65.67 | Pass |
| U4-M2 | Up | Not above base; best -56.59 | 250.00 | 4.86 | -36.59 | Pass |
| U4-M2 | Down | 117.77 | 250.00 | 4.49 | -77.91 | Pass |
| U6-M3 | Right | 179.94 | 7.04 | 5.00 | -75.24 | Boundary or unconfirmed |
| U6-M3 | Left | 179.94 | 7.04 | 5.00 | -75.24 | Boundary or unconfirmed |
| U6-M3 | Up | Not above base; best -73.55 | 250.00 | 4.84 | -53.55 | Pass |
| U6-M3 | Down | 133.52 | 250.00 | 4.38 | -60.15 | Pass |
| U8-M4 | Right | 179.64 | 4.90 | 1.80 | -75.76 | Pass |
| U8-M4 | Left | 179.64 | 4.90 | 1.80 | -75.76 | Pass |
| U8-M4 | Up | Not above base; best -68.54 | 85.54 | 4.84 | -48.54 | Pass |
| U8-M4 | Down | 148.33 | 250.00 | 4.82 | -50.23 | Pass |


The 5% value is a comparison diagnostic, not a measured allowable strain. The Up force belongs to the best recovery candidate when no positive upward angle is found. U6+M3 yaw reaches 5.0015% strain at sixteen cells per module, strictly above 5%; its 179.94 degree candidate is not a confirmed fine-mesh low-strain maximum. Boundary values must not be rounded into acceptance.

### Larger-strain exploratory endpoints

| Configuration | Direction | Angle deg | Peak tendon N | Max strain % | World elevation deg | 16 cell check |
|---|---|---|---|---|---|---|
| U4-M2 | Right | 180.00 * | 20.50 | 14.79 | -36.44 | Boundary or unconfirmed |
| U4-M2 | Left | 180.00 * | 20.50 | 14.79 | -36.44 | Boundary or unconfirmed |
| U4-M2 | Up | 180.00 * | 25.91 | 30.00 | -19.86 | Boundary or unconfirmed |
| U4-M2 | Down | 180.00 * | 26.67 | 19.85 | -19.83 | Boundary or unconfirmed |
| U6-M3 | Right | 179.94 | 7.04 | 5.00 | -75.24 | Pass |
| U6-M3 | Left | 179.94 | 7.04 | 5.00 | -75.24 | Pass |
| U6-M3 | Up | 177.09 | 19.73 | 18.96 | -17.03 | Pass |
| U6-M3 | Down | 180.00 * | 19.99 | 16.02 | -19.79 | Boundary or unconfirmed |
| U8-M4 | Right | 179.64 | 4.90 | 1.80 | -75.76 | Pass |
| U8-M4 | Left | 179.64 | 4.90 | 1.80 | -75.76 | Pass |
| U8-M4 | Up | 180.00 * | 144.86 | 30.00 | -19.29 | Boundary or unconfirmed |
| U8-M4 | Down | 180.00 * | 19.30 | 11.97 | -16.55 | Boundary or unconfirmed |


An asterisk denotes the 180 degree orientation search cap. It is not a demonstrated mechanical limit. Up/down 180 degree projected turning does not mean 180 degree world elevation. Some same-tension 16-cell checks cross an angular, strain, geometry or posture boundary; those points remain exploratory rather than converged maxima.

### Horizontal inspection-attitude diagnostic

The following additional search holds world head elevation at 20 +/- 5 degrees. It is separate from unrestricted yaw of a sagged tip. No low-strain candidate was found in the documented searches.

| Configuration | Mode | Yaw deg | Peak tendon N | Max strain % |
|---|---|---:|---:|---:|
| U4-M2 | low_strain | Not found | — | — |
| U4-M2 | exploratory | 180.00 * | 24.08 | 29.08 |
| U6-M3 | low_strain | Not found | — | — |
| U6-M3 | exploratory | 180.00 * | 69.70 | 29.93 |
| U8-M4 | low_strain | Not found | — | — |
| U8-M4 | exploratory | 180.00 * | 40.86 | 29.06 |

### Full tendon forces

Each bracket corresponds to one listed anchor, ordered [up,right,down,left] N. Printed values are rounded to 0.01 N. Exact arrays and complete left-force records are in `tendon_tensions.csv` and `maximum_steering.json`; left swaps the right/left entries. These are force allocations found for the endpoint, not certified minimum-force solutions.

| Configuration | Mode | Direction | Anchors | Tensions per set [up right down left] N |
|---|---|---|---|---|
| U4-M2 | low_strain | Right | [2, 4, 6] | [9.69, 47.04, 10.81, 0.16] ; [11.37, 146.48, 22.08, 0.49] ; [0.00, 10.86, 0.00, 0.00] |
| U4-M2 | exploratory | Right | [6] | [0.13, 20.50, 5.88, 0.25] |
| U4-M2 | low_strain | Up | [2, 4, 6] | [250.00, 250.00, 0.00, 250.00] ; [250.00, 250.00, 0.00, 250.00] ; [7.02, 0.00, 0.00, 0.00] |
| U4-M2 | exploratory | Up | [4, 5, 6] | [4.60, 0.45, 2.23, 25.91] ; [0.02, 0.01, 16.77, 0.00] ; [21.33, 1.55, 6.10, 0.02] |
| U4-M2 | low_strain | Down | [2, 4, 6] | [0.00, 0.00, 250.00, 250.00] ; [0.00, 250.00, 250.00, 89.55] ; [0.00, 0.00, 9.99, 0.00] |
| U4-M2 | exploratory | Down | [4, 5, 6] | [0.08, 4.93, 0.44, 0.00] ; [0.31, 2.70, 3.52, 0.77] ; [0.89, 1.17, 26.67, 0.14] |
| U4-M2 | exploratory | Right at held elevation | [6] | [24.08, 0.02, 20.17, 0.02] |
| U6-M3 | low_strain | Right | [9] | [0.00, 2.02, 7.04, 0.00] |
| U6-M3 | exploratory | Right | [9] | [0.00, 2.02, 7.04, 0.00] |
| U6-M3 | low_strain | Up | [6, 7, 9] | [0.00, 250.00, 250.00, 250.00] ; [0.00, 0.00, 0.00, 0.00] ; [9.11, 0.00, 0.00, 0.00] |
| U6-M3 | exploratory | Up | [9] | [0.01, 6.76, 4.11, 19.73] |
| U6-M3 | low_strain | Down | [3, 6, 9] | [0.00, 0.00, 250.00, 250.00] ; [0.00, 250.00, 250.00, 67.61] ; [0.00, 0.00, 10.74, 0.00] |
| U6-M3 | exploratory | Down | [9] | [1.75, 6.48, 19.99, 0.75] |
| U6-M3 | exploratory | Right at held elevation | [6, 9] | [4.13, 69.70, 55.50, 15.22] ; [17.72, 8.27, 4.83, 19.74] |
| U8-M4 | low_strain | Right | [4, 8, 12] | [0.01, 0.00, 0.00, 0.00] ; [0.13, 0.21, 0.00, 0.00] ; [1.26, 4.90, 0.01, 0.01] |
| U8-M4 | exploratory | Right | [4, 8, 12] | [0.01, 0.00, 0.00, 0.00] ; [0.13, 0.21, 0.00, 0.00] ; [1.26, 4.90, 0.01, 0.01] |
| U8-M4 | low_strain | Up | [8, 10, 12] | [85.54, 58.78, 0.00, 0.00] ; [0.00, 0.00, 0.00, 0.63] ; [0.00, 0.00, 0.00, 12.21] |
| U8-M4 | exploratory | Up | [8, 10, 12] | [0.07, 144.86, 12.37, 2.97] ; [0.74, 16.67, 2.25, 0.05] ; [0.03, 0.01, 7.20, 26.53] |
| U8-M4 | low_strain | Down | [8, 10, 12] | [0.00, 9.56, 250.00, 0.00] ; [0.00, 0.00, 0.00, 0.00] ; [0.00, 12.31, 0.00, 0.00] |
| U8-M4 | exploratory | Down | [12] | [0.07, 19.30, 3.67, 0.20] |
| U8-M4 | exploratory | Right at held elevation | [8, 10, 12] | [0.00, 0.03, 40.86, 27.93] ; [0.01, 0.01, 18.31, 2.68] ; [27.98, 0.26, 0.00, 0.04] |


### Search bounds and verification

The spatial extensible Kirchhoff rod retains finite rotations, two anisotropic bending components and independent twist. Gravity and all tendons act simultaneously. Initial two-cell-per-module searches use loaded-sag, small-tension, previously straightened and nonplanar branches. Each rope is bounded at 0 to 250 N. Coarse low-strain bounds are +/-4.75% with refinement margin; exploratory strain bounds are -30% to +15%. Per-cell rotation bounds and an optimization margin r*kappa <= 0.98 are numerical. Nonlocal 63 mm capsules are checked only for segments separated by at least 126 mm reference arc length, not detailed module contact.

Candidate maxima are re-equilibrated and, when needed, locally re-optimized at four and eight cells per module. Documented force-ray recovery is used for some fine boundary states. Each selected state receives a same-tension sixteen-cell check. Fixed-winch elastic-tendon local stability includes 1 m additional free rope; constant-tension Hessian results are retained separately. Local stability does not validate dynamics or a transition path.

There are 310 initial/supplementary local optimization attempts and 21 sixteen-cell checks, with 1.790 degrees maximum change. Energy gradients, planar energy/deformation equivalence and module twist energy are independently checked. Left mirror energy/gradient symmetry is verified. Numerical consistency does not establish physical material validity.

Pitch sensitivities at 15 and 25 degrees re-equilibrate the selected 20-degree tensions; they are not re-optimized maxima. Force curves use four cells per module and scale one fixed allocation vector through equilibrium solves. Intermediate samples can cross strain, geometry or stability screens, so these curves are not certified trajectories.

The angular cap, tendon cap or strain boundary can limit a result. No global optimum, physical maximum, real actuator rating or fuel-tank collision clearance is established. M axial load transfer and loaded head recovery remain the main design concerns.

### Files and reproduction

- `results/maximum_steering.csv` and `.json`: all selected endpoints and mesh flags.
- `results/tendon_tensions.csv`: one row per anchor set, with all four rope forces.
- `results/pitch_sensitivity.csv`: same-force 15/25 degree checks.
- `results/mesh_checks.csv`: fine mesh changes and boundary recovery records.
- `results/force_continuations.csv`: force-angle-strain samples.
- Four English PNG figures are linked above; the source database and earlier simulations remain unchanged.

Input SHA256: `584a1486f96af7603d794cc9a243706ee5344161054479b4e12d769d63588374`. Existing Python NumPy/SciPy/Numba/Matplotlib packages are used; no large dependencies or CAD runtimes are installed. The original project planar kernel and tendon catalogue remain read dependencies. From the project root:

```powershell
python simulations/u4m2/steering_63mm_20261106/search_steering.py validate
python simulations/u4m2/steering_63mm_20261106/search_steering.py coarse --u 4 --m 2
python simulations/u4m2/steering_63mm_20261106/extend_search.py --u 4 --m 2
python simulations/u4m2/steering_63mm_20261106/refine_steering.py --u 4 --m 2
python simulations/u4m2/steering_63mm_20261106/force_curves.py --u 4 --m 2
# Repeat the preceding four study steps for --u 6 --m 3 and --u 8 --m 4
python simulations/u4m2/steering_63mm_20261106/report_results.py
```

To reproduce a frozen source after the main database changes, set `ASRC_STIFFNESS_DB` to this study's `module_stiffness_input.sqlite3` before running. Input and code hashes are stored with the validation output. Existing results must be preserved before rerunning.
