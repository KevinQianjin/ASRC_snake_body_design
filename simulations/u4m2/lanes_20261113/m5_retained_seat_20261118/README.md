# Physical retained-seat study for the two M5 inner stations

Test 2, stage 2 of the [500 g validation plan](../../../../docs/500g_validation_plan.md). The source is commit `1c101887e4c6c84e66a660d2d2460594a741fd54`. The [preceding evening study](../evening_20261118/README.md) used an ideal, freely rotating pinned land. The present work adds explicit hardware, an assembly path, unilateral contact and loaded checks against the other portions of M5.

[English test report](../../../../reports/projects/m5_structure/M5_Retained_Seat_2026_11_18.md) · [CAD and assembly drawings](../../../../cad/lanes_u4m2/retained_seat_20261118/README.md) · [Numerical results](results/) · [Coupon and fixture handoff](../../../../reports/projects/m5_structure/M5_Retained_Seat_2026_11_18.md#next-tests)

## Coverage and coordinates

There are six converged endpoint states. Two are pure 96.19° M5 bends about the 0° and 67.5° axes. The other four are records 146, 141, 47 and 64 from the 500 g closed-loop archive. Each saved hold uses its prescribed end-disk pose and simultaneous bore loads. Each local calculation uses the force and rotation from the **same** rib, station, record and mesh. Four mounted webs at each of −12/+12 mm give 48 loaded sites. All eight ribs enter the CAD clearance check. The global shell model gives free dummy inserts to the four unmounted ribs. The physical body is machined only at the eight mounted sites.

- `recover_poses.py` reconstructs the 0.055 and 0.025 mm² shell endpoints and checks tip translations, site forces and site rotations against the committed pinned-seat results. The full nodal positions and directors are scratch data. Both shell meshes use the evening ideal pivot.
- `straight.py` checks all 44 components at each station against each other and the real machined body, repeats the V3 rope-bore measurements, and computes mass from exported volumes. PA12 and steel densities come from the V3 mass model. The aluminium assumption is 2.70 g/cm³.
- `assembly.py` tests the ordered part paths against the module and the parts already seated. For translations, a midpoint separation larger than the maximum possible relative travel certifies a collision-free subinterval. Near contact, the program subdivides to its stated limit. The journal gives any unresolved subinterval, sampled screw angles and any positive intersection. The published motion bounds use the larger pre-trim fork envelope, which contains the final fork. Both the moving parts and the seated obstacles use that conservative shape. A zero distance may represent intentional seating. Solid intersection volume distinguishes overlapping material.
- `tool_access.py` intersects a 70 mm coaxial tool-shank envelope with each obstacle present at that operation. The radius is 0.46 mm for the lap screws, 0.55 mm for the arm/fork screws and 0.50 mm for each pin end. It starts 0.002 mm beyond the screw head. This checks space for a shaft. Blade/socket fit, hand access, drive torque and transmission geometry need a tool trial.
- `side_drive.py` searches 72 side-entry orientations for each of the 16 lap screws and three driver exterior sizes. The 55 mm lateral entry and the complete 1.60 mm tightening stroke use continuous swept solids. The model encloses each round cylinder in a circumscribed polygon and takes the hull of its two end positions before forming the union. The best candidates receive a second solid-intersection check against the cage and the parts present at that operation. The envelope starts 0.002 mm above the target screw face. The drive internals and blade engagement require a physical fixture. [Tool sweeps](results/side_drive.json)
- `clearance.py` transfers the machined CAD using the eight rib shell mid-surfaces and their interpolated unit directors. It checks a ±4.85 mm axial window at each station, in the moving guide frame. Both wall families of the mount and the two intentional metal bearing surfaces are measured separately. An AABB screen precedes exact triangle distances with FCL, and independent Manifold distances and intersection volumes check the closest pairs. Shell area and CAD surface spacing are varied separately.
- `remaining_body.py` partitions the original M5 volume outside those windows into actual ribs, end disks, integral distal anchor lugs and four coupling rings. It transfers planar ribs with the shell field and rigid parts with a transform fitted to their constrained nodes. The uncut parent conservatively fills unused holes on the opposite station. A station-enclosing cylinder gives an axial distance bound. Close or axially overlapping pieces receive direct triangle-to-part checks. It compares the original and shortened fork at the offending rib, and measures separation between the two station envelopes.
- `contact.py` creates a 3-D HEX8 solid patch of the machined web, with a crowned hole and spherical thrust relief. It clamps the two cut faces at ±2.7 mm along the web in its co-rotating frame. The remaining outside faces are traction-free. Linear isotropic PA12 uses 1,530 MPa and Poisson ratio 0.40. A rigid Ø0.60 mm shaft and two finite spherical thrust pads apply compressive normal reactions. The solver balances the three components of the applied force, permits three relative translations, recomputes the normals and records the reaction moment about the ideal pivot. The indentation, tensile/compressive principal strains, nodal bearing pressure and contact distribution are incremental local quantities. The cut-face constraints supply any required moment. Friction, plasticity, PA12 anisotropy, the far-field strain and fastener elasticity are outside this model.
- `corrected.py` transfers the solved fine-mesh local displacement to the actual CAD through inverse trilinear HEX8 coordinates. Each mounted web receives its own translation and elastic displacement; unmounted webs retain their global-shell motion. The least-squares fit of one rigid guide to the four independent pivot corrections is a compatibility diagnostic. A common-guide equilibrium must supply the bore displacement for a future controller replay.

The contact study also varies the web crown radius, cut-face distance and alignment of mesh layers with the two outer recess transitions. The regular and feature-fitted meshes describe the same analytical surface. The [transfer check](results/transfer_sensitivity.json) compares distance to the discrete mesh separately from the displacement difference applied to CAD. Two load sites in each of the 67.5°-axis pure bend and record 146 receive the feature-fitted check. The same file gives the distance of the nominal CAD window vertices outside their closest global-shell triangle. Its largest values occur on the four unmounted webs where the source has dummy pin holes.

## Reproduction

Run from the repository root with a scratch directory that can hold the nodal fields. Use the package versions in [run provenance](results/provenance.json). The geometry builder uses Manifold double-precision booleans and round-trips the deliverable single-precision STLs. The first three shell commands below generate the pinned checkpoints on a clean machine. Existing pinned or rotating-band checkpoints at the matching mesh area can seed `recover_poses.py` directly. For checkpoints split by case group, call the recovery script once per group with its directory and `--cases`. [Original shell workflow](../evening_20261118/README.md#reproduction)

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cad=cad/lanes_u4m2/retained_seat_20261118
study=simulations/u4m2/lanes_20261113/m5_retained_seat_20261118
pin=simulations/u4m2/lanes_20261113/evening_20261118/pin_seat.py
scratch_dir=/tmp/asrc-retained-reproduction
mkdir -p "$scratch_dir/fields" "$scratch_dir/results"
python "$cad/build.py" --out "$scratch_dir/parts"
python "$pin" --hole-radius .3 --area .18 --cache "$scratch_dir/pinned018" --out "$scratch_dir/source018"
python "$pin" --hole-radius .3 --area .055 --seed "$scratch_dir/pinned018" --cache "$scratch_dir/pinned055" --out "$scratch_dir/source055"
python "$pin" --hole-radius .3 --area .025 --seed "$scratch_dir/pinned055" --cache "$scratch_dir/pinned025" --out "$scratch_dir/source025"
python "$study/recover_poses.py" --area .055 --seed "$scratch_dir/pinned055" --out "$scratch_dir/fields"
python "$study/recover_poses.py" --area .025 --seed "$scratch_dir/pinned025" --out "$scratch_dir/fields"
python "$study/straight.py" --parts "$scratch_dir/parts" --out "$scratch_dir/results"
python "$study/assembly.py" --precision .06 --extended-forks --out "$scratch_dir/results"
python "$study/tool_access.py" --out "$scratch_dir/results"
python "$study/side_drive.py" --out "$scratch_dir/results"
python "$study/clearance.py" --cache "$scratch_dir/fields" --tag 0p055 --edge .2 --out "$scratch_dir/results"
python "$study/clearance.py" --cache "$scratch_dir/fields" --tag 0p025 --edge .2 --out "$scratch_dir/results"
python "$study/clearance.py" --cache "$scratch_dir/fields" --tag 0p025 --edge .1 --out "$scratch_dir/results"
python "$study/remaining_body.py" --cache "$scratch_dir/fields" --out "$scratch_dir/results"
python "$study/remaining_body.py" --cache "$scratch_dir/fields" --cases bend67.5 bend0 --edge .25 --out-name remaining_body_fine.json --out "$scratch_dir/results"
python "$study/loaded_section.py" --cache "$scratch_dir/fields" --results "$scratch_dir/results" --out "$scratch_dir/results/loaded_clearance.svg"
python "$study/contact.py" --level middle --shell 0p055 --out "$scratch_dir/results/contact_middle"
python "$study/contact.py" --level fine --fields "$scratch_dir/contact-fields" --out "$scratch_dir/results/contact_fine"
python "$study/contact.py" --level finer --station 12 --ribs 67.5 157.5 --out "$scratch_dir/results/contact_finer"
python "$study/contact.py" --level fine --crown 2 --cases bend67.5 146 --station 12 --ribs 67.5 157.5 --out "$scratch_dir/results/alternative_crown_2mm"
python "$study/contact.py" --level fine --length 3.6 --cases bend67.5 146 --station 12 --ribs 67.5 157.5 --out "$scratch_dir/results/longer_local_patch"
python "$study/corrected.py" --cache "$scratch_dir/fields" --fields "$scratch_dir/contact-fields" --edge .15 --out "$scratch_dir/results"
python "$study/contact.py" --level fine --fit-relief --cases bend67.5 146 --station 12 --ribs 67.5 157.5 --fields "$scratch_dir/feature-fields" --out "$scratch_dir/results/feature_fitted_patch"
python "$study/transfer_check.py" --cache "$scratch_dir/fields" --fields "$scratch_dir/contact-fields" --feature-fields "$scratch_dir/feature-fields" --out "$scratch_dir/results"
python "$study/summarize.py" --results "$scratch_dir/results"
python -m unittest discover -s "$study" -p test_retained.py -v
```

The CAD and body tests default to the committed STL set. Both are available in a fresh checkout. Use `--parts` where exposed to substitute a regenerated set. `figures.py` renders the two CAD drawings with a deterministic triangle depth buffer and exact solid sections.
