# Next-run handoff — from the 22 November 2026 Evening Report

Prepared at about **2026-11-22 20:40 EST (2026-11-23 01:40 UTC)** by the evening run. That run started at **2026-11-22 20:02:21 EST (2026-11-23 01:02:21 UTC)**, and its budget deadline is **22:02:21 EST (03:02:21 UTC)**. The pushed revision is reported in the completion message, which this pre-publication file cannot contain.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_22.md) · [Evidence](README.md) · [Previous handoff (21 Nov evening)](../evening_20261121/HANDOFF.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) · [Test programme](../../../../nextstep/README.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, the U4+M2 configuration, the actual CAD, the rope stations and the twelve Ø2 mm ropes. Do not add a backbone end ferrule.

## Established tonight (linear bond model and rigid CAD only)

- **Previous item 2 is done.** The crowned 0.25–0.31 mm layer was modelled with per-point thickness. The uncrowned nh = 2 `rod` case reproduces Round 2 to 4·10⁻¹³ mm, and the archived 63.96 MPa mission peak is reproduced exactly.
- **The Round 2 63.96 MPa pad traction is not a converged or load-driven number.** About 97% of it comes from the homogenised rod map, which imposes about 18% axial strain inside the 0.5 mm PA12 land. The linear field gives 103.6 MPa at 8 axial points (306 MPa at G = 1,500 MPa).
- **Load-driven tractions (`rigidland`) are 2–4 MPa** over the whole mission at both moduli. The crown lowers the kinematic peaks by about 18% (103.6 → 84.9 MPa) and raises the load-driven axial-shear peak by about 7% (3.44 → 3.67 MPa).
- **Witness motion is 0.0013–0.0029 mm and the guide-to-web rotation is 0.016–0.067°**, almost independent of the mismatch model.
- **Bond motion plus 0.2° tilt, exact CAD, at steps 1,709, 1,710 and 1,885:** the crowned land keeps **0.02839 mm (z = −12 mm)** and **0.04237 mm (z = +12 mm)**. Both are above 0.025 mm under every model and modulus. The uncrowned land keeps 0.00074 / 0.01554 mm.

## Priorities

1. **Bench: as-built land, bonded tilt and land strain (hardware, still first).**
   *Why:* the crowned margin and the bond demand now both hinge on unmeasured physical quantities.
   *Acceptance:* the unchanged acceptance from the [21 November handoff](../evening_20261121/HANDOFF.md): tilt ≤ 0.20° and offset ≤ 0.025 mm at both stations, with the land profile measured to 0.01 mm. **Add:** a lap-shear coupon of the chosen adhesive on PA12 at a 0.25–0.31 mm gap, giving G and shear strength; and, if possible, DIC or a strain gauge on the M6 web next to the land at the step-1,709 pose, to decide which mismatch model applies. Do not report this item as completed in simulation.
2. **Local solid model of one M6 rib with its bonded land (simulation, about 60 min).**
   *Why:* tonight's three mismatch models bracket the peak bond traction between 2–4 MPa (`rigidland`) and 85–306 MPa (`rod`). Only a model that resolves the web and cell deformation next to the land can select the right value.
   *How:* mesh the 247.5° rib of `end_bellmouth_v1/M6_lane_anchorC.stl` between the two neighbouring cell gaps with tetrahedra. Drive its cut faces with the rod-map displacement at step 1,709 (and 1,885), and bond the land with the crowned layer at the two assumed moduli. Converge the land-edge traction with mesh refinement.
   *Acceptance:* report the land-edge peak and mean tractions and the axial strain of the web across the land. State which of `rod`, `midplane` or `rigidland` the result is closest to. Re-check the strength demand in [`strength.py`](../../extreme_tests/round2_20261119/strength.py) without overwriting archived results.
3. **Mission-wide first-contact tilt at finer axis spacing, including bond motion (simulation, about 30–40 min).**
   *Why:* this was previous item 3, still open. Tonight's bond motion shifted the governing allowance by at most 0.0016 mm, so the combined first-contact tilt is still expected between 0.25° and 0.30°.
   *How:* extend [`../evening_20261121/tilt_mission.py`](../evening_20261121/tilt_mission.py) with axes every 5° from 120° to 180° (both senses). Bisect to 0.004° on the shapes whose 0.25° gap is below 0.02 mm. Optionally pre-apply the `rigidland` G = 1,500 MPa bond transform from [`bond_tilt_probe.py`](bond_tilt_probe.py).
   *Acceptance:* report the mission-wide minimum first-contact tilt and its step, phase and axis at both stations.

## Blockers and resources

- 4 cores and 15 GB of memory. Each process used less than 1.2 GB. The bond cases take about 25 s, a full-mission duty run (8 runs) about 2–4 min, and each probe about 5 min per station.
- Dependency note: importing the Round 2 bonded-land model also needs `vtk`, `shapely`, `triangle`, `manifold3d` and `networkx`, on top of the packages in the 21 November note (`clarabel`, a working `pillow`). Install them with `python -m pip`. `pillow` needed `--ignore-installed` over the broken system PIL.
- The `codex/m5-active-reset-load-export` branch (M5 active-reset pin screen) is still unmerged and has no committed results. It was not duplicated.
- The adhesive, as-printed land, bonded tilt and bond strength are unmeasured. The crowned candidate is not a manufacturing release.
