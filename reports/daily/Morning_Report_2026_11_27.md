# Morning Engineering Report — 2026-11-27

**Run:** ad-hoc morning engineering run. Started **2026-11-27 07:24:01 EST (2026-11-27 12:24:01 UTC)**; completed **2026-11-27 08:05:00 EST (2026-11-27 13:05:00 UTC)**.
**Reporting interval:** from the 26 November evening push **2026-11-26 20:55:26 EST (2026-11-27 01:55:26 UTC)** (PR #49 merged `2026-11-27 02:28:58 EST / 07:28:58 UTC`) to **2026-11-27 08:05:00 EST (2026-11-27 13:05:00 UTC)**.
**Branch:** `m6-nonlinear-coupled-backbone` (branched from `origin/main` at `61cd123`).

**Scope:** Execution of **Priority 1** from [`evening_20261126/HANDOFF.md`](../../simulations/u4m2/lanes_20261113/evening_20261126/HANDOFF.md) — a geometrically nonlinear, coupled corotational M6 lattice + extensible elastica NiTi backbone model to settle body–rod axial compatibility, sleeve-bond shear, and `ring_0`/`ring_1` bore clearance at 47°.

[Study and commands](../../simulations/u4m2/lanes_20261113/morning_20261127/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/morning_20261127/HANDOFF.md) · [Previous Evening Report](Evening_Report_2026_11_26.md) · [Summary figure](../../simulations/u4m2/lanes_20261113/morning_20261127/results/morning_20261127_summary.png)

## 1. Summary

- **Corotational lattice calibration (`calibrate_frame.py`):** A 7-segment corotational frame calibrated directly from `evening_20261126/results/unit_poses.npz` (no re-meshing) reproduces the bare PA12 `EI` (`39,701.3` vs `39,701.4 N·mm²`) and all 3,405 linear mission ring poses to **0.0054 mm (0.03%)** position and **0.035° (0.08%)** rotation. The flexible middle lattice (`R0 → R3`) has an axial stiffness of only **~1.56 N/mm** (~1,000× softer than the Ø1.80 mm NiTi backbone's `1,542 N/mm`).
- **Linear-regime acceptance (< 15°) — PASS:** The coupled nonlinear solver (`coupled_nonlinear.py`, damped Newton-Raphson to `|g| ≤ 5.7 × 10⁻⁸`) matches `q5` linear FE ring poses within **1.31%** at 2.3° (raw 3D), and within **1.69%** (lifted 3D) and **0.24%** (rotation) across 12 mission states in `2.3°–14.4°` — well inside the 2% acceptance threshold.
- **Axial compatibility settled:** Because the soft PA12 lattice readily absorbs the ~1.2 mm geometric foreshortening of the 66 mm NiTi backbone at 47° bend, coupled equilibrium gives a peak rod axial force of only **+3.52 N** (step 1,866, `left_return`, 46.74°; `+3.24 N` at 1,709; `+3.51 N` at 1,869), corresponding to a sleeve-bond average shear of **0.0404 MPa** over the `87.2 mm²` (`15 mm × Ø1.85 mm`) bond area. Under follower-frame guide wrenches, `N_rod` drops to **0.00 to −0.03 N**. This decisively rules out the non-physical 1,800–2,000 N fixed-chord bound.
- **`ring_1` clearance confirmed ≥ 0.25 mm with zero contact — PASS:** Across 183 mission states (stride 20 + all 11 per-phase maxima + governing steps 1,709 / 1,866 / 1,869 / 1,884), **0 states contact any bore (`0 N`)**. The governing clearance remains at **`ring_1` (`z = −5 mm`), step 1,866**, and improves over the 26 Nov uncoupled `0.393 mm` estimate because coupled rod forces pull the compliant lattice rings into alignment:
  - `h = 1.0 mm` (D0-frame wrench): **0.931 mm** (`ring_0 = 1.402 mm`, `ring_1 = 0.931 mm`, `ring_2 = 1.380 mm`, `ring_3 = 2.386 mm`);
  - `h = 0.5 mm` (converged rod mesh): **0.978 mm** (`1.157 mm` at 1,709; `0.994 mm` at 1,869; `N_rod = +3.54 N`, confirming `h = 1.0 mm` is conservative by 0.047 mm);
  - Follower-frame wrench sensitivity (`h = 1.0 mm`): **0.570 mm** (`0.773 mm` at 1,709; `0.587 mm` at 1,869).
  Because all variants exceed `0.25 mm` with zero contact, no contact force needs to be fed back into the hub-strain FE.
- **NiTi bending strain:** Peaks at **1.71%** (steps 1,866 / 1,869), slightly above the 26 Nov uncoupled `1.53–1.62%` and still outside the validated range of the linear 40 GPa rod model.

## 2. Validation and remaining limits

- All 8 automated checks in [`validation.json`](../../simulations/u4m2/lanes_20261113/morning_20261127/results/validation.json) pass.
- **Remaining limits:** The body is a calibrated corotational 7-segment frame (captures global geometric nonlinearity and axial compatibility, not local 3D shell/rib buckling); NiTi is modelled as linear-elastic `E = 40 GPa` at 1.71% strain (superelastic plateau not modelled); no print/assembly tolerance stack is included (eccentricity could still consume part of the 0.57–0.84 mm nominal gap); no hardware evidence exists yet.
