# M module with 1.8 mm NiTi backbone: straightening and steering

2026-11-08 · 63 mm · 24 mm tendon radius · 500 g head · follow-up to `../m_axial_sweep_20261108`

This study adds a central Ø1.8 mm NiTi rod to every M module, including its mass, and re-runs two of the 2026-11-06 studies:

- the planar active-straightening study (U4+M2, U6+M3 and U8+M4 at 15°, 20° and 25°);
- the spatial steering and held-elevation study (U4+M2).

The physical build and test plan is in [`M_BACKBONE_TEST_PLAN.md`](M_BACKBONE_TEST_PLAN.md).

![Backbone results](results/backbone_results.png)

## Rod model

| | M (database) | + rod, E = 40 GPa | + rod, E = 75 GPa |
|---|---:|---:|---:|
| EA, N | 166.7 | 101,954 | 191,018 |
| EI, N·m² (both planes) | 0.0441 | 0.0647 | 0.0828 |
| Module torsion, N·m/rad | 0.437 | 0.599 | 0.740 |
| Mass per M module, g | 23.948 | 25.524 | 25.524 |

- The rod is modelled as central, bonded to the module end disks and bending with the module, so its stiffness adds to the module's.
- E = 40 GPa represents a martensite or low-modulus lower bound; 75 GPa represents austenite. Torsion uses ν = 0.33.
- Rod end fittings and guides are not included in the mass. Neither are friction, NiTi phase transformation or contact.
- All other inputs are identical to the 2026-11-06 studies. The kernels are reused through `backbone.py` and are not modified.

## 1. Planar active straightening (`backbone_planar.py`)

The best stable result at ≤5% strain at 8 cells per module is shown below. "Pass" means all straightness checks pass: offset ≤ 10 mm, tangent error ≤ 5°, axial projection ≥ 95%, strain ≤ 5%, and stable.

| Configuration | Pitch | Current M | Rod, E = 40 GPa | Rod, E = 75 GPa |
|---|---:|---|---|---|
| U4+M2 | 15° | 89.7 mm / 57.5° — fail | **1.8 mm / 4.1° / 0.10% — pass** | **1.2 mm / 3.2° — pass** |
| U4+M2 | 20° | 94.7 mm / 61.3° — fail | **1.7 mm / 4.0° / 0.10% — pass** | **1.2 mm / 3.1° — pass** |
| U4+M2 | 25° | 99.1 mm / 64.9° — fail | **1.7 mm / 3.7° / 0.09% — pass** | **1.2 mm / 3.0° — pass** |
| U6+M3 | 20° | 176.8 mm / 87.2° — fail | 10.5 mm / 15.1° — fail | 9.6 mm / 10.5° — fail |
| U8+M4 | 20° | 278.0 mm / 98.1° — fail | 135.2 mm / 102.5° — fail | 19.2 mm / 29.9° — fail |

- **U4+M2 passes at all three pitches**, with anchors [4,5,6]. At 20° and E = 40 GPa, the top-rope tensions are 91.5, 21.4 and 8.5 N.
- **U6+M3 and U8+M4 do not pass** with three or fewer anchor sets. A search of every three-set layout with one set at the head (28 for U6+M3 and 55 for U8+M4, each at both moduli, 20°, `--all-three`) found no passing case. The closest was U6+M3 with anchors [7,8,9], at 5.04° tangent error but a 24.5 mm offset. Their M sections are longer, and gravity bending between anchor disks grows with the length of each span.
- The current-M (no rod) column reproduces the 2026-11-06 report values, for example 94.68 mm at 20° for U4+M2.

## 2. Spatial steering and held elevation, U4+M2 (`backbone_steering.py`, `refine_backbone_steering.py`)

The procedure, bounds and acceptance rules follow 2026-11-06:

- tendon tension 0–250 N;
- coarse strain bound ±4.75%;
- 180° angle search cap;
- geometry, capsule and fixed-winch stability checks.

Candidates start at 2 cells per module and are refined to 4 and then 8. A candidate is reported only if it passes at 8 cells. "Held elevation" means yaw with the world head elevation within base pitch ± 5°.

