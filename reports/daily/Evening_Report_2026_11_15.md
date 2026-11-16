# Evening Engineering Report — 2026-11-15

**Edition: Evening Report.** Run start and reporting cutoff:
**15 November 2026 20:01:41 EST (16 November 2026 01:01:41 UTC)**. Execution
deadline: **22:01:41 EST (03:01:41 UTC)**, a 120-minute limit. Exact run
records are in [run context](../../simulations/u4m2/lanes_20261113/evening_20261115/run_context.json).

## Outcome

The 500 g U4+M2 end-region rope problem is **larger than the morning centre-only
screen reported**. With the actual Ø2 mm rope diameter, the ideal routing
interferes with the M5/M6 end bores in **214 of 217** saved V3 equilibria.

The root cause is a routing idealisation. The rod solver bends each rope at
the module interface. The bore is rigid and only 0.25 mm larger than the rope
in radius, so the physical rope must bend where it leaves the inboard face.
On V2 parts it bends over a 0.25 mm chamfer edge.

This run produced a **bellmouth (convex-fillet) exit candidate** for the M5/M6
bodies, sized from the measured exit deflections. It verified the following:

- With rigid ends and exit pivots, all **5208 rope-exit checks** stay within
  the design wrap angle less a 1° margin.
- The new CAD has **0 finite-rope envelope failures**.
- Both bodies remain watertight single components.
- The same-ray B–C bridge is at least **0.544 mm**.

The design is **not released for manufacture**. The solver has **not** yet
been updated to use exit pivots, and no closed-loop replay was run.

## Reporting period and repository state

- **Interval:** 14 November 2026 20:01:41 EST to 15 November 2026 20:01:41 EST.
  In UTC this is 15 November 2026 01:01:41 to 16 November 2026 01:01:41.
- **Baseline:** `origin/main` = `claude/great-goodall-1wf2yh` =
  `d70550594bfb524b8e2e7e703cb1b8e4234a80f8`. `codex/guide-validation`
  (`73b0b51`) is contained in `main`. No other branch had commits in the
  interval. The working tree started clean.
- **Previously completed work in the interval** (counted once, although it
  appears on two branches):

  | Commit | Time (EST / UTC) | Content |
  |---|---|---|
  | `e309668` | 08:13:02 EST / 13:13:02 UTC | Morning Report work: refined CAD surface screening, V3 flared-socket guides, 217 re-solved 500 g equilibria and contact audit |
  | `76e87d6` | 09:43:10 / 14:43:10 | Timestamps normalised to US Eastern Time with UTC |
  | `73b0b51` | 10:26:39 / 15:26:39 | Engineering update labelled Morning Report |
  | PR #25, #26, #27 merges | 09:18:31, 09:49:05, 10:29:56 EST (14:18:31, 14:49:05, 15:29:56 UTC) | These merges brought the three commits above into `main` |

  See the [Morning Engineering Report — 2026-11-15](Morning_Report_2026_11_15.md)
  for those results. Its main findings were V3 guide/body contact in 55/217
  records (maximum 0.009 mm³) and end-region rope-centre penetration in 57/217
  records (maximum 0.241 mm).
- **Execution model:** this run could not verify the execution-model metadata.
  No model selection is claimed here.

## Why this priority

The morning handoff listed two blockers:

1. the stiffness of the shortened V3 saddle joint;
2. finite end routing with the full rope diameter.

The standing instruction for these runs puts actual guide/body and rope/end
interference first. The guide/body overlap is now very small (≤ 0.009 mm³).
The end-region problem had not been checked with the real rope diameter, and
it could be completed within one run. The joint-stiffness task is carried
forward unchanged; it was not started tonight.

## 1. Finite-rope screen of the current design (new)

[`end_region_envelope.py`](../../simulations/u4m2/lanes_20261113/end_region_envelope.py)
repeats the morning beam-mapped CAD screen on the V2 M5/M6 bodies. The CAD
surface refinement is 0.5 mm and rope samples are spaced 0.05 mm. The script
reports *signed centre distance − 1 mm rope radius* instead of counting
centre points inside material.

