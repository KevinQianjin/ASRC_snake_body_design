# Next-run handoff — from the 27 November 2026 Evening Report

Prepared at **2026-11-27 20:55 EST (2026-11-28 01:55 UTC)**. The run started at **2026-11-27 20:02:05 EST (2026-11-28 01:02:05 UTC)**.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_27.md) · [Study and commands](README.md) · [Previous handoff (27 Nov hub fillet)](../hub_fillet_20261127/HANDOFF.md)

## Closed in this run (native B-Rep CAD and linear solid FE; no hardware)

- **Frame check:** `M6_lane_anchorC.stl` matches `Medium_Stiffness_96.step` rotated by −22.5° within 0.00066 mm in the hub region.
- **The `ring_0` corner peak** (3.68–3.85%) is the ceiling corner of a **0.30 × 2.0 mm slot** between each rib end and its hub socket (16 pockets). Native OCC fillets are valid only up to **R = 0.14 mm**. R = 0.25 mm gives an invalid solid, and R ≥ 0.30 mm fails. The handoff's R = 0.8–1.5 mm fillet is not buildable while the slot exists.
- **`ring_1`** lies on a tangent-continuous surface: there is no edge to fillet.
- **New governing finite-gauge site: the arch crown** below the socket bottom at the `ring_0` end (`r ≈ 9.4–9.7 mm, |z| ≈ 20.3 mm`). Its 0.5 mm gauge strain is **1.72% (q3) → 1.91% (q2.5)** and its 1.0 mm gauge strain is **1.02%**, above `ring_1` (1.49%). It is not converged.
- **Slot fill rejected:**
  - the slot-root peak falls 36%;
  - the arch-crown 0.5 mm gauge strain rises 19% (q3), and the crown element peak reaches 3.50% (q2.5/a0.40);
  - `EI` rises +4.7% bare and +2.8% with the backbone.

## Priorities (next)

1. **Converge the arch-crown gauge strain with local refinement (simulation, ~40 min).**
   - **Why:** this site now governs the PA12 fatigue question (0.5 mm gauge 1.72% → 1.91% between q3 and q2.5), and global q2.5/a0.25 is at the 15 GB memory limit.
   - **How:** refine the surface locally around both arch crowns (`morning_20261126/backbone_strain.build_body(refine_center=…, refine_passes=…)` or a TetGen region volume constraint) while keeping the global mesh at q3/a0.40. Reuse `hub_variant_fe.analyze_step_sites`.
   - **Accept when:** the 0.5 mm and 1.0 mm gauge strains at the crown change by < 5% over two refinements, at steps 1,709 / 1,869 / 1,884. Then run the full 3,405-state envelope for the crown site.
2. **Arch-crown geometry candidates in native B-Rep (CAD + FE, ~60 min).**
   - **Why:** fillets cannot help here. The crown is already a smooth arc, so the lever is crown radius or section depth.
   - **How:** trial a larger crown radius and/or a deeper rib section at the crown in `Medium_Stiffness_96.step`. Use OCC, and build FE bodies by OCC double-precision union/cut on the sewn FE lattice (the approach that worked tonight). Keep the slot as is unless the designer confirms it may be closed.
   - **Accept when:** the CAD is a valid single solid with the Ø8.40 mm bore preserved, the crown's 0.5 mm gauge is below ~1.2% with no new site above it (`ring_1`, slot root), and the change in `EI` is reported and fed into the rod/mission stiffness assumption before any full-motion replay.
3. **Designer decision on the 0.30 mm rib/socket slot and the bench measurements (hardware gating).**
   - Ask whether the slot is an intentional print clearance or compliance relief.
   - Instrument the M6 hub with DIC or strain gauges at the **arch crown** (`|z| ≈ 20.3 mm`, `r ≈ 9.5 mm`) as well as at `ring_0` (`z = −18 mm`) and `ring_1` (`r = 12 mm, z = −5.2 mm`).
   - Continue the queued rod-in-bore tolerance stack, PA12 lap-shear coupons, M6 socket coupons and U1 ±2/±5 N bench reversal.

## Resource notes

- Python 3.13 environment. Install `cadquery-ocp==7.8.1.1.post1`: 8.0 dropped the `TopTools` indexed maps used here.
- One q2.5/a0.25 solve uses about 13–14 GB. Run FE cases sequentially in separate processes.
