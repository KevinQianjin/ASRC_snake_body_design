# Next-run handoff — from the 27 November 2026 Hub Strain & Fillet Study

Prepared at **2026-11-27 09:07:00 EST (2026-11-27 14:07:00 UTC)** (run started **2026-11-27 08:36:24 EST / 2026-11-27 13:36:24 UTC**).

[Engineering Report](../../../../reports/daily/Hub_Strain_and_Fillet_Study_2026_11_27.md) · [Study and commands](README.md) · [Previous handoff (27 Nov morning coupled)](../morning_20261127/HANDOFF.md)

## Closed in this run (linear solid FE + manifold3d CAD trials; no hardware)

- **Refined-mesh hub strain with CAD sleeve backbone (`L = 66 mm`) converged (< 2.6%):**
  - `ring_0` (`r = 8.46 mm, z = −18.01 mm`) governs the **element corner peak**: **3.843%** (step 1,869), **3.894%** mission max (step 1,884), `q3 → q2.5` change **+2.57%**, 0.5 mm gauge **0.786%** (below the 1.0–1.2% PA12 fatigue band); 602 states > 3%, 1,063 > 2%.
  - `ring_1` (`r = 11.97 mm, z = −5.20 mm`, symmetric `ring_2` at `+5.21 mm`) governs the **0.5 mm finite-gauge bulk strain**: element peak **3.237%** (`q3 → q2.5` = **−1.62%**), 0.5 mm gauge **1.376%–1.397%** (exceeding the 15–18 MPa / ~0.98%–1.18% PA12 endurance band).
- **STL-boolean axisymmetric collar trials rejected (kept visible):**
  - Both `hub_fillet_R0p8` and `hub_plus_arm_R1p0` passed watertightness and Ø8.40 mm bore checks, and `hub_plus_arm_R1p0` reduced `ring_1` 0.5 mm gauge strain by 72% (`1.41% → 0.40%`), **but** boolean-unioning axisymmetric collars onto the STL introduced sharp re-entrant intersection cusps at `z = −20.0 mm` (`4.96%` and `34–37%`). Do not use STL boolean collars.

## Priorities (next)

1. **Native parametric B-Rep/STEP fillet at BOTH `ring_0`/`ring_3` (`r = 8.5 mm`) and `ring_1`/`ring_2` (`r = 11.9 mm`) junctions (CAD + FE).**
   - Author true tangent-continuous edge fillets (`R = 0.8–1.5 mm`) along the rib-to-hub and rib-to-spoke intersection curves in the parametric CAD source (not STL boolean collars), then re-run `sleeve_hub_strain.py` (`q3` / `q2.5`) to verify both `ring_0` corner peak and `ring_1` 0.5 mm gauge drop below the 1.0–1.2% PA12 fatigue band without shifting excess load into `ring_0`.
2. **U1 leaf-joint proximal retention CAD revision (PR #47) & M5 pin grade closeout (Draft PR #42).**
3. **Bench (hardware, gating all ratings):**
   - Print M6 sockets (uncrowned + crowned 0.06 mm), PA12 lap-shear coupons, M6 hub/arm DIC/strain-gauge at **both** `ring_0` (`z = −18 mm`) and `ring_1` (`r = 12 mm, z = −5.2 mm`), rod-in-bore tolerance stack + 47° `ring_1` endoscope check, and U1 ±2/±5 N bench reversal comparison.
