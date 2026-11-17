# Next morning reference — 17 November 2026

Prepared **16 November 2026 08:12:29 EST (16 November 2026 13:12:29 UTC)**
for the next morning from the 16 November Morning Report. Machine-readable
times are recorded in [run_context.json](run_context.json). Reviewed base:
`e9c4858524fc21db2e1a19d1d748836c3a1eb28e`, including evening revision
`e80406891b1d2485567412183ae79eba550d0bed`. Previously verified branch revision:
`73b0b51d1e9593cb924c33e4f5c85258effe584d`. This new handoff belongs to the commit
containing it; that commit is not claimed pushed by this pre-publication file.
The automation reference and completion result identify the verified pushed
revision after publication.

[Morning Report](../../../../reports/daily/Morning_Report_2026_11_16.md) ·
[Evidence and reproduction](README.md) · [Saved validation](artifact_validation.json)

**Fetch GitHub afresh first**, including `origin/main`, `codex/guide-validation`
and any newer evening results. This reference is advisory, not a fixed plan.
Keep the 500 g head, U4+M2, actual CAD dimensions and no new backbone end ferrule.
All outgoing files, labels, logs and metadata must remain entirely English;
run the blocking whole-file publication check before commit and before push.

## Reuse the completed evidence

- Opt-in constrained frictionless bellmouth paths now close at the actual
  prescribed guide centres and supply consistent energy gradients and loads.
  Previous outgoing CAD-check rays missed by up to 0.586111 mm.
- 217 fixed-winch selected holds / 199 unique states solve; reconstructed old
  rest lengths give up to 3.478548 mm head change, 1.147100 deg yaw change and
  0.626278 deg elevation change. Minimum fixed-winch tangent eigenvalue is
  0.225526. No updated full feedback trajectory or dynamic stability claim.
- 5208 rigid-end checks have no failures within 0.005 mm mesh tolerance;
  minimum sampled clearance is -0.0004246 mm at intended bearing. Tank-envelope
  minimum after allowance is 7.687012 mm. Tensions are 2.882692–18.732424 N.
- Simultaneous load tables are under `rigid_end_audit/`: maximum per-hole force
  5.718505 N, station resultant 28.449191 N, station moment 61.121935 N mm.
  Do not combine unrelated scalar maxima into an invented simultaneous load.
- Mount contact persists: 6/48 checks at 0.5 mm; all six repeated checks fail
  at 0.25 mm, maximum 0.009765079 mm3 (state 146, M5 z+12).
- Five 16-cell holds give up to 0.332326 mm, 0.096202 deg yaw and 0.031620 deg
  elevation difference from the eight-cell fixed-winch model. This is not a
  physical error bound or a replacement for the older force-controlled study.
- 45 regression tests and eleven configuration checks pass. The two
  non-converged fixed-tension probes at source states 38/39 remain visible.

## Provisional priorities

1. **Guide-to-web attachment compatibility.** Use actual V3 saddles/webs and
   the new simultaneous load vectors to formulate an articulated/compliant
   joint or other feasible attachment. Acceptance: closed connected CAD parts,
   real web attachment, unchanged or explicitly reconciled rope stations,
   straight and critical bent contact checks, quantified support displacement
   and stiffness implications. The 0.5 mm land has unqualified bond/printed
   strength; shaving away interference without a load path is insufficient.
2. **Remaining physical rope constraints.** Extend contact/routing to shared
   bore lateral motion, U4 exits, finite guide mouths and the rigid-to-flexible
   end transition. Acceptance: full 2 mm envelope, material-bridge checks,
   consistent solver/CAD paths, domain and friction assumptions declared.
   Current interface-centre constraints and homogeneous rod stiffness are
   modelling assumptions, not proof that the installed rope behaves this way.
3. **Controller and uncertainty after a defensible candidate.** Recalibrate
   using the consistent routing, joint stiffness and mass. Acceptance: loaded
   startup, insertion, both yaw excursions and returns, withdrawal, tension
   and actuator bounds, clearance and appropriate mesh/parameter sensitivity.
   Label any targeted subset; do not repeat unchanged whole studies merely
   because the previous plan listed them.

## Resources and stop conditions

The available memory limit was 8 GiB. The targeted 0.25 mm run completed in
65.78 s at 3.503 GiB peak RSS under a 6 GiB virtual-memory cap by loading only
the needed **complete M5 body**. No cropping was used. Run expensive CAD jobs
sequentially; preserve checkpoints and reject unsupported tangent-domain
trials. Do not extrapolate this memory observation to both refined bodies or
larger study sets. The 120-minute total budget includes validation, reporting,
push, reference update and completion notification. Stop expensive studies by
minute 95 or sooner. Preserve failures and report incomplete work explicitly.
