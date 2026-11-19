# P3 coupon fixture with 1.46 mm locating bores

This is the pin-side carriage for the P3 reversible-load bench test. The two nominal Ø1.46 mm bores locate the existing Ø1.44 mm shoulder-pin head and cap pilots. The coupon, production pin, cap, module and rope routing keep their published geometry. The pilot-to-carriage play affects the displacement a camera or stage encoder can attribute to the coupon.

[Replacement carriage STL](pin_carriage_bore_1p46.stl) · [Bench assembly and parts](../m5_seat_bench_20261119/README.md) · [Fit, compliance and optical checks](../../../simulations/u4m2/lanes_20261113/p3_pin_fixture_20261119/README.md)

| Quantity | Original carriage | Bench candidate |
|---|---:|---:|
| Pilot bore diameter | 1.50 mm | 1.46 mm |
| Available parallel reversal along the applied P3 transverse direction | 0.05964 mm | 0.01966 mm |
| Parallel reversal as a fraction of the 0.10755 mm rigid-support coupon prediction | 55.5% | 18.3% |

The source generator reproduced the original carriage volume. The candidate mesh is a closed 1,646-triangle solid of 789.459 mm³. The entire difference lies in the two pilot zones. With the nominal parallel axes, a 0.015 mm relative bore offset still admitted assembly in the tested direction. A 0.020 mm offset exhausted the available clearance. A further change to Ø1.45 mm left only 0.00966 mm of ideal reversal travel and tighter alignment requirements. Measure the bores and their coaxiality before using either candidate.

The 729 installation poses cover pin insertion, cap approach and cap threading. Zero sampled positive-volume collisions were found. During the ten-turn cap helix, consecutive checked positions allow up to 0.587 mm of surface travel. Seating, thread torque and the available drive-tool clearance still require a physical trial. [Pilot sections and offsets](../../../simulations/u4m2/lanes_20261113/p3_pin_fixture_20261119/results/pilot_fit.json) · [Assembly path coverage](../../../simulations/u4m2/lanes_20261113/p3_pin_fixture_20261119/results/candidate_assembly.json)
