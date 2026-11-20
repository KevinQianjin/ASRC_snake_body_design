# Extreme tests for the 500 g U4+M2 front

Both rounds use the [500 g yaw and pitch mission](../lanes_20261113/cycle_closeout_20261119/README.md). The [test programme](../../../nextstep/README.md) lists the physical measurements required for strength, friction and life ratings.

| Round | Question | Start here |
|---|---|---|
| **1 · 19 November 2026** | Which poses, guide clearances, web loads, U blades and return tensions govern the next tests? | [Study and commands](round1_20261119/README.md) · [Five-step load table](round1_20261119/results/five_step_poses_and_ropes.csv) · [Verification](round1_20261119/results/validation.json) |
| **2 · opened 19 November, reported 20 November 2026** | How do those sites behave over the full mission, on reversal, under overload and across combined motion? | [Engineering report](../../../reports/projects/extreme_tests/Extreme_Simulation_Round_2_2026_11_19.md) · [Methods and commands](round2_20261119/README.md) · [Verification](round2_20261119/results/verification/validation.json) |

## Round 2 result folders

| Folder | What it contains |
|---|---|
| [M6 guides](round2_20261119/results/m6_guides/) | Exact guide/body distances, refined meshes, elastic support wrenches and displaced bore geometry |
| [M5 structure](round2_20261119/results/m5_structure/) | Retained pin frames, local stress, proof loads and conditional yield brackets |
| [U structure](round2_20261119/results/u_structure/) | Blade response, four-blade/cage load sharing and interpolation checks |
| [Rope control](round2_20261119/results/rope_control/) | Twelve proximal and distal tension histories, take-up schedules, replay summaries and the tension plot |
| [Motion limits](round2_20261119/results/motion_limits/) | Combined yaw/pitch map, return and withdrawal checks, perturbed poses and timed response |
| [Fatigue and strength](round2_20261119/results/fatigue_and_strength/) | Signed mission channels, rainflow counts and required component resistance |
| [Verification](round2_20261119/results/verification/) | Input hashes, package versions, geometry matches and numerical closure checks |

Each round keeps its solver and data together. Run commands in the corresponding round directory. To recheck the archived second round without changing the published copy, use a Python environment with its [documented dependencies](round2_20261119/README.md#reproduction) and run:

```bash
cd simulations/u4m2/extreme_tests/round2_20261119
out=$(mktemp -d)
cp -R results/. "$out/"
python validate.py --out "$out"
python figures.py --out "$out"
```

New second-round outputs use the seven groups above. The readers also accept older flat output directories for validation and resumption. Input paths in the original verification records locate the files at the recorded source revision.
