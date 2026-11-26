# Evening Engineering Report — 2026-11-26

**Scope:** Execution of both simulation priorities from [`evening_20261125/HANDOFF.md`](../../simulations/u4m2/lanes_20261113/evening_20261125/HANDOFF.md):
1. **Priority 1:** M6 whole-body solid model with the central Ø1.8 mm NiTi backbone (`E = 40 GPa`), CAD bore check, kinematic vs load-controlled justification, mesh convergence (`q5 → q3 → q2.5/a0.25`), full 3,405-state strain envelope, land-traction verification, and cited PA12 (MJF/SLS) comparison.
2. **Priority 2:** Stride-1 exact FCL tilt closeout (±10 states around all 44 per-phase minima of the 25 Nov sweep).

[Study and commands](../../simulations/u4m2/lanes_20261113/evening_20261126/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261126/HANDOFF.md) · [Previous Evening Report](Evening_Report_2026_11_25.md) · [Summary figure](../../simulations/u4m2/lanes_20261113/evening_20261126/results/evening_20261126_summary.png)

## 1. Summary

- **CAD bore check:** All four hub rings of `M6_lane_anchorC.stl` have an inner bore of **Ø8.40 mm** (`r = 4.200 mm`), giving **3.30 mm radial clearance** to the Ø1.80 mm NiTi backbone. Because it is not a fit, the backbone is coupled only between the D0 (`z = −44.9 mm`) and D1 (`z = +40.9 mm`) end masters.
- **End-condition choice & moment split:** Prescribing the rod model's relative end rotation `ω_rod` on D1 of the parallel `(body + backbone)` assembly (**kinematic**) is directly consistent with `backbone_20261108/backbone.py`, which already summed `EI_rod = 44,118 + 20,612 = 64,730 N·mm²` when generating `rod_steps.npz`. Adding the backbone increases combined bending stiffness from `39,704` to `60,403 N·mm²` (parallel addition error `0.14%`). With guide wrenches applied, the reaction moment splits **75.2% / 24.8%** (step 1,709) and **76.5% / 23.5%** (step 1,869) between the PA12 body and NiTi backbone (`71.8%–72.6%` body under load-controlled `M_rod`).
- **Mesh-converged hub strain (FAIL for sharp corner fatigue, kept visible):**
  - On `q5`, adding the backbone reduces peak hub strain from **3.810% → 3.483%** (step 1,869) via D1 wrench stiffening.
  - Refining the mesh (`q5` 130k → `q3` 179k → `q2.5/a0.25` 246k tets, 1.34M reduced DOFs) converges the localized corner peak to **4.196%** (step 1,709) and **4.169%** (step 1,869), with `q3 → q2.5` change of **+2.55% / +2.59%**.
  - Across all 3,405 mission states on `q2.5/a0.25`, peak strain reaches **4.211%** (step 1,884, `left_return`), with **677 states > 3%** and **1,157 > 2%**.
  - Finite-gauge volume averaging at step 1,869 drops the strain to **0.850%** (0.5 mm radius) and **0.401%** (1.0 mm radius), confirming a highly localized re-entrant CAD corner concentration at `r ≈ 8.5 mm, z ≈ −17.9 mm`.
- **Cited PA12 comparison:** Against HP MJF PA 12 (ASTM D638: 10–11% yield strain, 15–20% break strain, 48 MPa UTS) and EOS SLS PA 2200 (ISO 527: 4–10% Z / 18–24% XY break strain), the 4.21% corner peak is below monotonic MJF yield but at the lower bound of SLS Z-axis break strain. Against the peer-reviewed SLS/MJF PA12 high-cycle fatigue endurance limit of **15–18 MPa** (~**0.98%–1.18% elastic strain** at `E = 1,530 MPa`; Van Hooreweder et al. 2013, DOI: `10.1016/j.polymertesting.2013.04.014`; Salazar et al. 2022, DOI: `10.1016/j.engfracmech.2022.108825`), the sharp corner exceeds the endurance band by ~3.5–4× while the 0.5–1.0 mm finite-gauge average sits below it.
- **Land tractions preserved:** All four governing bending-plane lands stay within **1.2%–5.1%** of the 25 Nov bare-body tractions (only low-load off-plane lands shift by `+0.18 MPa` [+21.5% / +22.2%] due to D1 wrench stiffening, remaining well inside the 2.40 MPa envelope).
- **New side finding — proximal backbone clearance:** At step 1,869 (~47° yaw), the unguided linear cantilever backbone deflects **4.25 mm** laterally relative to `ring_0` (`z = −18.48 mm`), exceeding the **3.30 mm** radial clearance (`ring_1..ring_3` stay within `0.07–1.48 mm`).
- **Priority 2 — Stride-1 FCL tilt closeout (PASS):** 776 exact FCL probes (±10 states around all 44 per-phase minima) find **0 contacts**, **0 states < 0.025 mm**, and a maximum drop vs the 25 Nov stride-5 sweep of **0.000097 mm** (`< 0.001 mm` acceptance):
  - Uncrowned `z = −12 / +12 mm`: **0.075241 mm** (step 1,950) / **0.073692 mm** (step 808)
  - Crowned 0.06 mm `z = −12 / +12 mm`: **0.078889 mm** (step 1,950) / **0.078408 mm** (step 1,681)

## 2. Validation and remaining limits

- All 8 automated checks in [`validation.json`](../../simulations/u4m2/lanes_20261113/evening_20261126/results/validation.json) pass (parallel `EI` addition error `0.14%`, PARDISO residuals ≤ `3.3 × 10⁻¹¹`, `q3 → q2.5` convergence `2.55–2.59%`, stride-1 drop `0.000097 mm`).
- **Remaining limits:** Linear small-strain FE; unmeasured PA12 process-specific strain/fatigue limits, adhesive modulus/strength, and as-printed geometry; backbone-to-`ring_0` contact is not modelled; hardware bench verification remains gating.
