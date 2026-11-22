# Next-run handoff — from the 21 November 2026 Evening Report

Prepared at **2026-11-21 20:40 EST (2026-11-22 01:40 UTC)** by the evening run. That run started at **2026-11-21 20:02:23 EST (2026-11-22 01:02:23 UTC)**, and its budget deadline is **22:02:23 EST (03:02:23 UTC)**. The pushed revision is reported in the completion message, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_21.md) · [Evidence](README.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Previous handoff (20 Nov evening)](../evening_20261120/HANDOFF.md) · [Test programme](../../../../nextstep/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, the U4+M2 configuration, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (rigid CAD simulation only)

- The **0.06 mm crowned M6 land is certified over all 3,405 archived steps** at both outer stations, for the guide, caps and wire envelope, with zero contacts. Its minimum gaps are 0.09451 mm (z = −12 mm) and 0.10892 mm (z = +12 mm), both at step 1,709. The crown never reduces a gap. The uncrowned rerun reproduces Round 2 exactly.
- **0.2° rigid tilt** about 26 axes at every step: the crowned land keeps a minimum gap of **0.02829 / 0.04400 mm** and has **0 steps** below the 0.025 mm probe offset. The uncrowned land keeps 0.00070 / 0.01719 mm and has **665 / 317 steps** below the probe offset, all in the yaw excursions. Previous handoff item 2 is therefore **complete**. It took about 4 minutes per pass with the Round 2 swept-crop method, not the estimated 1.5–2 h.
- At 0.25° the crowned land keeps 0.01171 / 0.02775 mm. At **0.30° it contacts at 138 left-yaw steps (1,674–1,921) at z = −12 mm**. The mission-wide first-contact tilt therefore lies between 0.25° and 0.30°.

## Priorities

1. **Bench: as-built land profile and bonded tilt (hardware, unchanged and still first).**
   *Why:* the crowned candidate's margin now depends only on unmodelled physical quantities: the printed crown, the post-cure plate tilt and the bond offset.
   *Acceptance:* print the uncrowned and crowned M6 ±12 mm guides. Measure the land profile at the 67.5° web to 0.01 mm. Measure the bonded plate tilt to 0.05° in the straight fixture and at the step-1,710 pose. **Pass if the tilt is ≤ 0.20° and the guide offset is ≤ 0.025 mm at both stations.** A tilt of 0.25° is acceptable only at z = +12 mm, or with an offset ≤ 0.0117 mm at z = −12 mm. If the crown cannot be printed, test a machined edge relief of the same height. Record the results in the [installation guide](../../../../docs/installation_guide.md) checklist. Do not report this item as completed in simulation.
2. **Bond tractions and witness motion for the crowned layer (simulation; previous item 3, not started).**
   *Why:* the Round 2 bonded-support model ([`m6_support.py`](../../extreme_tests/round2_20261119/m6_support.py)) assumed a uniform 0.25 mm layer. The crowned layer is 0.25 mm at mid-land and 0.31 mm at the edges, and the uncrowned trial pad traction peak (63.96 MPa) was not recomputed.
   *How:* make the pad spring thickness vary with the axial position of the 16 integration points. Rerun the uncrowned and crowned cases at 500/1,500 MPa for steps 1,709, 1,710 and 1,885.
   *Acceptance:* report land wrenches, peak and mean pad tractions and guide-to-web witness motion, with the assumed modulus labelled. Compare the witness motion plus tilt against tonight's full-mission allowance (0.0283 mm at 0.2°, z = −12 mm).
3. **Mission-wide first-contact tilt at finer axis spacing (simulation, about 30 min).**
   *Why:* tonight's 15° axis sampling puts the mission-wide first contact between 0.25° and 0.30°, on axes 150–165°. The bench acceptance in item 1 should rest on a bisected number, not a bracket.
   *How:* extend `tilt_mission.py` with axes every 5° from 120° to 180° (both senses). Bisect to 0.004° only on the shapes whose 0.25° gap is below 0.02 mm (254 shapes at z = −12 mm, all in left and right yaw; none at z = +12 mm, so bisect there on the shapes below 0.03 mm).
   *Acceptance:* report the mission-wide minimum first-contact tilt and its step, phase and axis at both stations. Confirm it lies between 0.25° and 0.30° at z = −12 mm.

## Blockers and resources

- 4 cores and 15 GB of memory. Each process used less than 1 GB. Each full-mission 26-tilt pass takes about 4–6 min per station with two shards. No checkpoints are pending; all shards are complete.
- Dependency note: importing the Round 2 helpers requires `clarabel` and a working `pillow` (the system PIL was broken). Install both with `python -m pip` into the interpreter that runs the scripts.
- Same-day Codex work on `codex/m5-active-reset-load-export` (M5 active-reset pin load export and stress screen, with CI) is not merged and has no committed results. Do not duplicate it; review its CI output once it is published.
- The adhesive, as-printed land, bonded tilt and bond strength are unmeasured. The crowned candidate is not a manufacturing release.
