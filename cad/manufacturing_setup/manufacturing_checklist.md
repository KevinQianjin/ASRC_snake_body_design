# NiTi leaf: self-guided file-to-machine checklist

## 1. What is ready now

- Four exact single-solid STEP leaves, preserving the original assembly placements.
- One DXF section profile at 1:1 scale for leaf 01, suitable as candidate geometry input for a process that cuts the leaf profile through a constant-width blank.
- A geometric verification: three sections across the width agree within CAD-kernel precision; the profile area is about 110.3438 mm² and the 6 mm width times that area matches the STEP volume.

The DXF is **not** machine code, a CAM project, proof of process suitability, or a released drawing. The confirmed contour orientation is X-DXF = leaf length (94 mm), Y-DXF = profile thickness (0–5 mm); stock width is along the leaf's local width direction (6 mm). Review the notes and drawing before use.

**Clarify the section-table axes:** in the intended oriented STEP frame, the end section is 6 × 5 mm with area 30 mm². `spring_strip.json` lists 7.05 × 6.33 mm end extents but also area 30 mm², so those extents are not a rectangular stock-section width/thickness pair. This does not establish a revision mismatch. The DXF traces the STEP within the recorded polyline approximation; resolve the table's coordinate convention before using those extent values in a stock drawing.

## 2. Choose the process yourself

For the variable profile, a 2D profile cut through a 6 mm-wide blank is geometrically plausible. Wire EDM is a candidate because NiTi is conductive, but material/process suitability and surface integrity must be confirmed for the exact alloy/condition. The DXF can serve as contour input only if the machine process can accept that profile, stock width, start/lead-in strategy, and workholding.

Alternatively, 3D milling can use a single-solid STEP as CAM input; it needs a complete stock, datum, setup, tools, collision checking, and a postprocessor for the exact machine/controller. Laser and waterjet should not be assumed suitable from a general material listing.

## 3. Resolve missing design and material information

Before buying stock or making a spring, personally establish from the design and supplier records:

1. Which of the four leaves is the manufacturing master and which assembly features establish its datums.
2. NiTi grade/composition, transformation temperatures, superelastic or shape-set condition, stock certification, and allowable material direction.
3. Final profile tolerances, edge condition, burr/notch limit, surface finish, transition radii, and quantity.
4. Whether this exact CAD contour is the finished profile or requires finishing allowance; do not add an allowance without specifying which side and how it is compensated.
5. How the enlarged ends are held and whether cutting changes the required shape-setting state.

The STEP and DXF do not contain these requirements.

## 4. Convert the DXF into the machine's required input

Use `robofil_profile_cam_job_sheet.md` as the geometry-specific setup record for the candidate Robofil wire-EDM route. It records the derived profile-plane axes, 94 × 5 mm contour bounds, 6 mm orthogonal stock width, zero nominal taper, and the CAM values that still require machine/material data.

1. Open `U_leaf_spring_01_profile.dxf` in the CAD/CAM software for the selected process. Confirm drawing units are millimetres and the measured bounding box is 94 × 5 mm.
2. If using wire EDM, create a process CAM job for the exact machine/controller. Define blank thickness/width as 6 mm along the documented width direction, workholding, profile datum, start hole or entry method, lead-ins, rough/trim passes, wire compensation, and cut sequence. These must come from the machine documentation and the chosen material/process limits; they are not encoded in DXF.
3. Simulate the full cut and inspect the resulting profile, side compensation, entry/exit, scrap behavior, stock retention, and machine travel. Post only with the exact supported postprocessor.
4. If using 3D milling, use STEP instead, define the complete setup and machining operations, simulate, then post for the exact controller. Do not convert DXF to generic G-code.
5. Inspect the posted file in the controller's supported viewer/backplot, verify units, offsets, limits, and dry-run procedure from the machine manual. Never run a program that has not been verified against the actual machine.

I cannot create a valid machine program from the files alone: the process selection, material state, stock setup, cut strategy, machine CAM/post, and machine-specific safety conditions are absent. The deliverable here is a checked manufacturing geometry input, not NC code.

## 5. Trial and inspect

Cut a representative coupon with the same stock, thin-section thickness, transition radii, process, and surface finishing. Inspect under magnification for burrs, notches, cracks, edge damage, recast/heat effects where relevant, and unintended thinning. Measure critical sections against the approved drawing. Run a guarded force/deflection and recovery check followed by a documented cyclic screen; a short screen does not establish service life.

## Handoff artifacts expected before production

- Approved drawing with material/condition, datums, tolerances, edge finish, and quantity.
- Confirmed stock certificate and process parameters.
- Native CAM project and simulation for the selected machine.
- Posted NC program verified for the exact controller and setup.
- Coupon/first-article inspection and cyclic-screening record.