| Variant | Pitch | Free yaw (elevation, peak N) | **Yaw with held elevation** (elevation, peak N) | Up / down |
|---|---:|---|---|---|
| Current M | 20° | 179.4° (−65.7°, 146.5 N) | **none found** | −56.6° / 113.8° |
| Rod, E = 40 GPa | 15° | 180°* (−33.3°, 24.4 N) | **165°** (+10.0°, 56.5 N)† | 180°* / 180°* |
| Rod, E = 40 GPa | 20° | 180°* (−36.3°, 22.2 N) | **180°*** (+15.0°, 98.3 N) | 180°* / 180°* |
| Rod, E = 40 GPa | 25° | 180°* (−39.5°, 21.1 N) | **180°*** (+30.0°, 246.9 N) | 180°* / 180°* |
| Rod, E = 75 GPa | 20° | 180°* (−36.6°, 29.3 N) | **180°*** (+22.3°, 46.2 N) | 180°* / 180°* |

\* Reaches the 180° search cap. This is not a demonstrated mechanical limit.
† At 15°, no 180° held state survived the 8-cell check: it was unstable at +10° elevation. The largest lower cap that passed was 165°.

- The no-rod control reproduces the 2026-11-06 results exactly at 8 cells: 179.42°, −65.67°, 146.48 N, and no held-elevation solution.
- **With the rod, the head can be swept through the full ±180° yaw search range while held near the working elevation**, at well under 1% strain. This was the main unsolved problem (priority 2) in the 2026-11-06 report.
- Strain is no longer limiting: it stays at or below 0.62% everywhere. The constraints that now decide the result are tension, stability and the elevation band.
- **The tensions are one allocation found by the optimizer, not minimum-force solutions.** The 8-cell re-optimization maximizes angle only, so tensions can rise during refinement: at 20° and E = 40 GPa, the 2-cell candidates needed about 33 N, while the 8-cell result needs 98 N. The 25° held case sits near the 250 N bound and at the edge of the elevation band. Minimum-tension allocation is a recommended next step.
- "Up 180° at elevation = −pitch" means the head has turned over the top and points back. Whether the intermediate postures form a continuous controllable path is not established.
- Full tension sets for every endpoint are in `results/steering_summary_8cell.json`. Each row is one anchor set, in the order [up, right, down, left], in N.

## 3. Tank entry screen with the straight low-strain shape (`entry_screen.py`, 2026-11-09)

This re-runs the 2026-11-06 front-only entry screen, reusing `path_check()` from `../stiffness_63mm_20261106/postprocess.py` unchanged. The best stable shape at ≤5% strain is held at fixed tension and translated along the installation axis through the bottom opening at x = 449 mm. The run starts with the whole front and head outside the tank and steps 4 mm, then 2 mm. Pass requires:

- the 63 mm envelope stays at least 5 mm clear of the five saved CAD width sections (628–668 mm) along the whole path;
- the front ends fully inside the sampled cavity.

Passing shapes are re-solved at 16 cells per module with the same tensions and re-checked. As a control, the 2026-11-06 U4+M2 20° shape-only result (62.06 mm) is reproduced exactly.

| U4+M2 | Pitch | Strain | Min gap, 8 cell | Min gap, 16 cell | Final clamp s | Result |
|---|---:|---:|---:|---:|---:|---|
| Current M | 15° / 20° / 25° | 4.96% | hits the tank at s ≈ −336 mm | — | — | fail |
| Rod, E = 40 GPa | 15° | 0.10% | 44.5 mm | 44.3 mm | 114 mm | **pass** |
| Rod, E = 40 GPa | 20° | 0.10% | 64.3 mm | 64.0 mm | 90 mm | **pass** |
| Rod, E = 40 GPa | 25° | 0.09% | 16.6 mm | 16.9 mm | 78 mm | **pass** (tight) |
| Rod, E = 75 GPa | 15° / 20° / 25° | 0.09% | 44.6 / 64.6 / 16.1 mm | 44.5 / 64.4 / 16.2 mm | 114 / 90 / 78 mm | **pass** |

