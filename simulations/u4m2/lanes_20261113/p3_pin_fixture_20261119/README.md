# P3 coupon fixture commissioning

The P3 case is a signed coupon-level reaction from the M5 guide study. The nominal rigid-support prediction placed the two full-load positions 0.10755 mm apart. A finite steel pin, clearance around its pilots and camera datum choice can all change the indicated reversal distance. The CAD, model and reduction here prepare a two-view bench measurement. The hardware log contains zero measurements.

[Fixture CAD](../../../../cad/lanes_u4m2/p3_pin_fixture_20261119/README.md) · [Paired load and reference commands](../m5_seat_bench_20261119/README.md) · [Numerical summary](results/summary.json) · [Empty measurement form](witness_measurements.csv)

## Fit and visibility

Ten cross-sections of the actual pin-head and cap pilots and the mating bores constrain their common transverse translation. Evaluating both sides of the P3 load direction gives 0.05964, 0.03965, 0.01966 and 0.00966 mm of on-axis free reversal at bore diameters of 1.50, 1.48, 1.46 and 1.45 mm. Ø1.46 reduces the original free reversal by 67.0%. Closed-solid intersection checks bracket the support limits. The parallel offset test uses the registered P3 direction. Printed roughness, angular offset and actual thread seating need measurement. [Section limits and offset tests](results/pilot_fit.json)

The assembly screen covered 94 unloaded part pairs and 729 installation poses. For the prescribed operating motions the minimum interpolation bound was 0.03278 mm. Separately, 18 optical test conditions cover both faces of the pin assembly. At least 66 of 72 sampled rim azimuths and at least 15 in each quadrant had an unobstructed sight line. The P3-only interpolated rigid-carriage bound was 0.24471 mm. Camera bodies, lenses, achievable pixel accuracy and elastic movement are separate from this sight-line model. [Assembly checks](results/candidate_assembly.json) · [Optics](results/optics.json)

## What the displacement includes

A finite beam represents the actual varying steel section and a solid model represents contact on the PA12 coupon. The inputs use steel at 200 GPa and PA12 at 1.53 GPa with Poisson's ratio 0.40. The published P3 force, its reversal and the +1 N reference act in the registered coupon orientation. The 38 solutions cover three web meshes, two steel discretisations, two tied-thread lengths and fixed-slope or free-slope transverse supports. These idealizations bracket support sensitivity under prescribed clearances. The peak converged force residual was 0.000077 N.

| Finest web mesh, full thread tie | Fixed-slope support | Free-slope support |
|---|---:|---:|
| Stage reversal, 3-D | 0.1152 mm | 0.2146 mm |
| Coupon relative to local shaft, transverse | 0.1043 mm | 0.1042 mm |
| Difference between shaft and optical face-chord reversal | 0.0085 mm | 0.1724 mm |
| Peak predicted clear-shaft bending stress | 402 MPa | 1,035 MPa |

The free-slope solution rotates the steel head into the actual solid cheek. A full-load head-half overlap of approximately 0.0127 mm³ excludes that ideal hinge as a physical seating description of the Ø1.46 carriage. The fixed-slope solution combined with opposite symmetric pilot seating gives a conditional stage reversal of 0.13438 mm, compared with 0.17374 mm at Ø1.50. Calibrating the stage still requires a bench measurement. The optically observed chord joins the pin-head and cap faces. Recovering strain relative to the shaft at the web requires actual contact and support characterization. The high unconverged local strain/pressure and estimated steel stress prevent a strength or fatigue release. [Restraint and CAD comparison](results/summary.json) · [Finest fixed-slope states](results/finer_clamped.json) · [Finest free-slope states](results/finer_hinged.json)

## Reproduce and measure

Use the repository's [bench environment](../m5_seat_bench_20261119/README.md). Run the following from this directory. Set `work` to a new scratch directory to preserve the dated outputs.

```bash
work=$(mktemp -d)
mkdir -p "$work/cad" "$work/results"
python pilot_fit.py --cad-dir "$work/cad" --out "$work/results/pilot_fit.json"
python ../m5_seat_bench_20261119/fixture_check.py --pin-carriage "$work/cad/pin_carriage_bore_1p46.stl" --out "$work/results/candidate_assembly.json"
for support in clamped hinged; do
  for mesh in middle finer; do
    python supported_contact.py --mesh "$mesh" --support "$support" --levels 1 -1 ref --out "$work/results/${mesh}_${support}.json"
  done
  python supported_contact.py --mesh fine --support "$support" --levels 1 -1 ref .25 -.25 .5 -.5 .75 -.75 --out "$work/results/fine_${support}.json"
  python supported_contact.py --mesh fine --support "$support" --spacing .075 --facets 48 --out "$work/results/fine_${support}_steel_refined.json"
  python supported_contact.py --mesh fine --support "$support" --thread-limit -3.125 --out "$work/results/fine_${support}_short_tie.json"
done
python optics.py --results "$work/results" --carriage "$work/cad/pin_carriage_bore_1p46.stl" --out "$work/results/optics.json"
python reduce_bench.py --results "$work/results" --cad "$work/cad"
python witness.py --out "$work/results/witness_status.json"
python -m unittest -v test_p3
```

For the bench, measure the installed bore diameters, relative offsets, pin/cap diameters, material lot and assembly torque. Calibrate both camera views in the same fixture frame. Record the two outer-face centres and actual axial face positions with each coupon/stage datum and its uncertainty. Use the same specimen, fixture, calibration, direction and program phase in both CSVs. The scorer interpolates the measured face chord to the pivot plane, propagates the stated bounds and retains signed reversal and residual motion. [Witness scorer](witness.py) · [Current measurement status](results/witness_status.json)
