# Reports and animations

[Project home](../README.md) · [Research history](../docs/history.md)

## Latest simulation report

- [Evening Report — 16 November 2026](daily/Evening_Report_2026_11_16.md): full-coverage guide/web compatibility (V3 contact in 59/217 holds) and a 0.25 mm bond-gap candidate clearing all 1736 checks. Start/cutoff: **20:02:13 EST (01:02:13 UTC, 17 November)**.
- [Morning Report — 16 November 2026](daily/Morning_Report_2026_11_16.md): constrained bellmouth routing, 217 re-solved fixed-winch holds, finite-rope/tank checks and persistent refined guide contact. Start/cutoff: **07:19:33 EST (12:19:33 UTC)**.
- [Evening Report — 15 November 2026](daily/Evening_Report_2026_11_15.md): finite-rope exit diagnosis and bellmouth CAD before solver integration.
- [Morning Report — 15 November 2026](daily/Morning_Report_2026_11_15.md): V3 saddle development and corrected CAD surface screening.
- [Guided full-path validation — 14 November 2026](../simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md): earlier ideal controller cycle and separate physical-mount failures.

- [Closed-loop round-trip report](../simulations/u4m2/backbone_20261108/closed_loop_results/REPORT.md) — 12 November 2026. Results remain beside their source and data.
- [Full-cycle MP4](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_full_cycle.mp4) · [Steering GIF](../simulations/u4m2/backbone_20261108/closed_loop_results/E75_steering.gif) · [Feedback correction GIF](../simulations/u4m2/backbone_20261108/closed_loop_results/payload550g_feedback_convergence.gif).

## Daily reports and weekly presentation

- [**Evening Report — 16 November 2026**](daily/Evening_Report_2026_11_16.md): full-coverage guide compatibility screen, mechanism and bond-gap candidate.
- [**Morning Report — 16 November 2026**](daily/Morning_Report_2026_11_16.md): detailed English results, comparison figures and next-run handoff.
- [**Evening Report — 15 November 2026**](daily/Evening_Report_2026_11_15.md): bellmouth CAD and finite-rope end checks.
- [**Morning Report — 15 November 2026**](daily/Morning_Report_2026_11_15.md): detailed English report, actual V3 CAD previews and reproducible evidence. Markdown is the source deliverable for this run.
- [**Engineering update — 14 November 2026**](../simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md): guided 500 g motion, archive coverage, V2 mounting and finite end-routing failures.

- [**Daily report — 13 November 2026**](daily/Report_2026_11_13.pdf): separate rope lanes (A 21 / B 24 / C 27 mm) re-run through the whole pipeline (everything passes, about 1 N lower peak tension); rope-chord limit in M5 beyond about 15° yaw; renewed lane-routed 3D modules, base interface, head adapter, assembly check and build guide. Built by [`build_report_2026_11_13.py`](builders/build_report_2026_11_13.py).
- [**Daily report — 12 November 2026**](daily/Report_2026_11_12.pdf): closed-loop control with the 3 N operating pretension enforced, tension-aware arrival and a refined motion path (v2), then an exact 20° reference (v3): four of five cases pass every check in every recorded state; the 550 g head keeps transient angle error at 155–175° yaw. Built by [`build_report_2026_11_12.py`](builders/build_report_2026_11_12.py).
- [Daily report — 11 November 2026](daily/Report_2026_11_11.pdf): model data sheet, prototype files marked, and the round-trip cycle re-run with a 3 N pretension floor and a stable startup (nominal cycle passes every check; remaining failures are open-loop calibration). Built by [`build_report_2026_11_11.py`](builders/build_report_2026_11_11.py).
- [**Model data sheet**](../simulations/u4m2/backbone_20261108/model_data/MODEL_DATA.md): every input of the simulation model (continuous 96 mm modules, full-length rod, module stiffness and mass, ropes, winch, tank, numerics).
- [Report — 10 November 2026](daily/Report_2026_11_10.pdf): coordinated winch control between the 5° poses (smooth, stable, reversible; winch command tables) and winch position error sensitivity (about ±0.2–0.5 mm per winch for ±1°; head-angle feedback recommended).
- [**Weekly report — 10 November 2026**](weekly/Weekly_report_2026_11_10.pptx): slide deck summarising the problem, the NiTi backbone fix and all results to date.
- [Report — 9 November 2026](daily/Report_2026_11_09.pdf): tank entry with the low-strain shape, 3D stability and pretension, minimum tendon force for held-elevation yaw, full 3D tank clearance, and horizontal flexibility (side-rope pull).
- [Report — 8 November 2026](daily/Report_2026_11_08.pdf): M module stiffness requirement, NiTi backbone concept, straightening and steering with the backbone, and the module test plan.
- [Report — 6 November 2026](daily/Report_2026_11_06.pdf): design concept, active straightening, tank entry and steering with the current M module; unresolved issues.
- [Report — 5 November 2026](daily/Report_2026_11_05.pdf): earlier design and analysis.

## Regenerating daily reports

Rebuilding requires Python, ReportLab, the source figures/data, and the Carlito Regular, Bold, Italic and BoldItalic TTF fonts. The default font directory is `/usr/share/fonts/truetype/crosextra`; set `ASRC_REPORT_FONT_DIR` to the directory containing those four files when using a different installation.

The report generators are in [the builder source folder](builders). Builders for 8–12 November write to `reports/daily/` at the repository root. For example:

```bash
python reports/builders/build_report_2026_11_11.py
```

The relocated PDF and PPTX files retain their original bytes. They are dated records; read the latest report and current limitations before using historical conclusions.
