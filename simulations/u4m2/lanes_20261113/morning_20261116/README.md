# Morning evidence — 16 November 2026

[Morning Report](../../../../reports/daily/Morning_Report_2026_11_16.md) ·
[Next-run handoff](HANDOFF.md) · [Run context](run_context.json) ·
[Artifact validation](artifact_validation.json)

Actual start/cutoff: **16 November 2026 07:19:33 EST (12:19:33 UTC)**.
Deadline: **09:19:33 EST (14:19:33 UTC)**. Source revision before the new work:
`e9c4858524fc21db2e1a19d1d748836c3a1eb28e`. The commit containing this folder
adds the implementation; [source hashes](source_sha256.json) identify its exact
source files. No historical result folder is overwritten.

## Scope and evidence map

The 500 g head, U4+M2, 21/24/28 mm lanes, guides at -24/-12/+12/+24 mm and
backbone are unchanged. Existing bellmouth STL geometry is reused. Its measured
0.043337 g PA12 removal is included in the mass model. This is constrained,
frictionless interface-centre routing, not complete physical contact simulation.

| Folder/file | Coverage and result |
|---|---|
| `fixed_winch_holds/` | 217/217 solved, 199 unique states; reconstructed V3 rest lengths held fixed; 1 m free rope. Four validated probe solutions reused, 195 new unique solves. |
| `rigid_end_audit/` | 5208 exits, 10416 guide-hole load rows, 1736 simultaneous station rows; no end-envelope failures within 0.005 mm tolerance, sampled at 0.02 mm. |
| `tank_envelope/` | All 217 selected 63 mm envelope checks pass; minimum allowance-adjusted clearance 7.687 mm. This does not certify the actual head CAD. |
| `path_comparison/` | Previous outgoing ray misses actual guide centre by up to 0.586111 mm. New curves reach the prescribed centres; two English SVG comparison figures. |
| `mount_selected_0p5mm/` | Six poses x eight parts = 48 checks; six contacts remain. |
| `mount_targeted_0p25mm/` | Three poses x two M5 parts = six checks; all six still contact, maximum 0.009765 mm3. |
| `mount_targeted_resources.json` | Complete M5 body, no cropping, 3.503 GiB peak RSS, 6 GiB virtual-memory cap, 65.78 s including process startup. |
| `refined_16_cell/`, `rod_mesh_comparison.json` | Five independently re-solved holds at identical reconstructed rest lengths. Maximum 8-to-16-cell differences: 0.332326 mm head, 0.096202 deg yaw, 0.031620 deg elevation. |
| `bellmouth_holds/` | Initial fixed-tension attempt: 38 saved solved states, then an unsupported trial-domain exception. Incomplete; not the final study. |
| `solver_probe/` | Safeguarded fixed-tension diagnostic: states 64 and 146 solve, 38 and 39 do not converge. The failure traces are retained. |
| `rest_probe/` | Four fixed-winch probes solve and are reused after residual/hash checks. |
| `logs/` | Study output and validation logs, including the missing-pytest runner failure. |
| `environment.json`, `source_sha256.json`, `SHA256SUMS` | Dependency versions, final source hashes and evidence-file checksums. |

The source archive is
`../guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz`,
SHA-256 `db7148962360e24d914040c2dfd9e5a537832aa0c3aa8581ad3539a0830dd944`.
The published solved archive SHA-256 is
`855da889c69a917f5493781ccedb56c27e353701db551b33acfa0d985227a544`.
Each archive preserves force/state alignment and source metadata. All 217
records are retained even where geometries repeat.

## Reproduction

Use Python 3.12 and the versions in [environment.json](environment.json).
In this run, existing isolated dependencies were loaded with
`PYTHONPATH=/workspace/guide_dependencies`. On another machine use a virtual
environment with the listed packages. Set `OPENBLAS_NUM_THREADS=1` and
`OMP_NUM_THREADS=1` to bound CPU/memory use. Run from
`simulations/u4m2/lanes_20261113`.

