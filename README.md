# ASRC Project Index

[GitHub repository](https://github.com/KevinQianjin/ASRC_snake_body_design) · Updated 6 November 2026

## Reports

- [Latest report — 6 November 2026](https://github.com/KevinQianjin/ASRC_snake_body_design/blob/main/Report_2026_11_06.pdf): design concept, simulation findings, unresolved issues and development worklist.
- [Previous report — 5 November 2026](https://github.com/KevinQianjin/ASRC_snake_body_design/blob/main/Report_2026_11_05.pdf): earlier design and analysis.

## Latest studies and key results

### Active straightening and tank entry

[Study README and files](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106)

Compares U4+M2, U6+M3 and U8+M4 using 63 mm modules and a 24 mm tendon guide radius. The representative U4+M2 straightening solution reaches 4.21 mm axis deviation and 4.75 degrees tangent error, but requires 17.26% maximum axial strain. Near straight geometry has not yet been achieved together with the 5% strain diagnostic and stability screens.

![Active front shapes](https://raw.githubusercontent.com/KevinQianjin/ASRC_snake_body_design/main/ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106/results/active_front_shapes.png)

*Loaded front shapes and the tradeoff between straightening and axial compression.*

![Front only entry screening](https://raw.githubusercontent.com/KevinQianjin/ASRC_snake_body_design/main/ASRC_kevin/telescopic_planar_study/stiffness_63mm_20261106/results/front_only_entry_screen.png)

*Entry screening of actively tensioned front shapes. Passing paths remain high strain and do not establish complete 3D deployment.*

### Spatial steering and tendon forces

[Study README and files](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/telescopic_planar_study/steering_63mm_20261106)

Reports horizontal and vertical steering, individual tendon tensions and mesh checks. U4+M2 reaches approximately 179.42 degrees yaw in a low strain candidate, but its world head elevation is −65.67 degrees. No tested configuration produced a low strain candidate holding world elevation at 20 ± 5 degrees.

![Steering angles and tendon forces](https://raw.githubusercontent.com/KevinQianjin/ASRC_snake_body_design/main/ASRC_kevin/telescopic_planar_study/steering_63mm_20261106/results/steering_angle_and_pull.png)

*Selected steering endpoints and corresponding peak individual tendon forces.*

![Heading and elevation](https://raw.githubusercontent.com/KevinQianjin/ASRC_snake_body_design/main/ASRC_kevin/telescopic_planar_study/steering_63mm_20261106/results/heading_and_elevation.png)

*Yaw must be interpreted together with head elevation; a large yaw value does not establish useful horizontal inspection coverage.*

The 5% strain threshold, 250 N tendon cap and 180 degree angle cap are numerical diagnostics or search bounds, not validated hardware ratings.

## Geometry and input data

- [Telescopic rear and tank geometry study](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/telescopic_planar_study): tank sections, rear beam calculations and deployment screening. Its top-level README includes earlier geometry assumptions.
- [Module stiffness database](https://github.com/KevinQianjin/ASRC_snake_body_design/blob/main/ASRC_kevin/module_stiffness.sqlite3): module mass, EA, EI and torsional stiffness. Use each study's saved input snapshot when reproducing its results.

## Earlier studies

- [H8U12 rear and 500 g head](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/h8u12_front5to8_payload500g): comparison of 5–8 front modules.
- [Four tendon inverse study](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/four_rope_inverse_5_to_11): methods, frozen inputs and results.
- [Front module count sweep](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/ASRC_kevin/front_sweep_5_to_11): comparison of 5–11 front modules.
- [Reach and extension screening](https://github.com/KevinQianjin/ASRC_snake_body_design/tree/main/reach_extension_results): earlier passive reach study with different dimensional assumptions.

Start with the two studies dated 20261106. Earlier results use different geometry or material assumptions and should not be combined directly with the latest baseline.
