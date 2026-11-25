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

## Target software identified

Camtek's official PEPS Wire EDM product page explicitly lists AC Robofil and AC Millennium technology databases/post support, plus profile simulation, offsetting, automatic wire threading/start-hole generation, slug handling, and setup-sheet/NC output. Its training outline covers the required workflow from DXF/STEP import through billet/technology/strategy/post/simulation. PEPS is the most relevant software route discovered for making the actual machine file. [Camtek PEPS Wire EDM](https://www.camtek.de/en/wire-edm) · [PEPS Wire EDM training outline](https://www.camtek.de/assets/template/Medien/Dateien/PEPS/Schulungen/PEPS_Schulung_Wire_EDM.pdf)

The official trial is 90 days, but requires a contact-form request and hardware-context/license activation; the published system requirements specify Windows 10 64-bit minimum and recommend Windows 11. This cloud environment is Linux, has no Wine or PEPS installation, and cannot run the vendor software. Trial request/activation details are on the [official trial page](https://www.camtek.de/en/peps/peps-testversion.html); system requirements are on the [official specifications page](https://www.camtek.de/en/peps/peps-technical-specifications.html). No user contact data or hardware license request was transmitted.

## Section-table axis interpretation

In the oriented STEP frame, the end section is 6 × 5 mm with 30 mm² area. `spring_strip.json` lists 7.05 × 6.33 mm end extents but also reports area 30 mm². The extents cannot both be orthogonal rectangular section dimensions; this is an axis/projection or extent-interpretation issue, not evidence of a different model revision. Use the STEP and its section-area check as geometry, but do not interpret the JSON extents as stock width/thickness until their axes are understood.

## References

- FreeCAD CAM postprocessor docs: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/CAM_Post.md
- Local generic WEDM post: `/usr/share/freecad/Mod/CAM/Path/Post/scripts/wedm_post.py`
- Source CAD/profile/audit: `U_leaf_spring_01.step`, `U_leaf_spring_01_profile.dxf`, `profile_dxf_audit.json`
- Published PolyU machine information and process questions: `../../niti_manufacturing_polyu_report.md`
