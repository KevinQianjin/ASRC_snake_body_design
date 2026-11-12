# Model data: U4+M2 front with 1.8 mm NiTi backbone

Generated 2026-11-11 from the model objects by `../export_model_data.py`. Full data: [`model_data.json`](model_data.json). Per-module table: [`module_properties.csv`](module_properties.csv). All studies dated 8–10 November 2026 use these inputs.

## 1. Geometry

| Item | Value |
|---|---|
| Configuration | U4+M2. Modules 1–4 are U (PA12 + NiTi); modules 5–6 are M (PA12). Numbered from the base. |
| Module length | 96 mm each, **continuous**. No separate pin joint or gap is modelled. |
| Flexible length | 576 mm |
| Interface | 20 mm, rigid and massless, from the clamp to module 1 |
| Nominal front length | 596 mm |
| Outer diameter / collision envelope | 63 mm (radius 31.5 mm) |
| Tendon radius | 24 mm from the axis. Ropes are up (+Y), right (+Z), down (−Y) and left (−Z); world X is forward and Y is up. |
| Rope routing | Each rope passes through every module end disk up to its anchor, as straight chords between disks. Distal ropes therefore also compress the proximal modules. |

## 2. Module properties used by the solver

Values are structural rigidities of a whole module from `module_stiffness.sqlite3`, plus the rod. They are not material moduli.

| Module | Type | Bare mass, g | Rope mass, g | EA, N | EI vertical, N·m² | EI horizontal, N·m² | Torsion T/θ, N·m/rad |
|---|---|---:|---:|---:|---:|---:|---:|
| 1–4 | U (PA12 + NiTi) | 37.990 | 4.162 | 128,122 | 22.2052 | 1.67184 | 4.70037 |
| 5 | M, no rod (database) | 23.948 | 2.775 | 166.694 | 0.0441178 | 0.0441178 | 0.437396 |
| 6 | M, no rod (database) | 23.948 | 1.387 | 166.694 | 0.0441178 | 0.0441178 | 0.437396 |
| 5–6 | M + rod, **E = 40 GPa** (lead case) | 25.524 | as above | 101,954 | 0.0647298 | 0.0647298 | 0.598831 |
| 5–6 | M + rod, E = 75 GPa | 25.524 | as above | 191,018 | 0.0827653 | 0.0827653 | 0.740086 |

- U vertical EI resists gravity; U horizontal EI is about 13 times lower. M EI is the same in every direction.
- **Torsion:** the database value is the whole-module spring T/θ. The rod model uses T/θ × 0.096 m (U 0.4512, M 0.0420, M + rod 0.0575 / 0.0710 N·m²), which keeps module twist energy the same at any mesh.
- **Rope mass:** 4 ropes per anchor set routed through the module. With anchors [4,5,6], 12 ropes pass through U modules, 8 through M5 and 4 through M6.
- **Totals:** modules 199.9 g (no rod) or 203.0 g (with rod), plus ropes inside the front 20.8 g. The front is 223.8 g with the rod, excluding the head.

## 3. NiTi backbone rod

| Item | Value |
|---|---|
| Layout | One central Ø1.8 mm rod per M module, running the **full 96 mm** module length. It is fixed to both M end disks, guided laterally, and bends with the module, so its stiffness adds in parallel. |
| Density | 6450 kg/m³ → 1.576 g per module |
| Modulus | 40 GPa (martensite or low-modulus lower bound, lead case) and 75 GPa (austenite) |
| Rod EA | 101,788 N (E = 40 GPa), 190,852 N (E = 75 GPa) |
| Rod EI | 0.020612 N·m² (40 GPa), 0.038647 N·m² (75 GPa) |
| Rod torsion GJ/L | 0.16143 / 0.30269 N·m/rad (ν = 0.33) |
| Not included | Rod end fittings, guide and adhesive mass; NiTi phase transformation and hysteresis |

## 4. Payload

- **Head:** 500 g point mass at the tip of module 6, with no offset moment or rotary inertia.
- **Collision envelope:** 63 mm, which is provisional because the real head CAD is not available.
- **Gravity:** 9.81 m/s².

## 5. Tendons and winches

| Item | Value |
|---|---|
| Rope | PA6 solid-stock surrogate, Ø2 mm, E = 3.3 GPa, density 1150 kg/m³, **not calibrated** for a real braided rope |
| Rope EA / linear density | 10,367 N / 3.613 g/m |
| Lead anchor layout | Sets at modules **[4, 5, 6]**, each with 4 ropes (up, right, down, left) |
| Other layouts compared | [6], [4, 6], [2, 4, 6] |
| Pretension | **at least 1 N on every rope**, needed for 3D lateral stability |
| Numerical tension bounds | 1–250 N per rope (search limit, not a rating) |
| Friction, rope bending stiffness | none |
| Winch model | Fixed winch, tension-only linear rope: T = EA·max(0, L + L_free − R)/R. L is the routed length inside the front, L_free = 1 m of free rope, and R is the unstretched length set by the winch. Effective stiffness is about 6.5 N/mm at a total of about 1.6 m. |

## 6. Installation and tank

| Item | Value |
|---|---|
| Installation pitch | 15°, 20° and 25° studied; **20° recommended** |
| Insertion point | Length 449 mm, height 98.6 mm (cavity floor), width plane 648 mm |
| Clamp position s | Distance of the base clamp along the axis past the insertion point. Steering is recommended at **s = 0–30 mm**. |
| Tank model | All 362 solids of the tank subtree in `cad/tank/tank-v2.step`, 461,524 triangles at 0.5 mm deflection. Coordinates: length = −oldX, height = oldY, width = −oldZ (mm). |

## 7. Numerical model and acceptance

| Item | Value |
|---|---|
| Rod model | Extensible rod. **Planar:** angle and axial strain per cell. **Spatial:** finite-rotation Kirchhoff rod with twist, two bending components and axial strain per cell. |
| Mesh | 2–4 cells per module for searches, **8 reported**, 16 for mesh checks; 4-point Gauss-Legendre per cell |
| Loads | Gravity and all ropes act together |
| Stability | Minimum eigenvalue of the energy Hessian including fixed-winch rope stiffness (1 m free rope) must be ≥ 0 |
| Strain | 5% diagnostic; coarse search bounds ±4.75% (spatial) and ±4.85% (planar) |
| Geometry | Local bend radius ≥ 31.5 mm (0.98 margin); 63 mm capsule self-clearance for segments ≥ 126 mm apart |
| Straightness | Offset ≤ 10 mm, tangent error ≤ 5°, axial projection ≥ 95%, strain ≤ 5%, stable |
| Held elevation | World head elevation equal to the installation pitch (exact, or within ±5°) |
| Angle search cap | 180° |

The 5% strain, 250 N and 180° values are numerical diagnostics or search bounds, not hardware ratings.
