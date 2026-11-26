# Whole-mission envelope of the bonded whole-body solid M6 model — evening, 25 November 2026

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_25.md) · [Next-run handoff](HANDOFF.md) · [Previous study (24 Nov evening)](../evening_20261124/README.md) · [Crowned-land CAD](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md)

This run took handoff item 1 of the [24 November evening run](../evening_20261124/HANDOFF.md): the 24 November whole-body solid model was evaluated at only two governing steps (1,709 and 1,885). Because that model is linear, the whole 3,405-state mission can be covered by superposing 15 unit solutions instead of solving 3,405 systems.

Simulation only. No CAD, guide position, rope bore, station, mass or solver input changed. The head payload stays 500 g, U4+M2 is kept and no backbone end ferrule was added. The mechanical model, its assumptions and its limits are exactly those of the [24 November study](../evening_20261124/README.md); only the step coverage is new.

## Outcome

1. **Bond demand over the whole mission.** Over all 3,405 states (straighten → entry → right yaw out/return → left yaw out/return → pitch up/return → pitch down/return → exit), the mission maxima exceed the step-1,709 values by **at most 4.3% (land-edge peak axial shear), 4.4% (area-mean axial shear) and 0% (peak normal traction)** on the finer q3 mesh (q5: up to 7.1%, 4.4% and 0%). On q3:
   - area-mean axial shear: **2.48 MPa (G 500) / 3.60 MPa (G 1,500)**, uncrowned;
   - land-edge peak axial shear: **9.0 / 16.8 MPa** uncrowned, **7.8 / 14.5 MPa** crowned;
   - peak normal traction: **21.2 / 36.4 MPa** uncrowned (at steps 1,709 / 1,885 — already the governing steps).
