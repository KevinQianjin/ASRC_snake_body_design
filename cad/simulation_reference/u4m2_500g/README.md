# U4+M2 / 500 g simulation reference

This revision replaces the earlier illustration's 21/24/27 mm tendon lanes with the exact solver coordinates. It defines the geometry, material properties, loads and ideal constraints used by the successful nominal v3 run at commit `bee65b7`.

**Status: numerical design reference, not a released manufacturing design.** The checks in `validation.json` establish agreement of exported parameters with the solver. They do not establish that the original STEP bodies or an assembled prototype realize the solver's stiffness and constraints. Four physical issues remain open below. No new equilibrium simulation has been run.

## Files and viewing

- `baseline.json`: authoritative extracted dimensions, per-module stiffness/mass, backbone properties, rope properties, load, installation and runtime controller settings.
- `tendon_coordinates.csv`: every ideal pass-through and anchor coordinate for all 12 tendons.
- `module_properties.csv`: required module properties, including the added M backbone contribution.
- `simulation_reference.scad`: straight reference with all ropes at exactly 24 mm radius; group selection permits inspection without artificially separating coincident paths.
- `simulation_reference.blend`: rotatable nominal reference, saved 90-degree equilibrium and optional original CAD reference scenes.
- `saved_pose.json`: actual nominal v3 sample 386, exported from the stored equilibrium state; not an animation interpolation or a newly computed solution.
- `cad_geometry_audit.json`: measured source-mesh envelope and hashes.
- `validation.json`: parameter conformance checks and unresolved physical conflicts.
- `viewer_validation.json`: 68 independent checks of the saved Blender coordinates, world-space dimensions, numerical properties and absence of invented fixtures.
- `source_hashes.json`: hashes of the pinned model/data inputs.

The local frame is X along the front, Y up, Z right. The clamp is at X=0. World orientation is obtained by a +20-degree rotation about Z. Local coordinates are not absolute tank coordinates.

## Frozen geometry and mechanics

| Item | Requirement |
|---|---|
| Module sequence | U1, U2, U3, U4, M5, M6 |
| Module length | 96 mm each, continuous equivalent-rod model |
| Flexible front | 576 mm |
| Clamp interface | 20 mm, rigid and massless in the solver |
| Straight clamp-to-head reference | 596 mm |
| Collision envelope | 63 mm diameter; provisional spherical/capsule head envelope |
| M backbone | Separate central 1.8 mm diameter, 96 mm rod per M module |
| Nominal backbone modulus | 40 GPa, density 6450 kg/m³, Poisson ratio 0.33 |
| Tendons | 12 independent length commands, 2 mm equivalent diameter |
| Tendon offsets | [Y,Z] = [24,0], [0,24], [-24,0], [0,-24] mm for every group |
| Anchor ends from clamp | A: X=404 mm (U4), B: X=500 mm (M5), C: X=596 mm (M6) |
| Free rope | 1 m per tendon in the elastic rope model; winch hardware is unspecified |
| Payload | 0.5 kg point mass at the tip; no offset moment or rotary inertia |
| Installation | 20 degrees; nominal turn occurs at clamp insertion s=15 mm |
| Latest controller | 3 N prediction target, 2.5 N settled floor; 0.2-degree settled angle target |

The 63 mm cylinders and sphere in the viewer are collision-envelope representations, not solid PA12 parts or a designed sensor housing. The payload marker is a mathematical point, not a head size. Display materials do not replace the numerical stiffness and mass properties.

## Installation requirements represented by the model

### Module-to-module interface

End frames transmit deformation continuously. There is no added hinge, joint gap, sliding connection, backlash, connector mass or interface compliance. U modules must provide the exported high vertical and lower horizontal bending rigidity in the defined frame. The original STEP orientation alone does not establish measured principal stiffness directions.

No arbitrary M2.5 screw pattern, clamp boss or connector is introduced here: the present solver does not define those details. Hardware implementing this requirement still needs to be designed and checked; its rigidity, mass and dimensions must be reconciled with the baseline.

### Backbone attachment and deformation

The backbone stiffness is added in parallel to the M stiffness. Each rod is treated as fixed/bonded at both M end disks, laterally constrained and co-deforming with the module. Independent rod slip, end rotation relative to the module, loss of contact and buckling between supports are absent from the DOFs.

There are **no explicit ferrule or guide solids** in this reference, consistent with the requested drawing. Their absence from a drawing does not remove the ideal mechanical constraint. Neither a free rod in an 8.4 mm passage nor a newly invented clamp is treated as validated. Whether the original M body supplies adequate restraint remains unresolved.

### Tendon routing and anchoring

Each tendon follows straight chords through every module-end disk up to its own anchor. A ends at U4, B at M5, C at M6. Routes have no friction, bending rigidity or anchor slip. No offset lanes or angular spreading are introduced. End coordinates specify ideal force-transfer points, not rated rope anchors.

## Physical conflicts preventing a manufacturing release

1. **Coincident routes.** In U1-U4, A/B/C of each direction share exactly the same centerline: three finite-diameter ropes would overlap. B/C also coincide through M5. This is acceptable in the current idealized force model but not a realizable physical routing. Separate holes require new measured coordinates and corresponding solver changes; strict equality to every current coordinate cannot be retained.
2. **Original mesh envelope.** Source U/M bodies measure about 63.240 mm across X/Y bounding directions and require about a 63.311 mm concentric cylindrical envelope based on mesh vertices. Both exceed the nominal 63 mm collision envelope. The source meshes are kept unchanged as a reference layer. No clipping or scaling is used to silently alter their structural stiffness.
3. **Unimplemented constraints.** Rigid module interfaces and fixed/co-deforming backbones are constitutive assumptions. Their hardware implementation and stiffness have not been validated.
4. **Unspecified hardware.** Actual head shape/center of mass, interface, winches, rope material calibration, connection mass and manufacturing tolerances are not defined by the successful run.

For a physical redesign, the next decision must resolve the coincident routes. Once a feasible route and installation are selected, their coordinates, mass and stiffness must be used in a new simulation. The archived passing results are not certification of a new build.

## Source precedence

The exporter reads executable model objects plus the saved v3 `nominal_summary.json`. The v3 gains `settings.json` still contains a historical 1.5 N feedback target; `closed_loop_v2.py` and the saved v3 runtime summary specify 3 N. The runtime summary is authoritative for that run. The older model sheet's 1 N exploration is not used as the latest control target.

## Rebuild

From the repository root:

```bash
/workspace/.venvs/development/bin/python cad/simulation_reference/u4m2_500g/build_baseline.py
python cad/simulation_reference/u4m2_500g/build_viewers.py
blender -b -t 6 --python cad/simulation_reference/u4m2_500g/render_reference.py
python cad/simulation_reference/u4m2_500g/layout.py
blender -b --python cad/simulation_reference/u4m2_500g/validate_viewer.py
```

The exporter refuses to proceed if the checked local numerical sources differ from the pinned revision. It checks the dimensions, offsets, anchors, rod count, payload, runtime tension settings and sample count. The original CAD, existing solver and saved simulation data are not modified.
