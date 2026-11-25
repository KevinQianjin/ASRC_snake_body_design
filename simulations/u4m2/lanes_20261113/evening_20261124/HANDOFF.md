# Next-run handoff — from the 24 November 2026 Evening Report

Prepared at about **2026-11-24 21:05 EST (2026-11-25 02:05 UTC)** by the evening run. That run started at **2026-11-24 20:02:31 EST (2026-11-25 01:02:31 UTC)**, and its budget deadline is **22:02:31 EST (03:02:31 UTC)**. The final pushed revision is reported in the completion message, which this pre-publication file cannot contain. Checkpoint `20decfa` holds the code and the linear results.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_24.md) · [Evidence](README.md) · [Previous handoff (23 Nov evening)](../evening_20261123/HANDOFF.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (linear solid FE unless stated; no hardware)

- **Whole M6 lattice solid model, validated.** [`body_solid.py`](body_solid.py): bare EI is 40,368 N·mm² with elastic rings and 43,483 / 44,102 N·mm² with the plate model's rigid masters. That is 0.86–0.94× the plate model, and 0.1% / 1.4% from the database EA / EI. It is mesh-converged to 0.18%.
- **The rod's 64,730 N·mm² is the body plus the Ø1.8 mm NiTi backbone** (20,612 N·mm²). Do not use it as a body comparator.
- **Bond demand** ([`body_bond.py`](body_bond.py)): end masters driven by the rod's ~47° relative rotation, guides bonded with the distributed layer, station wrenches applied (step 1,709 / 1,885).
  - Area-mean axial shear is 1.0–3.5 MPa; land-edge peaks are 3.6–16.8 MPa (G 500–1,500 MPa).
  - Peak normal tractions are 7–36 MPa.
  - The crown lowers the peaks by about 15%.
  - The `rod` model (103–306 MPa) is ruled out.
- **Arm distortion** is 0.001–0.006 mm in the land and 0.016–0.064 mm at the socket ends (rod map: 0.05 / 0.30–0.37 mm).
- **Solid-arm clearance at 0.2° tilt** ([`solid_arm_probe.py`](solid_arm_probe.py)): 0.0742–0.0763 mm uncrowned and 0.0785–0.0794 mm crowned, at steps 1,709 / 1,885 only.
- **Validity:** peak strain is 3.7% at the hub/arm junction (r ≈ 8.5 mm, z ≈ −18 mm), and linearised rotations reach 0.85 rad. Land bands are below 0.7%. The total-Lagrangian check ([`nonlinear_check.py`](nonlinear_check.py), end rotation only, q10) converged at full load: end moment 0.991× linear, peak strain 3.22% against 3.25% linear, land bands 0.45%. Geometric nonlinearity is therefore about 1%, and the hub strain is real.

## Priorities

1. **Mission envelope by linear superposition (simulation, about 60 min).**
   *Why:* tonight covered only the two governing steps. The bonded body is linear, so the mission needs one factorisation, not 3,405 solves.
   *How:*
   - In `body_bond.Body` (q5 mesh), solve 15 unit right-hand sides: three unit D1 rotations and six unit wrenches per guide.
   - Store the layer tractions per land (per point) and the probe-patch relative displacements for each unit field.
   - For every step, combine them with that step's rod end rotation (`rod_rotations`, local moment scale) and the archived station wrenches.
   - Then run the FCL tilt probe on the archived low-margin steps (787 at −12 mm, 430 at +12 mm, from [`evening_20261120`](../evening_20261120/README.md)), or on the steps with the largest superposed relative motion.

   *Acceptance:*
   - Mission maximum of the area-mean and peak axial/normal traction per land (G 500 / 1,500, both lands).
   - Minimum solid-arm gap at 0.2° tilt over the probed steps.
   - A note whether any step exceeds the step-1,709 values.
2. **Hub-junction strain with the backbone (simulation, about 60 min).**
   *Why:* the peak body strain is 3–4% at the hub/arm junction (r ≈ 8.5 mm, z ≈ −18 mm). Tonight's total-Lagrangian check showed that this is not a linearisation artefact (about 1% effect). The backbone, fixed at both end disks per [`niti_supplier_report.md`](../../../../niti_supplier_report.md), changes how the end rotation is shared.
   *How:*
   - Add the Ø1.8 mm backbone as a beam between the end masters (and coupled at the hub rings only if the CAD bore is a fit) to `body_bond.Body`; linear is enough.
   - Refine locally at the peak site, and report the converged peak and the body/backbone moment split.
   - [`nonlinear_check.py`](nonlinear_check.py) is available if a nonlinear confirmation is wanted (q10: 30 s per Newton iteration, 25 min for 8 increments).

   *Acceptance:*
   - The converged hub peak strain with the backbone, compared with 3.7%.
   - A comparison with a cited PA12 strain or fatigue limit, not an assumed one.
   - Land tractions within ±20% of tonight's values, or the difference explained.
3. **Bench (hardware, unchanged plus one gauge site).**
   *Acceptance:*
   - Tilt ≤ 0.20° and offset ≤ 0.025 mm at both stations, with the land profile measured to 0.01 mm.
   - A lap-shear coupon of the chosen adhesive on PA12 at a 0.25–0.31 mm gap; the target strength is at least the 3.5 MPa area-mean with margin, and the 17 MPa edge peak for a conservative design.
   - A strain gauge or DIC on one M6 arm next to the land **and at the hub/arm junction (r ≈ 8.5 mm, z ≈ −18 mm)** while the module is bent to the step-1,709 curvature.

   Do not report this item as completed in simulation.

## Blockers and resources

- 4 cores and 15 GB of memory. MKL PARDISO solves the q5 / q3 / q2 bare body in 8 / 13 / 21 s.
  - The **q2 bonded run (1.79 M DOF plus layer) exceeds 15 GB** and was killed. Use q3 at most for bonded runs, or drop the dense `Kbg` (n × 6) assembly.
  - Run heavy jobs one at a time. Overlapping jobs were killed twice tonight.
- pypardiso:
  - set `PYPARDISO_MKL_RT` to `libmkl_rt.so.3` from the `mkl` wheel;
  - pass the **upper triangle** for `mtype = 2`/`-2` (a full matrix segfaulted MKL);
  - create a **fresh `PyPardisoSolver` per factorisation**.
- Install with `python -m pip`: numpy, scipy, trimesh, tetgen, triangle, pypardiso, mkl, python-fcl, vtk, numba, clarabel, shapely, rtree, networkx, matplotlib. `pillow` needs `--ignore-installed`.
- TetGen on the full lattice: `pq5a0.4` gives 130 k tets and `pq3a0.3` gives 189 k. `pq1.5` refines to more than 600 k because of the 0.04 mm CAD fillet edges. Surface decimation breaks the CAD; do not use it.
- `codex/m5-active-reset-load-export` is still unmerged and has no committed results. It was not duplicated.
- The adhesive, as-printed land, bonded tilt and bond strength are unmeasured. The crowned candidate is not a manufacturing release.
