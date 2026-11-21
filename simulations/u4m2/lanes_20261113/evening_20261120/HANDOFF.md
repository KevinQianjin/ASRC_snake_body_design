# Next-run handoff — from the 20 November 2026 Evening Report

Prepared at **2026-11-20 20:42 EST (2026-11-21 01:42 UTC)** by the evening run. That run started at **2026-11-20 20:01:45 EST (2026-11-21 01:01:45 UTC)**; its budget deadline is 22:01:45 EST (03:01:45 UTC). The completion message reports the verified pushed revision, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_20.md) · [Evidence](README.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Previous handoff (19 Nov evening)](../evening_20261119/HANDOFF.md) · [Test programme](../../../../nextstep/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (rigid CAD simulation only)

- A **0.06 mm crown** on the 0.25 mm M6 outer-socket land raises the smallest first-contact rigid tilt (in-plane axes every 15°) at the governing left-yaw steps from 0.207° to **0.289°** (z = −12 mm) and from 0.258° to **0.340°** (z = +12 mm). At 0.2° tilt the smallest translation allowance rises from 0.0013 to **0.0290 mm** and from 0.0176 to **0.0443 mm**. The y/z limits (≈ ±0.48°/±0.69°) are the kept 0.25 mm mid-land datum of another socket; one CAD-x sign is limited by a cap.
- **Mission screen:** zero contacts for the 0.06 mm crown over 787 (z = −12 mm) and 430 (z = +12 mm) low-margin steps, all 11 phases. The smallest gaps are 0.09451 and 0.10892 mm (uncrowned 0.06674 / 0.08239 mm). The crown never reduced a gap. The remaining steps are not yet checked for the crown.
- The 0.04 mm crown leaves 0.0230 mm at 0.2° (z = −12 mm), below the 0.025 mm Round 2 probe offset.
- The previous 19 November handoff items 1 (bond compliance) and 3 (remaining exact M6 screen for the uncrowned candidate) were already completed by Round 2 on 20 November; this run did not repeat them.

## Priorities

1. **Bench: as-built land profile and bonded tilt (hardware).**
   *Why:* every remaining M6 margin now depends on post-cure plate tilt and on whether a 0.06 mm crown can be produced on a 0.5 mm PA12 land.
   *Acceptance:* print the uncrowned and crowned M6 ±12 mm guides; measure the land profile at the 67.5° web (target resolution 0.01 mm) and the bonded plate tilt relative to the module axis (0.05° resolution) in the straight fixture and at the step-1,710 pose. Record in the [installation guide](../../../../docs/installation_guide.md) checklist. If the crown cannot be printed, test a machined or post-processed edge relief of the same height. Do not report this as completed in simulation.
2. **Full-mission certification of the crowned candidate (low risk).**
   *Why:* tonight's screen covered 787 + 430 low-margin steps. Round 2 certified the uncrowned candidate on all 3,405 steps at both stations. The crown only enlarges the socket, but the caps also move outward.
   *How:* `m6_socket_screen.py` with `g025` and `crown060` on the remaining steps, in 4 shards (≈ 5 s per step per core, ≈ 1.5–2 h for both stations; use a stride of 5 first if time is short).
   *Acceptance:* zero contacts; the smallest crowned gap stays at or above the uncrowned value at every step.
3. **Bond tractions and witness motion for the crowned layer.**
   *Why:* the Round 2 bonded-support model (`extreme_tests/round2_20261119/m6_support.py`) assumed a uniform layer. The crowned layer is 0.25 mm at mid-land and 0.31 mm at the edges, and its trial pad traction peak (63.96 MPa, uncrowned) was not recomputed.
   *How:* give the pad springs a thickness that varies with the 16 integration points' axial position, rerun the 0.15/0.25 mm and crowned cases at 500/1,500 MPa for steps 1,709, 1,710 and 1,885.
   *Acceptance:* land wrenches, peak and mean pad tractions and guide-to-web witness motion for crowned versus uncrowned, with the assumed modulus labelled. Report any increase in witness motion against the 0.0290 mm tilt-translation allowance.

## Blockers and resources

- 4 cores and 15 GB. Peak memory was below 2 GB per process. No checkpoints are pending; all screen shards are in `results/screen/`.
- Adhesive, as-printed land profile, bonded tilt and bond strength are unmeasured. The crowned candidate is not a manufacturing release. Round 2 bond tractions were not recomputed for the non-uniform layer.