The commands below deliberately use a **new** output folder. The hold/audit
scripts reject existing output directories. The historical mount script permits
an existing directory, so always give it a fresh one. Run expensive CAD jobs
sequentially. Timings are observations on this environment, not runtime promises.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export MPLCONFIGDIR=/tmp/asrc-matplotlib
python solve_bellmouth_holds.py guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz --mode rest --out reproduction_20261116/holds --max-seconds 1200
python audit_bellmouth_holds.py reproduction_20261116/holds/equilibria_states.npz --mass reproduction_20261116/holds/mass_model.json --out reproduction_20261116/ends --max-seconds 1200
python audit_bellmouth_envelope.py reproduction_20261116/holds --out reproduction_20261116/tank
python compare_bellmouth_paths.py guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz --solved reproduction_20261116/holds --out reproduction_20261116/comparison
python solve_bellmouth_holds.py guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz --mode rest --sub 16 --indices 38 48 63 64 146 --out reproduction_20261116/fine_rod --max-seconds 300
python mount_refinement_study.py reproduction_20261116/holds/equilibria_states.npz --cad ../../../cad/lanes_u4m2/end_bellmouth_v1 --guide-cad ../../../cad/lanes_u4m2/guides_v3 --out reproduction_20261116/mount_0p5 --resolutions 0.5 --states 0 38 48 63 64 146 --max-seconds 300
(
  ulimit -v 6291456
  python mount_refinement_study.py reproduction_20261116/holds/equilibria_states.npz --cad ../../../cad/lanes_u4m2/end_bellmouth_v1 --guide-cad ../../../cad/lanes_u4m2/guides_v3 --out reproduction_20261116/mount_0p25 --resolutions 0.25 --states 63 64 146 --parts M5_z-12 M5_z+12 --max-seconds 300
)
```

The completed run first used `--indices 38 39 64 146 --mode rest` for
`rest_probe`, then `--reuse morning_20261116/rest_probe` for the full solve.
Omitting reuse recomputes the same selected set. The diagnostic force probe
uses `--mode force --indices 38 39 64 146`; two non-converged states are expected
with the recorded solver settings. The initial unguarded attempt is retained
for provenance, but the final guarded solver does not reproduce its crash.

The five-point rod comparison uses base-frame head positions from the two
archives, shortest signed yaw differences, elevation differences and maximum
absolute tension differences. It holds the original reconstructed winch
lengths fixed, rather than reconstructing new lengths from each solved mesh.

### Tests and saved-evidence checks

From the lane folder, the exact 31-test geometry suite can run without pytest:

```bash
python - <<'PY'
import inspect
import unittest
import test_guides, test_cad_surface_refinement, test_bellmouth_solver, test_end_bellmouth
suite = unittest.TestSuite()
for module in (test_guides, test_cad_surface_refinement, test_bellmouth_solver):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
for name, function in inspect.getmembers(test_end_bellmouth, inspect.isfunction):
    if name.startswith('test_'):
        suite.addTest(unittest.FunctionTestCase(function))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
PYTHONPATH=../backbone_20261108:$PYTHONPATH python -m unittest -v test_length_cycle test_closed_loop test_closed_loop_v2
python validate_bellmouth_results.py morning_20261116 --out /tmp/asrc_artifact_validation.json
```

The 14 control tests exercise the existing controller/rope code. They do not
constitute a new closed-loop replay using the bellmouth model. The new lane
kernel is opt-in through `apply_bellmouth()`, leaving default routing unchanged.
Run `python scripts/validate_configs.py` from the repository root for the eleven
configuration checks. The dedicated evidence validator rechecks all 217 saved
equilibrium residuals and force/rest-length alignment, CSV counts, CAD/source
hashes and finite arrays without repeating the expensive CAD-distance study.

## Publication checks

[publication_validation.json](publication_validation.json) records the exact
outgoing path list and full-content methods. Scope includes files newly brought
onto `codex/guide-validation` from the already published evening/main revisions,
as well as this morning's changes. It is not a repository-wide historical audit.

The blocking gate reads staged Git blobs before commit and committed blobs
before push. It checks ASCII paths, Han extension/compatibility/radical ranges,
escaped/HTML/URL text and Python/JSON strings. NPZ members are decompressed and
parsed without pickle; binary STL headers are read and numeric triangle records
identified. Unknown binary types fail. Both SVGs retain text, have no embedded
images, and were rendered and visually reviewed for English labels. No PDF or
Office export is created by this run. Numerical values and failures are retained.
No private notification content, mail address or delivery metadata is published.

From the repository root (substitute the actual pre-push remote revision if it
has changed):

```bash
python scripts/check_publication_language.py --base 73b0b51d1e9593cb924c33e4f5c85258effe584d --tree index --reviewed-visual simulations/u4m2/lanes_20261113/morning_20261116/path_comparison/endpoint_closure.svg --reviewed-visual simulations/u4m2/lanes_20261113/morning_20261116/path_comparison/pose_changes.svg --out /tmp/asrc_language_before_commit.json
python scripts/check_publication_language.py --base 73b0b51d1e9593cb924c33e4f5c85258effe584d --tree HEAD --reviewed-visual simulations/u4m2/lanes_20261113/morning_20261116/path_comparison/endpoint_closure.svg --reviewed-visual simulations/u4m2/lanes_20261113/morning_20261116/path_comparison/pose_changes.svg --out /tmp/asrc_language_before_push.json
```

`SHA256SUMS` covers every evidence file except itself. It is refreshed after the
publication records are saved. Relative links in all outgoing Markdown files
are checked; external-link reachability is not implied. The saved publication
record precedes commit; the same exact committed file set is checked again
before push without changing that record or its checksum.

## Interpretation limits

End-envelope acceptance permits 0.005 mm faceting tolerance at intended bearing;
the minimum is -0.0004246 mm, not a positive manufacturing clearance. The screen
uses rigid-end coordinates through `|z| >= 38 mm` and cannot qualify the end/web
transition. Interface centres remain prescribed; shared-bore lateral freedom,
U4 exits, finite guide-mouth contact, friction, D/d fatigue/wear, printed
strength and adhesive/support compliance remain unresolved. Fixed-winch
tangent positivity is quasi-static, not dynamic stability or physical accuracy.
Only six poses received updated coarse guide Booleans and three received fine
Booleans. All required path phases are represented in selected holds, but no
new full feedback trajectory is claimed. The design is not released for manufacture.
