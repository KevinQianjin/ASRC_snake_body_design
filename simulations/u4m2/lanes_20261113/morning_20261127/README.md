# Geometrically nonlinear coupled M6 lattice + NiTi backbone — morning, 27 November 2026

**Run time:** started **2026-11-27 07:24:01 EST (2026-11-27 12:24:01 UTC)**; completed **2026-11-27 08:05:00 EST (2026-11-27 13:05:00 UTC)**.

[Morning Report](../../../../reports/daily/Morning_Report_2026_11_27.md) · [Next-run handoff](HANDOFF.md) · [Previous study (26 Nov evening)](../evening_20261126/README.md) · [Summary figure](results/morning_20261127_summary.png)

This study executes **Priority 1** of the [26 November 2026 evening handoff](../evening_20261126/HANDOFF.md): settling body–rod axial compatibility, sleeve-bond shear, and `ring_0`/`ring_1` radial clearance at 47° using a **geometrically nonlinear coupled corotational M6 lattice + extensible elastica NiTi backbone** model calibrated directly from [`evening_20261126/results/unit_poses.npz`](../evening_20261126/results/unit_poses.npz) (no re-meshing).

Simulation only. No CAD, guide position, rope bore, station, mass, or solver input changed.

## 1. Corotational M6 lattice calibration (`calibrate_frame.py`)

Seven corotational sub-segments spanning `D0 (−44.9) → R0 (−18.475) → G− (−12.0) → R1 (−4.975) → R2 (+4.975) → G+ (+12.0) → R3 (+18.475) → D1 (+40.9)` with guaranteed-SPD 6×6 local shear-bending-coupled stiffness matrices were calibrated against `cad_sleeve_L66_rings`, `cad_sleeve_L66_d1`, and bare `EI = 39,701.4 N·mm²`:
- Bare `EI` over 85.8 mm: `39,701.3 N·mm²` (`−0.000%` error).
- Across all 3,405 linear mission states: max ring position error **0.0054 mm (0.03%)**, max ring rotation error **0.035° (0.08%)**, max D1 position error **0.0012 mm (0.003%)**.
- Axial stiffness of the flexible middle lattice (`R0 → R3`) is only **~1.56 N/mm**, ~1,000× softer than the Ø1.80 mm NiTi backbone (`EA / 66 mm = 1,542 N/mm`).

## 2. Linear-regime verification below 15° (`coupled_nonlinear.py`)

- Small-angle tangent check (`0.05×` step 1,869, `2.3°`): raw 3D ring position error **1.31%**, rotation error **0.17%** (`|g| = 1.3 × 10⁻⁸`).
- 12 mission states across all phases (`2.3°–14.4°`): max lifted 3D ring position error **1.69%**, max transverse XY error **1.13%**, max rotation error **0.24%** — **PASS (< 2% criterion)**.

## 3. Coupled nonlinear equilibrium at 47° & mission sweep (`results/coupled_nonlinear.json`)

| Step (phase, D1 angle) | `ring_0` gap | **`ring_1` gap** | `ring_2` gap | `ring_3` gap | Rod axial force `N_rod` | Sleeve shear (`87.2 mm²`) | Peak NiTi strain | Contact force |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,709 (`left_out`, 47.16°) | 1.408 mm | **1.110 mm** | 1.531 mm | 2.328 mm | +3.24 N | 0.0371 MPa | 1.67% | 0.00 N |
| **1,866 (`left_return`, 46.74°)** | **1.402 mm** | **0.931 mm** | **1.380 mm** | **2.386 mm** | **+3.52 N** | **0.0404 MPa** | **1.71%** | **0.00 N** |
| 1,869 (`left_return`, 46.91°) | 1.398 mm | **0.947 mm** | 1.395 mm | 2.376 mm | +3.51 N | 0.0402 MPa | 1.71% | 0.00 N |
| 1,884 (`left_return`, 47.15°) | 1.403 mm | **1.067 mm** | 1.496 mm | 2.339 mm | +3.31 N | 0.0380 MPa | 1.68% | 0.00 N |
| 1,001 (`right_return`, 47.28°) | 1.402 mm | **1.096 mm** | 1.520 mm | 2.327 mm | +3.27 N | 0.0375 MPa | 1.68% | 0.00 N |
| 2,390 (`pitch_up`, 33.49°) | 2.001 mm | **1.940 mm** | 2.139 mm | 2.592 mm | +1.41 N | 0.0162 MPa | 1.13% | 0.00 N |
| 2,819 (`pitch_down`, 32.36°) | 2.081 mm | **2.220 mm** | 2.390 mm | 2.546 mm | +1.01 N | 0.0115 MPa | 1.03% | 0.00 N |

- **Mission sweep (183 states, stride 20 + key steps):** **0 contacts**, worst gap **0.931 mm** (`ring_1` @ step 1,866), peak `|N_rod|` = **3.52 N**, peak sleeve-bond average shear = **0.0404 MPa** (40 kPa).
- **Convergence (`h = 0.5 mm`) & follower-wrench sensitivity at step 1,866:**
  - `h = 0.5 mm` (D0-frame wrench): **`ring_1` gap = 0.978 mm**, `N_rod = +3.54 N` (step 1,709: `1.157 mm`; step 1,869: `0.994 mm`; `h = 1.0 mm` is conservative by `0.047 mm`).
  - Follower-frame wrench (`h = 1.0 mm`): **`ring_1` gap = 0.570 mm**, `N_rod = 0.00 N` (step 1,709: `0.773 mm`; step 1,869: `0.587 mm`).
- **Acceptance (`gap ≥ 0.25 mm`):** **PASS** across all variants (`0.570–0.931 mm`, zero contact force to feed back into hub-strain FE).

## 4. Reproduction and validation

```bash
python calibrate_frame.py
python coupled_nonlinear.py
python summarize_and_validate.py
```

All 8 checks in [`results/validation.json`](results/validation.json) pass.
