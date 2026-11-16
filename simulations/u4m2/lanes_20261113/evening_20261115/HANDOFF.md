# Next-run handoff — prepared by the 15 November 2026 Evening Report run

Prepared at **2026-11-15 20:35 EST (2026-11-16 01:35 UTC)**. The next
scheduled run is the Codex **Morning Report** at **2026-11-16 07:00 EST
(12:00 UTC)**. Fetch all branches first. These priorities are advisory; newer
GitHub evidence takes precedence.

Read: [Evening Report](../../../../reports/daily/Evening_Report_2026_11_15.md),
[evidence README](README.md), [bellmouth CAD](../../../../cad/lanes_u4m2/end_bellmouth_v1/README.md),
[morning handoff](../guided_refinement_20261115/HANDOFF.md).

## State at handoff

- Finite Ø2 mm rope end-region screen of V2 bodies: **214/217** records
  interfere when the solver's interface pivot is used. The rope centre-only
  screen (57–60 records) under-reported the problem.
- Rigid-end, exit-pivot geometry shows exit deflections up to **27.09°**
  (M5 distal, C/up). The new `end_bellmouth_v1` M5/M6 bodies pass watertight,
  single-component, bridge (0.544 mm ≥ 0.5 mm) and envelope checks
  (**0/5208** failures) for all 217 saved equilibria.
- The guide/body V3 contact status from the morning remains open: 55/217
  records, maximum 0.009 mm³. The V3 saddle joint stiffness remains unvalidated.
- Do **not** rerun the completed studies in `evening_20261115/` unchanged.

## Priorities (max three)

1. **Put exit pivots into the rod solver and re-solve the 217 holds.**
   - *Why:* the solver bends the rope at the module interface. The physical rope
     bends at the inboard bellmouths. Rope lengths differ by up to 0.307 mm per rope,
     and the force distribution changes.
   - *Work:* add rigid end-region rope points at local z = −45 and +41 mm on
     each lane. Include the fillet arc length or the equivalent tangent-intersection
     point.
   - *Acceptance:* finite-difference gradient checks as in `lanes.py`. All 217
     holds must re-solve with positive fixed-winch tangents. Report head pose
     changes and new guide and exit loads. Report the exit wrap angle with the
     re-solved geometry; it must stay ≤ θ_d − 1°.
2. **Joint stiffness of the V3 saddle land (morning priority 1).**
   - *Why:* this priority is still unaddressed. The 5.67 mm² bonded land
     carries simultaneous guide forces and moments; peak station loads are
     27.4 N and 60.8 N·mm.
   - *Acceptance:* an explicit local structural/contact model gives guide
     displacement and rotation under the exported simultaneous loads. Its
     assumptions must be stated, without a strength claim unless the model
     supports one.
3. **Full closed-loop replay only after priorities 1 and 2 have results.**
   - *Coverage:* loaded startup/straightening → insertion → right yaw → return →
     left yaw → return → withdrawal.
   - *Required checks:* the end-exit wrap check and the guide/body check.
   - *Keep separate:* numerical settling from the unresolved 0.359° 8-to-16-cell
     discrepancy.

## Blockers, resources and constraints

- No hardware, printed-part, rope D/d or friction data exist. The rope
  centreline radii of 4.9–8 mm are geometric choices. Capstan friction on the
  fillets is unmodelled.
- U4 distal exits, where B/C ropes leave U4, were not checked. Use the same
  rigid-end method on the U4 body.
- Resources: the evening container had 4 CPUs and 15.7 GiB. The beam-mapped
  envelope screen took about 7.5 min, with about 0.9 GB RSS observed once.
  The CAD envelope check took about 10 min for 217 states; its peak memory was
  not measured. Keep studies sequential in an 8 GiB environment.
- Retain the 500 g head, U4+M2 design and 21/24/28 mm lanes. Do not add a
  backbone end ferrule.
