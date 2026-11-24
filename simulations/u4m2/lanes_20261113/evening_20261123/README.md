# Local solid model of the bonded M6 struts: what it can and cannot decide — evening, 23 November 2026

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_23.md) · [Next-run handoff](HANDOFF.md) · [Previous study (22 Nov evening)](../evening_20261122/README.md) · [Round 2 bonded-land model](../../extreme_tests/round2_20261119/README.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

This run took handoff item 2 of the [22 November evening run](../evening_20261122/HANDOFF.md): a local solid model of the M6 rib and its bonded land, to decide which of the three fit-mismatch models (`rod`, `midplane`, `rigidland`) applies.

It is simulation only. No CAD, guide position, rope bore, station, mass or solver input changed. The head payload stays 500 g, U4+M2 is kept, and no backbone end ferrule was added.

**Outcome in one line.** The solid model was built, verified and converged. It was then shown to be **over-constrained**: when the cut faces of the strut follow the rod map, the strut cell carries about 30× the rod model's bending moment. Its tractions are therefore **not** a physical bond demand. The study also found two things that change the next steps:

- The bonded "webs" are arms of a zig-zag rib lattice.
- The rod map distorts the arm geometry around the guide by much more than the crowned-land clearance margin.

## What was built

1. **[`strut_fe.py`](strut_fe.py): a quadratic-tetrahedron (P2, 10-node) linear-elastic solver.**
   - PA12, E = 1,530 MPa, ν = 0.4. These are the repository values used by `rib_joint_3d`.
   - It crops one strut from the actual CAD (`end_bellmouth_v1/M6_lane_anchorC.stl`) with two capped planes and checks that the crop is a single watertight body.
   - Meshing uses TetGen.
   - Interpolation from the P2 field gives a bond-point operator `H` (bond-point displacement = `H` × cut-face displacement), precomputed per strut.
2. **[`solid_bond.py`](solid_bond.py): a fourth mismatch model, `solid`, for the 22 November bond model.**
   - Each bond point takes the displacement of its own solid strut, driven at both cut faces by the same rod map.
   - The guide is **not** coupled to the strut (free web).
   - The `convergence` sub-command runs the mesh and cut-plane study.
3. **[`coupled_land.py`](coupled_land.py): one complete guide station.**
   - Four solid CAD struts, each driven by the rod map at its cut faces.
   - The adhesive is a distributed crowned layer on the **actual inclined CAD side walls** inside |z − station| ≤ 0.25 mm. That is 8.00 mm² per land, compared with the 5.67 mm² rectangular equivalent in Round 2. There are 45,086 area-weighted points per land.
   - Layer stiffness: tangential G/t(z), normal 2(1+ν)G/t(z), with t(z) = 0.25 + crown·(zh/0.25)² mm.
   - One rigid guide carries the archived station wrench. Guide, struts and layer are solved together.
   - The strut is an exact prism (a convex 10-vertex section translated along its axis), so a structured graded mesher ([`prism_mesh`](coupled_land.py)) extrudes a Triangle section mesh through axial layers that are 0.05–0.1 mm thick in the land band.
4. **[`cell_moment.py`](cell_moment.py): a boundary-condition consistency check.** It drives all eight struts of a station the same way and compares the bending moment they carry with the rod model's own cell moment.
5. **[`socket_distortion.py`](socket_distortion.py): the rod map's non-rigid distortion of the arm walls inside the guide socket** (|z − station| ≤ 1.62 mm), measured relative to the land's rigid motion.
6. **[`validate.py`](validate.py)** writes [`results/validation.json`](results/validation.json).

## Checks

| Check | Result |
|---|---|
| P2 patch test (uniaxial stress along the strut axis plus a rigid motion), prism mesher / TetGen mesher | relative error 2.9·10⁻¹² / 3.4·10⁻⁸ — **pass** |
| Regression: `rod` and `rigidland` rows against the archived 22 November `bond_cases.json` (48 rows) | maximum difference 0.0 MPa — **pass** |
| Free-strut field, mesh h = 0.6 vs 0.45 mm (8 struts × 3 steps) | ≤ 0.14% change in the maximum non-rigid displacement — **pass** |
| Free-strut field, cut planes moved 0.75 mm inwards | ≤ 2.6% change |
| Coupled station, wrench closure | 1.2·10⁻¹¹ — **pass** |
| **Boundary-condition consistency** (solid strut cell moment ÷ rod cell moment) | **30.4–35.4 — FAIL** (this is the finding) |

## Results

### 1. Free solid strut versus rod map at the land (step 1,709; h = 0.45 mm; z = −12 / +12 mm)

| Arm | Rod map: max non-rigid over land | Solid strut: max non-rigid over land | Rod / solid axial strain over land | Max abs. mismatch, rod / solid |
|---|---:|---:|---:|---:|
| 67.5° and 247.5° (bending plane) | 0.0512–0.0514 / 0.0447–0.0449 mm | 0.1088–0.1107 / 0.0933–0.0943 mm | ±0.197 / ±0.316 (z = −12 mm) | 0.052 / 0.60 mm |
| 157.5° and 337.5° (near the neutral axis) | 0.0073–0.0075 / 0.0063–0.0065 mm | 0.0186–0.0195 / 0.0160–0.0168 mm | ±0.015 / ±0.025 | 0.008 / 0.058 mm |

Steps 1,709, 1,710 and 1,885 differ by less than 0.1%. A rod-driven solid strut deforms **more** over the land than the rod map does, not less. Put into the pad model, the free-web `solid` mismatch gives an axial-shear peak of 148 MPa (crowned, G = 500 MPa) and 420 MPa (G = 1,500 MPa), and an 11.8° guide-to-web rotation. That is not physically credible, so these rows ([`solid_bond_cases.json`](results/solid_bond_cases.json)) are kept only as a record.

### 2. Coupled station (crowned, G = 500 MPa, step 1,709, z = −12 mm, mesh 0.5 mm section / 0.1 mm band layers)

| Land | Peak axial shear | Peak normal | Area-mean axial shear | Max layer slip |
|---|---:|---:|---:|---:|
| 67.5° | 123.7 MPa | 165.5 MPa | 44.6 MPa | 0.085 mm |
| 247.5° | 125.9 MPa | 163.2 MPa | 43.9 MPa | 0.085 mm |
| 157.5° | 20.9 MPa | 44.2 MPa | 5.3 MPa | 0.017 mm |
| 337.5° | 23.6 MPa | 44.9 MPa | 4.9 MPa | 0.018 mm |

- The guide rotates about 1.2° relative to the station frame (rotation vector 0.0195, −0.0065, 0 rad).
- The production run (both stations, two moduli, crowned and uncrowned) and a three-level mesh refinement were **stopped deliberately** once check 5 failed. Their outputs would not be physical.
- This single case is archived in [`results/overconstrained_rigid_ring/`](results/overconstrained_rigid_ring/). It is **not mesh-converged**.

### 3. Why the strut model is over-constrained ([`cell_moment.json`](results/cell_moment.json))

With all eight struts driven at both cut faces by the rod map, the struts carry the following bending moments:

| Step | z = −12 mm: solid / rod | z = +12 mm: solid / rod |
|---|---:|---:|
| 1,709 | 19,747 / 650 N·mm | 16,914 / 543 N·mm |
| 0 | 6,303 / 188 N·mm | 3,560 / 101 N·mm |

- The rod values come from the rod cell stiffness of 5.394 N·m/rad per 12 mm cell, which corresponds to EI ≈ 64,700 N·mm².
- The Round 2 plate model gives a bare-body EI of 46,700 N·mm² for the module.
- The CAD sections explain the mismatch:
  - Between z = −16.75 and −6.5 mm, the eight 8.0 mm² struts are the whole M6 cross-section.
  - Each strut joins the hub disk at z ≈ −5.5 mm (r ≈ 10.4 mm) and runs out to a knee at r ≈ 30.6 mm, z ≈ −20.3 mm.
  - From the knee, a 4.89 mm² outer member runs on towards r ≈ 24 mm at z ≈ −35 mm, where it meets further members of the same rib.
- The outer cut face is therefore **not** a rigid ring or plane section. It is part of a compliant zig-zag rib lattice, which is how the module bends at roughly 6–8° per 12 mm cell.
- Forcing both strut ends onto the plane-section rod map removes that compliance. Neither the free-web nor the coupled strut result is a valid selector between `rod` and `rigidland`.

### 4. The rod map's distortion of the arm around the guide ([`socket_distortion.json`](results/socket_distortion.json))

Deviation of the rod-mapped arm walls from the land's least-squares rigid motion, at steps 1,709, 1,710 and 1,885 (the steps differ by less than 0.002 mm):

| Arm | Inside the 0.5 mm land | At the socket ends (±1.62 mm) | Land rigid rotation |
|---|---:|---:|---:|
| 67.5° / 247.5°, z = −12 mm | 0.054 mm | **0.371–0.373 mm** | 0.27° |
| 67.5° / 247.5°, z = +12 mm | 0.050 mm | **0.296–0.297 mm** | 0.23° |
| 157.5° / 337.5° | 0.007–0.008 mm | 0.043–0.057 mm | 0.015–0.022° |

- The 19–22 November clearance results (crowned land 0.0284 / 0.0424 mm at 0.2° tilt) were computed against the rod-mapped arm.
- The non-rigid distortion that the rod map writes into that arm is about 2× the margin inside the land and about 10× at the socket ends.
- A solid PA12 arm cannot strain 23% over 1.6 mm. The clearance margin is therefore model-dependent at its own scale. The sign of the error is not known until the rib lattice is solved.

## Interpretation

- **The 22 November bracket is not resolved.** The bond demand is still between the load-driven `rigidland` value (2–4 MPa) and the kinematic values (tens to hundreds of MPa).
- **What was established:**
  - The `rod` field is **not** a physical upper bound. A solid strut forced to follow the rod map at its ends deforms more than the rod field over the land.
  - The correct selector must include the whole rib lattice between the Round 2 master regions:
    - D0/D1: z ≤ −45 / ≥ 45 mm, plus the core r < 3.3 mm beyond |z| > 30 mm;
    - hub rings: r < 8.6 mm at z ∈ [−20, −16.95], [−6.5, −3.45], [3.45, 6.5] and [16.95, 20] mm.
  - That model must be validated against the plate-model body EI before its tractions are used.
- **New risk.** The crowned-land clearance certification depends on the rod map's distortion of the arm, at a scale larger than the margin. Until a solid rib solution exists, the 0.0284 / 0.0424 mm margins are not model-independent.

## Limits

- Linear, small-displacement elasticity. PA12 is isotropic and linear, with no yield. The free-strut strains of up to about 30% are far beyond PA12's elastic range. That alone shows the boundary conditions are wrong; it is not a prediction of strut failure.
- G is assumed. The adhesive and the as-printed land are unmeasured.
- The coupled case is a single case on one mesh and is over-constrained. Do not quote its tractions or its 1.2° guide rotation as design values.
- No physical validation was performed. Nothing here is a manufacturing release.

## Reproduce

Python 3.11.18, numpy 2.3.5, scipy 1.17.0, trimesh 5.2.0, tetgen 0.8.4 (TetGen 1.6), triangle 20250106, numba 0.68.1, python-fcl 0.7.0.11, clarabel 0.11.1, vtk 9.7.2, matplotlib 3.10.8, plus shapely, manifold3d, networkx and rtree. Source revision `7c2d006`. 4 cores, 15 GB of memory.

```
python solid_bond.py convergence --h 0.8 0.6 0.45      # free-strut field, 3 meshes + short cut, ~12 min
python solid_bond.py cases --h 0.6 --nh 8              # pad model with rod / rigidland / solid, ~2 min
python cell_moment.py                                  # BC consistency, ~1 min
python socket_distortion.py                            # rod-map distortion of the arm, ~1 min
python coupled_land.py --mesh 0.5:0.1 --stations -12 --steps 1709 --crown 0.06 --G 500 \
       --out results/overconstrained_rigid_ring        # one coupled case, ~6 min (archived file renamed)
python validate.py
```

Logs are in [`results/logs/`](results/logs/). The `coupled_production` and `coupled_convergence` logs end where those runs were stopped on purpose.
