# M6 NiTi-backbone hub-strain convergence and stride-1 tilt closeout — morning, 26 November 2026

**Run time:** started **2026-11-26 10:19:41 EST (2026-11-26 15:19:41 UTC)**; completed **2026-11-26 11:25:00 EST (2026-11-26 16:25:00 UTC)**.

[Morning Report](../../../../reports/daily/Morning_Report_2026_11_26.md) · [Next-run handoff](HANDOFF.md) · [Previous study (25 Nov evening)](../evening_20261125/README.md) · [Summary figure](results/morning_20261126_summary.png)

This study executes both simulation priorities from the [25 November 2026 handoff](../evening_20261125/HANDOFF.md):
1. **Priority 1 — Hub-junction strain with the central Ø1.8 mm NiTi backbone** (`backbone_strain.py`): checks the CAD central bore diameter, adds the 40 GPa linear beam backbone between the D0 and D1 masters, evaluates kinematic vs load-controlled end conditions, refines the tetrahedral mesh across three levels (`q5` → `q3` → `q2.5/a0.25`, up to 1.34M reduced DOFs), re-runs the full 3,405-state strain envelope by superposition, checks land tractions, and compares against cited PA12 (MJF/SLS) datasheets and peer-reviewed fatigue endurance limits.
2. **Priority 2 — Stride-1 FCL tilt closeout** (`stride1_tilt_sweep.py`): closes the gaps of the 25 November stride-5 tilt sweep by evaluating exact FCL distances (untilted + 26 rigid ±0.2° tilts) at stride 1 on ±10 states around every per-phase minimum across all 11 mission phases, both stations (`z = −12, +12 mm`), and both land variants (uncrowned and crowned 0.06 mm).

Simulation only. No CAD, guide position, rope bore, station, mass, or solver input changed. The 500 g head payload and U4+M2 configuration are kept; no backbone end ferrule was added.

## 1. Priority 1 — Hub-junction strain with the NiTi backbone

### 1.1 CAD bore check and coupling
Measuring [`M6_lane_anchorC.stl`](../../../../cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl) at all four hub-ring bands (`z ∈ [−20, −16.95]`, `[−6.5, −3.45]`, `[3.45, 6.5]`, `[16.95, 20]` mm) gives an inner bore radius of **4.200 mm (Ø8.40 mm diameter)** and an end-disk bore of **Ø6.00 mm** (`r = 3.000 mm`). Against the **Ø1.80 mm** NiTi backbone (`r = 0.900 mm`), the hub rings have **3.30 mm radial clearance** — not a fit. The backbone (`E = 40 GPa`, `ν = 0.33`, `EI = 20,612 N·mm²`, `GJ = 15,498 N·mm²`, `EA = 101,788 N`, `L = 85.8 mm` between D0 and D1) is therefore coupled **only between the D0 and D1 masters**.

*Side finding (backbone-to-hub clearance):* at step 1,869 (47° yaw), the unguided cantilever backbone's lateral deflection differs from `ring_0` (`z = −18.48 mm`) by **4.25 mm** (> 3.30 mm radial clearance) because the proximal lattice segment near the clamped D0 disk bends less than a uniform beam. At `ring_1..ring_3`, relative lateral motion is `0.07–1.48 mm` (< 3.30 mm). This indicates potential backbone contact with the `ring_0` bore at extreme yaw and should be checked in a coupled-contact or bench test.

### 1.2 Kinematic vs load-controlled end conditions & moment split
The archived 3,405-state mission (`rod_steps.npz`) was generated with the parallel rod model (`backbone_20261108/backbone.py`), where `EI_rod = EI_body (44,118) + EI_backbone (20,612) = 64,730 N·mm²`. Because the PA12 body and central NiTi backbone are bonded to the same rigid end disks (D0/D1) in parallel, both share the exact same end rotation `ω_rod`.

- **Kinematic (prescribed `ω_rod` on D1 of `body + backbone`)** is directly consistent with the parallel rod model. Adding the backbone increases combined bending stiffness from `39,704` to `60,403 N·mm²` (`L = 85.8 mm`, parallel addition error `0.14%`). Because `ω_rod` already reflects the backbone's stiffening in the rod simulation, hub strain does **not** drop by 44/65; instead it drops modestly from **3.73% → 3.45%** (step 1,709) and **3.81% → 3.48%** (step 1,869) on `q5` because the backbone resists D1 lateral/axial deflection under the applied guide wrenches.
- **Load-controlled (`M_rod = K_rod ω_rod` applied to D1 of `body + backbone`)** is likewise consistent with the rod model and yields **4.51% / 4.48%** at steps 1,709 / 1,869 because the solid-ring PA12 lattice (`39.7 kN·mm²`) is ~10% softer than the database `44.1 kN·mm²` and D1 rotates freely under guide wrenches.
- **Body / backbone moment split (with guide wrenches):**
  - Kinematic: **75.2% / 24.8%** at step 1,709 (`340.5 / 112.5 N·mm`, total `453.0 N·mm`); **76.5% / 23.5%** at step 1,869 (`336.8 / 103.6 N·mm`, total `440.4 N·mm`).
  - Load-controlled: **71.8% / 28.2%** at step 1,709 (`446.0 / 174.9 N·mm`); **72.6% / 27.4%** at step 1,869 (`448.1 / 169.5 N·mm`).

### 1.3 Mesh convergence & full-mission strain envelope (`G = 500 MPa`, crowned 0.06 mm)

