# NiTi U-leaf geometry and CAM handoff

This folder contains exact neutral geometry and a candidate profile-cut contour. It is **not a released manufacturing package** and contains no CAM project or CNC/EDM machine code.

## Files

- `U_leaf_spring_01.step` through `U_leaf_spring_04.step`: exact single B-rep spring solids, extracted from source STEP solids 2–5 without geometric changes.
- `U_leaf_spring_01_profile.dxf`: 1:1 millimetre section contour for leaf 01, candidate input to a compatible profile-cut process.
- `profile_dxf_audit.json`: section comparison, DXF closure/dimensions, and sampled contour area error.
- `profile_dxf_notes.md`: coordinate mapping, stock width, approximation, and process boundary.
- `spring_geometry_audit.json`: source and STEP export geometry checks.
- `manufacturing_checklist.md`: self-guided file-to-machine-input workflow and release checks.
- `robofil_profile_cam_job_sheet.md`: geometry-specific wire-EDM CAM setup sheet with the values already derived from CAD and unresolved machine-control fields.
- `cam_post_feasibility_review.md`: installed-post review and reason no target-machine code was emitted.
- `../../docs/niti_file_to_machine_setup.md`: self-service explanation of the geometry mismatch and the PEPS-to-Robofil route.
- `source_files.txt`: provenance and geometry interpretation.

The full U module source is `../../modules/UniDirectional_96.step`. The combined spring STL is visual reference only and is not a CAM master.

## Geometry finding

After removing the spring's 45° diagonal orientation, three sections across the approximately 6 mm width match within CAD-kernel precision. Each is one closed profile with 94 × 5 mm envelope and 110.343785 mm² area. Solid volume divided by width matches the section area. Thus the variable 1–5 mm profile along the length is representable as a 2D contour through a 6 mm-wide blank. This geometry supports a candidate profile-cut route; it does not prove process/material suitability.

## Important limits

No file specifies NiTi grade, transformation state, stock lot, cut allowance, tolerances, surface finish, datum, workholding, wire/cutter compensation, entry strategy, machine CAM setup, or postprocessor. The DXF is a sampled polyline approximation of the STEP section (147 vertices; +0.055286 mm² area difference, about +0.0501%). The STEP remains the exact geometry master. The provided files are not machine-ready code and do not validate manufacturability, superelastic response, or fatigue life.

For the candidate Robofil wire-EDM route, the most directly matched CAM product found is Camtek PEPS Wire EDM, which lists AC Robofil/AC Millennium technology and post support. Its 90-day trial requires vendor registration and a hardware-context license activation, and the current product requires Windows 10/11; this cloud workspace is Linux. See `robofil_profile_cam_job_sheet.md` for the source links and setup sequence. PEPS does not supply qualified NiTi process settings by itself; those and the STEP-vs-section-table mismatch remain unresolved.
