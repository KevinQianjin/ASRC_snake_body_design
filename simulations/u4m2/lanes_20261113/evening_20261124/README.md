# Whole-body solid M6 model: stiffness validation, bonded-guide tractions and solid-arm clearance — evening, 24 November 2026

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_24.md) · [Next-run handoff](HANDOFF.md) · [Previous study (23 Nov evening)](../evening_20261123/README.md) · [Round 2 bonded-land model](../../extreme_tests/round2_20261119/README.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

This run took handoff item 1 of the [23 November evening run](../evening_20261123/HANDOFF.md) — a solid model of the M6 rib lattice between the Round 2 master regions, validated against the plate model before any traction is used — and then handoff item 2, the crowned-clearance re-check against the solid arm.

Simulation only. No CAD, guide position, rope bore, station, mass or solver input changed. The head payload stays 500 g, U4+M2 is kept and no backbone end ferrule was added.

## Outcome

1. **Stiffness validated.** The whole CAD lattice of `M6_lane_anchorC.stl` (10,487 mm³, one watertight body) meshed with P2 tetrahedra converges to a bare bending stiffness of **40,368 N·mm²** (elastic hub rings) or **43,483–44,102 N·mm²** (rigid hub rings, the plate model's masters). That is **86–94% of the plate model's 46,708 N·mm²** (acceptance: within 30%) and **0.92–1.00× the user's database PA12 body value of 44,118 N·mm²**. The rigid-ring EA of 166.8 N matches the database's 166.694 N to 0.1%.
2. **The rod's 64,730 N·mm² is not a body stiffness.** It is the PA12 body (44,118) plus the Ø1.8 mm NiTi backbone at 40 GPa (20,612 N·mm²) added in [`backbone_20261108/backbone.py`](../../backbone_20261108/backbone.py). The 23 November "rod EI ≈ 64,700" comparator therefore mixed body and backbone. This does not change the 23 November over-constraint verdict (30–35× is far beyond 1.47×).
3. **Bond demand is load-level, not kinematic.** With the rod's ~47° end-to-end rotation at step 1,709/1,885 imposed only on the end masters and both guides bonded through the distributed crowned layer on the real land walls, the area-mean axial shear on any land is **1.0–3.5 MPa** and the land-edge peak is **3.6–16.8 MPa** (G = 500–1,500 MPa). This is the `rigidland`/`midplane` regime of 22 November (3.4–4.6 MPa peaks at nh = 8), and 6–40× below the `rod` model's 103–306 MPa. Peak normal tractions are 7–36 MPa and are edge-concentrated (mesh-sensitive by ±15%).
4. **The rod map overstated the arm distortion.** The solid arm walls deform non-rigidly by **0.001–0.006 mm inside the land** and **0.016–0.064 mm at the ±1.62 mm socket ends** (rod map: 0.05 mm / 0.30–0.37 mm). The guide rotates 0.01–0.06° relative to its land.
5. **Crowned and uncrowned lands both clear 0.2° tilt against the solid arm.** Minimum gaps over the 26 ±0.2° tilts: **0.0742–0.0763 mm (uncrowned)** and **0.0785–0.0794 mm (crowned)**, against 0.0789 / 0.0804 mm for an undeformed body and 0.0007–0.044 mm for the rod-mapped body. The crown's benefit is about 0.003–0.004 mm here; it is no longer needed for the 0.025 mm probe offset at these steps.
6. **Validity limit (FAIL, kept visible).** The linear model imposes up to 0.85 rad of linearised rotation, and the peak body strain is 3.7% in the hub/arm region (2.4% of elements above 2%); the land bands stay below 0.7%. A geometric-nonlinearity check of the end-rotation case is in [§ 6](#6-geometric-nonlinearity-check).

## What was built

| File | Purpose |
|---|---|
| [`body_solid.py`](body_solid.py) | Crops the CAD at z = −44.9 / +40.9 mm (0.1 mm inside the proximal disk face and the distal anchor block), drops the two central posts (r < 3 mm, \|z\| > 33 mm, rigid D0/D1 masters in the plate model), meshes the lattice with TetGen, upgrades to P2 and solves with MKL PARDISO. D0 clamped, D1 one rigid body loaded by a unit wrench; EI = 96 mm / rotation (the plate model's convention). Variants: elastic rings, rigid R0–R3 ring bands, and rigid rings plus rigid per-rib land patches (the plate model's bare body). |
| [`body_bond.py`](body_bond.py) | The same body with both guides bonded: the distributed layer of [`coupled_land.py`](../evening_20261123/coupled_land.py) (91,448 area-weighted points on the actual inclined land walls, 8.00 mm² per land, tangential G/t, normal 2(1+ν)G/t, t(z) = 0.25 + crown(zh/0.25)² mm). Load cases: (a) the rod's relative D0→D1 rotation imposed on D1 with free D1 translation (pure end moment); (b) the archived station wrenches on the guides. Total = a·s + b, where s is the rod's local-to-mean moment ratio at the station (1.07 at −12 mm, 0.92 at +12 mm). |
| [`solid_arm_probe.py`](solid_arm_probe.py) | Exact FCL clearance with the body around each guide moved by the solid field relative to the bonded guide; same parts, 26 tilts, 0.5 mm refinement as [`rigid_arm_probe.py`](../evening_20261123/rigid_arm_probe.py). |
| [`strain_check.py`](strain_check.py) | Peak principal strain and linearised rotation of the solid field (validity of the linear model). |
| [`nonlinear_check.py`](nonlinear_check.py) | Total-Lagrangian St Venant–Kirchhoff P2 continuation of the end-rotation case with the exact finite rotation on D1 (tangent verified against finite differences to 2·10⁻¹¹). |
| [`validate.py`](validate.py) | Writes [`results/validation.json`](results/validation.json). |

## 1. Bare-body stiffness ([`results/conv_*/body_stiffness.json`](results/conv_q2/body_stiffness.json))

| Mesh (TetGen q / max tet vol) | Tets | DOF | EI, elastic rings | EI, rigid rings | EI, rigid rings + lands | GJ (elastic / rigid+lands) | EA (elastic / rigid) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10 / 2.0 mm³ | 70,571 | 437,406 | 41,214 | 44,283 | 44,931 | 41,891 / 48,476 | 153.2 / 169.1 |
| 5 / 0.4 | 130,278 | 774,219 | 40,548 | 43,630 | 44,256 | 40,219 / 46,757 | 151.4 / 167.3 |
| 3 / 0.3 | 188,766 | 1,075,065 | 40,439 | 43,531 | 44,163 | 39,997 / 46,534 | 151.0 / 167.0 |
| 2 / 0.3 | 327,949 | 1,792,176 | **40,368** | **43,483** | **44,102** | 39,853 / 46,450 | 150.8 / 166.8 |
| Plate model (Round 2 `m6_support.json`, bare) | | | | | 46,708 | 43,299 | |
| User database (`middle_stiffness_pa12`) | | | | 44,118 | | 41,990 | 166.694 |
| Rod M cell (body + Ø1.8 mm NiTi backbone, 40 GPa) | | | | 64,730 | | 57,488 | |

Units: N·mm² (EI, GJ) and N (EA). EIxx and EIyy agree to 0.01%. The last two mesh levels differ by 0.18%.

## 2. Bonded guides: tractions and relative motion ([`results/bond_q3/body_bond.json`](results/bond_q3/body_bond.json), q5 in [`bond_q5`](results/bond_q5/body_bond.json))

Step 1,709, finest completed mesh (q3), maximum over the eight lands, "local" moment scaling plus station wrench. Step 1,885 differs by < 1%.

| G, crown | Axial shear peak / area-mean | Normal peak / area-mean | Cross shear peak | Max layer slip | Guide − land rotation | Arm non-rigid: in land / socket ends |
|---|---:|---:|---:|---:|---:|---:|
| 500 MPa, none | 8.7 / 2.45 MPa | 21.2 / 2.58 MPa | 5.4 MPa | 0.0058 mm | 0.057° | 0.0050 / 0.064 mm |
| 500 MPa, 0.06 mm | 7.4 / 2.40 | 18.3 / 2.52 | 4.6 | 0.0061 | 0.062° | 0.0053 / 0.064 |
| 1,500 MPa, none | 16.8 / 3.45 | 36.4 / 3.43 | 11.4 | 0.0036 | 0.023° | 0.0032 / 0.060 |
| 1,500 MPa, 0.06 mm | 14.3 / 3.36 | 31.7 / 3.33 | 9.8 | 0.0038 | 0.025° | 0.0034 / 0.060 |

- The 67.5°/247.5° lands (bending plane) govern at z = −12 mm; at +12 mm all four lands carry 1.8–2.3 MPa area-mean.
- Split at G = 500 MPa (unscaled end moment / wrench only, area-mean axial): 2.2–3.0 / 0.6–2.6 MPa. Neither part dominates, unlike the `rod` model where 97% was kinematic.
- Mesh change q5 → q3: area-mean ≤ 4.5%, peak axial ≤ 13%, peak normal up to 15%. The 1.79 M-DOF q2 bonded run was **killed for lack of memory** (15 GB) and is not reported.
- The solid's own section rotation over the 24 mm around each station is 1.74× its uniform share: compliance concentrates in the arm/strut bays between the stiff hub rings. That is a property of the CAD, and it is kept.

## 3. Solid-arm clearance at ±0.2° tilt ([`results/solid_arm_probe.json`](results/solid_arm_probe.json))

| Station | Land | No tilt | Worst of 26 tilts (solid arm, G 500) | Undeformed body (23 Nov) | Rod-mapped body (21–22 Nov) |
|---|---|---:|---:|---:|---:|
| z = −12 mm | uncrowned | 0.1323 mm | **0.0762** (75° in-plane +) | 0.0789 | 0.0007 |
| | crowned 0.06 mm | 0.1385 | **0.0794** | 0.0804 | 0.0283 |
| z = +12 mm | uncrowned | 0.1335 | **0.0742** (60° in-plane +) | 0.0789 | 0.0172 |
| | crowned 0.06 mm | 0.1385 | **0.0785** | 0.0804 | 0.0440 |

Steps 1,709 and 1,885 agree to 0.0001 mm. The governing part is the guide in every case. Within 3 mm of the station (12 < r < 27 mm) the body moves up to 0.36 mm relative to the guide; that motion is in the unbonded neighbouring members. The largest relative motion in the probe patch (6.8 mm at z = −12 mm, 1.6 mm at +12 mm) is at the hub ring (r ≈ 8.5 mm, \|z − station\| ≈ 5 mm), far from the guide, and is a symptom of the large linearised rotations of § 5.

## 4. Comparison with the 22–23 November models

| Quantity | `rod` (22 Nov) | `rigidland` (22 Nov) | Strut cut faces on rod map (23 Nov) | **Whole-body solid (tonight)** |
|---|---:|---:|---:|---:|
| Peak axial shear, G 500 / 1,500, uncrowned | 103.6 / 306.4 MPa | 3.4 / 3.5 MPa | 124–126 MPa (G 500, crowned) | **8.7 / 16.8 MPa** |
| Area-mean axial shear (G 500) | 30.5 MPa | ~1.8 MPa | 44 MPa | **≤ 2.45 MPa** |
| Arm distortion in land / socket ends | 0.05 / 0.30–0.37 mm | — | — | **0.005 / 0.064 mm** |

The solid result is closest to `rigidland` (area-mean) and `midplane` (axial peaks 3.6–4.6 MPa at nh = 8), with land-edge peaks 2–5× higher because the layer here resolves the real inclined walls and the land edges. The `rod` field is ruled out as a bond demand.

## 5. Validity of the linear model ([`results/strain_check.json`](results/strain_check.json))

| Field (q5, G 500, crowned, step 1,709) | Peak principal strain | 99th percentile | Land bands | Max linearised rotation |
|---|---:|---:|---:|---:|
| End moment only | 3.65% | 2.47% | 0.74% | 0.85 rad |
| Station wrench only | 1.79% | 0.99% | 0.72% | 0.40 rad |
| Both | 3.74% at r ≈ 8.5 mm, z ≈ −17.9 mm | 2.41% | 0.67% | 0.85 rad |

The land bands are within small-strain range. The hub/arm junctions are not (FAIL in `validation.json`), so the hub-region field and anything it drives should be treated as first-order only.

## 6. Geometric-nonlinearity check

See [`results/nonlinear_check.json`](results/nonlinear_check.json) and the Evening Report for the outcome of this run's check.

## Checks ([`results/validation.json`](results/validation.json))

All checks pass except the deliberate small-strain validity check (§ 5). Highlights: rigid modes give zero force (≤ 1.6·10⁻¹⁴), uniform strain energy is exact (≤ 8·10⁻¹⁵), mesh volume equals the CAD lattice volume (≤ 3·10⁻⁷), EI converges to 0.18%, linear residuals ≤ 1.7·10⁻¹², station-wrench force closure ≤ 6.4·10⁻⁹ N.

## Reproduce

```bash
python -m pip install numpy scipy trimesh tetgen triangle pypardiso mkl python-fcl vtk numba clarabel shapely rtree networkx matplotlib
python -m pip install --ignore-installed pillow          # the system PIL is broken
export PYPARDISO_MKL_RT=$(python -c "import sys,glob;print(glob.glob(sys.prefix+'/lib/libmkl_rt.so*')[0])")
cd simulations/u4m2/lanes_20261113/evening_20261124
python body_solid.py --quality 10 --max-vol 2.0 --out results/conv_q10     # ~1 min each level
python body_solid.py --quality 5  --max-vol 0.4 --out results/conv_q5
python body_solid.py --quality 3  --max-vol 0.3 --out results/conv_q3
python body_solid.py --quality 2  --max-vol 0.3 --out results/conv_q2      # ~10 GB, run alone
python body_bond.py  --quality 5  --max-vol 0.4 --out results/bond_q5      # ~2 min
python body_bond.py  --quality 3  --max-vol 0.3 --out results/bond_q3      # ~3 min
python solid_arm_probe.py                                                 # ~2 min
python strain_check.py
python nonlinear_check.py --steps 8                                        # ~25 min, q10 mesh
python validate.py
```

Versions: Python 3.11.18, NumPy 2.4.6, SciPy 1.17.1, trimesh 5.2.2, tetgen 0.8.4, pypardiso 0.4.7 with MKL 2026.2.1, python-fcl 0.7.0.11, VTK 9.7.2, numba 0.68.1. pypardiso needs `PYPARDISO_MKL_RT`, the upper triangle for `mtype = 2`, and a fresh solver instance per factorisation (re-using one instance stalled Newton). The q2 bonded run needs more than 15 GB.

## Limitations

- Linear elasticity for the stiffness, bond and clearance results; PA12 E = 1,530 MPa, ν = 0.4; the adhesive G is assumed and unmeasured.
- The NiTi backbone is not in this body. The body is driven by the rod's end rotation (which includes the backbone's share of the moment) and the station wrenches; how the backbone is attached to the hub rings would change the curvature distribution.
- Pure end moment plus a per-station moment scale replaces the rod's shear distribution; D1 translations are free.
- Ropes, rope contact, friction, guide flexibility, adhesive failure, print tolerances and the as-printed land are not modelled. Clearance is rigid-CAD distance on the deformed geometry, not contact mechanics.
- Only the governing steps 1,709 and 1,885 were run, not the mission.
