# M6, U1 and 500 g mission closeout

This engineering run began on **27 November 2026 at 23:38 EST (28 November 2026 at 04:38 UTC)** from repository revision `d9347e87ab3612342962125580187523a0b42fd5`. It evaluates, in order, the M6 crown geometry, the recessed U1 single-leaf joint and the 500 g fixed-winch mission with the U1 fit candidate.

[M6 result comparison](results/M6_crown_comparison.png) · [U1 fabrication and assembly](../../../../cad/lanes_u4m2/u_leaf_mechanical_joint/recessed_backstop/README.md) · [500 g force and clearance plot](results/mission/mission_overview.png) · [Bench work](#m6-bench-work)

## M6 crown refinement and CAD screening

The study uses the U4+M2 mission with a 500 g head and the linear PA12 solid and NiTi sleeve attachment from the 27 November engineering work. The four fixed crown measurement centres come from the archived finer-mesh peak locations and their diametrically opposite ribs. They cover both hub ends and use spherical radii of 0.5 mm and 1.0 mm. The three selected solver steps are 1,709, 1,869 and 1,884. [Source measurements and native pocket study](../evening_20261127/README.md)

## Reference convergence

| Surface discretization | Solid tetrahedra | Maximum change from previous level over both gauges, four locations and three states | Largest 0.5 mm fixed-gauge strain over those states |
|---|---:|---:|---:|
| Original cropped STL, q5 | 130,530 | — | 2.034% |
| Local 0.28 mm edge target | 157,516 | 3.22% | 2.058% |
| Local 0.18 mm edge target | 201,279 | 1.62% | 2.051% |

The fixed-location gauge check meets the less-than-5% criterion for both successive refinements. The figure and decision record identify the actual value of each refined measurement. The archived gauge used whole tetrahedra around a moving peak element centroid. This study averages the P2 strain field at the same 4,096 deterministic points in each gauge, restricted to those mapped inside the mesh. Halving the points changed the selected reference gauge results by at most 0.45%. Gauge radii describe the numerical averaging regions. [Decision record](results/M6_decision.json)

Shared surface edges are bisected conformingly in 1.70 mm windows about the measurement centres. The total faceted volume and connected surface topology are checked prior to tetrahedralization. The original pressure-free bore, Ø1.80 mm backbone over a 66 mm span, reference cut planes, guide wrench sequence, 500 MPa bond shear modulus, 0.06 mm guide-land crown and PA12 elastic constants follow the archived body model. Fifteen linear load solutions project the gauge fields onto all 3,405 archived mission states. These fields use archived boundary rotations and simultaneous station wrenches. The load projections are a structural evaluation at those input states.

On an 8 GiB machine, block nested dissection and CHOLMOD solved the 201,279-tet level at 6,655 MiB measured process peak RSS. The relative residual remained below 9e-13. A background-metric TetGen trial terminated with a segmentation fault. The separate 0.12 mm surface trial made 219,978 tetrahedra and stopped at the recorded memory screen before stiffness assembly.

## Native variants

The existing arch has a cylindrical radius of 1.50 mm along the full 3.00 mm rib width. The radius trial replaces its load-side arc with an R2.00 mm tangent arc using the measured original arc normals. The section trial adds material with a smooth spline and a peak radial offset of 0.42 mm into the arch void. This depth is measured normal to the original arch, with zero offset and matched tangent at both ends. The pattern covers 16 arches. Each patch lies beyond the 0.30 mm slot region. STEP exports use the published FE clocking, rotated −22.5° from the original native STEP. [Native model and cropped FE surface files](results/crown_cad/)

Both variants reimport as single valid native solids. The solid finite elements use three matched B-Rep tessellations cropped between the reference cut faces. Relative to the archived faceted control, the native-control surface deviation is below 0.012 mm and the total volume change is below 2.0 mm³. The preliminary faceted-boolean splice developed zero-length edges after STL export, so its results were rejected before solving. The first q5 / 0.28 mm native FE attempts exceeded the bounded tetrahedron count. The matched native screening tier uses q7, 0.85 mm³ nominal volume and 0.39 mm target surface edge in the same windows.

The candidate screen reports absolute principal strain at the same gauge positions and gauges at the discovered element peak locations. It also reports combined elastic bending stiffness in both axes, mass change and the minimum linearized rod-to-ring gap over the archived loads. The 1.2% strain and 0.25 mm gap are screening thresholds. Nonlinear fatigue, manufacturing tolerances, bond restraint and as-built hardware require separate evidence. [Comparison plot](results/M6_crown_comparison.png) · [Scored cases](results/M6_decision.json)

| Native mesh | Fixed 0.5 mm crown gauges, maximum | Including the newly located hotspot | Coupled EI change in the two axes | Estimated added PA12 | Linear rod gap |
|---|---:|---:|---:|---:|---:|
| Baseline R1.50 | 2.077% | 2.208% | — | — | 0.664 mm |
| R2.00 | 0.325% | 2.225% | +5.87% / +5.85% | 0.214 g | 0.741 mm |
| 0.42 mm extra section depth | 1.903% | 1.903% | +0.87% / +0.83% | 0.036 g | 0.669 mm |

R2.00 relocates the strain concentration along the arch. The section-depth trial reduces the maximum by 13.8% and retains a smaller stiffness change. Both candidates remain above the strain screen. The motion work therefore uses the published M6 geometry and model. These CAD files document the two evaluated changes. The original STEP in this study supplies the module shape for the crown region. Use the separately published lane-routed assembly CAD when integrating a future M6 candidate.

## U1 proximal compression stop

The revised compression path is NiTi heel → recessed backing shoe → PA12 lip on the same disk. In straight CAD the NiTi heel travels 0.060 mm to the shoe and moves it another 0.050 mm to the lip. At first lip contact the shoe sits 0.090 mm inside the mating plane and has a 0.07776 mm minimum gap to the seated screw. It clears both the actual U1 base and an adjacent unmodified U end face. The lip has 13.417 mm² nominal backed area. Proximal reversal is 0.360 mm and the nominal two-ended reversal is 0.610 mm. These are geometric values. [Joint checks and machining files](../../../../cad/lanes_u4m2/u_leaf_mechanical_joint/recessed_backstop/README.md)

The printed U1 body can be tested with two mechanical seats on one NiTi leaf. The net increase is +2.226 g from the CAD volume change and assumed PA12 and steel densities, excluding the mass credit for displaced adhesive. Fit and shakedown results are required before using the trial joint as a structural substitution.

## 500 g fixed-winch mission

The full U4+M2 path uses the archived eight-cell-per-module rod, 500 g head payload, M5 and M6 geometry, lanes and shared C-rope routing. The revised U1 has the single-leaf hardware and its nominal added mass distributed over the eight U1 cells, following the archived module-mass convention. The commanded rope lengths and clamp positions are held at their published values for every one of the 3,405 steps. The solver re-equilibrates the rod under gravity and rope elasticity. The original effective U stiffness is used because the joint's load–displacement response has yet to be measured. The head housing and harness lack explicit collision models.

The 63 mm body capsule is the established reference. The added polymer and hardware meshes at U1 are placed using their disk frames, including travel extremes for the retainers. Their closest vertex maintains a positive inside margin against the adjacent segment capsule. Body gap bounds deduct the maximum change in a centreline node from the original allowed gap. The rigid head adapter bound also deducts its rotational displacement using the 32.017 mm maximum radius measured from the actual adapter mesh. Independent detailed tank and adapter queries at phase ends and limiting samples check the estimates. Continuous bounds use linear translation for capsule nodes and shortest-arc rotation with linear translation for the disk hardware and rigid adapter.

| Numerical measure | Result |
|---|---:|
| States / phases | 3,405 / 11 |
| Minimum tension | 2.901208 N, C-down, step 0 |
| Maximum tension | 21.553795 N, C-up, step 2,432 |
| Largest per-rope difference vs. archived mission | 0.000219 N |
| Largest pointing error across the mission | 0.507°, step 1,775 |
| Signed forward/up pitch at the +90° and −90° targets | +89.946° and −90.072° |
| Three-dimensional pointing error at those pitch targets | 0.081° and 0.079° |
| Minimum body / adapter gap lower bounds at samples, after allowance | 8.055 / 8.629 mm |
| Minimum body / adapter gap lower bounds between samples, after allowance | 7.089 / 7.446 mm |
| Minimum remaining margin of the U1 added geometry inside the sampled capsule | 0.0723 mm |
| Independent triangle-mesh clearance and tangent checks | 18 / 18 pass |
| Minimum scaled tangent eigenvalue at these 18 checks | 0.2742, step 913 |

All 3,405 samples met the recorded 5 mm wall-gap, 1° pointing, 2.5–250 N rope-force and rod geometry/strain checks. The separate interpolated model bounds clear the 5 mm threshold for all 3,404 intervals. The selected tangent checks indicate local quasi-static equilibrium. The mass-effect values are predictions at fixed commands. Closed-loop feedback performance, stiffness and backlash of the new joint, deformed solid contact including the NiTi seats, endurance and the as-built tolerance stack require additional evidence.

[All twelve rope forces and full head pose per step (CSV.gz)](results/mission/per_step.csv.gz) · [Event rows, including ±90°](results/mission/events.csv) · [Phase summary](results/mission/phase_summary.csv) · [Sampled validation](results/mission/mission_screen.json) · [Independent CAD and tangent checks](results/mission/independent_verification.json)

## M6 bench work

Use baseline M6 modules as first specimens. Prepare three PA12 bodies from the same recorded build and a reference coupon from each PA12 build/orientation being compared. Use the [lane-routed body STL](../../../../cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl), two [crowned guide fit assemblies](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md), the Ø1.80 mm NiTi rod with a 66 mm exposed span and the specified end sleeves. Record measured radial offsets, bond line and PA12 build conditions before applying load. A specimen with the 0.42 mm crown addition is an optional A/B research sample once the change is transferred to the complete lane-routed CAD and checked.

1. Place the two end disks into the matched holders. Fix the proximal holder and prescribe relative rotation with a distal holder free to translate. Register tracked points at the virtual model master planes, z = −44.9 and +40.9 mm. Calibrate the end pose and guide wrench channels on a dummy specimen and measure mount compliance.
2. Keep optical access to the crown regions near r ≈ 9.5 mm and |z| ≈ 20.3 mm. Register the four tabulated centres to the clocked CAD. Set up surface strain measurement with DIC, using a mirror or borescope if necessary. Compare physical surface patches to simulated surface strain on the same footprints. The present numerical spherical gauges average volume strain.
3. Record the unloaded pose. Ramp relative end rotation and both guide wrenches together from a low fraction of one archived load vector. Progress in stages toward each of steps 1,709, 1,869 and 1,884 if the mount stays repeatable and the specimen stays intact. Their rotation vectors are expressed in the D0 frame. Each station's local wrench uses the deformed guide CAD frame and moment about its centre. Record force, moment, rotation and translation together. Inspect for cracking, bond movement, bore contact and permanent set between cases.
4. Compare the measured station forces, end rotations, local crown strain and minimum accessible rod gap to the corresponding model. Revisit specimen geometry and material parameters before using the results for a repeated-duty test. The static screen by itself supplies neither a fatigue life nor a material limit.

[M6 fixture layout](results/M6_bench_fixture.png) · [The six simultaneous station targets](results/m6_target_wrenches.csv) · [Crown gauge centres](results/m6_crown_gauge_locations.csv) · [Blank M6 trace worksheet](results/m6_bench_trace_blank.csv) · [U1 specimen list and low-load procedure](../../../../cad/lanes_u4m2/u_leaf_mechanical_joint/recessed_backstop/README.md#assembly-and-low-force-measurement)

## Reproduce

Use Python 3.12, NumPy/SciPy, trimesh, TetGen 0.8.4, CVXOPT, PyMetis, CadQuery and the archived study dependencies. Set `OPENBLAS_NUM_THREADS=2` for the tested two-core host. Run the following from this folder in order. Numerical JSON files include package versions and input hashes.

```sh
python crown_mesh.py --out results/crown_global.json
python crown_mesh.py --edge 0.28 --out results/crown_local_0.28.json
python crown_mesh.py --edge 0.18 --out results/crown_local_0.18.json
python crown_variants.py
for name in native_control radius_2p0 depth_0p42; do
    python crown_mesh.py --quality 7 --volume 0.85 --edge 0.39 \
        --lattice "results/crown_cad/${name}_lattice.stl" --out "results/crown_${name}.json"
done
python summarize_m6.py
python bench_m6.py
```

Build the [U1 model](../../../../cad/lanes_u4m2/u_leaf_mechanical_joint/recessed_backstop/README.md#reproduce) before the mission. From this folder run `python mission_screen.py` and `python inspect_mission.py`. The first command takes approximately 167 seconds on the tested two-core machine. The inspection command uses the previous tank STEP tessellation pipeline, VTK and Python-FCL. The archived command data and their hashes are listed in the mission JSON. The CSV rows use zero-based step numbers and the tank frame X forward, Y up, Z right. Quaternions use x, y, z, w ordering in that frame. A blank interval gap marks the first step, which has no predecessor. Use the full archived checkout for numerical reproduction.

Validation included the eight archived full-cycle tests and five length-drive tests, all passing. The deliverable checks cover the 3,405 finite state rows, 3,404 interpolated intervals, the six listed input hashes, the CAD solid exports, figure rendering and study documentation links.
