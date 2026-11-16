# V3 flared-socket guide candidate — 15 November 2026

**16 November Morning Report follow-up:** [Re-solved bellmouth-route states](../../../reports/daily/Morning_Report_2026_11_16.md) increase the selected peak station load to 28.449 N. All six targeted M5 outer-saddle contact checks remain positive at 0.25 mm CAD resolution (maximum 0.009765 mm³). The guide geometry is unchanged and its joint still needs a physical stiffness/contact model.

**Engineering candidate; not released for manufacture.** This revision relieves
the mouths of the four outer-web saddles at each local z = ±12 mm station. It
addresses the guide/body interference identified by the refined CAD screen.
It does not establish joint strength, guide stiffness, assembly access or a
physically valid complete robot cycle. See the [Morning Report](../../../reports/daily/Morning_Report_2026_11_15.md)
for the measured coverage, failures and comparison with V2. That morning
run started at **15 November 2026 07:01:11 EST (12:01:11 UTC)**; its report
preparation time was **08:12:54 EST (13:12:54 UTC)** on the same date.

## What changes

The guide still has four rope arms and four attachments to actual M-body webs.
At the ±12 mm stations, the socket keeps its nominal 0.15 mm gap over a central
**0.5 mm axial land**. Away from this land, the radial and tangential gaps grow
linearly with axial distance, with a **1.5:1 relief slope**:

`gap(z) = 0.15 + 1.5 × max(abs(z) - 0.25, 0)` mm, in local socket coordinates.

The gap reaches 2.205 mm at the ±1.62 mm socket faces. The 0.85 mm socket wall is
generated around this relieved cavity. The inward cap follows the new cavity;
the nominal Ø0.35 mm lockwire and 0.45 mm groove retain their central positions.
Early relief slopes 0.3 and 0.6 reduced but did not eliminate interference at
the 175° hold. An early 1.0 variant passed three poses but failed 17 of 181
expanded records. The final 1.5 variant remains an engineering candidate;
contact near its fixed land is still a release blocker.

The outer-saddle loft now includes the exact ±0.25 mm land boundaries, for
eleven section planes. The early nine-section loft did not actually preserve
the whole flat land and could let the retaining groove split a cap at larger
relief. The final exported gap profile is checked with 112 rays from actual
source-CAD web faces; see [gap verification](../../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/socket_gap_verification.json).

The ±24 mm inner-web stations retain the V2 geometry. Lane radii **21/24/28 mm**,
rope bores Ø2.6 mm, rounded mouths Ø3.0 mm, plate thickness 3.2 mm and the four
station locations **−24/−12/+12/+24 mm** remain unchanged. The central Ø1.8 mm
NiTi backbone remains independent; no end ferrule is added.

## Parts and installation limits

This folder supplies eight station-specific frames, their inward caps and their
lockwire envelopes. Reuse the [V2 module bodies, disks and anchors](../guides_v2/README.md);
they have not changed. Open [assembly.scad](assembly.scad) to inspect the actual
M5 parts with ropes and backbone. The body is a cutaway preview, so some support
webs are intentionally hidden. It does not prove installation access.

Only the outer socket's central 0.5 mm land is a proposed adhesive zone; the
flared mouths must remain free of adhesive fillets if their geometric relief
is to be retained. The nominal projected bonding area per outer saddle falls
from about **36.27 to 5.67 mm²**, an **84.4% reduction**. A qualified adhesive,
surface preparation, actual gap, pull/shear tests and cyclic tests are still
required. Lockwire closes the cap radially; it is not demonstrated axial
retention. Do not treat the narrow land as a validated hinge or flexure.

Four bonded webs still connect to one rigid guide. Relief does not establish
that the mounting preserves the M module's homogenised stiffness or the ideal
guide positions used by the solver. A local structural/contact model remains
necessary, including loads shared by the four saddles and cap/wire effects.

## Evidence and reproduction

- [Design parameters](design.json) and [straight assembly checks](geometry_check.json).
- [Updated CAD mass estimate](mass_model.json), including frames/caps/wire but
  excluding adhesive and closure tails. The head remains a separate **500 g payload**.
- [Dated simulation and contact evidence](../../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/README.md).
- [Full English Morning Report](../../../reports/daily/Morning_Report_2026_11_15.md).

With the V2 CAD dependencies available, run `python build.py` from this folder.
The default slope is 1.5. For a separate experimental variant, use
`python build.py --slope 0.6 --out /tmp/asrc-guide-slope-0p6`.
The builder reads the unchanged V2 bodies, writes only the selected output
folder, checks all eight straight assemblies and updates the mass estimate.
Regenerate and recheck the simulation whenever geometry or mass changes.

`--legacy-nine-sections` exists only to reproduce rejected early variants.
After building, run `python verify_socket_land.py --out socket_gap_check.json`
to measure the actual exported land/relief, independently of the loft inputs.

The end-disk/anchor rope contact problem is separate and remains unresolved.
Zero returned guide/body intersection volume in selected nominal poses is not
a manufacturing-clearance margin, full-motion certification or strength pass.
