# M6 hub pocket in native B-Rep: what the ring_0 corner really is, a slot-fill trial, and the arch-crown site the gauge metric missed — evening, 27 November 2026

**Run:** scheduled evening run. Started **2026-11-27 20:02:05 EST (2026-11-28 01:02:05 UTC)**; 2-hour deadline **22:02:05 EST (03:02:05 UTC)**.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_27.md) · [Next-run handoff](HANDOFF.md) · [Previous study (27 Nov hub strain & STL fillet collars)](../hub_fillet_20261127/README.md) · [Summary figure](results/evening_20261127_summary.png)

This run takes **Priority 1 of [`hub_fillet_20261127/HANDOFF.md`](../hub_fillet_20261127/HANDOFF.md)**: fillet the hub junctions in the native parametric B-Rep instead of with STL boolean collars, then check the effect on hub strain.

Simulation and CAD-candidate work only. The repository CAD (`cad/modules/Medium_Stiffness_96.step`, `cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl`), guide positions, rope routing, masses, the 500 g payload and U4+M2 are **unchanged**. No backbone end ferrule is added. The variant STEP files below are **candidates and are not adopted**.

## Outcome

1. **The FE body is the STEP rotated by −22.5° about z.** In the hub region (`r < 14 mm`, `|z| < 30 mm`, 3,014 vertices), `M6_lane_anchorC.stl` matches `Medium_Stiffness_96.step` rotated by −22.5° to within **0.00066 mm** (95th percentile 0.00034 mm). B-Rep edges can therefore be mapped onto FE hotspots exactly.
2. **The `ring_0` corner peak is not a re-entrant fillet edge.** It sits at the root of a **0.30 mm-wide, 2.00 mm-deep slot**. The slot is the air gap between each 3.0 mm rib end and the 3.6 × 3.1 mm socket it passes through in the hub ring. There are 8 such pockets at each hub end (16 in all). The rib is joined to the hub only through the socket ceiling at `|z| = 17.970 mm`. The peak lies at socket-local `a = 8.26 mm, b = 1.81 mm, z = −18.01 mm`, which is the slot's ceiling corner at the `r = 8.5 mm` rim.
3. **Native fillets are limited by the slot.** `BRepFilletAPI_MakeFillet` was run on all 114 concave edges in the pocket zone (5 edge families):

   | R (mm) | Result |
   |---:|---|
   | 0.14 | **valid**, single solid, +1.05 mm³ (+0.001 g) |
   | 0.25 | builds, but `BRepCheck` reports the solid **invalid** (the fillets overlap inside the 0.30 mm slot) |
   | 0.30 / 0.50 / 0.80 | **fail** (32 / 32 / 48 faulty contours) |

   The R = 0.8–1.5 mm fillet requested in the handoff cannot be built at this corner while the slot exists.
4. **`ring_1` has no edge to fillet.** Every B-Rep edge within 1.8 mm of the `ring_1` peak (`r = 12.0 mm, z = −5.19 mm`) is either tangent-continuous (`ChFi3d` "Tangential", dihedral 0°) or convex. Its 0.5 mm gauge strain is bending of a smooth surface. Reducing it needs a change of section, not a fillet.
5. **A third, previously unnamed site governs the 0.5 mm gauge strain: the arch crown.** This is the concave crown of the rib arch just below the socket bottom face (`r ≈ 9.4–9.7 mm, |z| ≈ 20.3 mm`). The archived metric took its gauge average only at the element-peak location (the slot root), so it did not see this site. At step 1,869 in the unchanged baseline:

   | Site | Element peak (q3 → q2.5) | 0.5 mm gauge (q3 → q2.5) | 1.0 mm gauge (q2.5) |
   |---|---|---|---|
   | Slot root, `ring_0` end | 3.68% → **3.85%** | 0.98% → 0.85% | 0.41% |
   | **Arch crown, `ring_0` end** | 3.17% → 3.14% | **1.72% → 1.91%** | **1.02%** |
   | `ring_1` | 3.29% → 3.25% | 1.32% → 1.49% | 0.67% |
   | Arch crown, `ring_3` end | 2.32% → 2.41% | 1.24% → 1.48% | 0.90% |

   The arch crown is above the ~0.98–1.18% PA12 endurance band at both gauge lengths. Its 0.5 mm gauge value is **not mesh-converged** (+11% from q3 to q2.5). That check is reported as FAIL and kept visible.
