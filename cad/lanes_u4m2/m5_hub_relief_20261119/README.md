# M5 retained hub with a 0.15 mm inside-edge chamfer

The large M5 bend brings the returning web to the inner rim of the segmented guide hub. These two replacement sector geometries break the inner corner on both axial faces. Each chamfer extends 0.15 mm in radius and 0.15 mm axially. This dimension describes the hub edge. The V3 saddle bond gap describes a different interface. [Published source hub](../retained_seat_20261118/README.md) · [Dimension and volume checks](parts/manifest.json)

Use four [upper sectors](parts/hub_upper_sector.stl) and four [lower sectors](parts/hub_lower_sector.stl) per station in the existing alternating 45° positions. The remaining pieces, holes, ropes and independent backbone use the retained-seat design. This option was studied at the two M5 stations at ±12 mm. Keep the original sectors as the comparison specimens.

At the same archived 96.19° bend about 67.5°, the closest +12 mm rib-to-hub distance was 0.0440, 0.1002, 0.1567 and 0.2144 mm for inner-edge breaks of 0, 0.15, 0.30 and 0.45 mm. The 0.15 mm candidate was carried forward because it removed the hub as the closest part in the targeted coupled check with the smallest change in section. The tightly meshed +12 mm station improves from 0.04152 to 0.07483 mm at this bend. A second physical measurement is needed at the 0°-axis bend, where the −12 mm rib-to-fork gap of 0.06286 mm governs the six-case comparison. [Four-size comparison](../../../simulations/u4m2/lanes_20261113/m5_seat_bench_20261119/results/hub_sweep_original_pose.json) · [Common-guide CAD results](../../../simulations/u4m2/lanes_20261113/m5_seat_bench_20261119/README.md)

- Original inner radius 7.80 mm. A 2.90 mm axial band remains at this radius. The beginning of each chamfer is 0.855 mm above the nearest axial socket face.
- Each sector loses 0.13761 mm³. Four upper and four lower sectors remove 1.10084 mm³ per station. The exported parts are closed, connected solids.
- Conservative radial separation of the removed material from the lap, rope-arm and offset-fork screw envelopes is at least 1.229, 1.190 and 1.568 mm respectively. The half-height socket slice is preserved to the STL round-trip precision recorded in the manifest.
- The calculation treats each plate as rigid. Sector stiffness, lap-thread stripping, torque capacity and as-built edge quality need evidence. Local web/cage clearance after measured print and assembly errors remains an open release condition.

From this directory, run `python relief.py --size .15 --out /tmp/asrc-hub-sectors`. The generator reads the actual exported source mesh, removes material, then validates each delivered binary STL and its socket region.
