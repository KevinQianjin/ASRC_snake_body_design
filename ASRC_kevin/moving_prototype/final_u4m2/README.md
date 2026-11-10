# U4+M2 STEP-derived geometry preview — incomplete, not print-ready

## Download and open the complete set

Download [`final_u4m2_openSCAD_bundle.zip`](final_u4m2_openSCAD_bundle.zip) and
extract it. Keep the files together in the extracted folder, then open
`final_u4m2_assembly.scad` in OpenSCAD. Press **F5** to preview the model.

The SCAD file needs these six STL files beside it: `UniDirectional_96_part_01.stl`
through `UniDirectional_96_part_05.stl`, plus `Medium_Stiffness_96.stl`. If you
open only the `.scad` file, OpenSCAD will show “Can't open import file” warnings
because it cannot find those meshes. Do not rename or move the mesh files away
from the SCAD files.

## Important: the uploaded U geometry is incomplete

The U STEP assembly lists an inner ring, four NPJ wing parts, a disk, and a leaf
spring. Its solid geometry contains only the inner ring and four leaf-spring
solids; the named NPJ wings and disk have no solid geometry in the STEP file.
The five U meshes therefore do **not** make a complete U module. The M STEP
imports as one solid, but it does not include the separate 1.8 mm NiTi backbone
from the latest M-module study. Neither STEP file includes material labels.

Treat this package as a viewing and geometry-review aid only. Do not order the
full 4U+2M print from these meshes. The team needs complete, material-separated
U geometry and confirmation of the M rod guides and end attachments first.

This folder uses the actual uploaded flexible module assemblies:

- `UniDirectional_96.step` (U module), uploaded at `CAD/UniDirectional_96.step`
- `Medium_Stiffness_96.step` (M module), uploaded at `CAD/Medium_Stiffness_96.step`

Both source STEP files measure 96 mm along their main axis and about 63.24 mm
across. The U source's five solids are one inner ring and four leaf-spring
solids; they are kept separate because a combined U mesh has shared
non-manifold edges. The M source is one closed solid. The U source is aligned
along local Y; the M source is aligned along Z. The SCAD assembly rotates U
into the common Z direction and arranges
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

You can use the U selector to inspect the available solids individually, but
do not treat them as the complete printable module. The current assembly also
does not include inter-module joints, the M backbone, or rod end fittings.

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