| Region | Rope-end checks | Envelope failures | Minimum clearance |
|---|---:|---:|---:|
| M5 proximal disk | 1736 | 906 | −0.366 mm |
| M5 distal anchor/disk | 1736 | 1266 | **−1.252 mm** |
| M6 proximal disk | 868 | 227 | −0.199 mm |
| M6 distal anchor/disk | 868 | 718 | −0.281 mm |
| **Records affected** | | **214 / 217** | |

Centre-only penetration occurs in 60/217 records, maximum 0.252 mm. The
morning reported 57 records and 0.241 mm with about 1 mm sampling. Even the
loaded startup pose fails: its 8.7° M5 chord leaves only 0.76 mm from rope
centre to bore wall.

The beam map also bends the "rigid" end blocks. Measured against the
cell-mapped bore, the deflection is at most 8.7°. Measured against the rigid
interface frame, the M5 distal chord deviates by up to 13.8°. The map
therefore distorts the 7 mm block by roughly 3–4°. The interface-pivot screen
is thus not a physical model in either form.

## 2. Rigid-end exit-pivot geometry (new)

[`end_bellmouth_study.py`](../../simulations/u4m2/lanes_20261113/end_bellmouth_study.py)
treats each end region as rigid and attached to the rod frame at the interface
node. In this model the rope follows the bore and turns at the inboard face
(z = −45 mm proximal, z = +41 mm distal).

| Exit | Max deflection | Radial / tangential max | Ideal interface-chord angle | Straight-flare half-width needed with interface pivot |
|---|---:|---:|---:|---:|
| M5 proximal | 17.78° | 12.43° / 17.41° | 15.16° | 1.81 mm |
| M5 distal | **27.09°** | 26.98° / 19.94° | 13.80° | **2.72 mm** |
| M6 proximal | 10.26° | 9.47° / 10.26° | 8.97° | 1.47 mm |
| M6 distal | 8.14° | 7.45° / 6.93° | 5.22° | 1.64 mm |

The largest M5 distal deflections belong to the inner (concave-side) up
ropes. That rope's span from the inboard exit to the +24 mm guide is short.

A straight flare that kept the solver's interface pivot would need a 2.72 mm
half-width at the distal inboard face. Same-ray B and C holes are only 4 mm
apart, so that option is rejected.

The exit-pivot path is **0.005–0.307 mm longer per rope across M5+M6**
(mean 0.117 mm). That is a solver-input mismatch, not yet a re-solved result.

## 3. Bellmouth exit candidate v1 (new CAD)

Each inboard lane exit in [end_bellmouth_v1](../../cad/lanes_u4m2/end_bellmouth_v1/README.md)
gets a convex fillet. The fillet is tangent to the Ø2.5 mm bore and sweeps to
a design wrap angle at the face.

| Exit | Fillet radius | Rope centreline radius | Wrap | Hole Ø at face |
|---|---:|---:|---:|---:|
| M5 proximal | 6.0 mm | 7.0 mm | 19° | 3.140 mm |
| M5 distal | 3.9 mm | 4.9 mm | 29° | 3.456 mm |
| M6 proximal / distal | 7.0 mm | 8.0 mm | 18° | 3.172 mm |

The following parts are unchanged: lanes, rays, guide stations, V3 guides,
interface faces, return holes, anchor grooves, backbone bores/supports, joint
holes and outer bounds. No backbone end ferrule was added.

**Checks:**

- Both bodies are watertight and consistently wound, and each is one component.
- Measured section diameters match the nominal profile to ≤ 0.002 mm.
- The fillets remove 31.73 mm³ (M5) and 14.87 mm³ (M6), about 0.05 g in total.
  The mass model was left unchanged.
- The minimum same-ray B–C bridge is **0.544 mm** at the M5 distal face; the
  V2 value was 1.058 mm and the target is ≥ 0.5 mm.

