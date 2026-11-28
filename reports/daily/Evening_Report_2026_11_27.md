# Evening Engineering Report — 2026-11-27

**Run:** scheduled evening run (20:01 US Eastern). The run actually started at **2026-11-27 20:02:05 EST (2026-11-28 01:02:05 UTC)**. Its 2-hour deadline was **22:02:05 EST (03:02:05 UTC)**. The publication time is recorded in the README entry and the completion message. The execution-model metadata could not be verified from inside the run (see § 7).

**Reporting interval:** from the previous evening run's start, **2026-11-26 20:01:44 EST (2026-11-27 01:01:44 UTC)**, to this run's start cutoff, **2026-11-27 20:02:05 EST (2026-11-28 01:02:05 UTC)**, plus this run's own results.

**Branch:** `claude/great-goodall-1wf2yh`. It was already contained in `origin/main` and was fast-forwarded to `origin/main` at `76d026c` before work began.

[Study and commands](../../simulations/u4m2/lanes_20261113/evening_20261127/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261127/HANDOFF.md) · [Same-day Morning Report](Morning_Report_2026_11_27.md) · [Same-day hub strain & fillet study](Hub_Strain_and_Fillet_Study_2026_11_27.md) · [Previous Evening Report](Evening_Report_2026_11_26.md) · [Summary figure](../../simulations/u4m2/lanes_20261113/evening_20261127/results/evening_20261127_summary.png)

## 1. Repository updates in the interval (already on GitHub before this run)

Each change is counted once, even where it appears on more than one branch.

| When (ET / UTC) | Change | Where |
|---|---|---|
| 2026-11-26 20:55 EST (27 Nov 01:55 UTC) | **26 Nov Evening Report.** CAD-consistent `L = 66 mm` sleeve attachment of the M6 NiTi backbone. Mission-wide rod-to-hub-bore minimum gap 0.39 mm at `ring_1`, with 0 contacts. | PR #49 → `main` 2026-11-27 02:28:58 EST (07:28:58 UTC) |
| 2026-11-27 07:24–08:08 EST (12:24–13:08 UTC) | **27 Nov Morning Report.** Geometrically nonlinear coupled M6 lattice + NiTi backbone. Axial compatibility is settled (+3.52 N rod force, 0.04 MPa sleeve shear). `ring_1` gap 0.57–0.98 mm with zero contact. NiTi bending strain 1.71%. | `m6-nonlinear-coupled-backbone` → `main` 09:15:32 EST (14:15:32 UTC) |
| 2026-11-27 08:36–09:08 EST (13:36–14:08 UTC) | **Hub-strain convergence & fillet study.** `q3 → q2.5` converged: `ring_0` 3.843% corner peak (0.5 mm gauge 0.786%), `ring_1` 0.5 mm gauge 1.376–1.397%. STL boolean collar fillets were rejected (new cusps). | `m6-sleeve-hub-strain-and-fillet` → `main` 09:15:32 EST; README link 09:17:15 EST (14:17:15 UTC) |
| 2026-11-27 13:47:17 EST (18:47:17 UTC) | Interactive U4+M2 tank inspection station and mission replay (two HTML pages, Codex). Not merged into `main`. No engineering numbers changed. | `codex/tank-inspection-station` (`13cca17`) |

No other branch holds newer engineering commits. `codex/guide-validation` is unchanged since 2026-11-21.

## 2. Priority chosen and why

Both same-day handoffs put the hub junction first: author true tangent-continuous fillets at `ring_0`/`ring_3` and `ring_1`/`ring_2` in native B-Rep CAD, then re-run the hub strain. The handoffs also leave the guide/body and rope/end-region interference questions closed by the latest evidence:

- 0 rod–bore contacts with a 0.57–0.98 mm gap (27 Nov morning);
- stride-1 FCL tilt closeout with 0 contacts (26 Nov).

So tonight's run took the hub junction. It is a CAD + FE item that fits within the 80-minute work window. One change from the plan: tonight's first finding was that the `ring_0` hotspot is a slot, not a fillet edge. The run therefore tested the geometric alternative (closing the slot) instead of stopping at the fillet result.

