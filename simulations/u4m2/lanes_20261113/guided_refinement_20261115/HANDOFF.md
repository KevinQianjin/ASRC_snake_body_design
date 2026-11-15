# Next morning-run handoff — 15 November 2026

Read the [Morning Report](../../../../reports/daily/Morning_Report_2026_11_15.md),
[validated summary](validated_summary.json), [evidence map](README.md) and
[V3 CAD notes](../../../../cad/lanes_u4m2/guides_v3/README.md) before launching work.
Fetch `codex/guide-validation` and compare `origin/main`; do not assume this
cloud filesystem or a particular commit remains current. The report identifies
the baseline revision; the Git commit containing these files records the update.

## Next morning schedule and reference status

Next scheduled start: **16 November 2026 07:00 EST (12:00 UTC)**. The current
runtime limit is **two hours**, giving **09:00 EST (14:00 UTC)** as the deadline
for an on-time start. Treat the priorities below as a reference: fetch the
latest GitHub commits and any newer evening report before choosing the work.
Publish an English Morning Report and send a completion summary, including
failures or incomplete work, when the run finishes.

## Completed evidence to reuse

- Actual V2 bodies, 500 g head, A/B/C lanes 21/24/28 mm and M guide stations
  −24/−12/+12/+24 mm remain the inputs. No backbone end ferrule was added.
- V2 complete-body contact has been checked at original/2/1/0.5 mm axial CAD
  surface resolution in the 0°/90°/175° holds. Do not rerun unchanged cases.
- Final V3 uses slope 1.5 and **explicit ±0.25 mm loft breakpoints** for the
  0.5 mm land. All eight straight assemblies, component counts and 112 gap rays
  pass. Earlier nine-section variants are rejected experiments.
- All 217 selected fixed-tension equilibria solve. The 1,736 complete-body
  contact checks are complete after checkpoint recovery: 96 failing part checks
  in 55 records; maximum overlap 0.008958824 mm³ at record 146, M5 z+12.
- Record 146 maps back to the source motion archive via
  [selected.json](contact_subset_final/selected.json). Record 64 is the 175°
  inverse hold. These are useful targeted follow-up poses, not full-path coverage.
- End-region rope-centre penetration remains in 57 records, maximum 0.240640 mm.
  Middle-flexure screening passes, with minimum sampled allowance-adjusted
  clearance 4.890498 mm. The full Ø2 mm rope envelope still needs finite contact.
- The consolidated pose table includes head frame/position, lengths, tensions,
  guide overlap and rope checks. Per-hole force vectors are in `v3_final_path/`.
  Peak station force and moment occur in different states; use simultaneous loads.

## Priority and acceptance gates

1. Resolve the fixed-land/guide-to-web joint kinematics with an explicit local
   structural/contact model. A short adhesive land is not a hinge. Its nominal
   area is only 5.67 mm² per saddle, about 84% below V2. Quantify stiffness and
   guide movement under the exported simultaneous loads before promoting it.
2. Revise disk/anchor entry and exit paths for the full 2 mm rope diameter.
   Check remaining material bridges, contact/friction and installation access.
   Do not simply enlarge adjacent bores and claim a strength pass.
3. Confirm geometry at straight and selected loaded poses before another full
   controller run. If mass, support stiffness or guide coordinates change,
   update solver inputs. Preserve startup, insertion, both yaw excursions and
   returns, and withdrawal when the full cycle is eventually replayed.
4. Keep separate numerical refinement, static tangent positivity, real contact,
   printed strength and hardware evidence. The old 0.359° equilibrium-mesh
   discrepancy is still unresolved; 0.2° settling is not physical accuracy.

## Resource failure and recovery

The cloud limit was 8 GiB. Running the 0.25 mm spot check concurrently with the
0.5 mm audit caused two OOM kills. The fine check produced **zero results**;
do not report V3 convergence at 0.25 mm. The main checkpoint retained 193 complete
records; only the 24 missing records were recomputed sequentially and validated
by `merge_contact_checkpoints.py`. Exact duplicate cached rows in the continuation
are explicitly counted and omitted by that merger; conflicting rows are rejected.

For finer checks, first reduce peak memory and process only needed bodies/parts,
then run one study at a time with an explicit memory/time budget. No study is
left running. Use a new dated output folder and preserve all historical failures.
