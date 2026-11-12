# M module with 1.8 mm NiTi backbone: build and test plan

2026-11-08 · for the U4+M2 front · companion to `README.md` in this folder

This plan sets out how to build and test the M module with a central backbone. The simulations in this folder assume the properties below. The tests either confirm them or replace them with measured values, which then go back into the models. All target values are simulation-derived and must be agreed before testing.

## 1. Specimen definition

| Item | Specification |
|---|---|
| Base module | Current PA12 M module, 96 mm long, 63 mm outer diameter, tendon guides at 24 mm radius |
| Backbone | Superelastic NiTi wire, Ø1.8 mm, straight-annealed. Record the supplier's Af and lot. |
| Rod mounting | The rod carries axial load into both end disks, for example with a crimp sleeve, set-screw collar or bonded ferrule. The joint must not slip at 2 × 124 N. |
| Lateral guides | Intermediate guide disks with a sliding fit around the rod, spaced at or below the buckling limit (§4.4). **Baseline spacing 24 mm**, which puts 3 intermediate guides in a 96 mm module. |
| Specimens | At least 3 of each: (a) M without rod, the control; (b) M with rod; (c) a 2-module M2 chain with rod for the bending and tendon tests. |
| Coupons | 5 rod coupons from the same NiTi lot, about 150 mm long |

## 2. Properties assumed in the simulations

| Property | M without rod (database) | M with rod (E = 40 GPa) | M with rod (E = 75 GPa) | Minimum needed (EA/EI sweep) |
|---|---:|---:|---:|---:|
| EA, N | 166.7 | 101,954 | 191,018 | ≥ 833, at EI ≥ 1.25× |
| EI, N·m² (both planes) | 0.0441 | 0.0647 | 0.0828 | ≥ 0.055, at EA ≥ 5× |
| Module torsion, N·m/rad | 0.437 | 0.599 | 0.740 | not limiting |
| Added mass per module, g | 0 | 1.58 | 1.58 | — |

With the rod, U4+M2 passes every straightness check at 15°, 20° and 25° using anchors [4,5,6]. It also reaches 165–180° of yaw with the head held within ±5° of the base pitch (see README). The single most important measurement is **EI, in both planes**. The required EA is easily met, but EI decides the straightness margin. At ×1.47 (E = 40 GPa) that margin is small.

## 3. Loads to cover

From the 8-cell simulation results (U4+M2 with rod):

| Case | Tendon force passing through M | Note |
|---|---:|---|
| Active straightening, anchors [4,5,6] | about 30 N (sets at 5 and 6) | Top ropes only |
| Held-elevation yaw, 20°, E = 40 GPa | up to about 81 N (four ropes of the set at 6) | Allocation found by the optimizer, not minimised |
| Held-elevation yaw, 25°, E = 40 GPa | up to about 73 N through M; 247 N peak rope in U | At the edge of the 250 N bound |
| **Design compression for the rod and guides** | **124 N × 2 = 248 N** | Margin over the straightening case total |

## 4. Tests

### 4.1 Rod material (coupons)
- **Method:** uniaxial tension to 6% strain, then unload, in the style of ASTM F2516. Run at 20 °C and at the expected lowest and highest operating temperatures. Also measure Af by DSC (ASTM F2004) or bend and free recovery (ASTM F2082).
- **Outputs:** austenite and martensite moduli, upper and lower plateau stress, residual strain, Af.
- **Use:** if Af is above the operating temperature, the rod works in its martensite or mixed state, so use the E = 40 GPa case or the measured value.

### 4.2 Module axial stiffness (specimens a and b)
- **Method:** in a universal test machine, clamp the end disks with the specimen guided against global buckling. Cycle 0 → +150 N (tension) and 0 → −150 N (compression), 5 cycles each, at 1 mm/min. Measure axial displacement with an LVDT or DIC across the end disks, not from the crosshead. At 100 N the expected shortening of specimen (b) is only about 0.09 mm, which needs a resolution of 5 µm or better.
- **Outputs:** EA in tension and compression, hysteresis, slip at the rod joint, and any nonlinearity.
- **Pass:** EA ≥ 833 N in both directions, and no permanent slip after cycling at 150 N.
- **Control (a):** confirms or corrects the database value of 166.7 N. If it differs, also re-run the EA/EI sweep with the measured value.