## 3. New work in this run

### 3.1 Native B-Rep model of the hub pocket ([`brep_hub_variants.py`](../../simulations/u4m2/lanes_20261113/evening_20261127/brep_hub_variants.py))

- **Frame:** the FE body `M6_lane_anchorC.stl` equals `cad/modules/Medium_Stiffness_96.step` rotated by **−22.5°** about z. The maximum deviation over 3,014 hub-region vertices is **0.00066 mm**.
- **What the `ring_0` corner really is:** each of the 8 ribs per hub end (3.0 mm wide) passes through a 3.6 × 3.1 mm socket in the hub ring. It is joined only through the socket ceiling at `|z| = 17.970 mm`, with **0.30 mm air gaps** on both sides and at the end, 2.0 mm deep. The archived 3.85% peak sits at that slot's ceiling corner on the `r = 8.5 mm` rim.
- **Native fillets** on all 114 concave pocket-zone edges:

  | R (mm) | Result |
  |---:|---|
  | 0.14 | **valid** (+1.05 mm³) |
  | 0.25 | **invalid** per BRepCheck |
  | 0.30, 0.50, 0.80 | **build fails** (32–48 faulty contours) |

  An R = 0.8–1.5 mm fillet cannot be built at this corner while the 0.30 mm slot exists.
- **`ring_1`:** all nearby edges are tangent-continuous or convex. There is no fillet target, so its strain is smooth-surface bending.

### 3.2 Slot-fill candidate and FE ([`hub_variant_fe.py`](../../simulations/u4m2/lanes_20261113/evening_20261127/hub_variant_fe.py))

The 16 pocket gaps were closed in B-Rep (valid single solid, +88.50 mm³, +0.089 g). The FE body is built by an OpenCASCADE double-precision union on the sewn FE lattice: watertight, one body, Ø8.40 mm bore preserved, +85.31 mm³. The fill stops 0.05 mm short of the open faces. The solver, loads and backbone (`L = 66 mm` sleeve, G = 500 MPa, crown 0.06 mm) are the same as in the 27 Nov study. Results at step 1,869:

| Case | Global peak | Slot root `ring_0` | **Arch crown `ring_0`** (peak / 0.5 mm / 1.0 mm gauge) | `ring_1` (peak / 0.5 mm) |
|---|---:|---:|---|---|
| Baseline q3 (179k tets) | 3.682% | 3.682% | 3.171% / **1.719%** / 1.092% | 3.288% / 1.317% |
| Baseline q2.5 (247k) | 3.846% | 3.846% | 3.135% / **1.905%** / 1.017% | 3.249% / 1.490% |
| Slot fill q3 (201k) | 3.470% | 2.367% (−36%) | 3.223% / **2.048%** (+19%) / 1.074% | 3.464% (+5%) / 1.392% |
| Slot fill q2.5/a0.40 (253k) | 3.503% | 2.044% | **3.503%** / 2.002% / 1.101% | 3.393% / 1.494% |

- **New finding: the arch crown governs the finite-gauge strain.** This is the concave crown of the rib arch just below the socket bottom (`r ≈ 9.4–9.7 mm, |z| ≈ 20.3 mm`). In the *unchanged* design it reaches 1.72–1.91% at 0.5 mm gauge and ~1.0% at 1.0 mm gauge. That is higher than `ring_1` (1.32–1.49%), which the 27 Nov study named as the governing finite-gauge site. The 27 Nov metric missed it because it averaged only around the element-peak location (the slot root), which also explains that study's low `ring_0` gauge value of 0.79%. The crown is above the ~0.98–1.18% PA12 endurance band.
- **Slot fill rejected:**
  - it removes the slot-root corner peak (−36% at q3);
  - but it moves the effective clamp outward and increases the governing crown strain (+19% at 0.5 mm gauge at q3), and at q2.5 the crown becomes the global element peak (3.50%);
  - it also raises M6 bending stiffness: bare `EI` 39,652 → 41,519 N·mm² (+4.7%), and 66,448 → 68,315 N·mm² (+2.8%) with the backbone. That would change the rod/mission stiffness assumption.

  The slot's design intent is unknown, and the user/designer should decide on it.

