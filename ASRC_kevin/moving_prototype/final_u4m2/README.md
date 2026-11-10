# U4+M2 full-scale geometry preview

This folder uses the actual uploaded flexible module assemblies:

- `UniDirectional_96.step` (U module), uploaded at `CAD/UniDirectional_96.step`
- `Medium_Stiffness_96.step` (M module), uploaded at `CAD/Medium_Stiffness_96.step`

Both source STEP models measure 96 mm along their main axis and about 63.24 mm
across. The U source contains five separate solids (one main body plus four
repeated solids). They are kept as separate companion meshes because a single
combined U mesh has shared non-manifold edges. The M source is one closed
solid. The U source is aligned along local Y; the M source is aligned along Z.
The SCAD assembly rotates U into the common Z direction and arranges
four U modules followed by two M modules, end-to-end, for a nominal 576 mm
straight layout.

## Open in OpenSCAD

Open `final_u4m2_assembly.scad`. Set `view_mode` near the top to one of:

- `"assembly"` — straight U1–U4 then M1–M2, with module ends abutting.
- `"exploded"` — same lineup with a visible gap between modules.
- `"U_only"` or `"M_only"` — one example of that module type.
- `"selected_only"` — one numbered position, chosen with `selected_module` (0–5).

The colors distinguish U (blue) and M (orange). `U_module_96.scad` and
`M_module_96.scad` show the corresponding single modules with their lower end
at Z=0. In the U file, set `component_to_show` to 1–5 to isolate one solid or
leave it at 0 to show the five-solid module. Keep all SCAD and STL files
together in this folder.

For an individual-part print check, export U solids 1–5 separately by setting
`component_to_show`, pressing F6, and using **File → Export → Export as STL**.
The four small U solids (02–05) are repeated parts. Export M from
`M_module_96.scad`. Do not export the whole 576 mm chain as one print; its
inter-module connections have not yet been designed or validated.

## Important design limits

The STL files are mesh conversions of the uploaded STEP assemblies at 0.12 mm
linear deflection. They preserve the uploaded solid geometry for viewing and
mesh export, but are not feature-editable SCAD geometry. The STEP files remain
the editable CAD sources.

To regenerate the companion STL files, install the Python package
`cadquery-ocp`, then run `convert_step_meshes.py` with `--cad-dir` pointing to
the repository's `CAD` folder. For example, from this folder:

```powershell
python convert_step_meshes.py --cad-dir ..\..\..\CAD
```

The 576 mm model is a straight geometry layout, not a motion simulation. It
does not yet model joints between modules, validate tendon continuity across
interfaces, tank clearance, material strength, fatigue, or printing tolerances.
Start with one U and one M set of solids, then check their interface and tendon
route by hand before printing the full lineup.