- **This is the first low-strain shape to pass the entry screen.** On 2026-11-06, only shapes at 17% or more strain passed; every low-strain shape sagged into the tank.
- The margins match the 2026-11-06 high-strain straight shapes (44 / 62 / 20 mm), so the rod gives the same geometry at about 1/170 of the strain.
- **Where the limit is:**
  - At 15° and 20°, the tightest point is the distal M section passing internal structure just after the head enters, at clamp s ≈ −355 mm.
  - At 25°, crossing the opening is comfortable (about 50 mm), but at the final placement the head is only about 19 mm below the roof. 20° remains the preferred installation angle.
- U6+M3 with the E = 75 GPa rod passes only at 15° (40 mm). It fails at 20° and 25°, and every U8+M4 case fails. U4+M2 remains the development length.

![Entry screen](results/entry_screen.png)

**Limits, unchanged from 2026-11-06:**

- Planar sweep of a fixed shape with a translating clamp.
- The five width planes do not cover the full 616.5–679.5 mm band of a 63 mm front.
- Not included: sleeve or guide contact, rear storage, rope take-up, retraction, tension changes during feed, and real head CAD.

This is a geometric screen, not a validated deployment.

## Conclusions

1. A Ø1.8 mm NiTi backbone in M resolves both blocking problems for **U4+M2** in the simulation: straightening within the strain limit, and loaded head recovery at the working elevation. This holds at 15–25° and for both moduli. The straight low-strain shape also passes the front-only tank entry screen at 15–25° (2026-11-09).
2. **U4+M2 remains the only viable length** with three or fewer anchor sets. Longer fronts would need more anchor sets inside M, or a stiffer M again.
3. The conclusions now depend on the rod's real EI, its end attachment and its buckling between guides. Run the physical tests in `M_BACKBONE_TEST_PLAN.md` before any further simulation refinement.

## Limitations

- Linear-elastic constant EA and EI.
- Frictionless tendons.
- No contact, NiTi hysteresis or fatigue.
- Local optimization only.
- Free-space steering with no tank geometry.
- The rod is assumed perfectly bonded and guided.

The 5% strain value, 250 N bound and 180° cap are numerical diagnostics, not hardware ratings.

## Reproduction

The commands below take about 10 minutes in total on 4 cores.

```bash
python backbone_planar.py --u 4 --m 2
python backbone_planar.py --u 6 --m 3
python backbone_planar.py --u 8 --m 4
python backbone_planar.py --u 6 --m 3 --all-three --pitches 20 --variants niti18_E40 niti18_E75
python backbone_planar.py --u 8 --m 4 --all-three --pitches 20 --variants niti18_E40 niti18_E75
python summarize_planar.py
python backbone_steering.py validate
python backbone_steering.py run --variant niti18_E40 --pitch 20
# repeat for: --variant niti18_E75 --pitch 20 ; --variant none --pitch 20 ; --variant niti18_E40 --pitch 15 / 25
python refine_backbone_steering.py --variant niti18_E40 --pitch 20
# same set; for 15 deg add: --top 4 --maxiter8 150
python plot_backbone.py
python entry_screen.py   # tank entry screen (needs ../results/cad_sections.json)
python plot_entry.py
```

## 中文摘要

- 在每個M模組中心加Ø1.8 mm NiTi棒（計入質量）後，U4+M2在15°/20°/25°均通過所有拉直檢查。偏差約1–2 mm，切線3–4°，應變約0.1%，錨點[4,5,6]。
- U6+M3及U8+M4在不超過三組錨點時仍未通過，已窮舉全部三組錨點佈置。
- 空間轉向（8單元/節確認）：頭部保持在基準仰角±5°內時，20°、E=40或75 GPa可達180°搜尋上限偏航，峰值拉索46–98 N。15°可達165°。原設計在此條件下無解。
- 張力為優化器找到的一組分配，非最小力解。180°為搜尋上限，非機械極限。
- 下一步：依`M_BACKBONE_TEST_PLAN.md`製作並測試含棒M模組，以實測EA/EI更新模型。
