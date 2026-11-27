# M6 NiTi backbone vs hub-ring bore: CAD-consistent attachment and mission-wide clearance (evening, 26 November 2026)

**Run:** scheduled evening run. Started **2026-11-26 20:01:44 EST (2026-11-27 01:01:44 UTC)**. Deadline **22:01:44 EST (03:01:44 UTC)**.

[Evening Report](../../../../reports/daily/Evening_Report_2026_11_26.md) · [Next-run handoff](HANDOFF.md) · [Morning study, same date](../morning_20261126/README.md) · [Summary figure](results/evening_20261126_summary.png) · [Validation](results/validation.json)

## Why this study

The [26 November morning study](../morning_20261126/README.md#11-cad-bore-check-and-coupling) found a **4.25 mm** lateral offset between the "unguided" NiTi backbone and the `ring_0` hub bore at step 1,869, which exceeds the **3.30 mm** radial clearance. It flagged backbone-to-body contact as a priority. The morning model attached the Ø1.80 mm rod only at the cropped FE cut faces. It used a clamp at `z = −44.9 mm` and a beam on the D1 reference point at `z = +40.9 mm`, giving `L = 85.8 mm`.

**The actual CAD does not attach the rod that way.** Ray-casting the central bore of [`M6_lane_anchorC.stl`](../../../../cad/lanes_u4m2/end_bellmouth_v1/M6_lane_anchorC.stl) from the axis (36 directions, 0.1 mm steps, 34,560 rays) found the following:

| CAD feature | Measured | Source agreement |
|---|---|---|
| Integral rod sleeve bore | **r = 0.921 mm** (Ø1.84; design Ø1.85) | `lane_design.json`: `rod_bore_d = 1.85` |
| Sleeve extent | **z = −47.95…−33.05** and **+33.05…+47.95 mm** (sampling limit 0.05 mm) | `rod_support_length_per_end_mm = 15`; [installation guide](../../../../docs/installation_guide.md): "bond only the 15 mm at each end … 66 mm free to bend" |
| Closest material to the axis in the free span | **r = 4.19 mm** at `z = −19.95` (the Ø8.40 hub-ring bores). Nothing else lies inside r < 5.5 mm | morning bore check: Ø8.40 |

The rod is therefore clamped at the sleeve tips **z = ±33 mm**, giving **L = 66 mm**. The morning study's sleeve-free 85.8 mm span is not the built geometry. This run corrects the attachment and re-checks clearance over the full mission at three model levels. No CAD, guide position, rope bore, mass, payload (500 g) or solver input was changed, and no backbone end ferrule was added.

## Method

1. **`bore_fe.py`** rebuilt the 25 Nov/26 Nov **q5 bonded solid body** (130,278 tets, 762,645 reduced DOFs, `G = 500 MPa`, 0.06 mm crown). It solved the 15 kinematic unit fields (3 prescribed D1 rotations + 12 station-wrench components) for two backbone attachments:
   - (a) the morning model, as published (`L = 85.8 mm` on the D1 reference);
   - (b) the **CAD-consistent model**: a beam from the D0 sleeve tip `(0,0,−33)` to the D1 sleeve tip `(0,0,+33)`, `L = 66 mm`, rigidly offset −7.9 mm from the D1 reference. As in the morning model, the sleeves are taken as rigid parts of the D0/D1 masters.

   For every unit field it saved the least-squares rigid pose of each Ø8.40 ring band and of D1 in [`results/unit_poses.npz`](results/unit_poses.npz). Superposing with the archived [`rod_steps.npz`](../evening_20261125/results/rod_steps.npz) coefficients gives the ring poses for all 3,405 states.
2. **`bore_contact.py`** evaluated the backbone-to-bore offset at three levels:
   - **L0** reproduces the morning metric exactly: a Hermite backbone with `L = 85.8` against the mean ring-node displacement at the band mid-plane.
   - **L1** is linear and CAD-consistent: a Hermite backbone clamped at ±33 mm. The offset is taken as the maximum over 7 sections through each 3.05 mm bore band, including ring tilt. It was evaluated on **all 3,405 states**.
   - **L2** is geometrically nonlinear and CAD-consistent:
     - The body chain D0→R0→R1→R2→R3→D1 is rebuilt by exact SO(3) composition of the per-segment relative rotations. Each segment's bending is lifted as an exact circular-arc chord, and the linear residual (shear offset, axial strain) is kept.
     - The backbone is a discrete extensible elastica (`EI = 20,612 N·mm²`, `EA = 101,788 N`, `h = 1.0 mm`), clamped in both sleeves. The distal end may slide along its sleeve axis (zero axial force).
     - Unilateral penalty contact (`2×10⁴ N/mm` per node) acts against the four Ø8.40 ring bores over their real band length, measured radially in each ring frame.
     - Coverage: **737 states**, made up of stride 5 over the mission, the 40 largest L1 offsets, the 20 largest end rotations, the per-phase L1 maxima and steps 1,709/1,869/1,884. All **11 phases** are covered: loaded straightening → entry → right yaw out/return → left yaw out/return → pitch up/down and returns → exit.
3. **`convergence.py`** ran coarse-to-fine continuation (`h = 2 → 1 → 0.5 → 0.25 mm`) at steps 1,866, 1,869 and 1,709. **`sensitivity.py`** compared lift variants and a fixed-chord bound. **`summarize_and_validate.py`** produced the figure and 11 automated checks.

## Results

### Backbone-to-bore clearance (radial clearance of the rod centreline = 4.20 − 0.90 = 3.30 mm)

| Level | States | Max offset (ring, step) | Min gap | States over clearance |
|---|---:|---|---:|---:|
| L0 morning model, reproduced | 3,405 | **4.248 mm** (`ring_0`, 1,869); morning: 4.247 | −0.948 mm | **664** |
| **L1 linear, CAD sleeves** | 3,405 | **2.650 mm** (`ring_1`, 1,866) | **0.650 mm** | **0** |
| **L2 nonlinear, CAD sleeves (h = 1 mm)** | 737 | **2.913 mm** (`ring_1`, 1,866, left return, 46.7°) | **0.387 mm** | **0** (0 contact force) |
| L2 converged (h = 0.25 mm, continuation) | 3 governing | `ring_1`: 0.393 / 0.409 / 0.607 mm gap at 1,866 / 1,869 / 1,709 | 0.393 mm | 0 |

- **The morning study's predicted `ring_0` contact is an artefact of the 85.8 mm sleeve-free attachment.** With the rod clamped in its 15 mm sleeves, it leaves D0 tangent to the axis 14.5 mm before `ring_0`. Its `ring_0` offset falls from 4.25 to **1.98 mm (L1)** and **1.50 mm (L2)**.
- The governing location moves to **`ring_1` (z = −5 mm)** during the left-yaw return, near 47°. Here the lattice bay between `ring_0` and `ring_1` carries ~20° of relative rotation plus a ~6.4 mm lateral shear offset. Per-ring L2 minimum gaps are **1.50 / 0.39 / 0.76 / 2.53 mm** (`ring_0…ring_3`). In L2, 148 of 737 states have a gap < 1.0 mm and 67 have a gap < 0.5 mm, all in the two yaw excursions.
- Nonlinear geometry costs **0.26 mm** of margin relative to the linear L1 result at the governing state (0.650 → 0.387 mm). Below 15° end rotation, L1 and L2 agree within **0.035 mm**.
- **Max NiTi bending strain** is **1.62%** (h = 1 mm; 1.53% converged at h = 0.25 mm) at step 1,866. That is about **twice** the uniform-curvature estimate for a 47° bend over the 96 mm module (≈0.77%). The bend is concentrated on the 66 mm free span and further between `ring_0` and `ring_3`. The validity of the linear `E = 40 GPa` rod model at this strain has **not** been established. The [NiTi supplier report](../../../../niti_supplier_report.md) lists working strain and fatigue for the rod as unknown.

### Consequence for the FE body model (q5, CAD-consistent vs morning backbone attachment, same mesh)

| Quantity | Morning attachment (L = 85.8) | **CAD sleeves (L = 66)** | Rod-model reference |
|---|---:|---:|---:|
| Equivalent bending stiffness over 85.8 mm (load-controlled unit D1 moment) | 60,404 N·mm² | **66,501 N·mm²** | 64,730 N·mm² (+2.7% vs CAD) |
| Backbone share of D1 moment, steps 1,709 / 1,869 / 1,884 | 24.8% / 23.5% / 24.5% | **20.7% / 18.7% / 20.2%** | — |
| Body D1 moment, step 1,869 | 336.8 N·mm | **409.7 N·mm** | — |
| q5 peak \|principal strain\|, steps 1,709 / 1,869 / 1,884 | 3.467% / 3.485% / 3.462% | **3.375% / 3.306% / 3.369%** | — |

- The CAD-consistent attachment brings the solid model's combined stiffness **closer to the rod model's parallel `EI_rod`** (+2.7% instead of −6.7%). This supports the kinematic end rotation used by the 25/26 Nov studies.
- With the sleeve attachment, the q5 element peak at step 1,869 moves from the `ring_0` hub/arm corner (`z = −17.9 mm`) to `z = −5.2 mm` (`ring_1` side). The morning study's mesh-converged **4.17–4.21%** corner value came from the 85.8 mm model and **was not recomputed tonight** on the refined `q3`/`q2.5` meshes; it is a handoff item. Because the morning-model peaks on this machine differ from the published q5 values by ≤ +0.6% (3.467% vs 3.446% at step 1,709; a TetGen/library-version difference), only same-mesh differences are compared above.

### Sensitivity (steps 1,866 / 1,869 / 1,709, [`results/sensitivity.json`](results/sensitivity.json))

| Variant | `ring_1` gap at 1,866 | `ring_0` gap at 1,866 | Interpretation |
|---|---:|---:|---|
| **Base** (arc-length lift, floating distal end) | 0.386 mm | 1.502 mm | production setting |
| Plain linear-translation lift (rejected) | 0.476 mm | 1.632 mm | lift choice moves gaps ≤ 0.13 mm |
| **Fixed chord** (distal end pinned to the lifted sleeve tip; not physical) | 2.644 mm | **−0.681 mm (contact, 80 N)** | see below |

The fixed-chord bound is **not** a credible state:
- The axially floating rod settles **1.19–1.30 mm** short of the lifted sleeve tip.
- This mismatch matches the second-order shortening that the linear lattice shear offsets omit, `Σ δ²/2ℓ` = **1.85–1.98 mm** (6.2–6.4 mm shear over the 13.5 mm `ring_0→ring_1` bay).
- Forcing the rod to that chord would require **≈ 1,800–2,000 N** of backbone tension (`EA·δ/L`). That contradicts the linear FE, where the backbone and body share the axial load.

The result does however show that **axial compatibility between the PA12 body and the bonded rod is the decisive unmodelled quantity**. It can only be resolved by a geometrically nonlinear coupled body+backbone FE, which is next-run priority 1.

### Solver convergence ([`results/convergence.json`](results/convergence.json))

The first full-mission L2 attempt used `h = 0.5 mm` with a 400-evaluation cap. It stopped **under-converged**: a 0.509 mm minimum gap vs 0.393 mm converged, which is unconservative by 0.12 mm. It is retained as `results/superseded_h0p5_*` and is **not used**. With coarse-to-fine continuation, the governing gaps change ≤ 0.004 mm from `h = 0.5` to `0.25 mm`. The production setting (`h = 1.0 mm`, 400 evaluations) is **0.005–0.008 mm conservative** against the converged value at all three governing states. The production elastica reproduces exact circular arcs to 0.04/0.10/0.14 mm radius error at 20/47/60°.

## Validation ([`results/validation.json`](results/validation.json)): 11 of 11 checks pass

The checks were:
- CAD sleeve bore and extent;
- ring bores as the only material in r < 5.5 mm;
- the morning model reproduced (L0 at 1,869: 4.248 vs 4.247 mm; moment shares 23.5%/24.8% exact);
- PARDISO residuals ≤ 2.8×10⁻¹³;
- the arc test;
- production vs converged gap (−0.005 to −0.008 mm);
- `h = 0.5 → 0.25` change < 0.01 mm;
- L1/L2 agreement below 15° (0.035 mm);
- all 11 phases covered;
- the rotation lift (D1 error 0.001°);
- the figure.

## Limitations (kept visible)

- The body is **linear small-strain FE**. The large-rotation lift is a segment-wise corotational approximation, not a nonlinear FE, and the body–rod axial compatibility is unresolved (see sensitivity).
- The sleeves (Ø6 OD PA12, 12 mm between the cut face and the sleeve tip) are treated as rigid. Bond compliance of the 15 mm rod bond, sleeve straightness, rod straightness and as-printed bore size and concentricity are unmeasured. A 0.39 mm nominal gap can be consumed by print/assembly eccentricity of the Ø8.40 ring bores or the sleeves, and no tolerance stack has been done.
- L2 covers 737 of 3,405 states (stride 5 plus targeted states). L1 covers all states. L2 tracks L1 smoothly (see figure).
- The q5 hub-strain change under the corrected attachment is a single-mesh result. The refined-mesh corner value was not recomputed.
- The NiTi rod model is linear elastic at 40 GPa. The 1.5–1.6% bending strain is an unverified regime for that model. No hardware, material test or bench evidence exists for any of these results.

## Reproduction

```bash
export PYPARDISO_MKL_RT=/usr/local/lib/libmkl_rt.so.3   # if pypardiso cannot locate MKL
python bore_fe.py                  # ~160 s, 2 PARDISO factorisations on q5 (writes unit_poses.npz, bore_fe.json)
python bore_contact.py 5 4         # stride 5 + targeted states, 4 workers, ~8 min (bore_contact.json, bore_contact_rows.npz)
python convergence.py              # ~2 min
python sensitivity.py              # ~1 min
python summarize_and_validate.py   # figure + validation.json
```

Environment: Python 3.11.18, numpy 2.4.6, scipy 1.17.1, trimesh 5.2.2, tetgen 0.8.4, pypardiso 0.4.7 (MKL 2026.2), python-fcl 0.7.0.11 and numba 0.68.1 (imported by the reused 19–25 Nov modules). Source revision: `origin/main` at `dfd27da` (PR #48 merged). Reused unchanged: `morning_20261126/backbone_strain.py`, `evening_20261125/mission_envelope.py`, `evening_20261124/body_bond.py`, `evening_20261124/body_solid.py`.
