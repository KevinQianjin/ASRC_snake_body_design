# M6 CAD-sleeve refined-mesh hub strain and hub/arm fillet study — 27 November 2026

**Run time:** started **2026-11-27 08:36:24 EST (2026-11-27 13:36:24 UTC)**; completed **2026-11-27 09:07:00 EST (2026-11-27 14:07:00 UTC)**.

[Engineering Report](../../../../reports/daily/Hub_Strain_and_Fillet_Study_2026_11_27.md) · [Next-run handoff](HANDOFF.md) · [Previous study (27 Nov morning coupled)](../morning_20261127/README.md) · [Summary figure](results/hub_fillet_20261127_summary.png)

This study executes **Priority 2 of `evening_20261126/HANDOFF.md`** (Priority 1 of `morning_20261127/HANDOFF.md`):
1. **Stage 1 (`sleeve_hub_strain.py`):** Recomputes the `q5 → q3 → q2.5/a0.25` hub-strain convergence and full 3,405-state mission envelope using the CAD-consistent `L = 66 mm` sleeve backbone attachment (`bore_fe.sleeve_backbone_stiffness_d1()`), tracking both `ring_0` (`r = 8.46 mm, z = −18.01 mm`) and `ring_1` (`r = 11.97 mm, z = −5.20 mm`) hotspots separately.
2. **Stage 2 (`fillet_study.py`):** Trials two watertight `manifold3d` STL-boolean fillet collar candidates (`hub_fillet_R0p8` and `hub_plus_arm_R1p0`), verifying watertightness, single body, Ø8.40 mm bore preservation, stiffness delta, and strain impact.

## 1. Stage 1 — Refined-mesh convergence with CAD sleeve backbone (`results/sleeve_hub_strain.json`)

| Mesh level | Tets | Step 1,869 `ring_0` peak (`g0.5`) | Step 1,869 `ring_1` peak (`g0.5`) | Step 1,884 global peak | Mission >3% / >2% |
|---|---:|---:|---:|---:|---:|
| `q5_a040` | 130,481 | 3.220% (0.934%) | 3.262% (1.322%) | 3.349% (`z = −5.18`) | — |
| `q3_a040` | 178,517 | 3.747% (0.949%) | 3.290% (1.412%) | 3.798% (`z = −18.01`) | — |
| `q2p5_a025` | 245,723 | **3.843%** (**0.786%**) | **3.237%** (**1.376%**) | **3.894%** (`z = −18.01`) | **602 / 1,063** |

- **`q3 → q2.5` convergence (PASS < 5%):**
  - `ring_0`: **+2.53%** (step 1,709) / **+2.57%** (step 1,869).
  - `ring_1`: **−1.88%** (step 1,709) / **−1.62%** (step 1,869).
- **Two distinct governing mechanisms (vs 15–18 MPa / ~0.98%–1.18% PA12 endurance band):**
  - **`ring_0` (`r = 8.46 mm, z = −18.01 mm`)** governs the **pointwise element corner peak** (**3.843%–3.894%**), but its 0.5 mm finite-gauge average (**0.786%**) lies below the PA12 fatigue band (highly localized sharp corner).
  - **`ring_1` (`r = 11.97 mm, z = −5.20 mm`)** (and symmetric `ring_2` at `z = +5.21 mm`) governs the **0.5 mm finite-gauge bulk bending strain** at **1.376%–1.397%** (`ring_2`: `1.353%`), exceeding the 15–18 MPa (~0.98%–1.18%) PA12 endurance band.

## 2. Stage 2 — STL-boolean fillet collar trials (REJECTED, kept visible; `results/fillet_study.json`)

Both candidates passed all geometric checks (`watertight = True`, `body_count = 1`, Ø8.40 mm bore preserved), but **failed mechanically as boolean STL collars**:

| Candidate | ΔMass (g) | Bare / Sleeve `EI` (`N·mm²`) | `q3` `ring_0` peak (`g0.5`) @ 1,869 | `q3` `ring_1` peak (`g0.5`) @ 1,869 | Verdict |
|---|---:|---|---:|---:|---|
| Baseline CAD (`q3`) | 0.000 | 39,701 / 66,497 | 3.747% (0.949%) | 3.290% (1.412%) | Baseline |
| `hub_fillet_R0p8` | +1.087 | 42,668 / 69,463 (+4.5%) | 4.961% (1.214%) | 3.382% (1.398%) | **REJECTED** (new sharp cusp at `z = −20.09 mm`) |
| `hub_plus_arm_R1p0` | +2.933 | 45,771 / 72,567 (+9.1%) | 37.03% (1.450%) | 5.572% (**0.397%**) | **REJECTED** (cuts `ring_1` gauge −72%, but creates `z = −20.00 mm` cusp & shifts load to `ring_0`) |

**Takeaway:** Boolean-unioning axisymmetric collars onto the triangulated STL creates new sharp re-entrant cusps where the collar intersects the 8 inclined ribs. True smooth fillets must be authored natively in the parametric B-Rep/STEP CAD along the actual rib-to-hub (`ring_0`/`ring_3`, `r = 8.5 mm`) and rib-to-spoke (`ring_1`/`ring_2`, `r = 11.9 mm`) intersection curves.

## 3. Reproduction and validation

```bash
python sleeve_hub_strain.py
python fillet_study.py
python summarize_and_validate.py
```

All 7 checks in [`results/validation.json`](results/validation.json) pass.
