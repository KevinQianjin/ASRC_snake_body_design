# Hub-Junction Strain Convergence & Fillet Study — 2026-11-27

**Run:** ad-hoc morning engineering run. Started **2026-11-27 08:36:24 EST (2026-11-27 13:36:24 UTC)**; completed **2026-11-27 09:07:00 EST (2026-11-27 14:07:00 UTC)**.
**Branch:** `m6-sleeve-hub-strain-and-fillet` (branched from `origin/main` at `61cd123`).

**Scope:** Execution of **Priority 2 of `evening_20261126/HANDOFF.md`** (Priority 1 of `morning_20261127/HANDOFF.md`):
1. Recompute refined-mesh (`q5 → q3 → q2.5/a0.25`) hub-junction strain and full 3,405-state mission envelope using the CAD-consistent `L = 66 mm` sleeve NiTi backbone attachment, tracking both `ring_0` and `ring_1` hotspots.
2. Trial watertight hub/arm fillet CAD candidates and evaluate stiffness, clearance, and strain reduction.

[Study and commands](../../simulations/u4m2/lanes_20261113/hub_fillet_20261127/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/hub_fillet_20261127/HANDOFF.md) · [Summary figure](../../simulations/u4m2/lanes_20261113/hub_fillet_20261127/results/hub_fillet_20261127_summary.png)

## 1. Stage 1 — Refined-mesh hub strain with CAD sleeve backbone (PASS convergence)

- **Mesh convergence (`q3` 179k → `q2.5/a0.25` 246k tets, 1.34M reduced DOFs):** both hotspots converge well inside the 5% target:
  - **`ring_0` (`r = 8.46 mm, z = −18.01 mm`):** `3.747% → 3.843%` (**+2.57%**) at step 1,869; `3.788% → 3.884%` (**+2.53%**) at step 1,709; **3.894%** mission max at step 1,884 (`602` states > 3%, `1,063` > 2%, down from `4.211%` / `677` / `1,157` under the superseded 85.8 mm model). Its 0.5 mm finite-gauge average is **0.786%** (below the PA12 fatigue band).
  - **`ring_1` (`r = 11.97 mm, z = −5.20 mm`, symmetric `ring_2` at `+5.21 mm`):** `3.290% → 3.237%` (**−1.62%**) at step 1,869; `3.350% → 3.287%` (**−1.88%**) at step 1,709. Its **0.5 mm finite-gauge average is 1.376%–1.397%** (`ring_2`: `1.353%`), **1.75× higher than `ring_0`** and **above the 15–18 MPa (~0.98%–1.18% elastic strain) SLS/MJF PA12 fatigue endurance band** (Van Hooreweder et al. 2013; Salazar et al. 2022).
- **Finding:** The `q5` shift of the pointwise maximum to `ring_1` was a coarse-mesh artefact, **but `ring_1` / `ring_2` (`r = 12.0 mm, z = ±5.2 mm`) is genuinely the governing finite-gauge fatigue hotspot**, while `ring_0` (`r = 8.5 mm, z = −18.0 mm`) governs the sharp corner peak.

## 2. Stage 2 — Watertight STL-boolean fillet collar trials (REJECTED, kept visible)

- Two watertight `manifold3d` axisymmetric collar candidates (`hub_fillet_R0p8`, `+1.09 g`, `+4.5%` combined `EI`; `hub_plus_arm_R1p0`, `+2.93 g`, `+9.1%` combined `EI`) preserved single-body watertightness and the Ø8.40 mm central bore, and `hub_plus_arm_R1p0` cut `ring_1`'s 0.5 mm gauge strain by **72%** (`1.412% → 0.397%`).
- **Why rejected:** Boolean-unioning axisymmetric collars onto the triangulated STL created new sharp re-entrant intersection cusps where the collars met the 8 inclined ribs at `z = −20.0 mm`, raising the `ring_0` peak to `4.96%` (`R = 0.8 mm`) and `34.3%–37.0%` (`R = 1.0 mm` + arm collar).
- **Conclusion:** True tangent-continuous edge fillets must be authored natively in the parametric B-Rep/STEP CAD along both `ring_0`/`ring_3` (`r = 8.5 mm`) and `ring_1`/`ring_2` (`r = 11.9 mm`) intersections—not via STL boolean collars.

## 3. Validation

All 7 automated checks in [`validation.json`](../../simulations/u4m2/lanes_20261113/hub_fillet_20261127/results/validation.json) pass (both hotspots `< 2.6%` convergence, all PARDISO residuals ≤ `3.3 × 10⁻¹¹`, CAD watertightness & Ø8.40 mm bore preservation).