| Mesh level | Tets | Reduced DOFs | Step 1,709 peak | Step 1,869 peak | 0.5 mm gauge (1,869) | 1.0 mm gauge (1,869) | Mission max (step) | States > 3% / > 2% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `q5` (bare, 25 Nov) | 130,278 | 762,645 | 3.736% | 3.810% | — | — | 3.810% (1,869) | 615 / 1,124 |
| `q5` (+ NiTi) | 130,481 | 764,679 | 3.446% | 3.483% | — | — | 3.483% (1,869) | 547 / 1,034 |
| `q3` (+ NiTi) | 178,517 | 1,002,852 | 4.091% | 4.063% | 1.027% | 0.389% | — | — |
| `q2.5/a0.25` (+ NiTi) | 245,723 | 1,335,234 | **4.196%** | **4.169%** | **0.850%** | **0.401%** | **4.211%** (1,884) | **677 / 1,157** |

- `q3 → q2.5/a0.25` changes the element peak by **+2.55%** (step 1,709) and **+2.59%** (step 1,869), well within the 5% convergence target.
- The steep drop from the `4.17%` element peak (`h = 0.094 mm`) to `0.85%` (0.5 mm gauge) and `0.40%` (1.0 mm gauge) confirms a highly localized sharp re-entrant corner concentration at the hub/arm junction (`r ≈ 8.5 mm, z ≈ −17.9 mm`).

### 1.4 Land traction comparison (with vs without NiTi backbone, step 1,869)
- On all four governing bending-plane lands (`±12@67.5°`, `±12@247.5°`), peak axial shear changes by **1.2%–1.6%**, area-mean axial shear by **−2.5% to −5.1%**, and peak normal traction by **0.1%–0.4%**.
- Only the low-load off-plane lands (`−12@157.5°`, `−12@337.5°`) show a > 20% relative shift in area-mean axial shear (`0.80 → 0.98 MPa` [+21.5%] and `0.77 → 0.95 MPa` [+22.2%], i.e. `+0.18 MPa` absolute), caused by the backbone stiffening D1 against lateral guide-wrench shear; both remain far below the 2.40 MPa governing envelope.

### 1.5 Comparison with cited PA12 (MJF / SLS) limits
- **HP 3D High Reusability PA 12 (MJF, ASTM D638):** tensile modulus 1,700–1,800 MPa, tensile strength 48 MPa, elongation at yield **10% (Z) / 11% (XY)**, elongation at break **15% (Z) / 20% (XY)**.
- **EOS PA 2200 (SLS PA12, ISO 527):** tensile modulus 1,650–1,700 MPa, tensile strength 48–50 MPa (XY) / 42 MPa (Z), elongation at break **18–24% (XY) / 4–10% (Z)**.
- **High-cycle fatigue endurance limit:** Van Hooreweder et al. (2013, *Polymer Testing*, DOI: `10.1016/j.polymertesting.2013.04.014`) and Salazar et al. (2022, *Engineering Fracture Mechanics*, DOI: `10.1016/j.engfracmech.2022.108825`) report **15–18 MPa** at $10^6\text{–}10^7$ cycles (~**0.98%–1.18% elastic strain** at E = 1,530 MPa).
- **Assessment:** The 0.5–1.0 mm finite-gauge strain (`0.40%–0.85%`) lies near or below the ~1.0–1.2% fatigue endurance band, but the localized sharp-corner peak (`4.17%–4.21%`) exceeds the fatigue limit by ~3.5–4× and sits at the lower bound of SLS PA12 Z-axis break strain (4%). A hub/arm junction fillet and hardware DIC/strain-gauge verification remain necessary.

## 2. Priority 2 — Stride-1 FCL tilt closeout (`results/stride1_tilt_sweep.json`)

776 exact FCL probes (untilted + 26 rigid ±0.2° tilts) covering ±10 states around every per-phase minimum across all 11 phases:

| Land, station | Stride-1 min (step, phase, tilt) | 25 Nov stride-5 min (step) | Δ (mm) | States < 0.025 mm | Contacts |
|---|---|---:|---:|---:|---:|
| Uncrowned, `z = −12 mm` | **0.075241 mm** (1,950, left_return, in-plane 75°+) | 0.075193 mm (1,950) | +0.000048 | 0 | 0 |
| Uncrowned, `z = +12 mm` | **0.073692 mm** (808, right_out, in-plane 60°+) | 0.073686 mm (805) | +0.000006 | 0 | 0 |
| Crowned 0.06 mm, `z = −12 mm` | **0.078889 mm** (1,950, left_return, in-plane 75°+) | 0.078878 mm (1,950) | +0.000011 | 0 | 0 |
| Crowned 0.06 mm, `z = +12 mm` | **0.078408 mm** (1,681, left_out, in-plane 75°−) | 0.078320 mm (1,681) | +0.000088 | 0 | 0 |

- Maximum drop across all 44 phase-station-crown windows relative to the 25 Nov stride-5 sweep: **0.000097 mm** (`< 0.001 mm` acceptance threshold — **PASS**).

## 3. Reproduction and validation

```bash
python stride1_tilt_sweep.py --workers 8
python backbone_strain.py
python summarize_and_validate.py
```

All 8 checks in [`results/validation.json`](results/validation.json) pass (CAD bore, parallel EI addition, PARDISO residuals ≤ 3.3×10⁻¹¹, mesh convergence < 3%, stride-1 acceptance < 0.001 mm, 0 contacts, 0 states < 0.025 mm, summary plot).
