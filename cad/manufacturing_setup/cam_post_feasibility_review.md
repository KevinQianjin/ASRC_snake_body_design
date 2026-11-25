# CAM/post feasibility review

Date: 2026-11-25

## Geometry-supported operation

The isolated `U_leaf_spring_01.step` has been validated as a constant-width profile: after a 45-degree Y reorientation, three cuts across its width each give one closed profile, 94 × 5 mm, with section area 110.343785 mm². Width is 6 mm, and volume/width matches the section area. `U_leaf_spring_01_profile.dxf` is a 1:1 closed profile contour through that 6 mm blank width. For geometry, the closest match is a 2D profile cut such as wire EDM. The DXF approximation and dimensions are in `profile_dxf_audit.json` and `profile_dxf_notes.md`.

## Software and postprocessor findings

The installed FreeCAD 1.0 CAM source contains `/usr/share/freecad/Mod/CAM/Path/Post/scripts/wedm_post.py`. It is a generic Wire EDM post, not a post identified for the Agie Charmilles Robofil 240SL. Its defaults output a generic mill-like header (`G17 G54 G40 G49 G80 G90`), a stop M-code, and generic end codes. The script does not define Robofil technology tables, wire/flush/servo settings, threading/entry handling, or an installation-specific machine configuration. FreeCAD also has Siemens-independent milling posts (e.g. Fanuc/Heidenhain), but no identified Siemens 840D / U004 HPM600U post in the installed library.

The Robofil documentation search indicates ISO programming on Robofil machines, which means some coordinate-motion syntax may resemble generic ISO G-code. That is not enough to validate the complete program dialect or the wire-EDM process commands. Do not infer compatibility from shared `G01`/`G02` motion syntax.

## Recommended path and release boundary

Wire EDM is the most direct geometry route because the solid is a constant-width 2D profile through a 6 mm blank. It is only a candidate pending actual NiTi grade/condition, stock dimensions, cut direction, entry/start-hole, workholding, wire compensation, rough/trim pass, surface integrity, and fatigue-coupon requirements. An actual postprocessed file also needs the exact Robofil controller/software and its validated postprocessor.

Do not call generic WEDM output “post-CAM” for the target machine and do not run it on the machine. A safe deliverable that can be produced without machine-specific data is the checked DXF + geometry audit + CAM setup sheet/process plan. The file currently needed to finish actual post-CAM is the Robofil-specific process/post definition from that exact installation (including required technology and M-code conventions), followed by simulation and a supervised dry-run.

## Separate drawing mismatch

The STEP profile has 5 mm maximum profile dimension; project `spring_strip.json` reports end sections around 6.33 mm. The DXF follows the STEP. Resolve whether these represent the same model revision and axis convention before stock purchase or any CAM setup.

## References

- FreeCAD CAM postprocessor docs: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/CAM_Post.md
- Local generic WEDM post: `/usr/share/freecad/Mod/CAM/Path/Post/scripts/wedm_post.py`
- Source CAD/profile/audit: `U_leaf_spring_01.step`, `U_leaf_spring_01_profile.dxf`, `profile_dxf_audit.json`
- Published PolyU machine information and process questions: `../../niti_manufacturing_polyu_report.md`