### 4.3 Module bending stiffness, both planes (specimens a and b)
- **Method:** cantilever test with one end disk clamped. Apply tip loads of 0.1–0.6 N in 0.1 N steps and measure tip deflection, for example with a laser or DIC. EI = F·L³/(3·δ). At 0.5 N, the expected δ is 3.3 mm for (a), 2.3 mm for (b) at E = 40 GPa, and 1.8 mm at E = 75 GPa.
- Repeat at 0°, 90° and 45° orientation to confirm the stiffness is the same in all directions, and repeat with the specimen flipped to check symmetry.
- **Pass:** EI ≥ 0.055 N·m² in every plane. Any value below 0.0647 N·m² reduces the straightness margin and must be fed back into the model.

### 4.4 Rod buckling at the guide spacing (specimen b)
- Pinned Euler buckling load of the rod alone (P = π²EI/L²) for different guide spacings:

| Guide spacing, mm | 16 | 20 | 24 | 28 | 32 | 40 | 48 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P at E = 40 GPa, N | 795 | 509 | 353 | 259 | 199 | 127 | 88 |
| P at E = 75 GPa, N | 1490 | 954 | 662 | 487 | 372 | 238 | 166 |

- **Method:** build variants with 20, 24 and 32 mm spacing. Compress through the rod's end attachment until it buckles or reaches 300 N. Identify buckling from the load–displacement knee, with video or DIC of the rod between guides.
- **Pass:** no buckling at or below 248 N for the chosen spacing. **Expected result:** 24 mm passes at both moduli, and 32 mm fails at E = 40 GPa.

### 4.5 Torsion (specimen b; optional)
- Twist one end disk ±10° and measure torque. Expected about 0.60–0.74 N·m/rad. This is not limiting in the simulations and is recorded to update the model.

### 4.6 Tendon-driven bending (specimen c, M2 chain with rod)
- **Method:** mount the base horizontally with no head mass. Pull one top rope at the M2 tip in steps from 0 to 60 N, and measure tip angle and curvature by camera. Compare with the model's moment arm of 24 mm and the EI measured in §4.3. Repeat for each of the 4 ropes.
- **Outputs:** curvature against tension, friction hysteresis (loading against unloading), and tendon-guide wear.
- **Pass:** curvature within ±15% of the model prediction made with the measured EI.

### 4.7 Bending fatigue (specimen c)
- **Method:** cycle a 180° bend across the M2 section, which gives a rod surface strain of about 1.5%, for 10⁴ cycles. Inspect the rod joints, the guides and the PA12 for cracking, and measure EI again afterwards.
- **Pass:** EI changes by less than 10%, with no joint slip and no cracks.

### 4.8 Integrated U4+M2 check (after 4.1–4.7 pass)
- **Setup:** install at 20° with a 500 g dummy head and anchors [4,5,6]. Apply the planar straightening tensions from `results/planar_summary.json` (E = 40 GPa, 20°: 91.5 / 21.4 / 8.5 N on the top ropes).
- **Measure:** shape by photogrammetry. Compare maximum offset (≤ 10 mm), tangent error (≤ 5°) and head elevation with the simulation.
- **Then:** test the held-elevation yaw (20 ± 5°), using the stored tension allocation as a starting point.

## 5. Data return

For each test, record the specimen ID, NiTi lot, temperature, raw force and displacement files, and the reduced EA, EI and torsion values. Place the measured values in a copy of `module_stiffness.sqlite3` as a new module entry, for example `middle_stiffness_pa12_niti18`. Do not overwrite the existing M entry. Re-run `backbone_planar.py` and `backbone_steering.py` with that entry.
