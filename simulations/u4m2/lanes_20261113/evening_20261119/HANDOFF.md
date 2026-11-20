# Next-run handoff — from the 19 November 2026 Evening Report

This handoff was prepared at **2026-11-19 20:25 EST (2026-11-20 01:25 UTC)** by the evening run. That run started at **2026-11-19 20:01:53 EST (2026-11-20 01:01:53 UTC)**, and its budget deadline is 22:01:53 EST (03:01:53 UTC). The completion message reports the verified pushed revision, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_19.md) · [Evidence](README.md) · [Candidate CAD](../../../../cad/lanes_u4m2/m6_bond_gap_20261119/README.md) · [Extreme-test plan](../../../../nextstep/README.md) · [Previous handoff (18 Nov evening)](../evening_20261118/HANDOFF.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2, the actual CAD and the rope stations. Do not add a backbone end ferrule.

## Established tonight (simulation only)

- **M6 ±12 mm outer-land bond gap 0.15 → 0.25 mm.** The fine exact gap rises to 0.06733 mm at z = −12 mm and 0.08284 mm at z = +12 mm, from 0.020932 and 0.03431 mm. The 406 screened station-steps across all 11 mission phases show no contact. The rope bores are unchanged and the mass change is −0.0016 g per station.
- **Tilt governs.** V3 touches at −0.1° rigid guide tilt about CAD x. The candidate stays clear to ±0.2° about every axis and touches at −0.25° (x, z = −12 mm) and +0.3° (x, z = +12 mm).
- **Rejected:** a 0.3 mm land (its caps split at the lockwire groove) and a steeper flare (no effect, because the witness is on the land edge).

## Priorities

1. **Exact-triangle screen of the remaining M6 ±12 mm steps for the candidate (first-stage closure).**
   *Why:* 3,201 and 3,203 steps were not checked with exact triangles. Their candidate gap of about 0.064 mm or more is estimated from the sampled bound, which differs from the exact gap by up to 0.0034 mm.
   *How:* reuse `m6_socket_screen.py` with only `V3` and `bond_gap_0p25`, sharded over 4 cores. It takes about 5.5 s per step per core. All 6,404 remaining station-steps take about 2.5 h wall time, which exceeds one run. Instead, do every step with archived sampled bound < 0.03 mm, then a stride of 5.
   *Acceptance:* no contact. Report the smallest candidate gap per phase, and recheck any step below 0.064 mm at 0.125 mm.
2. **Bond-compliance check at M6 with the thicker land.**
   *Why:* the clearance assumes the guide sits at its ideal rod position. A 0.25 mm adhesive layer (about 0.6× shear stiffness) must take up to 0.055 mm land movement. The 17 November rib model (M5) found that the rigid bond carries about 8 N axial force and up to 100 N·mm per land.
   *How:* adapt the 17 November rib-level model (`evening_20261117`) to the M6 webs, with a bond spring of G·A/t for t = 0.15 and 0.25 mm. Use a bracketing adhesive shear modulus (for example 0.5 and 1.5 GPa) and label it as assumed.
   *Acceptance:* land forces and moments and the change in M6 EI/GJ for both gaps at steps 1,709/1,710 and 1,885. State whether the guide displacement relative to the ideal position is below 25% of the new gap.
3. **Bench: measure the bonded M6 guide tilt and gap.**
   *Why:* the margin is now limited by about 0.2° of tilt, which the simulation cannot supply.
   *Acceptance:* print the six candidate parts and bond them on an M6 body. Measure the plate tilt relative to the module axis (aim for 0.05° resolution) and the land gap at the 67.5° web, in the straight fixture and at the step-1,710 disk pose. This is a hardware task. Record the evidence in the [installation guide](../../../../docs/installation_guide.md) checklist and do not report it as completed in simulation.

## Blockers and resources

- The machine has 4 cores and 15 GB. Peak memory in this study was below 2 GB per process. No checkpoints are pending. All screen outputs are in `results/screen/`.
- The adhesive, the printed gap and the bond strength are unmeasured. The candidate is not a manufacturing release.
