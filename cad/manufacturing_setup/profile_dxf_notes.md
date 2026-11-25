# Leaf 01 DXF profile notes

## Geometry and orientation

`U_leaf_spring_01_profile.dxf` is one closed lightweight polyline in millimetres. Its intended bounds are 94 mm along DXF X and 5 mm along DXF Y. It was extracted from `U_leaf_spring_01.step` after rotating the leaf 45° about global Y, then taking a section normal to its approximately 6 mm constant-width direction.

- DXF X = oriented leaf length coordinate + 47 mm.
- DXF Y = oriented section thickness coordinate + 10 mm.
- The stock width direction is orthogonal to the profile plane and measures 6.000000 mm in this solid.
- Thus the DXF coordinates are translated to start at (0,0); no scale factor is applied. The extracted STEP profile has a 5 mm maximum section dimension, while the separate `spring_strip.json` project sample reports end sections around 6.33 mm. Resolve that revision/axis discrepancy before ordering stock; the DXF traces the STEP, not the JSON table.

The STEP profile section is one closed wire. Three sections across the width have matching area/perimeter within the CAD kernel's precision. The section area is 110.343785 mm² and solid volume is 662.062712 mm³; volume divided by the 6 mm width is 110.343785 mm². The DXF polyline is a tessellated approximation of the STEP section: 147 vertices and polygon area 110.399071 mm², a +0.055286 mm² (+0.0501%) difference from the exact section. Curved details are approximated, so do not silently substitute it where exact arc/radius control is required; use STEP or a drawing with defined radii in that case.

## Process boundary

This is a contour geometry file, not a machining program. It does not specify a machine, controller, CAM project, stock chemistry/condition, datum, clamp/fixture, lead-in, start hole, wire offset, rough/trim passes, feeds, safety interlocks, or acceptance tolerances. Its use as wire-EDM input is only a candidate route for review and process qualification on the actual NiTi stock. It is not evidence that the part or process is approved.
