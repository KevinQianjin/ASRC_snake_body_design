# Free-space steering, local strength and repeat-duty life

This manual study uses four U modules, two M modules and a 500 g head including the adapter. The reference is commit `bbed30bde93a03fc8d7135533bc2b4c7fac02eec`. It retains the twelve 2 mm ropes, 21/24/28 mm lanes, 20° inclined clamp, gravity, two separate 1.8 mm M backbones and the retained M5 pivots. The external tank wall and the 5 mm tank criterion are removed from the angle search. The archived normal mission retains its original motion.

[Engineering results](../../../../reports/projects/extreme_tests/Free_Space_and_Service_Life_2026_11_20.md) · [Boundary table and hypothetical material limits](results/strength/limits.json) · [Normal duty](results/fatigue/life.json) · [Inputs, versions and checksums](results/verification.json)

## Reading the results

| Result group | Contents |
|---|---|
| [Offline 3D replay](results/replay/ASRC-500g-3D-Replay.html) · [Download ZIP](results/replay/ASRC-500g-3D-Replay.zip?raw=true) | Nine 8-cell round trips with 642 playback samples, all twelve ideal rope tensions and a separate first failed sample for each route. The 16-cell values are local fixed-command checks. Extract the HTML and open it in a browser. |
| [Angles](results/angles/) | An outward search and fixed-winch reverse replay for each direction. Each CSV row gives the actual head axis, all twelve forces, commanded and internal rope lengths, signed twist, bend and minimum radius for each module, body separation and simultaneous guide wrenches. The state arrays have the same row order. |
| [CAD and rope exits](results/geometry/) | Working CAD at six bonded stations, the remote adapter envelope and 24 finite end routes for each stored state. Additional midpoint rows resolve a sampled transition to at most one degree. |
| [Return before a geometric obstruction](results/return/) | A second replay starts at the screened endpoint, reverses the accepted commands and rejoins the published neutral-return motion. |
| [Discretization and candidate mass](results/mesh/) | The same twelve commands are re-equilibrated on 8- and 16-cell rods with the candidate guide mass. The governing commands and inward samples also receive a 16-cell, 0.25 mm CAD check. A [second boundary table](results/mesh/refined_transitions.json) resolves the fine-grid transition when the two meshes differ. A separate [directly opposite pointing test](results/mesh/opposite_axis.json) trims the upward meridian at +200° on each rod and recovers the original twelve commands. Errors above the 1° operating allowance remain visible. |
| [Alternative command allocation](results/allocation/) | Replay of the published 2° mixed-down schedules at ±175° yaw with end-angle margins, complete CAD checks to the first failure and a fixed-command return. |
| [Local strength](results/strength/) | An angle-resolved shell and pin analysis, a hypothetical installed-rope tensile-capacity lookup and trial printed-web strain thresholds. |
| [Repeated service](results/service/) | The first reset, the entire second mission and the second reset of each re-equilibrated friction-plant variant. Archived first missions are linked through the input manifest. |
| [Fatigue and wear](results/fatigue/) | Full ranges, means, half cycles, per-rope sliding and drum travel, motion-phase contributions and resistance required for a stated design duty. |

## Steering and geometric checks

Yaw is an accumulated heading at +20° elevation. Pitch is signed travel along a vertical meridian and can pass through either vertical pole. The angle between the actual head axis and the original clamp axis is reported separately. It is always between 0° and 180°. Neither heading travel nor axis separation measures one module's bend or the roll of a sensor.

The original controller supplies four reached and reversible end poses. Extensions begin at those equilibria. The new six-station, 24-exit checks cover these extensions and their reversed commands. The archived approach and final return keep their original CAD coverage. Two further up/down pairs start at +175° or −175° yaw. The antipode route continues through +180° yaw before descending to −20° elevation. The source solver uses 8 constant-strain cells per module. Steps of up to 4° advance on the same solution branch. The first sampled failure is bracketed to 1° or less. A full turn of the requested heading can substantially change shape, rope loads and stored commands even when the head points in its initial direction.

Acceptance uses head-axis error ≤1°, 2.5–250 N on each ideal rope, axial cell strain magnitude ≤4.75%, positive fixed-winch tangent, equilibrium residual below 2 × 10⁻⁶ and the source rod's local-curvature and remote Ø63 mm capsule checks. The 250 N ceiling is a numerical bound. A solver or finite-routing domain boundary identifies the end of a model branch. A different redundant rope allocation can produce a different boundary.

