# Evening Engineering Report — 2026-11-23

**Run:** scheduled evening run. Started **2026-11-23 20:01:55 EST (2026-11-24 01:01:55 UTC)**. Budget deadline **22:01:55 EST (03:01:55 UTC)**.
**Reporting interval:** from 2026-11-22 20:01:55 EST (2026-11-23 01:01:55 UTC) to the cutoff at this run's start, 2026-11-23 20:01:55 EST (2026-11-24 01:01:55 UTC), plus the work done in this run.
**Branch:** `claude/great-goodall-1wf2yh`. It was already contained in `origin/main`, so it was fast-forwarded to `origin/main` at `7c2d006` before any work started. Mid-run checkpoint: `caa7ea7`.

[Evidence and commands](../../simulations/u4m2/lanes_20261113/evening_20261123/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261123/HANDOFF.md) · [Previous Evening Report](Evening_Report_2026_11_22.md) · [Crowned-land CAD](../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

## 1. Summary

The 22 November run left one main open question for the crowned M6 bond: how does the PA12 web actually strain at the 0.5 mm land? Its three fit-mismatch models put the bond demand anywhere between about 3 MPa (`rigidland`, load-driven) and about 100–300 MPa (`rod`, kinematic). This run took handoff item 2, a local solid model of the M6 rib with its bonded land.

- **Built and verified.** The new tools are:
  - a quadratic-tetrahedron (P2) solid solver for the actual CAD struts;
  - a structured graded mesher for the exact strut prism;
  - a coupled station model with four solid struts, a distributed crowned adhesive layer on the real inclined walls (8.00 mm² per land) and one rigid guide carrying the archived station wrench.

  Patch tests pass to 3·10⁻⁸ or better, and the free-strut field is mesh-converged to 0.14%. The 22 November `rod` and `rigidland` rows are reproduced exactly (48 rows, 0.0 MPa difference), and the wrench closure is 1.2·10⁻¹¹.
- **The local strut model failed its consistency check, and that failure is the main result.**
  - Driving the strut cut faces with the rod map (as handoff item 2 proposed) makes the eight struts carry **30–35× the rod model's cell bending moment**: 19.7 N·m against 0.65 N·m at step 1,709.
  - The CAD sections explain why. Each bonded strut is the arm of a zig-zag rib. It runs from the hub disk (z ≈ −5.5 mm) to a knee at r ≈ 30.6 mm, z ≈ −20.3 mm, and continues into further rib members. Its outer end is not a rigid section.
  - The resulting tractions (coupled: 126 MPa peak, 44 MPa area-mean axial shear on the 67.5°/247.5° lands, with a 1.2° guide rotation) are **not physical** and are not design values.
  - **The 3–300 MPa bracket is therefore still open.** One part is settled: the `rod` field is not a physical upper bound, because a strut forced to follow it at its ends deforms about 2× more over the land.
- **New risk for the clearance certification.** Relative to the land's rigid motion, the rod map distorts the arm walls around the guide by **0.050–0.054 mm inside the land** and **0.30–0.37 mm at the ±1.62 mm socket ends** (67.5°/247.5° arms). The crowned land's certified margins at 0.2° tilt (0.0284 / 0.0424 mm) are computed against this rod-mapped arm, so they are smaller than the model's own distortion. They are not model-independent until a solid rib solution exists.
- **Clearance bracket.** With an **undeformed** body around the guide (same parts, same 26 tilts of ±0.2°, exact CAD), the worst gap is **0.0789 mm (uncrowned) and 0.0804 mm (crowned)** at both stations. Against the rod-mapped body it was 0.0007 / 0.0283 mm (z = −12 mm) and 0.0172 / 0.0440 mm (z = +12 mm). The crown's benefit, and the failure of the uncrowned land, are produced by the rod map's distortion of the arms. Which land is needed depends on the real arm deformation, which has not yet been computed or measured.
- **No design change.** No CAD, guide position, rope bore, station, mass or solver input changed. The 500 g head payload and U4+M2 are kept, and no backbone end ferrule was added.

## 2. Repository updates in the reporting interval

Each change is listed once, even where it appears on several branches. Times are commit times.

| Time (EST / UTC) | Revision | Work | Where it is now |
|---|---|---|---|
| 22 Nov 20:29 / 23 Nov 01:29 | `6a6096c` | Previous evening run's Evening Report 2026-11-22: crowned bond-layer tractions, witness motion, bond motion with 0.2° tilt. Already reported in full in the [Evening Report 2026-11-22](Evening_Report_2026_11_22.md), so not counted again. | `main` |
| 23 Nov 01:06 / 06:06 | `7c2d006` | Merge of PR #44 (`claude/great-goodall-1wf2yh` → `main`). No content beyond `6a6096c`. | `main` |

There was no Morning Report for 23 November in the repository at the cutoff. No other branch received commits in the interval:

- `codex/guide-validation` was last updated on 21 Nov.
- `codex/m5-active-reset-load-export` was last updated on 21 Nov at 07:54 EST. It is still unmerged and has no committed results.
- `codex/internal-rope-guides`, `codex/kevin`, `codex/reach-extension-study` and `copilot/review-outdated-prototype-files` had no new commits.

**Plan changes.** The 22 November handoff ranked:

1. bench work (hardware);
2. a local solid M6 rib model (taken tonight);
3. a finer-axis tilt bisection.

Item 2 found that its proposed boundary conditions (strut cut faces driven by the rod map) are invalid. It is therefore re-specified as a whole-rib lattice model between the Round 2 master regions, with a stiffness validation step first. Item 3 is deferred, because it relies on the rod-mapped arm geometry that tonight's distortion result questions. A clearance re-check against a solid-arm geometry takes its place.

## 3. New work in this run

### 3.1 Solid strut solver and checks

[`strut_fe.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/strut_fe.py):

- crops a strut from `end_bellmouth_v1/M6_lane_anchorC.stl` with two capped planes and requires a single watertight body;
- meshes it with TetGen and upgrades the mesh to 10-node tetrahedra;
- assembles linear elasticity with PA12 E = 1,530 MPa, ν = 0.4 (the repository values);
- precomputes the bond-point operator H.

The bonded strut between its nodes (z = −16.75 to −6.5 mm at the −12 mm station, mirrored at +12 mm) is an exact prism: a convex 10-vertex section of 8.0 mm² that drifts radially at dr/dz ≈ −1.47. A patch field (uniaxial stress along the strut axis plus a rigid motion) is reproduced to 3.4·10⁻⁸ (TetGen mesh) and 2.9·10⁻¹² (prism mesh).

### 3.2 Free strut against the rod map (`solid` mismatch)

Both cut faces follow the rod map. The guide is not coupled. Results at step 1,709, h = 0.45 mm:

| Arm | Max non-rigid over land, rod / solid (z = −12 mm) | Axial strain over land, rod / solid |
|---|---:|---:|
| 67.5°, 247.5° | 0.051 / 0.109–0.111 mm | ±0.197 / ±0.316 |
| 157.5°, 337.5° | 0.007 / 0.019–0.020 mm | ±0.015 / ±0.025 |

- Changing h from 0.6 to 0.45 mm changes these by at most 0.14%. Moving the cut planes 0.75 mm inwards changes them by at most 2.6%. Steps 1,709, 1,710 and 1,885 differ by less than 0.1%.
- In the 22 November pad model this mismatch gives 148 MPa (crowned, G = 500 MPa) to 420 MPa (G = 1,500 MPa) axial-shear peaks and an 11.8° guide-to-web rotation. The rotation is not credible, so these rows are kept only as a record.

### 3.3 Coupled station

[`coupled_land.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/coupled_land.py) models one station:

- four solid struts on a structured mesh (0.5 mm section, 0.1 mm axial layers in the land band, 11–12k P2 tetrahedra and about 51–53k DOF each);
- the crowned layer on the actual walls (45,086 points per land; tangential stiffness G/t, normal stiffness 2(1+ν)G/t);
- one rigid guide with the archived station wrench.

Results for the crowned land, G = 500 MPa, step 1,709, z = −12 mm:

| Land | Peak axial shear | Peak normal | Area-mean axial shear | Max slip |
|---|---:|---:|---:|---:|
| 67.5° / 247.5° | 123.7 / 125.9 MPa | 165.5 / 163.2 MPa | 44.6 / 43.9 MPa | 0.085 mm |
| 157.5° / 337.5° | 20.9 / 23.6 MPa | 44.2 / 44.9 MPa | 5.3 / 4.9 MPa | 0.017–0.018 mm |

The guide rotates about 1.2° relative to the station frame. The production run (both stations, both moduli, crowned and uncrowned) and a three-level mesh refinement were started. Both were **stopped deliberately** once check 3.4 failed, so this case is single-mesh and not converged. It is archived only as an over-constrained record.

### 3.4 Boundary-condition consistency: failed

[`cell_moment.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/cell_moment.py) drives all eight struts of a station the same way and sums the moment on the inner cut faces:

| Step | z = −12 mm: solid / rod | z = +12 mm: solid / rod |
|---|---:|---:|
| 1,709 | 19,747 / 650 N·mm | 16,914 / 543 N·mm |
| 0 | 6,303 / 188 N·mm | 3,560 / 101 N·mm |

- The ratio is 30.4–35.4.
- The rod cell stiffness is 5.394 N·m/rad per 12 mm cell, so EI ≈ 64,700 N·mm². The Round 2 plate model gives a bare-body EI of 46,700 N·mm².
- The CAD sections show that the strut continues past z = −16.75 mm to a knee at r ≈ 30.6 mm (z ≈ −20.3 mm) and on into a 4.89 mm² member towards z ≈ −35 mm. The rib is a compliant zig-zag lattice.
- Clamping the strut's outer end to a plane section removes the compliance through which the module bends at roughly 6–8° per 12 mm cell. The local strut model cannot select between the mismatch models.

### 3.5 Rod-map distortion of the arm around the guide

[`socket_distortion.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/socket_distortion.py) measures the deviation of the rod-mapped arm walls from the land's least-squares rigid motion, at steps 1,709, 1,710 and 1,885:

| Arm | Inside the land | At the socket ends (±1.62 mm) |
|---|---:|---:|
| 67.5° / 247.5°, z = −12 mm | 0.054 mm | 0.371–0.373 mm |
| 67.5° / 247.5°, z = +12 mm | 0.050 mm | 0.296–0.297 mm |
| 157.5° / 337.5° | 0.007–0.008 mm | 0.043–0.057 mm |

The certified crowned margins (0.0284 / 0.0424 mm at 0.2° tilt) are smaller than this distortion. A solid PA12 arm cannot carry about 23% strain over 1.6 mm, so the margins depend on the body model. The direction of the error is unknown until the rib lattice is solved.

### 3.6 Clearance bracket with an undeformed body

[`rigid_arm_probe.py`](../../simulations/u4m2/lanes_20261113/evening_20261123/rigid_arm_probe.py) uses the same guide, caps and wire envelope, the 26 tilts of `tilt_mission.tilts`, 0.5 mm axial refinement and exact FCL distance. The body is undeformed around the guide.

| Station, land | Undeformed body | Rod-mapped body (21/22 Nov, steps 1,709–1,885) |
|---|---:|---:|
| z = −12 mm, uncrowned / crowned | 0.0789 / 0.0804 mm | 0.0007 / 0.0283 mm |
| z = +12 mm, uncrowned / crowned | 0.0789 / 0.0804 mm | 0.0172 / 0.0440 mm |

The no-tilt undeformed gap is 0.1406 mm, governed by the guide. The worst undeformed tilt is about the 75° in-plane axis; the worst rod-mapped tilt is about 165°. The real arm deformation is not bounded by these two cases. Only a solid rib-lattice solution or a bench measurement can place it.

## 4. Checks

All checks are in [`results/validation.json`](../../simulations/u4m2/lanes_20261113/evening_20261123/results/validation.json):

| Check | Result |
|---|---|
| Patch test | pass |
| Regression against 22 November (48 rows) | pass, 0.0 MPa |
| Free-strut mesh convergence | pass, 0.14% |
| Coupled wrench closure | pass, 1.2·10⁻¹¹ |
| Boundary-condition consistency | **fail**, ratio 30–35. This is the finding. |

## 5. Failed, interrupted and unsuccessful work

- **Graded TetGen meshing failed.** `tetgen` 0.8.4 segfaults with a background sizing mesh (`bgmesh`, `pyvista` 0.49.2). It was replaced by the structured prism mesher.
- **The first prism mesher placed the section with vertex means.** Many layer points then fell outside the mesh (barycentric coordinate down to −0.79). This was fixed by using the section area centroids; the worst coordinate is now −2·10⁻⁶.
- **Stopped runs.** The coupled production run and the coupled mesh-refinement run were stopped once the boundary conditions were shown to be invalid. Their logs end at the stop.
- **Not attempted.** A whole-module or whole-rib solid model (about 13,000 mm³ of lattice outside the end disks) was not attempted in the remaining window. A P2 model of that size needs an iterative solver or rib-wise condensation. It is the first handoff item.

## 6. Limits

- Linear, small-displacement, isotropic PA12 with no yield. The 30% free-strut strains are far outside PA12's elastic range, which confirms that the boundary conditions are wrong. They are not a strut-failure prediction.
- The adhesive modulus (500 / 1,500 MPa) is assumed. The adhesive, the as-printed crowned land and the bonded tilt are unmeasured.
- Distinguish:
  - rod-map kinematics (the controller replay and homogenised map);
  - rigid-CAD clearance (19–22 November);
  - tonight's local solid FE, which is over-constrained.

  None of them is hardware evidence. No calibration or physical test was performed, and nothing here is a manufacturing release.

## 7. Next-run handoff

The full text is in [`HANDOFF.md`](../../simulations/u4m2/lanes_20261113/evening_20261123/HANDOFF.md).

1. **Solid rib-lattice model between the Round 2 masters, with a stiffness check first.**
   - Use the D0 disk and the hub rings R_k (r < 8.6 mm at z ∈ [−20, −16.95] and [−6.5, −3.45] mm).
   - Accept only if the body EI is within 30% of the plate model (46,700 N·mm²). Then report mesh-converged tractions and the guide motion at steps 1,709 and 1,885.
   - Use rib condensation or an iterative solver; SuperLU on the whole lattice will not fit.
2. **Re-check the crowned clearance against a solid-arm geometry.** The brackets now exist: about 0.08 mm with an undeformed body and 0.0007–0.044 mm with the rod map. Report the gap at 0.2° tilt with the solid arm, and say whether the crown is still needed.
3. **Bench (hardware).**
   - Tilt ≤ 0.20° and offset ≤ 0.025 mm.
   - Land profile measured to 0.01 mm.
   - Adhesive lap-shear coupon.
   - **New:** a strain gauge or DIC on an M6 arm next to the land while the module is bent to the step-1,709 curvature.

**Resources:** 4 cores and 15 GB of memory. A coupled station takes about 6 min. Do not use TetGen `bgmesh`.
