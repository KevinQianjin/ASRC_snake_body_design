# Next-run handoff — from the 26 November 2026 Evening Report

Prepared at **2026-11-26 21:05 EST (2026-11-27 02:05 UTC)**. The run started at **2026-11-26 20:01:44 EST / 2026-11-27 01:01:44 UTC**.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_26.md) · [Study and commands](README.md) · [Previous handoff (26 Nov morning)](../morning_20261126/HANDOFF.md)

## Closed in this run (linear solid FE plus nonlinear rod post-processing; no hardware)

- **The morning `ring_0` backbone-contact flag (4.25 mm > 3.30 mm) is withdrawn.** It came from attaching the rod at the FE cut faces (`L = 85.8 mm`). In the CAD the rod sits in Ø1.85 mm sleeves over `|z| = 33…48 mm` and is clamped at `z = ±33` with `L = 66 mm`.
- With that attachment, no state reaches the bore:
  - linear check over all 3,405 states: minimum gap **0.650 mm**;
  - geometrically nonlinear elastica over 737 states in all 11 phases: minimum gap **0.387 mm** (converged 0.393 mm), at **`ring_1`, step 1,866 (left-yaw return, 46.7°)**;
  - 0 contact force.
- The CAD-consistent attachment gives an equivalent stiffness of **66,501 N·mm²**, against the rod model's 64,730 (+2.7%). The morning attachment gave 60,404. The backbone carries **18.7–20.7%** of the D1 moment. The q5 peak strain falls to **3.31–3.38%** and moves toward `ring_1` (`z = −5.2 mm`).
- Peak NiTi bending strain is **1.53–1.62%**, about twice the uniform-curvature estimate.

## Priorities (at most three)

1. **Run a geometrically nonlinear, coupled body + backbone check of axial compatibility and the `ring_1` gap (simulation, ~60–80 min).**
   - *Why:* the 0.39 mm nonlinear gap assumes the rod end is free to slide axially (zero axial force). Pinning the rod to the lifted sleeve-tip chord puts `ring_0` in contact (−0.68 mm, 80 N). That bound needs ≈ 1,800–2,000 N of rod tension and is judged non-physical, but only a coupled nonlinear model can settle it.
   - *How:* the cheapest decisive option is a corotational or total-Lagrangian beam-frame model of the M6 lattice. Calibrate segment stiffnesses from the q5 unit fields (`results/unit_poses.npz`: rings R0–R3 and D1). Add the rod as a nonlinear beam tied at the sleeve tips. Load-step through steps 1,709 / 1,866 / 1,869 and the per-phase maxima.
   - *Acceptance:*
     - the coupled solution reproduces the q5 linear ring poses within 2% below 15°;
     - it reports rod axial force, sleeve-bond shear (15 mm × Ø1.85 bond area ≈ 87 mm²) and `ring_0`/`ring_1` gaps at 47°;
     - gap ≥ 0.25 mm, or the contact force is fed back into the hub-strain FE.
   - *Resources:* well under 4 GB RAM. Avoid re-meshing; reuse `unit_poses.npz`.
2. **Recompute the hub strain with the CAD-consistent rod attachment on the refined meshes, then the hub/arm fillet study (simulation, ~45 min).**
   - *Why:* the morning study's mesh-converged 4.17–4.21% corner value used the 85.8 mm attachment. On q5, the CAD attachment lowers the peak to 3.31% and moves it from the `ring_0` corner (`z = −17.9`) toward `z = −5.2 mm`. The fillet target location therefore needs confirming before any CAD fillet is drawn.
   - *How:* reuse `morning_20261126/backbone_strain.py` with `bore_fe.sleeve_backbone_stiffness_d1()` in place of `backbone_stiffness_d1(85.8)`. Run `q3` and then `q2.5/a0.25` on both hotspots, plus 0.5/1.0 mm gauge averages. Only then trial an `R = 0.5–1.5 mm` fillet at the governing junction. That is a CAD change, so keep the watertightness, connectivity and clearance checks.
   - *Acceptance:* `q3 → q2.5` change < 5% at both hotspots, and the governing location and value are stated against the 15–18 MPa (~1.0–1.2%) PA12 endurance band.
3. **Bench (hardware, unchanged and gating all ratings) plus a tolerance stack for the rod-in-bore gap.**
   - Measure the as-printed Ø8.40 ring-bore and Ø1.85 sleeve concentricity, and the rod straightness. The nominal 0.39 mm gap at `ring_1` is smaller than plausible print/assembly eccentricity, and no tolerance stack exists yet.
   - Run the already-listed bench items: crowned/uncrowned M6 sockets, PA12 adhesive lap-shear coupons, strain gauge/DIC at the governing hub junction, and the PR #47 U1 leaf-joint reversal comparison.
   - Add an endoscope or feeler check of rod-to-`ring_1` contact during a 47° left-yaw bend.

## Blockers and resource notes

- No hardware results are available, and none were invented.
- The reused 19–25 Nov modules import `fcl`, `numba`, `clarabel`, `vtk`, `shapely`, `triangle` and `networkx`. Install them before running.
- `pypardiso` may need `PYPARDISO_MKL_RT=/usr/local/lib/libmkl_rt.so.3`.
- The q5 build plus two factorisations took ~160 s and < 4 GB. The L2 sweep took ~8 min on 4 cores.
