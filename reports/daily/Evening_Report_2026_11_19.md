# Evening Engineering Report — 2026-11-19

**Edition:** Evening Report (scheduled 20:01 US Eastern Time).
**Run start:** 2026-11-19 20:01:53 EST (2026-11-20 01:01:53 UTC). **Budget deadline:** 2026-11-19 22:01:53 EST (2026-11-20 03:01:53 UTC).
**Reporting interval:** 2026-11-18 20:01:53 EST (2026-11-19 01:01:53 UTC) to the run start above, the cutoff for repository updates. Results produced during this run are reported separately in section 3.
**Working branch:** `claude/great-goodall-1wf2yh`. It was already contained in `main` and was fast-forwarded to `main` at `e285061`. Execution model: see the completion message.

[Evidence and commands](../../simulations/u4m2/lanes_20261113/evening_20261119/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261119/HANDOFF.md) · [Candidate CAD](../../cad/lanes_u4m2/m6_bond_gap_20261119/README.md) · [Extreme-test round 1](../../simulations/u4m2/extreme_tests/round1_20261119/README.md)

## 1. Summary

This run addressed the tightest guide/body gap of the 500 g mission. At the M6 z = −12 mm guide, the round-1 extreme tests found **0.020932 mm** at the left-yaw step 1,710, with contact after a 0.025 mm rigid shift. All results are simulations on the actual repository CAD and the archived mission deformation.

- **Candidate: a 0.25 mm land bond gap at the four M6 outer-web sockets** (V3: 0.15 mm), at both M6 ±12 mm stations. The fine exact gap rises to **0.06733 mm** at z = −12 mm (3.2×) and **0.08284 mm** at z = +12 mm (2.4× from 0.03431 mm). The rope bores (17/17 sections per station), land length, flare, wall, stations and webs are unchanged, and the mass changes by −0.0016 g per station.
- **No contact in the screened mission.** The coverage screen checked 406 station-steps across all 11 phases (loaded startup → insertion → right yaw and return → left yaw and return → pitch up/down and returns → withdrawal) against four bond gaps (0.15/0.20/0.25/0.30 mm). A second closure screen checked V3 and the candidate at **every** M6 ±12 mm step whose archived sampled bound is below 0.040 mm. In total, 787 (z = −12 mm) and 430 (z = +12 mm) steps were checked exactly. The candidate's smallest gap is **0.06674 mm** (z = −12 mm, step 1,709) and **0.08239 mm** (z = +12 mm), with **zero contacts**.
- **Angular misalignment is the real tolerance.** Rotating the guide rigidly about its plate axes closes the gap much faster than translating it. V3 touches at −0.1° about CAD x. The candidate stays clear to **±0.2° about every axis** at both stations and first touches at −0.25° (z = −12 mm) and +0.3° (z = +12 mm). Measured tilt after bonding therefore becomes the acceptance quantity for the bench.
- **Rejected variants.** A shorter 0.3 mm land splits every cap at the 0.45 mm lockwire groove, giving 8 cap bodies instead of 4. A steeper flare, slope 2.0, gives no gain, because the witness lies on the land edge, not on the flare.
- **Costs and open items.** The thicker bond has about 0.6× the shear stiffness (G·A/t). It must still take up to 0.0545 mm land movement, a nominal shear of 22% compared with 36% for V3. Adhesive selection, printed gap, tilt after bonding and bond strength are unmeasured. This is **not** a manufacturing release.

## 2. Repository updates in the reporting interval

The table lists previously completed work. Each change is counted once, even where it appears on several branches. `codex/guide-validation` is identical to `main` at `e285061`. No other branch changed in the interval: `codex/kevin` was last changed 13 Nov, `codex/internal-rope-guides` 14 Nov, `codex/reach-extension-study` 6 Nov and `copilot/review-outdated-prototype-files` 12 Nov.

