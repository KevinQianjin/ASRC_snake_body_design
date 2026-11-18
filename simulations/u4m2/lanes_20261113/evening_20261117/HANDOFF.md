# Next-run handoff — from the 17 November 2026 Evening Report

Prepared **17 November 2026 20:45 EST (18 November 2026 01:45 UTC)** by the
evening run that started 20:02:11 EST (01:02:11 UTC). The verified pushed
revision is given in the completion result, not in this pre-publication file.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_17.md) ·
[Evidence](README.md) · [Previous handoff (16 Nov evening)](../evening_20261116/HANDOFF.md)

**Fetch GitHub first.** This plan is advisory. Keep the 500 g head, U4+M2,
actual CAD dimensions and rope stations. Do not add a backbone end ferrule.

## What is now established

- **The M body is eight 3.0 mm flat radial ribs**, joined only by the end disks
  and four inner rings. It is *not* "four 16 mm² struts". The ±12 mm guides
  grip one 1.53 mm × 3.0 mm inclined strut on each of four ribs.
- **A calibrated rib-level linear model exists.** It is
  `rib_joint_3d.py`, a membrane plus Mindlin plate model of the actual CAD rib.
  One PA12 modulus of **1530 MPa ± 1%** reproduces all three database
  stiffnesses: EA, EI and GJ (GJ as the rod coefficient T/θ × 0.096 m).
  Two meshes agree within 1%. A complete run takes under 3 minutes.
- **The rigid bonded land (V3 and its 0.25 mm-gap variant) is mechanically
  intrusive.** At record 146 each land carries about 8.3 N axial, 7.5 N
  radial and tangential force, and up to 100 N·mm moment. The bond raises
  module EI by 10.4% and GJ by 11.8%. 145/217 holds exceed half of that
  curvature (linear, worst-axis upper bound).
- **The homogenised beam map understates the joint incompatibility about
  6.2-fold** (0.535 vs 0.086 mm, in-plane stage). The 16 November bond-shear
  numbers were optimistic.
- **A translation-only (ball/point) attachment** is the least intrusive
  idealisation tested: 5.3 N radial and tangential, no moments, EI +1.3%,
  GJ +0%. It must allow about 0.22 rad of rotation and up to 0.92 mm
  in-plane strut motion inside the present socket. A tangential-axis pin
  is **not** load-free once out-of-plane stiffness is included (15 N,
  88 N·mm).
- The bare module reaches about **7.8% linear peak surface strain** at the
  record-146 curvature. The linear model is outside its range there.

## Priorities

1. **Nonlinear check of the rib model at large bends (decisive for trusting
   the loads).** The linear model is scaled to a 1.68 rad module rotation.
   - *Approach:* do an incremental or corotational large-rotation solve of the
     same rib superelement assembly, or a 3D solid FE if tools are
     available. Load in steps to the record-146 curvature, with bending axes
     0° and 67.5°.
   - *Accept when:* EI(κ), the rigid-bond and ball land loads, the
     ball-variant rotation and the peak strain are reported against the
     linear values. Also report whether the strain field stays where PA12
     can be assumed elastic, quoting a cited datasheet value, not an
     invented allowable. If no nonlinear capability can be built in time,
     state that and do a two-step secant check instead; do not claim
     nonlinear FE.
2. **First CAD of a point/line-contact guide saddle** (only if item 1 does
   not overturn the ball-variant ranking).
   - *Design:* the guide touches each strut through a short boss or ball seat
     at the land centre. That contact transmits radial and tangential force
     and gives the guide an axial datum, but leaves rotation free. The socket
     flare must clear 0.22 rad of rotation and the strut motions above.
     Define retention that transmits no moment, for example a captive ball
     or a lockwire loop.
   - *Accept when:*
     - closed, watertight CAD exists;
     - rope bores are unchanged (`rope_station_invariance.json` method);
     - the straight assembly is clear;
     - the 217-hold screen is clear with **rib-level kinematics**. Extend
       `guide_web_compatibility.py` to map body points with the rib model
       rather than the homogenised map, which is now known to understate
       local motion;
     - a stated load path exists for 28.45 N station loads plus about
       5.3 N parasitic load.
3. **Solver consistency.** If any rigid bond is retained, update the M5 EI and
   GJ used by the rod model (+10% / +12%) and re-solve the affected holds.
   With a ball-type joint the change is ≤ 1.3% and a re-solve is not needed.
   Only after a physically compatible joint exists, plan the labelled
   complete closed-loop replay: startup, insertion, right and left
   excursions with returns, and withdrawal.

## Resources and stop conditions

- Machine this run: 4 CPUs, 15 GiB. Each `rib_joint_3d.py` mesh solve takes
  under 2 minutes. Peak memory was not recorded, but the machine was never
  near its limit; the largest sparse factorisation has about 170k DOFs.
- Dependencies were not preinstalled. Pip installs into `/usr/bin/python3`
  (3.13), not into `/usr/local/bin/python3` (3.11); use the former. Install
  with:
  `pip install numpy scipy numba trimesh manifold3d matplotlib shapely networkx rtree 'cadquery-ocp==7.8.1.1.post1' triangle`.
  `vtk` is needed only for the existing compatibility screen.
- Stop expensive work by minute 95 of 120. Keep failures visible.
