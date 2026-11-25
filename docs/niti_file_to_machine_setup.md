# NiTi spring: CAD to machine-input workflow

This is a self-service file-preparation guide for the U-module NiTi leaves. It prepares a clean, reviewable handoff. The geometry is ready; the actual Robofil NC program is not produced because the available cloud machine cannot run the required Windows CAM and the NiTi technology/setup data are absent.

## Files already in the project

- Editable source: [`UniDirectional_96.step`](../cad/modules/UniDirectional_96.step). It contains five solids: body solid 1 and four spring solids 2–5.
- Existing viewing mesh: [`U_leaf_springs.stl`](../cad/lanes_u4m2/guides_v2/U_leaf_springs.stl). It combines the four spring leaves for reference; don't use it as the CAM master.
- Dimension samples and leaf count: [`spring_strip.json`](../cad/lanes_u4m2/guides_v2/spring_strip.json).
- Separate mesh exports of each STEP solid: [`UniDirectional_96_part_01.stl` to `part_05.stl`](../cad/previews/u4m2/README.md). Parts 02–05 are the four individual leaves, but these are still triangulated meshes, not editable solids.
- Visual assembly reference: [`U_spring_assembly.png`](../cad/lanes_u4m2/guides_v2/U_spring_assembly.png).

The STEP is the source of truth for the geometry. A new section check shows leaf 01 is a constant-width profile: after a 45° reorientation, three cross-sections across the width match at 6.000 mm width, 94 × 5 mm profile envelope, and 110.343785 mm² area. The STEP solid volume divided by width matches that area. The previous blanket warning that a 2D profile cannot describe the ends was incorrect for this leaf orientation. The extracted [`leaf 01 DXF`](../cad/manufacturing_setup/U_leaf_spring_01_profile.dxf) captures the variable profile through the 6 mm blank width, with orientation and approximation limits described in [`DXF notes`](../cad/manufacturing_setup/profile_dxf_notes.md). This geometric fact does not establish that a specific process can safely cut the material.

There is a project-data mismatch to resolve: this STEP has a 5 mm maximum section, while `spring_strip.json` reports about 6.33 mm at the ends. This DXF follows the STEP. Do not machine until you have established that the STEP is the intended design revision.

## The pre-CAM handoff is already prepared

Download [`U_leaf_preCAM_handoff.zip`](../cad/manufacturing_setup/U_leaf_preCAM_handoff.zip). It contains four individual spring STEP files, a source/export geometry audit, the checked leaf 01 contour DXF and audit, orientation notes, a one-page handoff PDF, and the machine-preparation checklist. Each STEP export was checked to reopen as one valid solid and preserve source volume. The four pieces preserve their original assembly placements.

The authoritative source remains [`UniDirectional_96.step`](../cad/modules/UniDirectional_96.step), which includes the polymer body and four springs. Keep it unchanged. Do not use the combined spring STL as the CAM master.

## Make the machine input for the selected process

Choose the route only after confirming the exact machine and its approved workflow. PolyU's public facility listing identifies candidate equipment, but it does not establish NiTi approval or reveal each controller's required input format.

### If the selected process is wire EDM

Start from the isolated leaf STEP, [`leaf 01 DXF`](../cad/manufacturing_setup/U_leaf_spring_01_profile.dxf), and [`DXF notes`](../cad/manufacturing_setup/profile_dxf_notes.md). The DXF is a checked closed contour in millimetres with a 94 × 5 mm envelope. It represents the variable profile through the 6 mm width direction. Confirm the machine CAM accepts this DXF version and intended setup, then define blank, datum, workholding, entry/start-hole method, lead-ins, wire compensation, rough/trim passes, and edge inspection for fatigue service. Those process-specific details are not encoded in DXF.

