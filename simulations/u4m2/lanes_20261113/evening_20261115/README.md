# Evening study, 15 November 2026 (EST): finite-rope end-region contact and exit bellmouths

Report: [Evening Engineering Report — 2026-11-15](../../../../reports/daily/Evening_Report_2026_11_15.md)
· Handoff: [HANDOFF.md](HANDOFF.md) · CAD: [end_bellmouth_v1](../../../../cad/lanes_u4m2/end_bellmouth_v1/README.md)
· Run times, source revision, input hashes, environment: [run_context.json](run_context.json)

All studies use the **217 saved V3 500 g equilibria** from
[`../guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz`](../guided_refinement_20261115/v3_final_mass_holds/)
at their saved tensions. These are re-solved equilibria for selected motion
states, **not a full closed-loop cycle replay**. No equilibrium was re-solved
tonight. Lanes are 21/24/28 mm and the head is 500 g.

## Folders

| Folder | Script | What it is | Result |
|---|---|---|---|
| `end_envelope_v2_bodies/` | [`end_region_envelope.py`](../end_region_envelope.py) | Morning-style beam-mapped CAD screen (0.5 mm surface refinement, 0.05 mm rope samples) with the **full Ø2 mm rope**: signed centre distance − 1 mm, on V2 M5/M6 bodies | **214/217 records** interfere; minimum −1.252 mm at the M5 distal bore; centre-only penetration in 60/217 records, max 0.252 mm |
| `exit_routing/` | [`end_exit_routing.py`](../end_exit_routing.py) | Diagnostic: deflections measured against the *cell-mapped (bent)* bore | Up to 8.7°. The beam map bends the 7 mm rigid block by up to ~3.8°, so it is not a rigid-bore model |
| `exit_pivot_uniform_R7_w18_rejected/` | [`end_bellmouth_study.py`](../end_bellmouth_study.py) | Rigid-end exit-pivot model, uniform 7 mm fillet / 18° wrap | **Rejected**: 279 exits in 102 records exceed the wrap; max 27.09° |
| `exit_pivot_trial_R4_w28_rejected/` | same | Per-exit trial: M5 distal 4 mm/28°; M6 12°/10° | **Rejected**: 9 exits (27.0–27.1°) inside 28° but not the 1° margin; M6 fillets also failed the CAD build |
| `exit_pivot_bellmouth_v1/` | same | Final per-exit design ([design.json](../../../../cad/lanes_u4m2/end_bellmouth_v1/design.json)) | **0/5208 exits** beyond wrap−1°; per-rope M5+M6 length change 0.005–0.307 mm |
| `bellmouth_cad_check_v1/` | [`bellmouth_cad_check.py`](../bellmouth_cad_check.py) | Exit-pivot rope envelopes against the **new CAD** (rigid end, undeformed frame) | **0/5208 failures**; min −0.0027 mm = intended bearing within the 0.005 mm faceting tolerance |
| `bellmouth_paths_on_v2_bodies/` | same | Same paths against the unchanged V2 bodies | 5200/5208 fail, min −0.335 mm. This shows that the fillets are necessary for this path; it does not reproduce the actual V2 rope path |
| `logs/` | | Console output of every run | |

## Rigid-end exit-pivot deflections (final design)

| Exit | Checks | Max deflection | Max radial | Max tangential | Interface-chord angle (ideal model) | Straight flare half-width that interface pivot would need | Max length change per exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| M5 proximal (3 mm) | 1736 | 17.78° | 12.43° | 17.41° | 15.16° | 1.813 mm | 0.058 mm |
| M5 distal (7 mm) | 1736 | 27.09° | 26.98° | 19.94° | 13.80° | 2.720 mm | 0.229 mm |
| M6 proximal (3 mm) | 868 | 10.26° | 9.47° | 10.26° | 8.97° | 1.474 mm | 0.027 mm |
| M6 distal (7 mm) | 868 | 8.14° | 7.45° | 6.93° | 5.22° | 1.639 mm | 0.038 mm |

A straight flare whose throat stays at the interface pivot needs a 2.72 mm
half-width at the M5 distal inboard face. Same-ray B (24 mm) and C (28 mm)
holes are only 4 mm apart, so that option is rejected for the distal end.

## Reproduce

Run these commands from `simulations/u4m2/lanes_20261113`:

```bash
S=guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz
python end_region_envelope.py $S --cad ../../../cad/lanes_u4m2/guides_v2 --out evening_20261115/end_envelope_v2_bodies     # ~7.5 min
python end_exit_routing.py $S --out evening_20261115/exit_routing
python end_bellmouth_study.py $S --design ../../../cad/lanes_u4m2/end_bellmouth_v1/design.json --out evening_20261115/exit_pivot_bellmouth_v1
(cd ../../../cad/lanes_u4m2/end_bellmouth_v1 && python build.py)
python bellmouth_cad_check.py evening_20261115/exit_pivot_bellmouth_v1/exit_pivot.csv --design ../../../cad/lanes_u4m2/end_bellmouth_v1/design.json --cad ../../../cad/lanes_u4m2/end_bellmouth_v1 --out evening_20261115/bellmouth_cad_check_v1   # ~10 min
python -m pytest -q test_end_bellmouth.py test_guides.py test_cad_surface_refinement.py
```

## Scope limits

- **Rigid ends.** The rigid-end frame is the rod frame at the module-interface node. The
  flexure between |z| ≤ 40 mm still uses the homogenised cell map. The two maps are not
  blended at z = ±40 mm. This affects only the flexure screen, which is unchanged tonight.
- **Contact model.** The rope path consists of a straight bore section, an arc concentric with the
  fillet and a tangent span. It has no friction, bending stiffness, flattening or
  wear. This is a geometric admissibility check, not a contact-force solution.
- **Solver mismatch.** The solver still uses interface pivots. Guide forces, rope lengths, head pose
  and the closed-loop controller have **not** been recomputed with exit pivots.
- **Out of scope.** U4 distal exits and guide/body contact were not rechecked. Guide/body contact
  (55/217 records, 0.009 mm³, morning) is unchanged by this end-region change.