Six bonded stations use rigid guide, cap and lockwire-envelope STL meshes. M6 ±12 mm uses the 0.25 mm gap candidate. M5 and M6 ±24 mm use V3. Body triangles are refined axially at 0.5 mm. The crop is bounded over the queried deformations and the nearest distances use triangle collision detection. A recorded guide distance of 0.6 mm means at least 0.6 mm. The adapter's actual STL sets a bounding sphere against nonlocal body capsules, with at least two reference body diameters of axial separation. The two M5 ±12 mm retained pivots are assessed separately by structural analysis. As-built guide tilt, sensor housing and full U-part contact still require dimensional evidence.

At each finite exit the centreline is sampled at up to 0.02 mm over the 10 mm rigid end region. The shared C route can slide laterally through M5/M6. The signed distance to the actual end solid is reduced by the 1 mm rope radius. The original gates allow 0.005 mm of mesh faceting and require 1° of remaining design wrap. A reusable triangle hierarchy supplies the distance magnitude. The sign is checked against the oriented solid wherever consecutive samples could cross its surface. The verification file compares this implementation to the archived VTK results.

## Strength and fatigue assumptions

The M5 shell receives the two simultaneous eight-hole loads and the actual relative end-disk pose from each selected point on the left-out leg. Reactions and moving web orientation drive the fine steel-shaft/relieved-web contact solve at the +12 mm station, 67.5° rib. A 205 MPa annealed-304 catalogue proof strength is one comparison case. The installed pin grade, post-yield law, printed-web failure strain and fracture energy are unknown. The tensile-force lookup assumes the same hypothetical static breaking or pullout capacity on all twelve finished rope assemblies at the local routing condition. The trial web thresholds use the maximum modelled tensile surface strain across the eight ribs.

The first duty block uses the published original command or take-up trace. Replaying a second block starts from the actual rope material allocation and drum positions at the end of the first. The clamp stays at −750 mm during reset. A neutral-command handover is followed by reverse startup commands, including take-up substeps. The 0.15 friction and 0.10 mm plant play are assumptions. The take-up schedules use matched estimates or estimates of 0.12 and 0.08 mm. A fourth repeatable-command study actively preloads the correct friction side during reset, equalizes proximal force and removes drum-command bias at the hanging position. The published reset commands and two consecutive blocks permit independent checks. The endpoint-compensation comparator has one archived open mission only. The structural fixed-location channels follow the nominal reference geometry through a separately identified idealized reset.

Cycle counting keeps the range, mean and residual half cycles of each continuous history. For slope b and amplitude A equal to half the force or strain range, the exposure of a block is S = Σ n Aᵇ. With a tested amplitude Aref at Nref cycles, a linear cumulative damage model gives Nref × Arefᵇ / S blocks. For repeated duty, the additional exposure from block two is the continuous two-block total less the first block. Phase contributions assign half of each counted cycle to each turning endpoint. Actual material and termination curves, mean-load effects, moisture, creep, wear, temperature and mission duration remain to be measured. A force range, a strain range and a sliding distance have different units and are reported separately.

## Reproduction

Use the [Round 2 environment](../round2_20261119/README.md#reproduction) with libigl 2.6.3. One CPU thread per BLAS job is sufficient. Allow enough memory for both refined body meshes and run the geometry and shell campaigns sequentially on small machines. From this folder, the following commands generate a fresh result tree. Each command uses the archived repository inputs at the declared revision.

~~~bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VTK_SMP_MAX_THREADS=1
out=$(mktemp -d)
python free_space.py --out "$out/angles"
python cad_screen.py --angles "$out/angles" --out "$out/geometry"
python screened_return.py --results "$out"
python allocation_sensitivity.py --results "$out"
python mesh_limits.py --results "$out"
python edge_confirmation.py --results "$out"
python opposite_axis.py --results "$out"
python mesh_transition.py --results "$out"
python pin_sweep.py --out "$out/strength"
python repeat_block.py matched mismatched original active_matched --out "$out/service"
python service_life.py --service "$out/service" --out "$out/fatigue"
python strength_boundaries.py --results "$out"
python verify_study.py --results "$out"
python figures.py --results "$out"
python -m unittest test_study
~~~

The dated original files in [Round 2](../round2_20261119/README.md) and the [full mission](../../lanes_20261113/cycle_closeout_20261119/README.md) are inputs to this study.
