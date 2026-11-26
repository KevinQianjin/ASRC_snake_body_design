# Evening Engineering Report — 2026-11-24

**Run:** scheduled evening run. Started **2026-11-24 20:02:31 EST (2026-11-25 01:02:31 UTC)**. Budget deadline **22:02:31 EST (03:02:31 UTC)**; expensive work was to stop by 21:37 EST (02:37 UTC).
**Reporting interval:** from 2026-11-23 20:02:31 EST (2026-11-24 01:02:31 UTC) to the cutoff at this run's start, 2026-11-24 20:02:31 EST (2026-11-25 01:02:31 UTC), plus the work done in this run.
**Branch:** `claude/great-goodall-1wf2yh`. It was already contained in `origin/main`, so it was fast-forwarded to `origin/main` at `a54cf53` before any work started. Mid-run checkpoint: `20decfa`.

[Evidence and commands](../../simulations/u4m2/lanes_20261113/evening_20261124/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261124/HANDOFF.md) · [Previous Evening Report](Evening_Report_2026_11_23.md) · [Crowned-land CAD](../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

## 1. Summary

The 23 November run left the M6 bond demand bracketed between about 3 MPa (`rigidland`) and 100–300 MPa (`rod`), and showed that the crowned land's certified clearance margins sat below the rod map's own distortion of the arms. Its handoff item 1 asked for a solid rib-lattice model, validated against the plate model's stiffness before any traction is used. This run built that model for the **whole M6 CAD lattice**, validated it, bonded both guides to it and then completed handoff item 2 (the clearance re-check against the solid arm).

- **Stiffness validated (acceptance met).** The whole lattice (10,487 mm³, P2 tetrahedra, up to 1.79 M DOF) converges to EI = 40,368 N·mm² with elastic hub rings and 43,483–44,102 N·mm² with the plate model's rigid ring masters. That is 86–94% of the plate model's 46,708 N·mm² (acceptance ±30%). It reproduces the user's database PA12 body values (EI 44,118 N·mm², EA 166.694 N) within 1.4% and 0.1%.
- **Comparator corrected.** The rod's M-cell EI of 64,730 N·mm², used on 23 November as the "rod cell stiffness", is the PA12 body (44,118) **plus the Ø1.8 mm NiTi backbone** (20,612 N·mm² at 40 GPa). It is not a body stiffness. The 23 November over-constraint verdict (30–35×) stands.
- **Bond demand settled at the load level.** The rod's ~47° end-to-end rotation (step 1,709/1,885) was imposed only on the rigid end masters, and both guides were bonded through the distributed crowned layer on the real inclined land walls and loaded by the archived station wrenches. The result is an area-mean axial shear of **1.0–3.5 MPa** on every land and land-edge peaks of **3.6–16.8 MPa** (G = 500–1,500 MPa). The `rod` model's 103–306 MPa is ruled out; the result sits with `rigidland`/`midplane`. The crown lowers the peaks by about 15%.
- **Arm distortion is 6–10× smaller than the rod map's.** Non-rigid deformation of the bonded arm walls relative to the land: 0.001–0.006 mm in the land and 0.016–0.064 mm at the socket ends (rod map: 0.05 / 0.30–0.37 mm). The guide turns 0.01–0.06° relative to its land.
- **Clearance against the solid arm (handoff item 2).** Worst gap over the 26 ±0.2° tilts: **0.0742–0.0763 mm uncrowned** and **0.0785–0.0794 mm crowned**, both well above the 0.025 mm probe offset. The crown's benefit is now 0.003–0.004 mm instead of the 0.027 mm seen against the rod-mapped body.
- **Validity limit kept visible.** Linearised rotations reach 0.85 rad and peak body strain is 3.7% at the hub/arm junctions (land bands < 0.7%). This fails the small-strain check. A total-Lagrangian check of the end-rotation case changes the end moment by 0.9% and the peak strain by 1.1%, so the linear results stand kinematically. The 3–4% hub strain is real, which makes it a PA12 material question (§ 3.5).
- **No design change.** No CAD, guide position, rope bore, station, mass or solver input changed. The 500 g head payload and U4+M2 are kept, and no backbone end ferrule was added.

## 2. Repository updates in the reporting interval

Each change is listed once, even where it appears on several branches. Times are commit times.

| Time (EST / UTC) | Revision | Work | Where it is now |
|---|---|---|---|
| 23 Nov 20:50 / 24 Nov 01:50 | `caa7ea7` | Previous evening run's checkpoint (solid strut model). | `main` |
| 23 Nov 20:54 / 24 Nov 01:54 | `e484300` | Evening Report 2026-11-23. Both commits are reported in full in the [Evening Report 2026-11-23](Evening_Report_2026_11_23.md) and are not counted again. | `main` |
| 24 Nov 00:09 / 05:09 | `ee91632` | [NiTi supplier and product specification report](../../niti_supplier_report.md) (new, repository root). It lists the two NiTi product forms (16 U-module leaves about 94 × 6 × 1.03–1.18 mm; two Ø1.80 × 96 mm M-module backbones fixed at both end disks), compares five suppliers' published forms, and recommends superelastic, straightened stock with lot-specific certificates and part-level fatigue tests. It notes that standard strip from several suppliers is thinner than the 1.03–1.18 mm leaf. Research only; no model input changed. | `main` |
| 24 Nov 08:43 / 13:43 | `a54cf53` | Merge of PR #45 (`claude/great-goodall-1wf2yh` → `main`), carrying the two 23 Nov commits and `ee91632`. | `main` |

There was no Morning Report for 24 November in the repository at the cutoff. No other branch received commits in the interval (`codex/guide-validation` last 21 Nov; `codex/m5-active-reset-load-export` last 21 Nov, still unmerged, no committed results; `codex/internal-rope-guides`, `codex/kevin`, `codex/reach-extension-study` and `copilot/review-outdated-prototype-files` unchanged).

The NiTi report's statement that each backbone is fixed at both end disks is consistent with the rod model adding the backbone EI in parallel with the body, which this run used to explain the 64,730 N·mm² comparator.

**Plan changes.** The 23 November handoff was followed in order. Item 1 was implemented for the whole lattice rather than one rib with symmetry conditions, because MKL PARDISO solves the full 0.8–1.8 M-DOF P2 model in 10–25 s. Item 2 followed directly. Item 3 (bench) is hardware and is not reported as done.

## 3. New work in this run

### 3.1 Whole-lattice solid model and stiffness validation

[`body_solid.py`](../../simulations/u4m2/lanes_20261113/evening_20261124/body_solid.py):

- crops `end_bellmouth_v1/M6_lane_anchorC.stl` with capped planes at z = −44.9 mm (0.1 mm inside the proximal disk face) and z = +40.9 mm (0.1 mm below the distal anchor block);
- keeps the one watertight lattice body (10,487 mm³) and drops the two central posts (r < 3 mm, |z| > 33 mm), which are rigid D0/D1 masters in the plate model (asserted in code);
- meshes with TetGen, upgrades to P2 and solves with MKL PARDISO; PA12 E = 1,530 MPa, ν = 0.4;
- clamps D0, makes D1 one rigid body and applies unit wrenches (EI = 96 mm / rotation, the plate model's convention).

| Mesh | DOF | EI, elastic rings | EI, rigid rings | EI, rigid rings + lands | EA (rigid rings) |
|---|---:|---:|---:|---:|---:|
| q10 / 2.0 mm³ | 437,406 | 41,214 | 44,283 | 44,931 | 169.1 N |
| q5 / 0.4 | 774,219 | 40,548 | 43,630 | 44,256 | 167.3 |
| q3 / 0.3 | 1,075,065 | 40,439 | 43,531 | 44,163 | 167.0 |
| q2 / 0.3 | 1,792,176 | **40,368** | **43,483** | **44,102** | **166.8** |
| Plate model, bare body | | | | 46,708 | |
| User database PA12 body | | | 44,118 | | 166.694 |

EI in N·mm². GJ: 39,853 (elastic rings) to 46,450 N·mm² (rigid rings + lands), against 43,299 (plate) and 41,990 (database). The elastic hub rings soften the body by 7% relative to the plate model's rigid-ring idealisation.

### 3.2 Bonded guides on the whole body

[`body_bond.py`](../../simulations/u4m2/lanes_20261113/evening_20261124/body_bond.py) bonds both guides (z = ±12 mm) to their four lands (67.5°, 157.5°, 247.5°, 337.5°) with the distributed layer from [`coupled_land.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/coupled_land.py): 91,448 area-weighted points, 8.00 mm² per land, t(z) = 0.25 + crown·(zh/0.25)² mm.

The rod map is applied **only to the end masters**, where it describes a rigid section:

- the relative D0→D1 rotation of the rod-mapped end faces (Kabsch fits, log map) is (−44.8°, 14.8°, 0.0°), 47.2° in total, at steps 1,709 and 1,885;
- D1's translation is free, so this is a pure end moment;
- each station's part is scaled by the rod's local-to-mean moment ratio (1.07 at −12 mm, 0.92 at +12 mm);
- the archived station wrenches load the guides.

Superposition is exact in this linear model.

| Step 1,709, q3 mesh, max over 8 lands | Axial shear peak / mean | Normal peak / mean | Slip | Guide − land rotation | Arm non-rigid, land / socket ends |
|---|---:|---:|---:|---:|---:|
| G 500 MPa, uncrowned | 8.7 / 2.45 MPa | 21.2 / 2.58 MPa | 0.0058 mm | 0.057° | 0.0050 / 0.064 mm |
| G 500 MPa, crowned 0.06 mm | 7.4 / 2.40 | 18.3 / 2.52 | 0.0061 | 0.062° | 0.0053 / 0.064 |
| G 1,500 MPa, uncrowned | 16.8 / 3.45 | 36.4 / 3.43 | 0.0036 | 0.023° | 0.0032 / 0.060 |
| G 1,500 MPa, crowned | 14.3 / 3.36 | 31.7 / 3.33 | 0.0038 | 0.025° | 0.0034 / 0.060 |

**Baseline comparison (step 1,709):**

| Model | Peak axial shear (G 500 / 1,500) | Area-mean (G 500) | Arm distortion, land / socket ends |
|---|---:|---:|---:|
| `rod` (22 Nov, nh = 8) | 103.6 / 306.4 MPa | 30.5 MPa | 0.05 / 0.30–0.37 mm |
| `midplane` (22 Nov) | 3.6 / 4.5 MPa | — | — |
| `rigidland` (22 Nov) | 3.4 / 3.5 MPa | ~1.8 MPa | — |
| Strut cut faces on rod map (23 Nov, crowned, G 500) | 124–126 MPa | 44 MPa | — |
| **Whole-body solid (tonight)** | **8.7 / 16.8 MPa** | **2.45 MPa** | **0.005 / 0.064 mm** |

The area-mean demand matches `rigidland`. The peaks are 2–5× higher than the 22 November pad models because the layer resolves the real inclined walls and the land edges. Kinematic and load parts are comparable (area-mean 2.2–3.0 and 0.6–2.6 MPa at G 500), unlike the `rod` model, where 97% was kinematic.

### 3.3 Solid-arm clearance at ±0.2° tilt (handoff item 2)

[`solid_arm_probe.py`](../../simulations/u4m2/lanes_20261113/evening_20261124/solid_arm_probe.py) moves the body around each guide by the solid field relative to the bonded guide (G 500 MPa), then repeats the archived exact-FCL probe (same parts, 26 tilts, 0.5 mm refinement).

| Station, land | Solid arm (tonight) | Undeformed body (23 Nov) | Rod-mapped body (21–22 Nov) |
|---|---:|---:|---:|
| z = −12 mm, uncrowned | **0.0762 mm** | 0.0789 | 0.0007 |
| z = −12 mm, crowned | **0.0794** | 0.0804 | 0.0283 |
| z = +12 mm, uncrowned | **0.0742** | 0.0789 | 0.0172 |
| z = +12 mm, crowned | **0.0785** | 0.0804 | 0.0440 |

Steps 1,709 and 1,885 agree to 0.0001 mm, and the guide governs in every case. Against the solid arm, both lands keep three times the 0.025 mm probe offset. The crown adds only 0.003–0.004 mm. The 21 November certification failure of the uncrowned land (665 / 317 yaw steps below the offset) was a rod-map artefact at these governing steps. This is shown only for steps 1,709 and 1,885, not for the whole mission.

### 3.4 Validity of the linear model

[`strain_check.py`](../../simulations/u4m2/lanes_20261113/evening_20261124/strain_check.py) (q5, G 500, crowned, step 1,709):

- peak principal strain 3.74% at r ≈ 8.5 mm, z ≈ −17.9 mm (hub ring / arm junction);
- 99th percentile 2.4%, 2.4% of elements above 2%;
- land bands 0.67%;
- maximum linearised rotation 0.85 rad.

The hub region is outside small-strain linear elasticity (**FAIL**, kept in `validation.json`). Inside the probe patch, the hub ring moves 6.8 mm relative to the guide at z = −12 mm (1.6 mm at +12 mm); within 3 mm of the guide, the body's relative motion is ≤ 0.36 mm (in unbonded neighbouring members).

### 3.5 Geometric-nonlinearity check

[`nonlinear_check.py`](../../simulations/u4m2/lanes_20261113/evening_20261124/nonlinear_check.py) repeats the end-rotation case (no guides, no wrench) with a total-Lagrangian St Venant–Kirchhoff P2 model:

- the exact finite rotation (47.2°) is applied on D1, with D1 translation free;
- the load goes in 8 increments with full Newton, the consistent tangent (verified against finite differences to 2·10⁻¹¹) and a linear predictor;
- it uses the q10 mesh (437 k DOF): 40 Newton iterations, 25 min, final residual ≤ 4·10⁻⁹ at every increment.

| Quantity (same 47.2° rotation) | Nonlinear | Linear | Ratio |
|---|---:|---:|---:|
| End moment | 350.2 N·mm | 353.4 N·mm | 0.991 |
| Peak principal strain (Green / linear) | 3.22% | 3.25% | 0.989 |
| 99th-percentile strain | 2.49% | 2.51% | 0.99 |
| Peak strain in the land bands | 0.45% | 0.45% | 1.01 |
| Arm socket non-rigid deformation (exact rigid fit) | 0.040–0.057 mm | — | — |

Geometric nonlinearity changes the end moment and strains by about 1%. The large linearised rotations therefore do not invalidate the linear bond and arm-distortion results, and the nonlinear arm distortion (0.040–0.057 mm) agrees with the linear small-rotation value (0.016–0.064 mm). The 3–4% hub/arm strain is a real strain level, not a linearisation artefact. It is now a material question: PA12 is modelled as linear elastic here, and no PA12 yield or fatigue limit at that strain is established by this run. The check excludes the guides, the wrench and the backbone, and it used the coarsest mesh.

## 4. Checks ([`validation.json`](../../simulations/u4m2/lanes_20261113/evening_20261124/results/validation.json))

| Check | Result |
|---|---|
| Rigid-body modes → zero force; uniform strain energy exact; mesh volume = CAD (4 meshes) | ≤ 1.6·10⁻¹⁴; ≤ 8·10⁻¹⁵; ≤ 3.2·10⁻⁷ — **pass** |
| EI mesh convergence, q3 → q2 | 0.18% — **pass** |
| EI within 30% of the plate model (all three master variants) | 0.86–0.94 — **pass** |
| EI against the database PA12 body | 0.91 (elastic rings) — **pass** (±15%) |
| Linear residuals; station-wrench force closure | ≤ 1.7·10⁻¹²; ≤ 6.4·10⁻⁹ N — **pass** |
| Area-mean axial shear, q5 → q3 | ≤ 4.5% — **pass** |
| Peak axial shear, q5 → q3 | ≤ 13% — reported (edge peak) |
| Solid-arm gap at 0.2° tilt > 0.025 mm (8 cases) | 0.0742–0.0794 mm — **pass** |
| Peak body strain < 2% (small-strain validity) | 3.74% — **FAIL** (hub/arm junctions) |
| Tangent of the nonlinear model vs finite differences | 2·10⁻¹¹ — **pass** |
| Total-Lagrangian end rotation: converged to full load; moment and peak strain vs linear | yes; 0.991; 0.989 — **pass** |

## 5. Failed, interrupted and unsuccessful work

- **The q2 bonded run (1.79 M DOF plus layer) was killed for lack of memory** (15 GB), twice. The first time it ran alongside another job, the second time alone. Bond results stop at q3 (1.08 M DOF). The q2 bare-stiffness run had also been killed once when it overlapped other jobs; it was re-run alone and completed.
- **Small-strain validity failed** in the hub region (§ 3.4).
- **First two nonlinear attempts stalled.** Newton's residual stuck at 0.96. The cause was the iterate: rotating D1 rigidly with the neighbouring nodes fixed drives the adjacent elements into St Venant–Kirchhoff compressive collapse. A consistent linear predictor per increment fixed it (quadratic convergence to 4·10⁻⁹). The tangent itself was verified against finite differences.
- Surface decimation of the CAD to cut the tetrahedron count was tried and rejected: at 50% reduction the surface deviated by 1.9 mm and self-intersected.

## 6. Limits

- Linear elasticity for stiffness, bond and clearance; PA12 E = 1,530 MPa, ν = 0.4; adhesive G assumed (500 / 1,500 MPa); no adhesive failure model.
- The NiTi backbone is not in the solid body. The body is driven by the rod's end rotation, which already includes the backbone's share of the moment. How the backbone couples to the hub rings is not modelled.
- Pure end moment plus a per-station moment scale replaces the rod's actual shear distribution.
- Only steps 1,709 and 1,885 (the governing left-yaw steps) were run. This is not a mission certification.
- Ropes, rope contact, friction, guide compliance, print tolerances, the as-printed land and the bonded tilt are not modelled or measured. Clearance is rigid-CAD distance on a deformed geometry, not contact mechanics.
- Simulation only. Nothing here is hardware evidence or a manufacturing release.

## 7. Next-run handoff

The full handoff is in [HANDOFF.md](../../simulations/u4m2/lanes_20261113/evening_20261124/HANDOFF.md). In priority order:

1. **Mission envelope by linear superposition (simulation, about 60 min).** The bonded body is linear. Three unit end rotations and twelve unit guide-wrench fields (one factorisation) give tractions and arm motion at all 3,405 steps. Run the solid-arm FCL probe on the low-margin steps. *Acceptance:* the mission maximum area-mean and peak tractions per land; the minimum solid-arm gap at 0.2° tilt over the 787 + 430 archived low-margin steps for both lands.
2. **Hub-junction strain with the backbone (simulation).** Geometric nonlinearity is shown to be about 1%, so the open item is the 3–4% hub/arm strain. Add the Ø1.8 mm backbone (fixed at both end disks per the NiTi report) as a beam coupled to the end masters, and to the hub rings only if the CAD bore is a fit. Report the body/backbone moment split and the hub peak strain at step 1,709 (q5, linear is enough), plus a local refinement at the peak site. *Acceptance:* the converged hub peak strain with the backbone, compared with 3.7%, and compared with a PA12 strain limit that is cited, not assumed.
3. **Bench (hardware, unchanged).** Tilt ≤ 0.20° and offset ≤ 0.025 mm; a lap-shear coupon on PA12 at a 0.25–0.31 mm gap. Strain gauge or DIC on one M6 arm next to the land **and at the hub/arm junction near z ≈ −18 mm, r ≈ 8.5 mm**, the new peak-strain site. Do not report this item as done in simulation.
