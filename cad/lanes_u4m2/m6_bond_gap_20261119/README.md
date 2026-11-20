# M6 outer-socket bond-gap candidate — 19 November 2026 (evening)

**Engineering candidate. Not released for manufacture.** These six parts replace only the **M6 z = −12 mm and z = +12 mm** guide, caps and lockwire envelope of [guides_v3](../guides_v3/README.md). In this candidate the gap between the bonded 0.5 mm central land and the M6 outer web is **0.25 mm instead of 0.15 mm**. All other parts are unchanged. M5 ±12 mm keeps its [retained rotating seat](../retained_seat_20261118/), and all four ±24 mm stations keep V3.

| Part set | Watertight bodies | Straight overlap with M6 body | Rope bores vs V3 |
|---|---|---:|---|
| `M6_z-12_*` | guide 1, caps 4, wire 4 | 0 mm³ | identical in 17/17 sections |
| `M6_z+12_*` | guide 1, caps 4, wire 4 | 0 mm³ | identical in 17/17 sections |

These quantities are unchanged: land length 0.5 mm, flare slope 1.5, socket wall 0.85 mm, lane radii 21/24/28 mm, Ø2.6 mm bores, station positions, webs and body. The net mass change is −0.0016 g per station, with the conservative wire envelope included. Hashes and per-part mass changes are in [geometry_check.json](geometry_check.json).

**Why.** At the governing left-yaw steps of the 500 g mission, the exact gap rises from 0.020932 to **0.06733 mm** at z = −12 mm and from 0.03431 to **0.08284 mm** at z = +12 mm. A rigid guide tilt of ±0.2° stays clear. V3 touches at −0.1°. Evidence and limits: [evening study](../../../simulations/u4m2/lanes_20261113/evening_20261119/README.md).

**Open.** A 0.25 mm adhesive layer has about 0.6× the shear stiffness of a 0.15 mm layer and must still accommodate up to 0.055 mm land movement (22% nominal shear). Adhesive choice, the as-printed gap, guide flatness and tilt after bonding, and pull/shear and cyclic strength are unmeasured. Measure the assembled guide tilt. A tilt above about 0.2° uses up the modelled margin.

Rebuild with `python build.py`. It runs `../guides_v3/build.py --bond-gap 0.25` in a temporary folder, copies only the six M6 ±12 mm parts and rechecks them.
