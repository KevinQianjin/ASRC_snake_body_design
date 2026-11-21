# M6 outer-socket crowned bond land — 20 November 2026 (evening)

**Engineering candidate. Not released for manufacture.** These six parts replace the [0.25 mm bond-gap candidate](../m6_bond_gap_20261119/README.md) at **M6 z = −12 mm and z = +12 mm** only. The bonded 0.5 mm central land keeps its **0.25 mm** gap at mid-land, and the gap grows quadratically to **0.31 mm** at each land edge (a 0.06 mm crown, `gap = 0.25 + 0.06·(z/0.25 mm)²`). The 1.5 flare continues from the crowned edge. All other parts are unchanged: M5 ±12 mm keeps its [retained rotating seat](../retained_seat_20261118/README.md) and all four ±24 mm stations keep [V3](../guides_v3/README.md).

| Part set | Watertight bodies | Straight overlap with M6 body | Rope bores vs 0.25 mm candidate |
|---|---|---:|---|
| `M6_z-12_*` | guide 1, caps 4, wire 4 | 0 mm³ | identical in 17/17 sections |
| `M6_z+12_*` | guide 1, caps 4, wire 4 | 0 mm³ | identical in 17/17 sections |

Unchanged: land length 0.5 mm, mid-land bond datum 0.25 mm, flare slope 1.5, socket wall 0.85 mm, lane radii 21/24/28 mm, Ø2.6 mm bores, station positions, webs and body. The mass change is −0.0021 g per station (guide −0.0031 g, caps +0.0010 g), negligible against the mission mass model. Hashes, mount data and per-part checks are in [geometry_check.json](geometry_check.json).

**Why.** The 19 November evening run and Round 2 found that rigid tilt of the bonded plate, not translation, uses up the M6 margin: the witness sits on the land edge about 21 mm from the axis. At the governing left-yaw steps the crown moves that edge away from the deformed web. Exact first-contact tilt (bisection, 0.004°) rises from **0.215° to 0.305°** at z = −12 mm and from **0.270° to 0.355°** at z = +12 mm. The remaining rigid-translation allowance at a 0.2° adverse tilt rises from **0.0046 to 0.0323 mm** and from **0.0209 to 0.0475 mm**, so the combined Round 2 probe (0.025 mm offset with 0.2° tilt) no longer closes the gap in this rigid model. Evidence: [evening study](../../../simulations/u4m2/lanes_20261113/evening_20261120/README.md).

**Mounting stiffness.** The adhesive layer is thicker toward the land edges (mean 0.27 mm). Its uniform-shear stiffness falls to about 0.93× that of the uncrowned 0.25 mm layer. That change is inside the 3× adhesive-modulus bracket (500–1,500 MPa) of the Round 2 bonded-support model, which was not rerun for the crown. The archived mission still places the guide at its ideal rod position.

**Open.** Printing a 0.06 mm crown on a 0.5 mm land is below typical PA12 powder-bed resolution (roughly 0.1 mm features). The as-printed land profile, the bonded tilt, the adhesive and its strength are unmeasured. A bench part may need the crown machined, or the land replaced by a measured edge relief.

Rebuild with `python build.py` (default crown 0.06 mm; `--crown 0` rebuilds the uncrowned candidate). It runs `../guides_v3/build.py --bond-gap 0.25 --crown 0.06` in a temporary folder, copies only the six M6 ±12 mm parts and rechecks them against the 19 November candidate.