**CAM software target:** Camtek PEPS Wire EDM is the best match found for the listed Agie Charmilles Robofil 240SL. The official PEPS page lists Robofil/AC Millennium post and technology-database support, automatic start-hole/threading, offsets, simulation, and NC output. The workflow is: import DXF/STEP → define 6 mm-thick billet and XY cutting plane → select the exact Robofil control/post → select the certified NiTi/wire technology record → set datum/fixture and entry/start hole → choose rough/trim passes and compensation → simulate and check slug retention → post NC. Follow the detailed [`Robofil CAM job sheet`](../cad/manufacturing_setup/robofil_profile_cam_job_sheet.md).

Camtek's trial is 90 days but requires a contact-form request and hardware-context license activation. PEPS 2022–2026 requires Windows 10 64-bit; Windows 11 is recommended. This cloud environment runs Linux, so PEPS cannot be installed/run here. Official pages: [wire-EDM features](https://www.camtek.de/en/wire-edm), [trial and activation](https://www.camtek.de/en/peps/peps-testversion.html), and [system requirements](https://www.camtek.de/en/peps/peps-technical-specifications.html). The generic FreeCAD `wedm_post.py` is not a Robofil post; do not use its output on that machine.

### If the selected process is waterjet or approved metallic laser

The same contour is geometric input for a profile-cut process only if the selected process supports the 6 mm-wide stock and its material/edge requirements. Do not manually offset for kerf unless its confirmed workflow explicitly requires it; compensation belongs in CAM. The published metallic laser list names titanium but not NiTi, so confirm explicit approval for the exact alloy and stock condition. Waterjet still needs a verified plan for support and edge quality.

### If the selected process is CNC milling

Use the isolated native STEP, drawing, stock dimensions, datum/orientation sketch, and workholding concept as the CAM inputs. Create operations in a CAM system only after identifying the exact machine/controller and its correct postprocessor. NiTi cutting data, tools, fixture, sequencing, and acceptable surface finish must be established for the actual material lot. Simulate stock removal and collisions, then inspect the posted file in the controller's supported viewer/backplot. Do not run generic or unverified NC code.

## Before making a real part

- Resolve what the 6.33 mm ends represent and whether the spring is cut from formed stock, machined from thicker stock, or made by another approved route. Confirm the section dimensions in the native solid; the listed sections are sparse samples, not a complete thickness map.
- Make a representative coupon with the same material lot, thickness, process, surface finish and transitions. Record measured dimensions and inspect edge defects under magnification.
- Test spring force/recovery and cycling in a guarded fixture before making all 16 leaves. File preparation and CAD checks cannot establish fatigue life or material condition.
- Keep source STEP, DXF, PDF drawing, CAM project, posted file, setup sheet, and coupon results together under one revision. Label the NC file with the exact machine/controller and postprocessor version.

## Deliverables checklist

| File | Purpose | Can prepare before machine selection? |
|---|---|---|
| Original assembly STEP | Traceable source | Yes; already exists |
| Isolated one-leaf STEP | Neutral solid geometry | Yes |
| Dimensioned PDF drawing | Defines dimensions, material and unknowns | Yes |
| One-leaf 1:1 DXF | Profile input for 2D cutting routes | Yes, as a draft; confirm accepted DXF version and thickness strategy |
| CAM project + simulation | Milling/route-specific setup | Only after exact machine, stock, fixtures and tool library are known |
| Posted NC/controller file | Machine code | Only after selecting and validating the exact controller/postprocessor |
| Coupon inspection/cycle record | Evidence of process suitability | After a test specimen is made |

The concrete geometry preparation is done: isolated leaf STEP exports, the checked candidate DXF, geometry audit, and Robofil setup sheet are ready. The remaining CAM needs a Windows PEPS installation/license, the exact PolyU Robofil control/post configuration, a qualified NiTi technology table for the actual wire/stock, a resolved STEP revision, and a complete datum/fixture/start-hole/cut sequence. Those are concrete missing CAM inputs; a generic G-code file would be an unsafe substitute.