6. **Slot fill: REJECTED (kept visible).** The 0.30 mm side and end gaps of all 16 pockets were closed in B-Rep (+88.50 mm³, +0.089 g, valid single solid). In the FE the fill is built from exact B-Rep dimensions and stops 0.05 mm short of the two open faces, adding 85.31 mm³. Like-for-like at q3 and step 1,869:
   - the slot-root peak falls **3.68% → 2.37% (−36%)**;
   - the global element peak falls 3.68% → 3.47%;
   - but the governing arch-crown 0.5 mm gauge strain rises **1.72% → 2.05% (+19%)**, and the `ring_1` element peak rises 3.29% → 3.46% (+5%).

   At the finer q2.5/a0.40 level the arch-crown element peak becomes the global peak (**3.50%**, still rising with refinement: 3.22% → 3.28% → 3.50%). Bare `EI` rises 4.7% (39,652 → 41,519 N·mm²) and `EI` with the sleeve backbone rises 2.8% (66,448 → 68,315 N·mm²). That would change the M6 stiffness used by the rod/mission solver.

   **In short, closing the slot moves the effective clamp 2 mm outward and puts more bending into the arch crown.** It also has no documented design intent behind it either way. A similar case of filled 2 mm blind reliefs is recorded for the end disks in [`cad/lanes_u4m2/README.md`](../../../../cad/lanes_u4m2/README.md).

## What was built

| File | Purpose |
|---|---|
| [`brep_hub_variants.py`](brep_hub_variants.py) | Loads the STEP with OpenCASCADE (OCP 7.8.1). Checks it against the FE STL (frame check), classifies pocket-zone edges with `ChFi3d.DefineConnectType`, builds the fillet variants with R = 0.14, 0.25, 0.30, 0.50 and 0.80 mm plus the slot fill, validates each with `BRepCheck_Analyzer`, and writes [`results/brep_variants.json`](results/brep_variants.json) and [`results/cad/`](results/cad/) (gzip STEP). |
| [`hub_variant_fe.py`](hub_variant_fe.py) | Runs `hub_fillet_20261127/fillet_study.evaluate_candidate` unchanged: CAD sleeve NiTi backbone `L = 66 mm`, G = 500 MPa bond layer, crown 0.06 mm, steps 1,709 / 1,869 / 1,884, with the same rod/mission inputs (`evening_20261125/results/rod_steps.npz`). Adds the named sites `slot_root_ring{0,3}` and `arch_crown_ring{0,3}` to `analyze_step`. The slot fill is unioned onto the cropped FE lattice in double precision with OpenCASCADE (sewn STL solid + 16 boxes, fuzzy 1e-5 mm). |
| [`run_all_levels.sh`](run_all_levels.sh) | Runs the four final FE cases sequentially. |
| [`summarize_and_validate.py`](summarize_and_validate.py) | Writes [`results/summary.json`](results/summary.json), [`results/validation.json`](results/validation.json) and the [summary figure](results/evening_20261127_summary.png). |

## FE results (step 1,869; step 1,709 / 1,884 differ by ≤ 1.5%)

| Case | Tets | Global peak | Slot root `ring_0` (peak / g0.5) | Arch crown `ring_0` (peak / g0.5 / g1.0) | `ring_1` (peak / g0.5) | Arch crown `ring_3` (g0.5) |
|---|---:|---:|---|---|---|---:|
| Baseline q3/a0.40 | 179,318 | 3.682% | 3.682% / 0.984% | 3.171% / 1.719% / 1.092% | 3.288% / 1.317% | 1.244% |
| Baseline q2.5/a0.25 | 247,131 | 3.846% | 3.846% / 0.850% | 3.135% / **1.905%** / 1.017% | 3.249% / 1.490% | 1.480% |
| Slot fill q3/a0.40 | 200,601 | 3.470% | 2.367% / 0.774% | 3.223% / **2.048%** / 1.074% | 3.464% / 1.392% | 1.347% |
| Slot fill q3/a0.25 | 223,820 | 3.409% | — | 3.281% / 2.144% (in `ring0_hotspot`) | 3.366% / 1.475% | — |
| Slot fill q2.5/a0.40 | 253,367 | 3.503% | 2.044% / 0.668% | **3.503%** / 2.002% / 1.101% | 3.393% / 1.494% | 1.546% |

