# Evening Engineering Report — 2026-11-20

**Edition:** Evening Report (scheduled 20:01 US Eastern Time).
**Run start:** 2026-11-20 20:01:45 EST (2026-11-21 01:01:45 UTC). **Budget deadline:** 2026-11-20 22:01:45 EST (2026-11-21 03:01:45 UTC).
**Reporting interval:** 2026-11-19 20:01:45 EST (2026-11-20 01:01:45 UTC) to the run start above, which is the cutoff for repository updates. Results produced during this run are reported separately in section 3.
**Working branch:** `claude/great-goodall-1wf2yh`. Its previous head `af4883a` was already contained in `main` (PR #38). It was fast-forwarded to `main` at `ef7e9fb` and then to `codex/guide-validation` at `0d914ab`, which adds the offline 3D replay. No merge commit was needed. Execution model: see the completion message.

[Evidence and commands](../../simulations/u4m2/lanes_20261113/evening_20261120/README.md) · [Next-run handoff](../../simulations/u4m2/lanes_20261113/evening_20261120/HANDOFF.md) · [Crowned-land CAD](../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Free-space and service-life report](../projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md)

## 1. Summary

The M6 outer guide sockets of the 500 g U4+M2 front remain the tightest rigid guide/body interface. Since the 19 November evening run, the 0.25 mm bond-gap candidate has cleared the nominal body over the whole mission. Its margin is set by the **tilt** of the bonded plate: the witness is on the land edge about 21 mm from the axis. This run tested a CAD-only change to that edge, keeping the 0.25 mm bond datum, the rope bores, the stations and every solver input.

- **Crowned land.** The land gap now rises quadratically from 0.25 mm at mid-land to 0.31 mm at each edge (0.06 mm crown). The builders gained an optional crown; with zero crown they reproduce the committed candidate exactly.
- **Tilt tolerance.** At the governing left-yaw steps, the smallest exact first-contact rigid tilt over in-plane axes sampled every 15° (bisection to 0.004°) rises from **0.207° to 0.289°** at z = −12 mm and from **0.258° to 0.340°** at z = +12 mm. At a 0.2° adverse tilt the smallest remaining translation allowance rises from **0.0013 to 0.0290 mm** and from **0.0176 to 0.0443 mm**. The Round 2 combined probe (0.025 mm offset plus 0.2° tilt), which closed the uncrowned gap, now stays clear in this rigid model.
- **Mission screen.** Over the 787 (z = −12 mm) and 430 (z = +12 mm) low-margin steps covering all 11 phases (loaded startup and straightening → insertion → right yaw and return → left yaw and return → pitch up/down and returns → withdrawal), the crowned candidate has **zero contacts**. Its smallest gap is **0.09451 mm** and **0.10892 mm**, against 0.06674 and 0.08239 mm uncrowned. The crown never reduced a gap at any step or part. This is a targeted subset of the archived states, not a complete-cycle certification.
- **Costs.** The adhesive layer averages 0.27 mm, so its uniform-shear stiffness falls to about 0.93× that of the uncrowned layer. The mass changes by −0.0021 g per station. A 0.06 mm crown is below typical PA12 print resolution and may need machining or a measured edge relief. This is **not** a manufacturing release.

## 2. Repository updates in the reporting interval

Commits are listed once, by content, even where they appear on several branches. Times are commit times.

| Time (EST / UTC) | Revision | Work | Where it is now |
|---|---|---|---|
| 19 Nov 20:25 / 20 Nov 01:25 and 20:45 / 01:45 | `0b48d1b`, `af4883a` | Previous evening run: 0.25 mm M6 outer-socket bond gap, coverage screen, tilt sensitivity. [Evening Report 2026-11-19](Evening_Report_2026_11_19.md) | `main` via PR #38 (`d0938c3`, 21:40 EST / 02:40 UTC) |
| 20 Nov 00:29 / 05:29 | `cedb9ad` | Extreme-test Round 2: full two-station M6 CAD check of the 0.25 mm candidate over all 3,405 states (no contact), bonded-support shell model (witness motion 0.0028 mm, bore motion 2.07–2.18 mm), moving-bore winch corrections, M5 pin contact (372.6 MPa service peak), U cage/tab sharing, reversal take-up, rainflow duty. [Round 2 report](../projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) | `main` |
| 20 Nov 02:56 / 07:56 | `bbed30b` | Repository reorganised into projects, with a project index and a repository map. [Project index](../../docs/project_index.md) | `main` |
| 20 Nov 11:05 / 16:05 | `ef7e9fb` | Free-space steering limits (yaw ±296°, pitch +215°/−149° on the 8-cell rod with CAD screening, first limits at M5/M6 distal C wrap allowance), M5 pin yield crossing near −110° left-out, repeated-duty endurance demand (active reset: 0 floor violations, 5.722 N reference amplitude). [Report](../projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) | `main` |
| 20 Nov 12:33 / 17:33 | `0d914ab` | Offline 3D replay of the free-space study, publication-language checker. | `codex/guide-validation` (not yet in `main`; included in this branch) |

There was no Morning Report for 20 November in the repository at the cutoff. Other remote branches (`codex/reach-extension-study`, `codex/internal-rope-guides`, `codex/kevin`, `copilot/review-outdated-prototype-files`) had no commits in the interval.

**Plan changes.** The 19 November handoff listed (1) an M6 bond-compliance model and (3) exact screening of the remaining M6 steps. Round 2 completed both on 20 November for the uncrowned candidate, so this run did not repeat them. Round 2 also showed that a 0.025 mm offset combined with 0.2° tilt closes the gap. That made tilt tolerance the remaining simulation-addressable guide/body item, and this run addressed it.

## 3. New work in this run

### 3.1 Builder change and reproduction

`cad/lanes_u4m2/guides_v2/build.py` accepts an optional `socket_land_crown_mm` key, and `guides_v3/build.py` a `--crown` option. With crown 0 neither adds sections, and `--bond-gap 0.25` reproduces the six committed 19 November parts with identical vertices and volumes. Crowns of 0.02, 0.04 and 0.06 mm were built. Every variant has one closed guide body, four closed caps, four wire envelopes and zero straight overlap with the M6 body. The rope bores are identical in 17 of 17 sections at each station.

### 3.2 Rigid tilt at the governing steps

The guide, caps and wire rotate together about the station origin relative to the deformed M6 body (actual STL, 0.25 mm axial refinement): z = −12 mm at step 1,710 and z = +12 mm at step 1,709.

| Crown (mm) | Gap at 0° (−12 / +12 mm) | First contact x− / x+, z = −12 mm (°) | First contact x− / x+, z = +12 mm (°) | Gap at 0.2° (−12 / +12 mm) |
|---:|---|---|---|---|
| 0 (19 Nov candidate) | 0.06724 / 0.08276 | −0.215 / +0.344 | −0.359 / +0.270 | 0.0046 / 0.0209 |
| 0.02 | 0.07653 / 0.09248 | −0.246 / +0.383 | −0.402 / +0.301 | 0.0138 / 0.0305 |
| 0.04 | 0.08582 / 0.10219 | −0.273 / +0.422 | −0.438 / +0.332 | 0.0230 / 0.0402 |
| **0.06 (selected)** | **0.09512 / 0.10917** | **−0.305 / +0.441** | **−0.453 / +0.355** | **0.0323 / 0.0475** |

Each 0.02 mm of crown adds about 0.009 mm of gap at 0° and about 0.03° of tilt about CAD x. About CAD y and z the first contact is at ±0.47°/±0.68° uncrowned and ±0.49°/±0.70° for every crown. A probe at those angles shows the witness moving to the mid-land side wall of another web socket, where the 0.25 mm datum is kept. Clocking is therefore limited at about 0.25 mm / 20.6 mm ≈ 0.69° whatever the crown. One sign about CAD x is set by a cap (radius about 17.4 mm) rather than the land. The 0.05° grid (`m6_tilt.py`) agrees with the bisection. The 19 November grid value of "−0.25°" for the uncrowned part is refined here to −0.215° about CAD x.

**All in-plane axes.** Tilt axes in the plate plane were then sampled every 15° in both senses for the uncrowned part and the 0.06 mm crown. The worst axes lie 150–165° from CAD x. The smallest first-contact tilt is 0.207° → **0.289°** (z = −12 mm) and 0.258° → **0.340°** (z = +12 mm). The smallest gap at 0.2° is 0.0013 → **0.0290 mm** and 0.0176 → **0.0443 mm**. A finer axis spacing could lower these minima slightly.

### 3.3 Mission screen

The unchanged 19 November `m6_socket_screen.py` checked the uncrowned part and the 0.04 and 0.06 mm crowns against one deformed body per step. It covered every step of the 19 November screen and closure sets: 787 steps at z = −12 mm and 430 at z = +12 mm, all 11 phases, including every step whose archived sampled bound is below 0.040 mm. Four shards ran in about 27 minutes.

| Station | Variant | Smallest gap (step) | Gain over uncrowned, min–max | Smallest cap gap | Contacts |
|---|---|---|---|---:|---:|
| z = −12 mm | 0.25 mm (19 Nov) | 0.06674 mm (1,709) | — | 0.08530 mm | 0 |
| | 0.04 mm crown | 0.08525 mm (1,709) | 0.0016–0.0198 mm | 0.10500 mm | 0 |
| | **0.06 mm crown** | **0.09451 mm (1,709)** | 0.0016–0.0281 mm | 0.11093 mm | 0 |
| z = +12 mm | 0.25 mm (19 Nov) | 0.08239 mm (1,709) | — | 0.08920 mm | 0 |
| | 0.04 mm crown | 0.10177 mm (1,709) | 0.0012–0.0198 mm | 0.10900 mm | 0 |
| | **0.06 mm crown** | **0.10892 mm (1,709)** | 0.0012–0.0265 mm | 0.11392 mm | 0 |

The uncrowned minima reproduce the 19 November closure exactly. The crown never reduced a gap. Its gain is smallest where the witness lies near mid-land, where the 0.25 mm datum is kept. The remaining 2,618 + 2,975 steps were certified for the uncrowned part by Round 2. For the crowned part they are not yet checked, and remain a handoff item.

### 3.4 Mounting stiffness and solver consistency

The bond datum stays 0.25 mm at mid-land. The layer is 0.31 mm at the land edges and 0.27 mm on average. For uniform shear its stiffness (∫G/t dz) is 0.930× the uncrowned layer. The nominal shear strain for the worst 0.0545 mm land movement stays 22% at mid-land and falls to 18% at the edges. The bond area is unchanged. The Round 2 bonded-support model used a 3× adhesive-modulus bracket (500–1,500 MPa), which covers this change, but it was not rerun with the non-uniform layer. Its trial pad traction peak (63.96 MPa) was therefore not recomputed, and no stress reduction is claimed. The archived mission keeps the guide at its ideal rod position. Rope bores, lanes, anchors and stations are unchanged, and the mass change is −0.0021 g per station, so archived rope lengths, tensions, head pose and guide forces remain the applicable inputs. No full-motion replay was needed or run. No backbone end ferrule was added, and the payload remains 500 g.

## 4. Failed checks, rejected variants and incomplete work

- **Rejected: 0.04 mm crown.** It leaves 0.0230 mm of translation allowance at 0.2° tilt (z = −12 mm), below the 0.025 mm Round 2 offset.
- **Not tested:** crowns above 0.06 mm, tilt axes finer than 15°, combined bond deformation and tilt, and the remaining 2,618 + 2,975 mission steps for the crowned candidate (covered for the uncrowned part by Round 2).
- **First attempts failed** on missing packages (numba, then vtk) before any result was produced. They were rerun after installation; the failed logs were overwritten.
- **Unmeasured:** as-printed land profile, bonded tilt, adhesive choice and strength. Rigid tilt excludes bond deformation, guide bending and printing error.

## 5. Next-run handoff (summary)

1. **Bench:** print the uncrowned and crowned M6 guides, measure the land profile (0.01 mm) and bonded tilt (0.05°). If the crown cannot be printed, test a machined edge relief.
2. **Full-mission certification** of the crowned candidate on the remaining steps (≈ 1.5–2 h on 4 cores).
3. **Bond tractions for the crowned layer:** rerun the Round 2 bonded-support model with the non-uniform 0.25–0.31 mm layer.

Details, acceptance checks and resources: [HANDOFF.md](../../simulations/u4m2/lanes_20261113/evening_20261120/HANDOFF.md).

## 6. Reproducibility

Source revision `0d914ab`. Python 3.11.18, numpy 2.3.5, scipy 1.17.0, trimesh 5.2.0, python-fcl 0.7.0.10, manifold3d 3.5.5, shapely 2.2.0, matplotlib 3.10.8, numba 0.68.1, vtk 9.7.2. Commands, step lists, hashes and validation: [study README](../../simulations/u4m2/lanes_20261113/evening_20261120/README.md) · [validation.json](../../simulations/u4m2/lanes_20261113/evening_20261120/results/validation.json) · [run_context.json](../../simulations/u4m2/lanes_20261113/evening_20261120/results/run_context.json).
