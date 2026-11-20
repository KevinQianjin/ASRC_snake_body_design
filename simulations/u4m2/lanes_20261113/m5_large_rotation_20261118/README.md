# M5 guide joint under large rotation

This study executes test 1 of the 500 g U4+M2 validation plan. It compares the PA12 M5 rib body, a rigidly bonded guide and a guide with an ideal rotating seat at its four mounting lands. Each mounted case has two guides, 12 mm either side of the module centre. The case files contain simulated equilibria, disk reactions, eight individual land reactions and surface strain locations. [Engineering report](../../../../reports/projects/m5_structure/M5_Joint_Test_2026_11_18.md) · [Test plan](../../../../docs/500g_validation_plan.md) · [Numerical checks and input hashes](summary.json)

## Geometry and joint model

The mesh comes from a radial section of the published M5 anchor-B bellmouth STL. The solver measures the local thickness by intersecting normal rays with the body, then repeats the measured section at the eight rib azimuths. It follows the earlier rib model in treating the two disks and the four inner rings as rigid patches. The nominal land is 0.50 mm long. The mounted ribs are at 67.5°, 157.5°, 247.5° and 337.5°. Each station uses a single rigid guide frame. The bond ties the position and rotation of each mounting patch to that frame. The rotating seat locates its patch centre and allows the patch to rotate in three dimensions. The bare control has independently moving land patches. [M5 body](../../../../cad/lanes_u4m2/end_bellmouth_v1/M5_lane_anchorB.stl) · [Previous linear rib study](../evening_20261117/README.md)

Edges conform to the land, socket and rigid-patch boundaries. A 0.003 mm section simplification and a 0.002 mm intersection grid remove near-coincident vertices at the patch cuts. The original section area is 656.511 mm² and the meshed section area is 656.483 mm². The active elements exclude triangles lying entirely inside a single rigid patch. The shell uses the earlier fitted modulus of 1,530 MPa and Poisson ratio 0.4. Both remain fixed throughout the runs.

Each triangle has three midsurface positions and three unit directors. Membrane strains follow the deformed midsurface metric. Bending uses the change in director projected onto each surface tangent. Three-point integration gives transverse shear with a 5/6 correction. The energy is objective under a superposed rigid motion. The consistent tangent includes geometric stiffness and the second derivatives of the director and rigid-patch maps. The material law is isotropic and elastic in shell strain. Some struts are only 1.53 mm wide in the rib plane and about 3 mm thick. Their local strain remains sensitive to the shell approximation and the rigid-patch geometry. The tests compare the undeformed element tangent with the independently implemented archived membrane and plate matrices. [Shell formulation](shell.py) · [Solver verification](test_shell.py)

## Boundary conditions

- **Pure bending.** Clamp the proximal disk. Apply a pure spatial end couple about the 0° or 67.5° axis. The distal force and the two transverse moment components are free to equilibrate at zero. Prescribe the signed end-disk bend coordinate in increments up to 96.19° (96 mm × 0.01748791 rad/mm). Each full sweep saves five equilibrium samples. Differentiate the equilibrium equations for tangent bending stiffness and torsional stiffness. The twist direction is the bent distal axis while holding the bend coordinate fixed. Selected full-bend states also receive positive and negative finite twists of 0.001 rad.
- **Installed guide loads.** Clamp the proximal disk and prescribe the relative position and orientation of the distal disk from each saved M5 pose. Ramp the archived eight cell strains and integrate them to obtain intermediate disk poses. Apply the eight signed bore forces simultaneously at each of the two guides. Each force stays fixed in the spatial frame of the clamped proximal disk. Its application lever rotates with the locally solved guide. Before local equilibrium, the source pose and levers reproduce the archived station force and moment. Applying a second resultant would duplicate the rope load. The 500 g payload enters through the archived full-arm solution. The local fixture applies the two end restraints and these 16 bore forces. [Transformed bore loads and source frames](load_cases.json) · [Source forces](../morning_20261116/rigid_end_audit/guide_holes.csv) · [Source station moments](../morning_20261116/rigid_end_audit/guide_stations.csv)

The local fixture isolates M5's printed ribs at its inner two guide stations. It omits distributed body weight, the central NiTi rod, the outer ±24 mm guide attachments, adhesive/retainer compliance, changing rope tensions, friction and self-contact. The saved whole-arm poses retain their original guide, backbone and payload assumptions. The strain/stiffness results describe the isolated rib fixture and ideal joint. Printed-part strength, contact clearance, assembled backbone stiffness and closed-loop positioning each require their own evidence.