2. **The governing land changes with yaw direction.** During right yaw (steps ≈ 800–1,050) the off-plane 157.5° / 337.5° lands at z = −12 mm carry about **twice** their step-1,709 peak (8.1–9.0 MPa vs 4.2–4.6 MPa, G 500), but stay inside the overall envelope set by the bending-plane lands during left yaw.
3. **Mesh check.** q5 → q3 (774 k → 1.08 M DOF) changes the mission maxima by −3.9% to +4.7%, the same band as the 24 November two-step check.
4. **Tilt clearance against the solid arm (G = 500 MPa).** Targeted exact FCL probes at the steps with the largest body motion near the guide lower the 24 November minimum only slightly: **uncrowned 0.0737 mm** (z = +12 mm, step 797, right yaw out) vs 0.0742 mm at step 1,709; **crowned 0.0785 mm** (unchanged, step 1,709). The strided sweep (689 states, [§ 3](#3-sampled-whole-mission-tilt-sweep)) finds **no state below 0.025 mm and no tilted contact**; the sampled minima are **0.0737 mm uncrowned** and **0.0783 mm crowned**.
5. **Hub strain is a mission-wide issue, not a two-step one (FAIL kept visible).** The linear peak principal strain reaches **3.81% at step 1,869** (left return), vs 3.74% at step 1,709, always at the same hub/arm element (r ≈ 8.5 mm, z ≈ −17.9 mm). **615 of 3,405 states exceed 3%** and 1,124 exceed 2%; the pitch phases reach 2.3–2.5%. The land bands stay below 0.68% over the whole mission.

## Method

| File | Purpose |
|---|---|
| [`rod_steps.py`](rod_steps.py) | Evaluates the rod's relative D0 → D1 end rotation and the local rotations at the two stations for all 3,405 archived states (4 processes, 4 s), plus the archived station wrenches → [`results/rod_steps.npz`](results/rod_steps.npz). Reproduces the archived 24 Nov values at steps 1,709 / 1,885 to < 10⁻⁹°. |
| [`mission_envelope.py`](mission_envelope.py) | Builds the 24 Nov `body_bond.Body`, factorises once per (G, crown) case and solves 15 unit right-hand sides (3 unit D1 rotations, 6 unit wrench components per guide). Layer tractions (normal / axial / cross), layer slip, guide-minus-land rotation, socket non-rigid motion and the body-relative-to-guide motion of the clearance patch are stored as linear (quantity × 15) maps and combined per step with c = [s·ω, W₋₁₂, W₊₁₂] (the 24 Nov "local" scaling). Then runs the exact FCL tilt probe on targeted steps. |
| [`probe_sweep.py`](probe_sweep.py) | Exact FCL probe (untilted + 26 tilts of ±0.2°) on every 5th mission state plus the targeted steps, both stations, both land variants, from the saved unit patch fields (`--save-patch`). |
| [`strain_envelope.py`](strain_envelope.py) | Exact per-step peak \|principal strain\| of the body (24 Nov `strain_check.py` case: q5, G 500, crowned, end rotation + wrenches) for all states, by Frobenius-norm screening. |
| [`summarize.py`](summarize.py), [`validate.py`](validate.py) | Tables, [`results/mission_envelope.png`](results/mission_envelope.png) and [`results/validation.json`](results/validation.json). |

Commands (from this folder; `PYPARDISO_MKL_RT=/usr/local/lib/libmkl_rt.so.3`):

```
python3 rod_steps.py
python3 mission_envelope.py                                    # q5, 4 cases + targeted probe   (333 s)
python3 mission_envelope.py --G 500 --no-probe --save-patch --out results/patch_q5             (156 s)
python3 mission_envelope.py --quality 3 --max-vol 0.3 --no-probe --out results/q3              (425 s)
python3 probe_sweep.py --stride 5 --workers 3
python3 strain_envelope.py                                                                       (129 s)
python3 summarize.py && python3 validate.py
```

Source revision: branch `claude/great-goodall-1wf2yh` at `2eff981` (merge of `origin/main` `8ef0fe0` into the 24 Nov evening head `9e876c1`). Python 3.11.18, numpy 2.4.6, scipy 1.17.1, trimesh 5.2.2, tetgen 0.8.4, pypardiso 0.4.7 with mkl 2026.2.1, python-fcl 0.7.0.11, matplotlib 3.11.2. Machine: 4 cores, 15 GB.

Inputs: [`controller_states.npz`](../cycle_closeout_20261119/results/yaw_pitch/controller_states.npz) (3,405 states, 500 g), [`guide_hole_loads.npz`](../cycle_closeout_20261119/results/yaw_pitch/guide_hole_loads.npz) (Round 2 station wrenches), phase boundaries from [`phase_results.csv`](../cycle_closeout_20261119/results/yaw_pitch/phase_results.csv), CAD `M6_lane_anchorC.stl` and the [`m6_bond_gap_20261119`](../../../../cad/lanes_u4m2/m6_bond_gap_20261119) / [`m6_crowned_land_20261120`](../../../../cad/lanes_u4m2/m6_crowned_land_20261120/README.md) guide variants.

Phase step ranges: straighten 0–165, entry 166–472, right out 473–913, right return 914–1,355, left out 1,356–1,796, left return 1,797–2,240, pitch up 2,241–2,390, pitch-up return 2,391–2,540, pitch down 2,541–2,819, pitch-down return 2,820–3,098, exit 3,099–3,404. This is the archived yaw/pitch replay; it covers the full required path (loaded startup/straightening → insertion → right yaw → return → left yaw → return → withdrawal) plus the pitch excursions.

## 1. Bond demand: mission maximum against step 1,709

Maximum over the eight lands; "local" moment scaling plus station wrench; area-mean is the area-weighted mean of \|traction\| on one land.

**q3 mesh (188,766 tets, 1.08 M DOF)** — [`results/q3/mission_envelope.json`](results/q3/mission_envelope.json)

| G, crown | Peak axial shear: mission max (step, phase, land) / step 1,709 | Area-mean axial: max (step, land) / 1,709 | Peak normal: max (step) / 1,709 | Area-mean normal max | Max layer slip | Guide − land rotation | Socket non-rigid, ends |
|---|---|---|---|---:|---:|---:|---:|
| 500 MPa, none | **9.04** (1,010, right return, +12@337.5) / 8.71 | **2.48** (1,869, −12@247.5) / 2.45 | 21.2 (1,709) / 21.2 | 2.68 | 5.8 µm | 0.058° | 0.064 mm |
| 500 MPa, 0.06 mm | **7.76** (1,010, right return, +12@337.5) / 7.43 | **2.42** (1,875, −12@247.5) / 2.40 | 18.3 (1,709) / 18.3 | 2.62 | 6.1 µm | 0.062° | 0.064 mm |
| 1,500 MPa, none | **16.83** (809, right out, −12@337.5) / 16.82 | **3.60** (1,866, −12@247.5) / 3.45 | 36.4 (1,885) / 36.4 | 3.58 | 3.6 µm | 0.024° | 0.060 mm |
| 1,500 MPa, 0.06 mm | **14.49** (809, right out, −12@337.5) / 14.32 | **3.50** (1,866, −12@247.5) / 3.36 | 31.7 (1,885) / 31.7 | 3.50 | 3.8 µm | 0.026° | 0.060 mm |

**q5 mesh (130,278 tets, 774 k DOF)** — [`results/mission_envelope.json`](results/mission_envelope.json)

| G, crown | Peak axial: max (step) / 1,709 | Area-mean axial: max / 1,709 | Peak normal: max / 1,709 |
|---|---|---|---|
| 500 MPa, none | 9.13 (1,000) / 8.67 | 2.43 / 2.40 | 22.0 / 22.0 |
| 500 MPa, 0.06 mm | 7.84 (1,001) / 7.32 | 2.37 / 2.36 | 19.0 / 19.0 |
| 1,500 MPa, none | 16.72 (1,701) / 16.67 | 3.44 / 3.30 | 37.5 / 37.5 |
| 1,500 MPa, 0.06 mm | 14.28 (1,701) / 14.24 | 3.35 / 3.21 | 32.8 / 32.8 |

- Mission / step-1,709 ratios (q3): peak axial 1.000–1.043, area-mean axial 1.008–1.044, peak normal 1.000. **Step 1,709 / 1,885 was a representative governing pair to within 5%.**
- The crown lowers the mission peak axial shear by 14% (both G) and the area-mean by 2–3%.
- The right-yaw maxima come from the off-plane lands; the left-yaw maxima from the 67.5° / 247.5° bending-plane lands. Per-land, per-step series are in `results/mission_G*_c*.npz` (`<land>__peak`, `__mean`, columns normal / axial / cross).

## 2. Targeted tilt probe ([`results/mission_probe.json`](results/mission_probe.json))

G = 500 MPa, q5. "Near-guide motion" is the largest body-relative-to-guide displacement within r > 12 mm and \|z − station\| < 3 mm.

| Station | Step (phase) | Near-guide motion | Uncrowned: no tilt / worst of 26 tilts | Crowned: no tilt / worst |
|---|---|---:|---:|---:|
| −12 mm | 1,709 (left out, 24 Nov baseline) | 0.359 mm | 0.1323 / 0.0763 | 0.1385 / 0.0794 |
| | 787 (right out, 20 Nov low-margin) | 0.346 | 0.1349 / 0.0762 | 0.1392 / 0.0792 |
| | 1,775 (left out, max near-guide motion) | 0.463 | 0.1337 / 0.0759 | 0.1389 / 0.0795 |
| | 1,681 (left out, max guide−land rotation) | 0.368 | 0.1326 / **0.0755** | 0.1385 / **0.0790** |
| +12 mm | 1,709 (left out, baseline) | 0.348 | 0.1335 / 0.0742 | 0.1385 / **0.0785** |
| | 430 (entry, 20 Nov low-margin) | 0.182 | 0.1386 / 0.0769 | 0.1399 / 0.0796 |
| | 797 (right out, max near-guide motion) | 0.416 | 0.1356 / **0.0737** | 0.1388 / 0.0785 |

All 26 targeted rows reproduce the archived 24 Nov gaps at steps 1,709 / 1,885 exactly. The guide is the governing part in every case.

## 3. Sampled whole-mission tilt sweep

[`probe_sweep.py`](probe_sweep.py) → [`results/probe_sweep.json`](results/probe_sweep.json): exact FCL distance, untilted plus the 26 rigid ±0.2° tilts, on **every 5th mission state plus the 13 targeted states (689 states)**, both stations, both land variants, G = 500 MPa, q5 unit fields (2,756 probes, 35 min on 3 workers).

| Land, station | Worst gap of 26 tilts: minimum (step, phase, tilt) | Untilted minimum | States < 0.025 mm | Tilted contacts |
|---|---|---:|---:|---:|
| Uncrowned, z = −12 mm | **0.0752 mm** (1,950, left return, in-plane 75°+) | 0.1323 mm | 0 | 0 |
| Uncrowned, z = +12 mm | **0.0737 mm** (805, right out, in-plane 60°+) | 0.1335 mm | 0 | 0 |
| Crowned 0.06 mm, z = −12 mm | **0.0789 mm** (1,950, left return, in-plane 75°+) | 0.1385 mm | 0 | 0 |
| Crowned 0.06 mm, z = +12 mm | **0.0783 mm** (1,681, left out, in-plane 75°−) | 0.1385 mm | 0 | 0 |

Per-phase minimum of the worst tilted gap (mm):

| Phase | Uncrowned −12 | Uncrowned +12 | Crowned −12 | Crowned +12 |
|---|---:|---:|---:|---:|
| straighten | 0.0765 | 0.0769 | 0.0795 | 0.0796 |
| entry | 0.0787 | 0.0769 | 0.0804 | 0.0796 |
| right out / return | 0.0762 / 0.0762 | **0.0737** / 0.0737 | 0.0792 / 0.0792 | 0.0784 / 0.0784 |
| left out / return | 0.0752 / **0.0752** | 0.0742 / 0.0742 | 0.0789 / **0.0789** | **0.0783** / 0.0783 |
| pitch up / return | 0.0769 / 0.0769 | 0.0740 / 0.0741 | 0.0796 / 0.0796 | 0.0785 / 0.0786 |
| pitch down / return | 0.0760 / 0.0760 | 0.0748 / 0.0747 | 0.0792 / 0.0792 | 0.0788 / 0.0788 |
| exit | 0.0787 | 0.0769 | 0.0804 | 0.0797 |

- Over the sampled mission the worst tilted gap varies by only **0.0737–0.0787 mm (uncrowned)** and **0.0783–0.0804 mm (crowned)**. Against the solid arm, the tilt clearance is set by the guide/socket geometry; body deformation changes it by at most about 0.005 mm.
- The 24 Nov two-step values (0.0742 / 0.0785 mm) are within 0.0005 mm of the sampled mission minima. The 21 Nov rod-map result (uncrowned below the 0.025 mm offset at 665 / 317 steps) is not reproduced with the solid arm; it was a rod-map artefact.
- Sampled at stride 5: unsampled steps are bracketed, not certified (handoff item 2).

## 4. Body strain over the mission ([`results/strain_envelope.json`](results/strain_envelope.json))

| Phase | Peak \|principal strain\| (step) |
|---|---:|
| straighten / entry / exit | 0.95% (0) / 0.59% (166) / 0.59% (3,099) |
| right out / return | 3.70% (900) / 3.71% (930) |
| left out / return | 3.80% (1,726) / **3.81% (1,869)** |
| pitch up / return | 2.49% (2,390) / 2.48% (2,391) |
| pitch down / return | 2.28% (2,819) / 2.27% (2,820) |

- Step 1,709 reproduces the 24 Nov value (3.736%) exactly; the mission maximum is 2% higher. The peak sits in the same element (r = 8.47 mm, z = −17.9 mm) at every yaw maximum.
- 615 states exceed 3% and 1,124 exceed 2% (linear model; geometric nonlinearity changed the step-1,709 peak by 1.1% on 24 Nov).
- Land bands (|z| = 12 ± 0.6 mm, 15 < r < 24 mm): at most 0.68% (step 809).
- This case has no NiTi backbone. The backbone shares the end rotation and is handoff item 1 for the next run.

## 5. Validation ([`results/validation.json`](results/validation.json))

All 17 checks pass ([`validate.py`](validate.py)):

- rod rotations at steps 1,709 / 1,885 equal the 24 Nov archive (difference 0.0°); all 3,405 states finite;
- superposition reproduces the archived 24 Nov direct solves at steps 1,709 / 1,885, for all eight lands and all traction, slip, rotation and socket metrics, to 5.9·10⁻⁹ (q5) and 3.2·10⁻⁹ (q3) relative;
- solve residuals ≤ 1.2·10⁻¹²; phase coverage 0–3,404 in the required order;
- the targeted probe reproduces the archived 24 Nov solid-arm gaps to 6·10⁻¹² mm, and the sweep (from saved unit fields) reproduces the targeted probe exactly;
- the strain envelope reproduces the archived step-1,709 peak and land-band strain to 1.1·10⁻¹¹;
- all relative links in this README, the handoff, the Evening Report and the top-level README resolve.

## Limits

- Linear small-strain FE with linearised rotations up to ~0.85 rad (the 24 Nov total-Lagrangian check bounds the geometric effect at ~1% for the end-rotation case at step 1,709 only).
- The adhesive shear modulus (500 / 1,500 MPa) is assumed; the adhesive, bond strength, as-printed land profile and bonded tilt are unmeasured.
- The NiTi backbone is not in the body model; ropes, rope contact, friction, adhesive failure, PA12 yield/fatigue and dynamics are not modelled.
- The FCL sweep is sampled (every 5th state plus targeted steps) and uses rigid ±0.2° tilts of nominal CAD; unsampled steps are not certified.
- The mission is the archived controller replay; numerical controller settling is not physical accuracy, and nothing here is hardware evidence or a manufacturing release.
