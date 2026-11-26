# Next-run handoff — from the 25 November 2026 Evening Report

Prepared at about **2026-11-25 20:55 EST (2026-11-26 01:55 UTC)** by the evening run, which started at **2026-11-25 20:02:23 EST (2026-11-26 01:02:23 UTC)**; budget deadline **22:02:23 EST (03:02:23 UTC)**. The final pushed revision is in the completion message, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_25.md) · [Evidence](README.md) · [Previous handoff (24 Nov evening)](../evening_20261124/HANDOFF.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (linear solid FE, superposition over all 3,405 states; no hardware)

- **Bond demand is closed out over the mission.** Mission maxima (q3) are within **+4.4% (area-mean axial)**, **+4.3% (land-edge peak axial)** and **0% (peak normal)** of the step-1,709/1,885 values: area-mean axial 2.48 / 3.60 MPa, peak axial 9.0 / 16.8 MPa uncrowned (7.8 / 14.5 crowned), peak normal 21.2 / 36.4 MPa at G 500 / 1,500. Mesh q5 → q3 changes them by −3.9% to +4.7%.
- **Off-plane lands double during right yaw** (157.5° / 337.5° at z = −12 mm: 8–9 MPa peak at G 500 vs 4.2–4.6 MPa at step 1,709) but stay inside the overall envelope.
- **Tilt clearance over the mission (sampled, stride 5 + targets, 689 states):** no state below 0.025 mm and no tilted contact; minima **0.0737 mm uncrowned** (+12 mm, step 805) and **0.0783 mm crowned** (+12 mm, step 1,681). The worst tilted gap varies by only about 0.005 mm over the mission ([README § 3](README.md#3-sampled-whole-mission-tilt-sweep)).
- **Hub strain over the mission** (q5, G 500, crowned, no backbone): peak **3.81% at step 1,869**, same element (r = 8.47 mm, z = −17.9 mm) at every yaw maximum; **615 states > 3%**, 1,124 > 2%; pitch phases 2.3–2.5%; land bands ≤ 0.68%.
- Superposition is exact: per-land tractions, slip, rotations and socket motion reproduce the archived 24 Nov direct solves at steps 1,709 / 1,885 to < 10⁻⁵ relative, and the probe and strain values to < 10⁻⁶ mm / 10⁻⁹.

## Priorities

1. **Hub-junction strain with the NiTi backbone (simulation, about 60 min).**
   *Why:* the hub/arm junction strain (3.81% peak, > 3% on 615 states) is now the largest open structural question of the M6 body, and the body model still omits the Ø1.8 mm backbone that shares the end rotation (rod EI 64,730 = body 44,118 + backbone 20,612 N·mm²).
   *How:*
   - Add the backbone as a linear beam (E = 40 GPa, Ø1.8 mm, as in [`backbone_20261108/backbone.py`](../../backbone_20261108/backbone.py)) between the D0 / D1 masters of `body_bond.Body`; couple it to the hub rings only if the CAD bore is a fit (check the CAD bore diameter first and state it).
   - With the backbone, decide whether the prescribed end rotation stays the rod's (kinematic: the strain does not change) or whether the rod's end MOMENT is applied (load-controlled: the body share drops to about 44/65). State which is consistent with the rod model and justify it; this is the decisive modelling choice.
   - Refine locally at the peak element (r ≈ 8.5 mm, z ≈ −17.9 mm) and report a converged peak.
   - Re-run [`strain_envelope.py`](strain_envelope.py) with the new body (15 unit fields + superposition, about 3 min).

   *Acceptance:* converged hub peak with the backbone at steps 1,709 and 1,869 and the number of states above 2% / 3%; the body/backbone moment split; a comparison with a **cited** PA12 (MJF/SLS) strain-at-yield and fatigue figure, not an assumed one; land tractions within ±20% of tonight's or the difference explained.
2. **Close the gaps of the sampled tilt sweep (simulation, about 20 min).**
   *Why:* the sweep sampled every 5th state. The governing minima should be bracketed at stride 1.
   *How:* `python3 mission_envelope.py --G 500 --no-probe --save-patch --out results/patch_q5` (156 s, regenerates the 13.5 MB `patch_units.npz` that was not committed), then run `probe_sweep.py` on ±10 states around each per-phase minimum (add a `--steps` option).
   *Acceptance:* the stride-1 minimum per station / land variant and confirmation that no unsampled step is lower by more than 0.001 mm.
3. **Bench (hardware, unchanged).** Tilt ≤ 0.20° and offset ≤ 0.025 mm at both stations with the land profile measured to 0.01 mm; an adhesive lap-shear coupon on PA12 at a 0.25–0.31 mm gap (target ≥ 3.6 MPa area-mean with margin, 17 MPa edge peak for a conservative design); strain gauge or DIC at one M6 arm next to the land **and at the hub/arm junction** with the module bent to the step-1,869 curvature. Do not report this as completed in simulation.

## Blockers and resources

- 4 cores, 15 GB. q5 bonded build 41 s, solve of 15 RHS about 60 s per (G, crown); q3 build 60 s, solve about 90 s. The q2 bonded model exceeds 15 GB (24 Nov) — do not run it.
- Run FE jobs one at a time; the FCL sweep (3 workers) can run alongside one FE job (it slowed by about 2×).
- pypardiso: `export PYPARDISO_MKL_RT=/usr/local/lib/libmkl_rt.so.3` (from the `mkl` wheel); upper triangle for `mtype = 2`; fresh solver per factorisation.
- Install with `python3 -m pip`: numpy scipy trimesh tetgen triangle pypardiso mkl python-fcl vtk numba clarabel shapely rtree networkx matplotlib; then `python3 -m pip install --ignore-installed pillow` (the system PIL breaks matplotlib).
- `codex/m5-active-reset-load-export` remains unmerged with no committed results; not duplicated.
- The adhesive, as-printed land, bonded tilt, bond strength and PA12 strain limit are unmeasured. The crowned candidate is not a manufacturing release.