The straight-state check also compares the derivative of each land reaction under a pure 67.5°-axis bend against the earlier linear model. It scales both derivatives to the reference curvature and repeats the extraction at two perturbation sizes. The large-bend case files come from the nonlinear continuation. [Land reaction slopes](linear_land_check.json) · [Reproduction](linear_reference.py)

## Reading the outputs

| Input or output | Meaning |
|---|---|
| `fraction` | Fraction of the target end angle for pure bending. For installed guides, fraction of the imposed rod-cell strains and bore forces. |
| `tangent_EI_Nmm2`, `tangent_GJ_Nmm2` | Incremental rotational stiffness multiplied by the 96 mm reference length, in N·mm². The average bend coordinate is end angle divided by 96 mm. |
| `force_N`, `land_moment_Nmm` within `lands` | Force and moment the guide applies to the rib. Components use the fixed proximal CAD axes. Moment is about each moving land centre. Point-joint reaction moments should vanish. |
| `relative_rotation_deg`, `inplane_rotation_deg` | Magnitude of the land-to-guide rotation vector and its signed projection onto the reference rib normal in guide coordinates. |
| `socket_travel_3d_mm`, `socket_travel_inplane_mm` | Maximum motion of a rib midsurface node relative to the guide across the ±1.62 mm socket window. These values include geometry and rotation of the strut. A contact model would be needed to convert travel into a physical seat clearance. |
| `surface_extremes` | Largest tensile and compressive in-plane principal strains and build-Z strains across both shell faces. Coordinates give radius, module axial position and signed distance from the rib midsurface, in mm. The strain measure is Green membrane strain plus the first-order bending term at that face. |
| `minimum_oriented_area_ratio` | Minimum deformed triangle area projected on its mean director, divided by its original signed area. A positive value checks local orientation. |
| `steps`, `split_last_step`, `finite_twist` | Continuation attempts and retries, independent split-step equilibrium at the same endpoint, and the signed finite torsion probes where run. |

The [installed guide frames](installed_guides.json) retain the solved position and orientation of each inner guide and all eight B/C bore centres at the four prescribed poses. Each mounted land includes its pivot position, signed guide-on-rib force and couple in guide axes, and signed relative rotation vector. The export also gives each bore's displacement from the archived whole-arm guide at the same disk pose. That difference compares two model assumptions. A measurement of bore displacement would need a physical guide and optical or dimensional tracking.

The solver accepts a state when all free generalized residuals fall below 0.00003 in the native translation and rotation coordinates. The reported force and moment balance also includes both disk reactions and the applied spatial bore forces. The area checks exclude locally folded equilibria. The bending and torsion tangents describe this prescribed quasi-static fixture.

## Reproduction

Run from this directory in a fresh Python environment with the package versions in the summary. The solver uses NumPy, SciPy, trimesh, Shapely, rtree, triangle, networkx, numba, matplotlib and CVXOPT. CVXOPT provides the sparse LDL factorisation used in these results. A SuperLU fallback is available. Pinning BLAS to one thread per process keeps the larger meshes within a shared machine's memory. Choose an empty output directory for a new calculation. Scratch checkpoints belong to a single mesh size and may be discarded after the checks. [Simulation inputs and versions](summary.json)

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
m5_run=$(mktemp -d)
python -m pip install numpy==2.3.5 scipy==1.17.0 shapely==2.2.0 trimesh==5.2.0 \
    triangle==20250106 numba==0.68.1 matplotlib==3.10.8 cvxopt==1.3.3 \
    rtree==1.4.1 networkx==3.7
python -m unittest -v test_shell
python linear_reference.py --area .025 --out "$m5_run/linear_land_check.json"
python study.py --area .18 --step .0625 --variants bare point \
    --cases bend67.5 bend0 146 141 47 64 \
    --cache "$m5_run/base-cache" --out "$m5_run/results/base_0p18"
python study.py --area .18 --step .0625 --variants bond --cases bend67.5 146 141 47 64 \
    --cache "$m5_run/base-cache" --out "$m5_run/results/base_0p18"
