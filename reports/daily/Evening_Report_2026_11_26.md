# Evening Engineering Report — 2026-11-26

**Run:** scheduled evening run (20:01 US Eastern). The actual run started at **2026-11-26 20:01:44 EST (2026-11-27 01:01:44 UTC)**, with a deadline 2 hours later of **22:01:44 EST (03:01:44 UTC)**. Execution-model verification: the configured model is Claude Opus 5.5. The `get_session` metadata tool was not available in this run, so the model actually serving the run could not be confirmed.
**Reporting interval:** **2026-11-25 20:01:44 EST (2026-11-26 01:01:44 UTC)** to the cutoff at this run's start, **2026-11-26 20:01:44 EST (2026-11-27 01:01:44 UTC)**, plus this run's own results.
**Branch:** `claude/great-goodall-1wf2yh`, fast-forwarded to `origin/main` at `dfd27da` (PR #48 merged) before work began.

[Study and commands](../../simulations/u4m2/lanes_20261113/evening_20261126/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261126/HANDOFF.md) · [Same-day Morning Report](Morning_Report_2026_11_26.md) · [Previous Evening Report](Evening_Report_2026_11_25.md) · [Summary figure](../../simulations/u4m2/lanes_20261113/evening_20261126/results/evening_20261126_summary.png)

## 1. Repository updates in the interval (already on GitHub before this run)

Each change is counted once, although several appear on more than one branch.

| When (ET / UTC) | Change | Where |
|---|---|---|
| 2026-11-25 20:02–20:50 EST (26 Nov 01:02–01:50 UTC) | **25 Nov Evening Report.** Whole-mission superposition envelope of the bonded solid M6 model: bond demand, a sampled 0.2° tilt sweep, and a hub strain of 3.81% at step 1,869. | PR #46 → `main` 2026-11-26 00:12:37 EST (05:12:37 UTC) |
| 2026-11-25 20:05 EST – 2026-11-26 00:06 EST (26 Nov 01:05–05:06 UTC) | First mechanical retention coupons for the U-module NiTi leaf, and the U-leaf joint reversal and compression load-path check (Codex). | PR #47 → `main` 2026-11-26 00:13:14 EST (05:13:14 UTC) |
| 2026-11-26 10:19–11:46 EST (15:19–16:46 UTC) | **26 Nov Morning Report.** The NiTi backbone was added to the M6 solid model and the hub strain mesh-converged to **4.17–4.21%**. A stride-1 FCL tilt closeout found 0 contacts and a worst drop of 0.000097 mm. The edition was renamed from "Evening" to "Morning" and US Eastern Time was adopted. The report flagged **possible backbone contact with the `ring_0` bore (4.25 mm offset > 3.30 mm clearance)**. | PR #48 → `main` 2026-11-26 11:46:06 EST (16:46:06 UTC) |

No other branch held engineering commits newer than `main`. `codex/u-leaf-mechanical-joint` is already merged.

## 2. Priority chosen and why

The morning handoff listed two items: (a) a hub/arm fillet and (b) a backbone-to-`ring_0` bore clearance check. The task instructions give priority to interference between the rope or rod and the guide or body. Item (b) also decides where the fillet should go, so it was taken first. While reviewing the morning model against the CAD, a modelling inconsistency appeared that changes the answer to (b):

- **CAD fact (measured tonight):** the M6 rod is carried in integral **Ø1.85 mm sleeves over `|z| = 33…48 mm`**. The evidence is ray-casting 34,560 rays from the axis of `M6_lane_anchorC.stl`. It agrees with `lane_design.json` (`rod_support_length_per_end_mm = 15`) and with the installation guide ("bond only the 15 mm at each end … 66 mm free to bend").
- **Morning model:** the rod was clamped at the FE cut faces, `z = −44.9 / +40.9 mm`, giving a free span `L = 85.8 mm`. That model, and its contact flag, do not represent the built geometry.

## 3. New work in this run

### 3.1 CAD-consistent backbone attachment in the solid FE (`bore_fe.py`)

The q5 bonded solid body was rebuilt (130,278 tets, 762,645 reduced DOFs, G = 500 MPa, 0.06 mm crown). The 15 kinematic unit fields were solved for the morning attachment and for the CAD attachment. The CAD attachment is a rod from sleeve tip to sleeve tip, `L = 66 mm`, rigidly offset 7.9 mm from the D1 reference. Rigid poses of the four Ø8.40 ring bands and of D1 were extracted for all 3,405 mission states.

| q5, same mesh | Morning attachment | **CAD attachment** |
|---|---:|---:|
| Equivalent EI over 85.8 mm | 60,404 N·mm² (−6.7% vs rod model) | **66,501 N·mm² (+2.7% vs rod model's 64,730)** |
| Backbone share of D1 moment, steps 1,709 / 1,869 | 24.8% / 23.5% (morning values reproduced exactly) | **20.7% / 18.7%** |
| Peak \|principal strain\|, steps 1,709 / 1,869 | 3.467% / 3.485% | **3.375% / 3.306%** |
| Peak location, step 1,869 | `z = −17.9 mm` (`ring_0` hub/arm corner) | `z = −5.2 mm` (`ring_1` side) |

### 3.2 Backbone vs hub-ring bore over the mission (`bore_contact.py`, `convergence.py`, `sensitivity.py`)

| Level | Coverage | Min gap to the 3.30 mm radial clearance | States over clearance |
|---|---|---:|---:|
| L0 morning metric (reproduced: 4.248 mm at 1,869 vs published 4.247) | 3,405 | −0.948 mm (`ring_0`) | 664 |
| **L1 linear, CAD sleeves** (7 sections per 3.05 mm bore band, ring tilt included) | **3,405, complete mission** | **0.650 mm** (`ring_1`, step 1,866) | **0** |
| **L2 geometrically nonlinear elastica, CAD sleeves** (exact SO(3) chain lift, arc-length-preserving; rod h = 1 mm; penalty contact on the real bore bands) | 737 states (stride 5 plus targeted), all 11 phases | **0.387 mm** (`ring_1`, step 1,866, left return, 46.7°) | **0** (0 N) |
| L2 converged (continuation to h = 0.25 mm) | steps 1,866 / 1,869 / 1,709 | 0.393 / 0.409 / 0.607 mm | 0 |

- **Result: the morning `ring_0` contact flag is withdrawn.** It was an artefact of the 85.8 mm attachment. With the sleeves modelled, the `ring_0` offset is 1.98 mm (L1) and 1.50 mm (L2).
- **New governing location: `ring_1` (z = −5 mm) during both yaw excursions near 47°.** Per-ring L2 minimum gaps are `ring_0…ring_3` = 1.50 / 0.39 / 0.76 / 2.53 mm. Of the 737 L2 states, 148 have a gap < 1.0 mm and 67 have a gap < 0.5 mm.
- **NiTi bending strain** peaks at **1.62%** at h = 1 mm (1.53% converged). That is about twice the uniform-curvature estimate of 0.77% for 47° over 96 mm. The linear 40 GPa rod model has not been validated at this strain.

### 3.3 Failures, unsuccessful variants and sensitivity (kept visible)

- **First full-mission L2 sweep rejected.** It used h = 0.5 mm with 400 solver evaluations and was under-converged: it gave a 0.509 mm minimum gap against 0.393 mm converged, which is **unconservative by 0.12 mm**. It is archived as `results/superseded_h0p5_*` and not used. The adopted h = 1.0 mm setting is 0.005–0.008 mm conservative against the converged value.
- **First nonlinear lift rejected.** Adding the linear translations directly produced a sleeve-tip chord (≈ 66.3 mm) longer than the 66 mm rod and an unphysical 9.9% kinked-rod strain. It was replaced by the arc-length-preserving lift, which agrees with L1 within 0.035 mm below 15°.
- **Fixed-chord bound:** pinning the rod to the lifted sleeve-tip chord puts **`ring_0` in contact (−0.68 mm, ≈ 80 N at 1,866)**. It is judged non-physical, for three reasons:
  - the free rod settles 1.19–1.30 mm short of the lifted chord;
  - that mismatch matches the omitted second-order shortening of the lattice shear offsets (`Σδ²/2ℓ` = 1.85–1.98 mm);
  - enforcing the chord would need ≈ 1,800–2,000 N of rod tension.

  It nevertheless shows that **body–rod axial compatibility is the decisive quantity this model cannot resolve**.
- **Validation:** 11 of 11 automated checks pass ([`validation.json`](../../simulations/u4m2/lanes_20261113/evening_20261126/results/validation.json)), covering:
  - CAD sleeves and bore;
  - reproduction of the morning model;
  - PARDISO residuals ≤ 2.8×10⁻¹³;
  - exact-arc test;
  - convergence;
  - L1/L2 agreement;
  - phase coverage;
  - rotation lift;
  - the figure.

## 4. Remaining limitations

- The body FE is linear. The nonlinear lift is an approximation, and body–rod axial compatibility is unresolved.
- The sleeves are treated as rigid. Rod bond compliance is ignored.
- **There is no tolerance stack.** Bore eccentricity, sleeve concentricity and rod straightness from printing and assembly could consume a 0.39 mm nominal gap.
- The hub-strain change under the CAD attachment is q5 only. The refined-mesh corner value (4.17–4.21%) belongs to the superseded attachment and was not recomputed.
- The NiTi strain of 1.5–1.6% lies outside any validated range for the linear rod model.
- No hardware, material or bench evidence exists. Nothing here is a physical validation or a manufacturing release.

## 5. Next-run handoff (summary; full version in [HANDOFF.md](../../simulations/u4m2/lanes_20261113/evening_20261126/HANDOFF.md))

1. **Geometrically nonlinear coupled body + rod model.** Settle axial compatibility and the `ring_1`/`ring_0` gap at 47°, and report rod tension and sleeve-bond shear. *Accept:* the model matches the q5 ring poses within 2% below 15°, and the gap is ≥ 0.25 mm or the contact force is fed back into the hub-strain FE.
2. **Recompute the hub strain on the q3/q2.5 meshes with the CAD rod attachment, then the fillet study** at the confirmed hotspot. *Accept:* < 5% mesh change, stated against the 15–18 MPa PA12 endurance band.
3. **Bench (gating) and tolerance stack.** Ring-bore and sleeve concentricity, rod straightness, a feeler or endoscope check at `ring_1` at a 47° left-yaw bend, plus the unchanged socket, lap-shear, DIC and U1 leaf-joint items.

## 6. Source revisions and reproduction

- **Base:** `origin/main` `dfd27da`.
- **New scripts:** `bore_fe.py`, `bore_contact.py`, `convergence.py`, `sensitivity.py`, `summarize_and_validate.py` in [`evening_20261126/`](../../simulations/u4m2/lanes_20261113/evening_20261126/).
- **Inputs:** `evening_20261125/results/rod_steps.npz` (3,405 states) and `M6_lane_anchorC.stl`.
- **Environment:** Python 3.11.18, numpy 2.4.6, scipy 1.17.1, trimesh 5.2.2, tetgen 0.8.4, pypardiso 0.4.7.
- **Runtime:** FE ≈ 160 s, mission sweep ≈ 8 min on 4 cores.
- **Unchanged:** no CAD, guide position, rope routing, mass, 500 g payload or solver input was changed, and no backbone end ferrule was added.
