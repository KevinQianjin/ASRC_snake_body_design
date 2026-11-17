# Next-run handoff — from the 16 November 2026 Evening Report

Prepared **16 November 2026 20:35:00 EST (17 November 2026 01:35:00 UTC)** by the
evening run that started 20:02:13 EST (01:02:13 UTC). The verified pushed
revision is given in the completion result, not in this pre-publication file.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_16.md) ·
[Evidence](README.md) · [Morning handoff it supersedes in part](../morning_20261116/HANDOFF.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2,
actual CAD dimensions and rope stations. Do not add a backbone end ferrule.

## What is now established

- A calibrated full-coverage screen (`guide_web_compatibility.py`) covers all
  217 holds × 8 guides in about 4 minutes on 4 CPUs. Its pass/fail result
  matches the manifold Boolean in all 54 comparisons (48 at 0.5 mm, 6 at
  0.25 mm), including near-threshold cases. Use it before Booleans.
- Published V3 penetrates in **59/217 records** (M5 ±12 only, worst −0.0211 mm).
  The morning's 6/48 result covered selected poses only.
- The candidate with a 0.25 mm land gap (`evening_20261116/cad_v3_gap0p25`)
  clears all 1736 checks (minimum +0.0182 mm). It also passes 10 Booleans at
  0.25 mm and 48 at 0.5 mm. Rope bores are unchanged.
- The bond land would still see up to 0.087 mm axial slip under
  homogenised-beam kinematics: **35% shear strain at 0.25 mm gap** (58% at
  0.15 mm). No adhesive can be assumed to survive this; none is qualified.

## Priorities

1. **Strut-level joint model at the ±12 mm saddles (decisive).** The slip and
   contact come from mapping CAD rigidly with the homogenised rod section.
   The real ±12 mm section is four inclined 16 mm² struts. Build a local
   FE or beam-frame model of one M5 strut bay with the guide bonded on the
   0.5 mm land. Use the saved simultaneous station loads (`rigid_end_audit`
   tables) and the record-146 curvature. *Accept when:* strut-level relative
   slip at the land is compared with the 0.087 mm homogenised estimate, and
   the change in module bending stiffness is quantified for a bonded versus
   unbonded guide. If FE tools are not available, state that and do a
   strut-beam hand model instead; do not claim FE.
2. **Choose a joint concept from that slip.** If slip remains above about
   10% of any feasible bond-line thickness, a rigid bonded land is not
   viable. Compare an elastomeric bond line (state its required strain, not
   an invented product rating), a single-web axial datum with sliding radial
   saddles at the other three webs, and the 0.25 mm-gap variant. *Accept
   when:* closed watertight CAD exists for the chosen concept. It must give
   0/1736 screen failures, Boolean confirmation on the five worst records,
   unchanged rope bores (`rope_station_invariance.json` method), and a
   stated load path for all station forces.
3. **Then re-solve, not before.** Re-solve the 500 g holds only after the
   mount stiffness or guide positions change materially. The 0.25 mm variant
   changes module mass by only −0.0003 g. After that, plan a labelled
   closed-loop replay covering startup, insertion, right/left excursions and
   returns, and withdrawal.

## Resources and stop conditions

- Machine this run: 4 CPUs, 15 GiB. Four screen shards ran concurrently. A
  `free -g` snapshot during setup showed about 2 GiB in use in total; peak RSS
  per shard was not recorded. A full screen of 199 unique geometries takes
  2.7–4 min. Boolean checks at 0.25 mm with only the M5 body need 4.3–5.0 GiB.
  Run Booleans one at a time.
- Dependencies were not preinstalled. `pip install numpy scipy numba trimesh
  manifold3d vtk matplotlib shapely networkx rtree` was needed, with
  `pillow` reinstalled. For the control tests, install
  `cadquery-ocp==7.8.1.1.post1`; version 8.0 breaks `cad_sections.py`.
- Stop expensive work by minute 95 of 120. Keep failures visible.