## 4. Baseline comparison and reproducibility

- **Reproduction:** in this environment the baseline reproduces the archived 27 Nov values. At q2.5, `ring_0` is 3.846% vs 3.843% and `ring_1` is 3.249% vs 3.237%. At q3, `ring_0` is 3.682% vs 3.747% (TetGen 0.8.4 gives 179,318 vs 178,517 tets).
- **Solver residuals:** all PARDISO residuals are ≤ 1.2 × 10⁻¹².
- **Steps:** steps 1,709 and 1,884 differ from step 1,869 by ≤ 1.5% at every site.
- **Inputs:** source `origin/main` `76d026c`. Dependency versions and commands are in the [study README](../../simulations/u4m2/lanes_20261113/evening_20261127/README.md#reproduction).

## 5. Failed checks, unsuccessful variants and interrupted studies (kept visible)

- **Convergence checks (FAIL):**
  - baseline arch-crown 0.5 mm gauge changes **+11%** from q3 to q2.5;
  - slot-fill arch-crown element peak rises **+9%** (3.22% → 3.28% → 3.50%).

  Both are recorded in [`validation.json`](../../simulations/u4m2/lanes_20261113/evening_20261127/results/validation.json); the other 12 checks pass.
- **R = 0.25 mm fillet:** invalid solid. **R ≥ 0.30 mm:** build failure.
- **Mesh-transfer approaches that failed before the OCC union worked:**
  - delta-slab union: 21 bodies;
  - hub-zone splice: TetGen segmentation fault;
  - `manifold3d.simplify`: clamp faces destroyed;
  - manifold float32 box union: zero-length edges;
  - exact-flush OCC fill: null-triangulated faces;
  - rounded-dimension fill: 3.0 M tets.

  The logs are in [`results/logs/`](../../simulations/u4m2/lanes_20261113/evening_20261127/results/logs/).
- **Slot fill q2.5/a0.25** was killed for lack of memory twice (~14 GB of the 15 GB limit). It was replaced by q3/a0.25 and q2.5/a0.40.
- **The R = 0.14 mm fillet variant has no FE result.** Its only FE path was the splice that crashed TetGen.

## 6. Remaining limitations

- Linear elastic FE at the three governing mission steps. No full 3,405-state envelope was run for the new crown site.
- The crown's gauge strain is not mesh-converged.
- The PA12 endurance band is a literature value, and the NiTi is modelled as linear 40 GPa.
- Neither variant is adopted. The repository CAD, guide positions, rope routing, masses, the **500 g head payload** and **U4+M2** are unchanged. No backbone end ferrule was added.
- There is no hardware evidence: no calibration, strain measurement, bench test or manufacturing qualification exists for any of these numbers.

## 7. Next-run handoff (also in [`HANDOFF.md`](../../simulations/u4m2/lanes_20261113/evening_20261127/HANDOFF.md))

1. **Converge the arch-crown gauge strain with local refinement** while keeping the global mesh at q3.
   - Accept when the 0.5 mm and 1.0 mm gauge strains change by < 5% over two refinements at steps 1,709 / 1,869 / 1,884; then run the full mission envelope for the crown.
   - Resource limit: global q2.5/a0.25 is at the 15 GB memory limit.
2. **Arch-crown geometry candidates in native B-Rep** (larger crown radius or deeper section), keeping the slot unless the designer approves closing it.
   - Accept when the solid is valid with the bore preserved, the crown's 0.5 mm gauge is ≤ ~1.2% with no new site above it, and the `EI` change is reported and fed into the rod/mission stiffness before any full-motion replay.
3. **Designer decision and bench work.**
   - Is the 0.30 mm rib/socket slot intentional?
   - Add an arch-crown gauge or DIC site (`|z| ≈ 20.3 mm, r ≈ 9.5 mm`) to the queued M6 hub strain test, together with the existing tolerance-stack and coupon tests.

**Execution model:** the task requested Claude Opus 5.5. The session's configured model identifier is `claude-opus-5-5`, but the `get_session` metadata tool was not available in this run, so the serving model was not independently verified.