| Time (ET / UTC) | Revision | Change |
|---|---|---|
| 2026-11-18 20:36:58 EST / 2026-11-19 01:36:58 UTC | `ff8494d` (merged by PR #33, `1c10188`, 21:51 EST) | [18 Nov Evening Report](Evening_Report_2026_11_18.md): bow-tie rotating-seat sizing and Ø0.6 mm pin for the M5 guides. |
| 2026-11-18 23:28:56 EST / 2026-11-19 04:28:56 UTC | `e950339` (PR #34) | Retained rotating guide validated on the machined M5 webs. |
| 2026-11-19 01:00:53 EST / 06:00:53 UTC | `a147217` (PR #35) | [M5 seat coupon, hub relief and the re-equilibrated shared C-rope bore](../projects/rope_routing/M5_Seat_and_Shared_Bore_2026_11_19.md). |
| 2026-11-19 02:44:16 EST / 07:44:16 UTC | `00fa1ba` (PR #36) | [Full 500 g yaw and ±90° pitch cycle](../projects/motion_control/Yaw_Pitch_Closeout_2026_11_19.md): 1,380/1,380 targets, 3,405 states, tension 2.901–21.554 N, minimum tank gap 8.056 mm. The closest full-mesh guide/web gap was 0.02047 mm at M6 z = −12 mm. |
| 2026-11-19 03:21:38 EST / 08:21:38 UTC | `215831f` (PR #37) | README streamlined, and the 500 g front assembly documented. |
| 2026-11-19 04:41:13 EST / 09:41:13 UTC | `24490d1` (merged `89b32a9`) | U-module leaf-spring pairs shown in the installation guide. |
| 2026-11-19 10:45:24 EST / 15:45:24 UTC | `e285061` | [Extreme-test plan](../../nextstep/README.md) and [round-1 results](../../simulations/u4m2/extreme_tests/round1_20261119/README.md). M6 gap 0.08438 mm straight → 0.020932 mm bent at step 1,710. Pitch-return sliding floor lost between μ = 0.16 and 0.17. Trial U1 blade strain peak 1.586%. |

No Morning Report file exists for 19 November. The Codex work above is today's same-day engineering update.

**Change from the previous plan.** The 18 November handoff asked for retained-seat CAD on M5, which `e950339`/`a147217` then delivered, and for an M6 screen. The round-1 extreme tests made the M6 −12 mm gap the smallest geometric margin of the whole mission, and its bench handoff asked for M6 gap measurement. The brief gives priority to guide/body interference, so this run went to the M6 geometry rather than to the M5 pin-contact refinement. The M5 seats are already redesigned. The M6 bonded socket was untouched since V3.

## 3. New work in this run

### 3.1 Reproduction

The round-1 `m6_clearance.py` at the 0.5 mm span reproduced **0.020468 mm** exactly. The new `m6_socket_screen.py` reproduces the round-1 fine value 0.020932 mm and the straight value 0.084376 mm to 1e-9 mm. Rebuilding V3 from `guides_v3/build.py` gives the committed M6 meshes with identical vertices and volumes. Only the face order in the STL files differs.

### 3.2 Variants and full-triangle coverage screen

| Station | V3 0.15 mm | 0.20 mm | **0.25 mm** | 0.30 mm |
|---|---:|---:|---:|---:|
| Straight assembly gap | 0.08438 | 0.11250 | **0.14063** | 0.16875 |
| −12 mm, smallest over 204 steps (0.5 mm span) | 0.02047 | 0.04361 | **0.06676** | 0.08991 |
| −12 mm, step 1,710, fine 0.125 mm | 0.020932 | 0.044137 | **0.06733** | 0.090514 |
| +12 mm, smallest over 202 steps | 0.03396 | 0.05817 | **0.08239** | 0.10661 |
| +12 mm, step 1,709, fine 0.125 mm | 0.03431 | 0.058587 | **0.08284** | 0.107091 |

All gaps are in mm. The screened steps were the 60 smallest archived sampled bounds per station, the minimum of every phase and every 25th step. The governing steps lie in the left-yaw outward and return passes. The guide body has the smallest gap in each variant. The caps and lockwire envelope have more clearance. Per-step data for all variants: [coverage_screen.csv](../../simulations/u4m2/lanes_20261113/evening_20261119/results/coverage_screen.csv).

**Choice of 0.25 mm.** It roughly triples the worst gap, keeps the bonded land length and area, and is within the 0.1–0.3 mm bondline range often quoted for structural epoxies, which must be confirmed for whichever adhesive is selected. 0.30 mm gives more clearance but a thicker, softer bond. It is the fallback if the measured tilt exceeds about 0.2°.

### 3.3 Angular-misalignment sensitivity (new)

| Station, step | Axis | V3 contact-free range | Candidate contact-free range |
|---|---|---|---|
| −12 mm, 1,710 | CAD x | −0.05° … +0.10° | −0.20° … +0.30° |
| | CAD y | −0.25° … +0.10° | ±0.30° |
| +12 mm, 1,709 | CAD x | −0.15° … +0.10° | −0.30° … +0.25° |
| | CAD y | −0.20° … +0.25° | ±0.30° |
| both | CAD z (clocking) | ±0.30° | ±0.30° |

These are rigid rotations of guide, caps and wire about the station origin, checked against the deformed body. They exclude bond and guide deformation.

### 3.4 Coverage closure for low-margin steps

`m6_socket_screen.py` was re-run with V3 and the committed candidate on every remaining M6 ±12 mm step whose archived sampled lower bound is below 0.040 mm: 583 steps at z = −12 mm and 228 at z = +12 mm, 0.5 mm surface span, 4 cores, about 20 min. Combined with the coverage screen, **787 and 430 steps** have now been checked exactly ([closure_summary.json](../../simulations/u4m2/lanes_20261113/evening_20261119/results/closure_summary.json)).

| Phase | z = −12 mm, steps checked | V3 min (mm) | Candidate min (mm) | z = +12 mm, steps checked | V3 min (mm) | Candidate min (mm) |
|---|---:|---:|---:|---:|---:|---:|
| straighten | 8 | 0.06465 | 0.11789 | 8 | 0.06701 | 0.12061 |
| entry | 13 | 0.07854 | 0.13396 | 13 | 0.06701 | 0.12061 |
| right yaw out | 148 | 0.02485 | 0.07185 | 58 | 0.03438 | 0.08289 |
| right return | 151 | 0.02502 | 0.07205 | 66 | 0.03433 | 0.08283 |
| left yaw out | 204 | **0.02045** | **0.06674** | 113 | **0.03396** | **0.08239** |
| left return | 210 | 0.02047 | 0.06676 | 119 | 0.03398 | 0.08242 |
| pitch up | 7 | 0.04900 | 0.09981 | 7 | 0.04290 | 0.09275 |
| pitch up return | 7 | 0.04900 | 0.09981 | 7 | 0.04298 | 0.09285 |
| pitch down | 12 | 0.04760 | 0.09819 | 12 | 0.05087 | 0.10197 |
| pitch down return | 12 | 0.04650 | 0.09692 | 12 | 0.05139 | 0.10257 |
| withdrawal | 15 | 0.07868 | 0.13412 | 15 | 0.06719 | 0.12082 |

No contact occurred for either variant. The 2,618 (z = −12 mm) and 2,975 (z = +12 mm) steps not checked exactly all have archived sampled bounds of at least 0.0400 mm. That sampled bound differed from the exact gap by up to 0.0034 mm, and the candidate added at least 0.0463 mm in every checked step. On that basis the unchecked steps are **estimated**, not certified, to keep a candidate gap of about 0.083 mm or more. The fine 0.125 mm checks were run at steps 1,710/1,885 and 1,709/1,885. At step 1,710 refinement raised the candidate gap by 0.0006 mm relative to the 0.5 mm span.

### 3.5 Mounting stiffness and solver consistency

The mission models M6 with homogenised database stiffness and ideal guide positions. Guide bond compliance is not in that model. A thicker bond is more compliant, which moves the hardware toward that idealisation. This was not quantified for M6, and the 17 November rib model quantified only M5. The mass change is −0.0016 g per station. Rope bores, lanes and anchors are unchanged. For these reasons the archived 3,405 states, rope lengths and tensions remain the applicable inputs, and the mission was not re-run. The clearance result still assumes the guide is held at its ideal pose. A bond that slips or creeps would change that.

## 4. Failed checks, rejected variants and incomplete work

- **Rejected:** a 0.3 mm land, with and without a 0.20 mm gap. The straight build fails because the lockwire groove splits the caps (4 of 8 stations invalid in the build check). A slope of 2.0 changes nothing.
- **Not done:** an exact screen of every mission step. Section 3.4 covers every step with an archived bound below 0.040 mm. The remaining steps are estimated from a sampled bound that is not strict (it differs from the exact gap by up to 0.0034 mm).
- **Not modelled:** bond compliance at M6, adhesive creep, guide bending, printed form error, and the actual head and harness envelope. There is no hardware evidence.
- Round-1 open items are unchanged by this run: the +69° pitch sliding floor (μ ≈ 0.16–0.17), the U-blade bond loads, and the M5 pin-region strain.

## 5. Next-run handoff (summary)

The full version, with acceptance checks, is in [HANDOFF.md](../../simulations/u4m2/lanes_20261113/evening_20261119/HANDOFF.md).

1. **Bond-compliance model at M6** for t = 0.15 and 0.25 mm, with a bracketed adhesive modulus. Compute the land loads, the change in EI/GJ, and the guide displacement relative to the new gap.
2. **Bench:** print and bond the candidate on an M6 body, then measure the plate tilt (target resolution 0.05°) and the land gap, straight and at the step-1,710 pose.
3. **Close the remaining exact M6 screen** (steps with a sampled bound ≥ 0.040 mm, a stride of 5 first). This is a low-risk confirmation.

Resources: 4 cores and 15 GB. The screen costs about 5.5 s per step per core. Blockers: there is no measured adhesive or print data.

## 6. Reproducibility

Source: `main` `e285061`. Python 3.11.18 with numpy 2.3.5, scipy 1.17.0, trimesh 5.2.0, python-fcl 0.7.0.10, manifold3d 3.5.5, shapely 2.2.0, matplotlib 3.10.8, clarabel 0.11.1 and cvxopt 1.3.3, matching the round-1 record. The commands are in the [study README](../../simulations/u4m2/lanes_20261113/evening_20261119/README.md#reproduce). The checks (CAD hashes, watertightness and component counts, zero straight overlap, unchanged rope bores, reproduction of round 1, coverage of all 11 phases, no candidate contact, relative links) are recorded in [validation.json](../../simulations/u4m2/lanes_20261113/evening_20261119/results/validation.json).