All PARDISO residuals are ≤ 1.2 × 10⁻¹². The baseline reproduces the archived [27 Nov study](../hub_fillet_20261127/README.md) in this environment within 3%: q2.5 `ring_0` 3.846% vs 3.843%, `ring_1` 3.249% vs 3.237%. At q3, `ring_0` is 3.682% vs 3.747%. TetGen 0.8.4 builds 179,318 tets here versus the archived 178,517.

## Failed or abandoned attempts (kept visible)

- **Delta-slab union** (B-Rep added material unioned onto the STL): the slabs only touch the lattice and do not overlap it. The result had 21 separate bodies ([`logs/fe_run1.log`](results/logs/fe_run1.log)).
- **Hub-zone splice** (replacing `r < 10.5, 15.5 < |z| < 21.5 mm` with the B-Rep variant): the result was watertight, but sub-micron seams between the STEP and STL tessellations crashed TetGen with a segmentation fault ([`logs/fe_run2.log`](results/logs/fe_run2.log)). `manifold3d.simplify(0.002)` then damaged the clamp faces and split the body into 19 parts. All three approaches were abandoned.
- **manifold3d box union**: float32 output produced zero-length edges at the slot corners, which TetGen rejected (`recoversubfaces`). The OpenCASCADE double-precision union was used instead.
- **Fill flush to the open faces with exact dimensions**: OCC skipped 16 faces with null triangulation. Fill boxes inflated with the *rounded* dimensions 17.97 / 19.97 / 8.31 left 0.0003 mm edges, and TetGen produced 3.0 M tets. Hence the final 0.05 mm offset from the open faces.
- **Slot fill q2.5/a0.25** was killed for lack of memory, twice (~14 GB RSS against the 15 GB session limit; [`logs/fe_run5.log`](results/logs/fe_run5.log)). q3/a0.25 and q2.5/a0.40 were run instead.
- **The R = 0.14 mm fillet variant has no FE result.** Its FE body was only obtainable through the splice that crashed TetGen. At 0.14 mm it is also about one to two q3 elements wide at the corner.

## Reproduction

```bash
# Python 3.13; numpy 2.5.3, scipy 1.18.1, trimesh 5.2.2, manifold3d 3.5.5, tetgen 0.8.4,
# pypardiso 0.4.7 (mkl 2026.2.2), cadquery-ocp 7.8.1.1.post1, numba 0.68.1, python-fcl 0.7.0.11,
# plus networkx, clarabel, shapely and triangle (imported by the archived dependency chain)
python3.13 brep_hub_variants.py         # ~1 min
bash run_all_levels.sh                   # ~10 min, sequential (q2.5 needs ~13 GB)
python3.13 hub_variant_fe.py --level q3_a025 3.0 0.25 slot_fill   # optional intermediate level
python3.13 summarize_and_validate.py
```

Source revisions: `origin/main` at `76d026c` (inputs). SHA-256 hashes of the CAD inputs:

- `Medium_Stiffness_96.step`: `ccfc29d4…e5935c`
- `M6_lane_anchorC.stl` (end_bellmouth_v1): `b82d83ec…dc7f5`

## Validation ([`results/validation.json`](results/validation.json))

12 required checks pass. Two convergence checks **FAIL and are kept visible**:

- the baseline arch-crown 0.5 mm gauge changes +11% from q3 to q2.5;
- the slot-fill arch-crown element peak changes +9% from q3 to q2.5/a0.40.

## Limits

- Linear elastic solid FE with the same load model as the archived study. The three governing mission steps were evaluated, not a full 3,405-state envelope. Nothing here is hardware evidence.
- The arch-crown gauge strain is not converged. It needs local refinement of the crown (not global q2.5/a0.25, which is at the memory limit).
- The purpose of the 0.30 mm rib/socket slot (print clearance, compliance relief, or a leftover from modelling the rib and hub as separate bodies) is unknown. Any change to it needs the designer's confirmation.
- The PA12 endurance band (~0.98–1.18% elastic strain, from 15–18 MPa) is a literature value carried over from the 27 Nov study, not a measured value.