if ! python study.py --area .18 --step .03125 --variants bond --cases bend0 \
    --cache "$m5_run/base-cache" --out "$m5_run/results/base_0p18"; then
    python study.py --resume --area .18 --step .00390625 --variants bond --cases bend0 \
        --cache "$m5_run/base-cache" --out "$m5_run/results/base_0p18"
fi
python audit_states.py --results "$m5_run/results/base_0p18" --cache "$m5_run/base-cache"
```

A refined calculation interpolates a prior displacement field to the new mesh and solves equilibrium again. The critical increment can be repeated from the same converged 93.75% state as one 6.25% increment or two 3.125% increments. This preserves loading history in the comparison. The endpoint Jacobian can also be checked against an independent signed twist pair. Keep the finest mesh runs sequential on a memory-limited machine. [Refinement driver](refine.py) · [Saved load continuation](continuation.py) · [Result reduction and verification](review.py)

The coarse bonded 0° sweep includes an archived folded endpoint. The accepted rerun used a maximum increment of 0.03125 and resumed from the last valid 0.99609375 fraction with a 0.00390625 increment. An interrupted solve can be continued with the same case, area and cache and the `--resume` option. Every accepted coarse checkpoint was reconstructed for an independent orientation audit. The results folders retain rejected trials separately from the accepted case families.

For the 0.055 mm² mesh, the pure sweeps include the finite twist probes. Record 146 also repeats the last load increment. The remaining installed cases solve the saved end poses. The raw JSON records exactly which fractions and probes were evaluated.

```sh
python refine.py --area .055 --variants bare point bond --cases bend0 bend67.5 \
    --all-samples --split --twist --seed "$m5_run/base-cache" --cache "$m5_run/mid-cache" --out "$m5_run/results/refined_0p055"
python refine.py --area .055 --variants point bond --cases 146 --split \
    --seed "$m5_run/base-cache" --cache "$m5_run/mid-cache" --out "$m5_run/results/refined_0p055"
python refine.py --area .055 --variants point bond --cases 141 47 64 \
    --seed "$m5_run/base-cache" --cache "$m5_run/mid-cache" --out "$m5_run/results/refined_0p055"
```

The 0.025 mm² runs use the intermediate mesh checkpoints. At the 67.5° full bend, the 0.055 and 0.025 mm² meshes gave overlapping ranges of absolute tangent stiffness for the two mounted designs. The additional 0.015 mm² mesh tests the straight and full-bend endpoints of all three joint models on that axis. The four area limits correspond to 32,976, 88,736, 187,048 and 309,416 active triangles across all eight ribs. The final reduction verifies the endpoints, equilibrium and mesh comparisons and writes the chart and input hashes.

```sh
python refine.py --area .025 --variants point --cases bend67.5 --all-samples --split \
    --seed "$m5_run/mid-cache" --cache "$m5_run/fine-cache" --out "$m5_run/results/fine_0p025"
python refine.py --area .025 --variants bare bond --cases bend67.5 --all-samples \
    --seed "$m5_run/mid-cache" --cache "$m5_run/fine-cache" --out "$m5_run/results/fine_0p025"
python refine.py --area .025 --variants bare point bond --cases bend0 --all-samples \
    --seed "$m5_run/mid-cache" --cache "$m5_run/fine-cache" --out "$m5_run/results/fine_0p025"
python refine.py --area .025 --variants point bond --cases 146 --split \
    --seed "$m5_run/mid-cache" --cache "$m5_run/fine-cache" --out "$m5_run/results/fine_0p025"
python refine.py --area .025 --variants point bond --cases 141 47 64 \
    --seed "$m5_run/mid-cache" --cache "$m5_run/fine-cache" --out "$m5_run/results/fine_0p025"
python refine.py --area .015 --variants bare point bond --cases bend67.5 \
    --seed "$m5_run/fine-cache" --cache "$m5_run/critical-cache" --out "$m5_run/results/critical_0p015"
python installed_guides.py --results "$m5_run/results/refined_0p055" \
    --cache "$m5_run/mid-cache" --out "$m5_run/installed_guides_coarse.json"
python installed_guides.py --results "$m5_run/results/fine_0p025" --cache "$m5_run/fine-cache" \
    --coarser "$m5_run/installed_guides_coarse.json" --out "$m5_run/installed_guides.json"
python review.py --results-dir "$m5_run/results" --output-dir "$m5_run"
```
