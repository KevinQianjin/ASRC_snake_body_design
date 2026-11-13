# Separate rope lanes (radial spread) for U4+M2 — 13 November 2026

This folder holds the rope-lane study. It does not copy the solver: `lanes.py` adds `../backbone_20261108` to the Python path and uses its scripts (`backbone.py`, `startup_sweep.py`, `min_force_sweep.py`, `length_cycle.py`, `closed_loop_cycle.py`, `closed_loop_v2.py`) unchanged. It also leaves the hash-pinned files in `steering_63mm_20261106` untouched.

| Path | Content |
|---|---|
| `lanes.py` | lane rope geometry (per-set rope offsets), `install()`, `validate()` |
| `lanes_study.py` | runs startup → sweep → reference → gains → closed-loop cycles with lanes |
| `rope_chord_check.py` | module bend angles and how far each straight rope leaves its lane |
| `results_lanes/` | startup, yaw sweep, logs, rope-chord JSON |
| `length_cycle_results_lanes/` | lane reference round trip |
| `closed_loop_lanes_results/` | gains and the five closed-loop cases |

Run every command from this folder. The comparison baseline (shared 24 mm holes) is in `../backbone_20261108/results/`, `length_cycle_results_pre3_tol1/` and `closed_loop_v3_results/`.


The pinned model routes all three anchor sets through the same four holes at 24 mm, which three 2 mm ropes cannot share. `lanes.py` gives each set its own radius on the same up/right/down/left rays: **A (ends at U4) 21 mm, B (M5) 24 mm, C (M6) 27 mm**. It does this by wrapping `backbone.spatial_rod` with a copy of the pinned kernel that has per-set rope offsets. No pinned file is changed. With equal radii it reproduces the pinned kernel to 1e-14 (energy) and 1e-16 (gradient). With lanes, the finite-difference gradient error is 2e-8. `lanes_study.py` re-runs the whole 3 N pipeline into separate folders (`results_lanes/`, `length_cycle_results_lanes/`, `closed_loop_lanes_results/`).

| Check | Shared holes (24 mm) | Lanes 21/24/27 mm |
|---|---|---|
| Startup, 32 states | all pass, peak 17.4 N, min eig 0.685 | all pass, peak 16.4 N, min eig 0.695 |
| Yaw holds 0–175° at 20° | peak 17.4 N, min eig 0.166 | all 36 pass, peak 16.4 N, min eig 0.185 |
| Yaw 0° / 90° / 150°: peak (sum) | 17.3 (79.0) / 11.2 (83.3) / 8.1 (69.8) N | 16.3 (76.0) / 10.9 (79.0) / 8.0 (69.2) N |
| Reference round trip | all checks pass, peak 17.6 N, clearance 20.6 mm | all pass (1101 states), peak 16.5 N, min 2.73 N, clearance 20.1 mm, min eig 0.185 |

| Closed loop (settled samples) | Shared holes, v3 | Lanes |
|---|---|---|
| nominal | 0 fail, yaw 0.14°, elev 0.18°, 2.98–17.7 N | 0 fail, yaw 0.08°, elev 0.14°, 2.99–16.6 N |
| E75 | 0 fail, yaw 0.20°, elev 0.20°, 2.92–22.5 N | 0 fail, yaw 0.20°, elev 0.20°, 2.90–22.5 N |
| payload550g | 0 fail, yaw 0.20°, elev 0.20°, 2.76–23.7 N | 0 fail, yaw 0.67°, elev 0.24°, 2.78–20.8 N |
| free1500mm | 0 fail, yaw 0.20°, elev 0.20°, 2.81–18.0 N | 0 fail, yaw 0.20°, elev 0.20°, 2.81–16.9 N |
| ropeEA80pct | 0 fail, yaw 0.20°, elev 0.20°, 2.89–17.9 N | 0 fail, yaw 0.20°, elev 0.20°, 2.89–16.8 N |

Closed loop with lanes uses gains rebuilt from the lane reference (`closed_loop_lanes_results/nominal_gains.npz`), with no correction during moves. Every case completes and every settled sample passes. Peak tensions are 1–3 N lower than with shared holes; the E75 peak is unchanged. **The 550 g head improves but is not solved.** 48 states during motion exceed 1° (maximum 2.32°), all at 174–178° yaw. The shared-hole runs had 115 states up to 3.13° (fixed reference) and 202 up to 3.79° (v3 with correction during moves). Two 550 g samples do not settle to 0.2° within 16 iterations, though both are within the 1° acceptance (maximum 0.67°). Online gain updating is still the suggested fix.

**Rope chords inside the modules** (`rope_chord_check.py`). The model guides each rope only at the module end disks, so inside a bent module the rope is a straight chord. U modules bend at most 7.3°, and their chords stay within 0.2 mm of the lane. **M5 bends 14° at the 0° hold, 25° at 15° yaw, 40–65° between 20° and 90° yaw, and up to 103° at 175° yaw.** M6 bends up to 40°. M5's chords leave their lanes by 4.0 mm at the hold, 6.8 mm at 15°, 11–18 mm at 20–90° and 33 mm at 175°. In the re-clocked M body (cad/lanes_u4m2) the straight corridor clearance is 5.5–7.8 mm. So the steering ropes in M5 would touch the spring strips beyond about 15° yaw, with lanes or shared holes alike. **Large-yaw steering therefore needs intermediate rope guides in the M modules, and the model must route ropes through those guides (per-cell chords) before the large-yaw results can be trusted.** The rod strain at 103° over 96 mm is about 1.7%, within the NiTi superelastic range.

The matching 3D modules (lane holes, anchors, rod bore, joints) are in [`cad/lanes_u4m2/`](../../../cad/lanes_u4m2/README.md).

```bash
cd simulations/u4m2/lanes_20261113
python lanes.py                      # validation
python lanes_study.py startup        # then: sweep, reference, gains, cycle --case <case>
python rope_chord_check.py results_lanes/minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz
```