**Finite-rope envelope verification** ([`bellmouth_cad_check.py`](../../simulations/u4m2/lanes_20261113/bellmouth_cad_check.py)):
each exit-pivot rope centreline is built in the rigid CAD frame. It runs along
the bore, follows an arc concentric with the fillet, and continues on the
tangent span to |z| = 38 mm. Its signed distance to the actual STL is then
measured.

| CAD | Exit checks | Failures (< −0.005 mm) | Minimum clearance |
|---|---:|---:|---:|
| New bellmouth bodies | 5208 | **0** | −0.0027 mm (intended bearing; 128-gon faceting) |
| Same paths in V2 bodies | 5208 | 5200 | −0.335 mm |

The V2 row only shows that the fillets are necessary for this path. It does
not reproduce the actual V2 rope path, which is a sharp-edge wrap.

**Unsuccessful variants, retained:**

| Variant | Result |
|---|---|
| Uniform 7 mm fillet, 18° wrap | 279 exits in 102 records exceed the wrap |
| M5 distal 4.0 mm fillet, 28° wrap | 9 exits fall within the 1° margin |
| M6 12°/10° wraps | Fillets smaller than the existing face chamfer; Boolean gave a non-watertight 33-component body |

## Verification

- **21 tests pass:** 5 new
  [bellmouth tests](../../simulations/u4m2/lanes_20261113/test_end_bellmouth.py),
  plus the 16 existing guide and refinement tests in `test_guides.py` and
  `test_cad_surface_refinement.py`. The new tests check:
  - profile tangency and face angle;
  - cutter volume validity;
  - zero-deflection length;
  - that the rope arc is concentric with the fillet;
  - that the published STL hashes match the geometry check.
- The 14 numerical/control tests from the morning were **not** rerun, because
  no solver code changed.
- Inputs, hashes, commands and versions:
  - [evidence README](../../simulations/u4m2/lanes_20261113/evening_20261115/README.md);
  - [run context](../../simulations/u4m2/lanes_20261113/evening_20261115/run_context.json).
  - This environment used Python 3.11, numpy 2.4.6 and vtk 9.7.2. These
    versions differ from the morning environment, and no historical result
    was recomputed with them.

## Limitations

- **Solver routing.** No equilibrium was re-solved. Head pose, guide forces,
  rope lengths and controller commands still use the solver's interface pivots.
  Exit deflections were computed from saved interface-pivot geometry.
- **Coverage.** The 217 records are the selected morning set, not a complete
  cycle. The cycle (startup → insertion → right yaw → return → left yaw →
  return → withdrawal) was **not** replayed.
- **Rope model.** The rope radii of 4.9–8 mm are geometric choices. No D/d
  rating, capstan friction, wear or printed-fillet tolerance is claimed. The
  rope model is an uncalibrated PA6 surrogate.
- **Bridge.** 0.544 mm is a thin printed wall and needs printer qualification.
- **U4.** U4 distal exits were not checked.
- **Map boundary.** The rigid-end and cell maps are not blended at |z| = 40 mm.
- **Still open from the morning:**
  - V3 guide/body overlap (55/217 records, ≤ 0.009 mm³);
  - V3 saddle-joint strength and stiffness;
  - the 0.359° equilibrium-mesh discrepancy.

## Next-run handoff

The full text is in [HANDOFF.md](../../simulations/u4m2/lanes_20261113/evening_20261115/HANDOFF.md).

1. **Exit pivots in the rod solver.** Add rigid-end rope points at z = −45 and
   +41 mm, then re-solve the 217 holds.
   - Gradient checks must pass, and all fixed-winch tangents must be positive.
   - Report pose, guide and exit loads.
   - The wrap must stay ≤ θ_d − 1° in the re-solved geometry.
2. **V3 saddle-joint local structural/contact model.** Use the simultaneous
   loads; peak station loads are 27.4 N and 60.8 N·mm. Quantify guide
   displacement and rotation.
3. **Complete closed-loop replay** with the end-exit and guide/body checks, only
   after items 1 and 2 have results.

Resources: 4 CPUs and 15.7 GiB this evening; keep heavy CAD studies sequential.
Keep the head at 500 g.
