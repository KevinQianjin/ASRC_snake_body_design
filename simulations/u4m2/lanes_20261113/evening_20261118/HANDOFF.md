# Next-run handoff — from the 18 November 2026 Evening Report

Prepared **2026-11-18 20:36:57 EST (2026-11-19 01:36:57 UTC)** by the evening run that started **2026-11-18 20:02:32 EST (2026-11-19 01:02:32 UTC)**. The completion message reports the verified pushed revision, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_18.md) · [Evidence](README.md) · [Validation plan](../../../../docs/500g_validation_plan.md) · [Previous handoff (17 Nov evening)](../evening_20261117/HANDOFF.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD and the rope stations. Do not add a backbone end ferrule.

## What is now established (simulation only)

- **V3-type sockets cannot host a rotating seat.** The web crosses the guide plate at 34.2°. The 0.5 mm-high V3 land holds web material up to about 1.1 mm from the pivot along the web, and in-plane rotation swings it into the radial walls. On the 0.025 mm² mesh, the 0.15 mm land gap fails all six cases (−0.065 to −0.636 mm). The 0.25 mm variant clears records 146, 141 and 64 by about 0.03 mm, but fails record 47 (−0.017 mm) and both 96° pure bends (about −0.5 mm).
- **A bow-tie seat centred on the pivot clears every case.** The candidate has a 0.3 mm land along the web, 0.15 mm running clearance and a flare slope of 0.25. Its minimum clearance is +0.032 to +0.057 mm on the fine mesh, and the middle-to-fine mesh change is at most 0.004 mm. Running clearance below about 0.12 mm fails at the land, because the 3 mm-thick web tilts by up to 4.7° (holds) or 5.8° (pure bend).
- **The retainer must carry a reversing along-web force**: up to 12.3 N in the saved holds and 24.7 N in the 96° pure bend. It must also allow both about 10.4° in-plane rotation and about 5° out-of-plane tilt. A slot cannot do this, and neither can a cylindrical pin along the rib normal.
- **Pinned seat (Ø0.6 mm, ideal spherical release):** A Ø0.6 mm pin through the web, modelled as a perfectly fitting rigid ring with a spherical release, gives a mesh-converged hole-edge strain of 2.4–2.7% in the saved holds and the pure bends (fine-mesh change ≤ 0.18 points). The rigid-band idealisation used so far has a non-converging 7.1% corner singularity. The pin changes the 96° holding couple by −1.2%, but raises seat rotation to 11.3° and tilt to 6.6°, so the pinned seat needs 0.20 mm running clearance at the land (margins +0.058 to +0.107 mm).

## Priorities

1. **Draw the retained seat in CAD on the real M5 webs and check it.** Use a bow-tie cavity (ℓ 0.3 mm, c **0.20 mm**, k 0.25) plus a Ø0.6 mm pin with a spherical or crowned release. Assume a hardened steel pin; the pin diameter is open to a short trade study. Add the cap and retention, and choose an assembly order.
   *Why:* the kinematic and load requirements are now quantified, and no seat CAD exists yet.
   *Acceptance:* closed, watertight parts that are connected to the frame. The straight assembly keeps its nominal bore centres. Re-run `seat_envelope.py` against the real exported cavity rather than the analytic profile, with positive clearance in all six cases and no web/guide Boolean overlap in the straight state. Check the pin hole's edge distance against the 1.50 mm web width.
   *Limits:* about 15 min CPU. Build from `cad/lanes_u4m2/guides_v3/build.py` in a new dated folder and do not overwrite V3.
2. **Make the pin contact more realistic in the shell model.** Model the pin with a diametral clearance of about 0.02–0.05 mm and unilateral contact at the hole edge, or alternatively a cylindrical pin that releases only in-plane rotation. Compare the land forces and moments with the spherical ideal.
   *Why:* the present pin is a perfect bonded rigid ring with all rotations free. The 17 November linear model found 15 N and 88 N·mm for a cylindrical pin.
   *Acceptance:* the same six cases on 0.055 and 0.025 mm² meshes. Report hole-edge strain and bearing pressure, and keep the mesh change below 5%.
3. **Extend to M6 and the ±24 mm stations, then screen all 217 holds.** This applies only after priority 1 gives an actual cavity. *Why:* the plan requires every saved hold against all eight guides. *Acceptance:* minimum unintended clearance per part, hold and location, with the worst cases confirmed on a finer mesh.

## Blockers and resources

- The machine has 4 cores and 15 GB. Each 0.025 mm² point-variant case takes about 2–6 min single-threaded, with three case groups running in parallel.
- Scratch checkpoints were not committed because they are large. Regenerate them with the commands in the [evidence README](README.md#reproduction). The coarse re-run is bit-for-bit consistent with the archive.
- PA12 strength at a hole edge, print tolerance and adhesive or pin fit are unmeasured. Physical test 4 of the plan remains necessary before any manufacturing claim.
