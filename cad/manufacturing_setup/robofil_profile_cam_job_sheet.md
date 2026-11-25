# Leaf 01 wire-EDM CAM job sheet

**Status: geometry setup prepared; machine post is not released.** This sheet turns the validated CAD geometry into a specific CAM setup brief for a 2D profile cut. It is not an NC program, machine setup sheet, or approval to cut NiTi.

## Selected geometry route

Wire EDM is the best geometric fit among the researched candidate processes: the exact STEP leaf is a constant-width extrusion of one 2D outline. The source assembly contains four individual leaves. This sheet uses isolated leaf 01 and its derived profile DXF.

| CAM field | Current geometry value | Basis / boundary |
|---|---:|---|
| Input contour | `U_leaf_spring_01_profile.dxf` | One closed polyline, mm units |
| Profile-plane bounds | X = 0–94 mm; Y = 0–5 mm | Measured from leaf 01 STEP section after 45° Y reorientation |
| Blank thickness through profile plane | 6.000000 mm | Orthogonal width dimension of STEP solid; confirm physical stock certificate |
| Coordinate frame | X along spring span; Y along section profile; stock thickness along Z | Do not use the unrotated assembly placement as the EDM cutting plane |
| Taper / upper-head offset | nominally zero | Constant profile through width; do not program taper unless a revised model requires it |
| Contour compensation | not defined | Must come from selected wire, material, generator/technology table, and trim strategy; do not treat DXF polyline as compensated wire-center path |
| Start/entry | not defined | Requires actual thread/start-hole and lead-in plan in stock/fixture |
| Rough/trim strategy | not defined | NiTi edge integrity and fatigue behavior require a qualified test coupon |
| Section-table interpretation | needs axis clarification | Oriented STEP section is 6 × 5 mm, area 30 mm². `spring_strip.json` lists 7.05 × 6.33 mm extents but area 30 mm², so those extents are not a rectangular stock-section width/thickness pair |

## CAM construction sequence

1. Open the DXF and STEP in the selected wire-EDM CAM package. Set units to millimetres and verify the DXF extents are 94 × 5 mm and that the STEP stock-width direction is 6 mm.
2. Select the exact Robofil 240SL machine definition, installed control/software version, and its matching 4-axis postprocessor. Disable taper for this constant-width contour. Choose a datum and work origin that are physically probed/settable on the fixture; record it in the setup sheet.
3. Define the certified NiTi blank and workholding. Plan the start hole, wire threading, lead-in, slug/support, and cut order so the spring stays retained and the finished fatigue edge is not damaged during release.
4. Select wire and technology table for the actual NiTi grade/condition and 6 mm thickness. Define rough and trim passes, wire offset/spark gap, corner strategy, flushing/servo settings, cut direction, and any edge-cleaning operation only from the machine/process data. Do not substitute steel or generic titanium values.
5. Simulate stock removal and slug behavior. Check the resulting shape against the exact STEP and an approved drawing; report the measured edge/section and profile deviations. The DXF polyline has a documented +0.0501% section-area approximation error, so use the STEP/drawing for acceptance.
6. Post with the Robofil-specific post. Verify program syntax and technology-selection references against the actual controller version and installed wire/technology tables. Backplot in the machine software, then perform the machine's documented graphical/dry-run procedure before cutting a coupon.
7. Cut a representative coupon and inspect edge integrity, burr/recast condition, dimensions, force/recovery, and cyclic response before making the production leaves.

## Software route found

Camtek's PEPS Wire EDM is the most directly matched software route found for this geometry. Camtek says PEPS has an AC Robofil post/database option, technology databases, wire offsetting/simulation, automatic threading/start-position and start-hole output, slug handling, and setup-sheet output. The official trial offer is 90 days free, but it is requested through a vendor contact form and license activation process. PEPS 2022–2026 requires Windows 10 64-bit (Windows 11 recommended); this cloud computer runs Linux and has no Wine/PEPS install, so it cannot run the trial here. [PEPS Wire EDM capabilities](https://www.camtek.de/en/wire-edm) · [Trial request and activation](https://www.camtek.de/en/peps/peps-testversion.html) · [PEPS system requirements](https://www.camtek.de/en/peps/peps-technical-specifications.html) · [Official PEPS Wire EDM training outline](https://www.camtek.de/assets/template/Medien/Dateien/PEPS/Schulungen/PEPS_Schulung_Wire_EDM.pdf)

The training outline follows the right sequence for this job: import DXF/STEP, define billet, select material/wire technology, define contour/start position, choose machining strategy and offsets/tags, simulate, configure the post, and generate NC. That sequence is documented here so the file setup is ready to continue in PEPS. PEPS's Robofil support does not itself supply qualified NiTi settings: the actual NiTi grade/condition, wire and machine technology table still need identification. The end-section figures in `spring_strip.json` also need their coordinate/extent definitions clarified before treating them as a stock specification; the listed extents and area show they are not a simple rectangular 7.05 × 6.33 mm section.

## Why there is no posted machine program here

The cloud FreeCAD 1.0 install includes a generic `wedm_post.py`, but it is not a Robofil 240SL post. Its mill-like preamble/end code and missing Robofil technology, threading, process control, and upper-head U/V handling mean that output would not be valid target-machine code. A motion-only file could move axes without selecting safe/qualified EDM conditions. PEPS is the promising target-specific software, but it is not installed/runnable in this Linux cloud environment and its trial is issued after contact/license activation. The actual control revision, NiTi technology data, stock condition, fixture/datum, wire, compensation, and entry/trim strategy are not encoded in the CAD files.

This is the complete machine-agnostic CAM setup description that can be prepared from the available geometry. It is not safe to relabel generic G-code as post-CAM for the target Robofil.
