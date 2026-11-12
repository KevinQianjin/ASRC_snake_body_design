"""Build Report_2026_11_09.pdf (reports/daily/): daily report for 9 November 2026.

Uses the layout helpers of build_report_2026_11_08.py; numbers are read from
the saved results in ../backbone_20261108/results where practical.
"""
import json
from pathlib import Path
import numpy as np
import build_report_2026_11_08 as base
from build_report_2026_11_08 import P, bullets, table, callout, figure, Spacer, PageBreak, KeepTogether, SimpleDocTemplate, A4, mm

base.DATE = '9 November 2026'
HERE = Path(__file__).resolve().parent
BB = HERE.parent / 'backbone_20261108'
RES = BB / 'results'
OUTPUT = HERE.parent.parent.parent / 'reports' / 'daily' / 'Report_2026_11_09.pdf'
J = lambda name: json.loads((RES / name).read_text())


def build():
    entry2d = {(r['configuration'], r.get('variant'), round(r['pitch_deg'])): r for r in J('entry_screen.json')['results']}
    pre = {(r['variant'], r['pitch_deg']): r for r in J('pretension1_recheck.json')}
    mf = {r['file']: r for r in J('minforce_summary.json')}
    e3 = J('tank3d_entry.json')['entry']
    stop = {'15': 114, '20': 90, '25': 78}
    e3min = {p: min(g for s, g in zip(d['s_mm'], d['clearance_mm']) if s <= stop[p] + 1e-9) for p, d in e3.items()}
    sp = {(r['variant'], r['pull'], r['mode']): r for r in J('sidepull_summary.json')}

    def sweep_rows(run, tag=''):
        return J(f'tank3d_sweep_{run}{tag}.json')['rows']
    r40 = sweep_rows('minforce_niti18_E40_p20_a456_pre1_exact_smooth1') + sweep_rows('minforce_niti18_E40_p20_a456_pre1_exact_smooth1', '_s0_30_60')
    r75 = sweep_rows('minforce_niti18_E75_p20_a456_pre1_exact_smooth1') + sweep_rows('minforce_niti18_E75_p20_a456_pre1_exact_smooth1', '_s0_30_60')

    def cell(rows, s, side):
        rr = [q for q in rows if q['clamp_s_mm'] == s and q['side'] == side]
        ok = sum(q['clearance_mm'] >= 5 for q in rr); w = min(q['clearance_mm'] for q in rr)
        return f"all clear, min {w:.1f} mm" if ok == len(rr) else f"{ok}/{len(rr)} clear, min {w:.1f} mm"

    story = []
    # ---------------- Page 1
    story += [P('ASRC Fuel Tank Robot Daily Report', 'title'),
              P('Backbone M module: entry, stability, tendon force, 3D tank and horizontal flexibility, 9 November 2026', 'subtitle'),
              P('Yesterday\'s review showed that a central 1.8 mm NiTi rod in each M module lets U4 plus M2 straighten within the 5% strain '
                'diagnostic and hold the 500 g head near 20 degrees. Today tested whether that design also enters the tank, stays stable in 3D, '
                'can be steered with small and smooth tendon forces, and fits inside the full 3D tank.'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        f"<b>Tank entry, low strain.</b> The straight rod shape feeds through the bottom opening at 15, 20 and 25 degrees with "
        f"{entry2d[('U4-M2','niti18_E40',15)]['refined16_min_clearance_mm']:.0f}, {entry2d[('U4-M2','niti18_E40',20)]['refined16_min_clearance_mm']:.0f} and "
        f"{entry2d[('U4-M2','niti18_E40',25)]['refined16_min_clearance_mm']:.0f} mm minimum clearance at about 0.1% strain. On 6 November every low-strain shape hit the tank.",
        '<b>3D stability needs pretension.</b> With only the up ropes pulled, the straight front is laterally unstable in 3D; the 2D model could not show this. '
        'A 1 N pretension on every rope fixes it, and straightening and entry still pass.',
        '<b>Minimum tendon force.</b> Holding the head at 20 degrees while sweeping yaw from 0 to 175 degrees in 5 degree steps needs only about 7 to 15 N peak '
        'rope force (anchors [4,5,6]), against 46 to 98 N for yesterday\'s allocations. With smoothing, no rope changes by more than about 5 N per step.',
        f"<b>Full 3D tank.</b> All 362 tank solids were meshed from the STEP file. Entry clearance is {e3min['15']:.0f} / {e3min['20']:.0f} / {e3min['25']:.0f} mm in full 3D. "
        'At 20 degrees with the clamp 0 to 30 mm past the opening, the whole yaw sweep clears the tank by at least 12.6 mm on both sides; 25 degrees hits the roof.',
        '<b>Horizontal flexibility.</b> Reeling in the tip\'s right rope turns the head about 1.25 degrees per mm, smoothly and stably. Alone it keeps the head at '
        '20 plus or minus 5 degrees only to about 20 degrees of yaw. Tension-only control snaps the straight front (258 mm jump), so rope-length control is required.',
    ])
    story += [Spacer(1, 6),
              table([['Check (U4 plus M2, 1.8 mm NiTi rod)', 'Result', 'Status'],
                     ['Straightening at or below 5% strain, 15 to 25 deg', '1.2 to 2.0 mm offset, about 0.1% strain, with 1 N pretension', 'Pass'],
                     ['Tank entry (2D sections and full 3D)', '44 to 65 mm at 15 and 20 deg; 17 to 19 mm at 25 deg', 'Pass'],
                     ['3D lateral stability', 'Unstable with up ropes only; stable with 1 N on every rope', 'Pass with rule'],
                     ['Held-elevation yaw sweep, 20 deg', '0 to 175 deg, 7 to 15 N peak, smooth 5 deg steps', 'Pass'],
                     ['Yaw sweep inside full 3D tank', '20 deg, clamp s = 0 to 30 mm: at least 12.6 mm', 'Pass'],
                     ['25 deg installation, yaw sweep', 'Hits the tank roof at every clamp depth', 'Fail'],
                     ['Side pull of one rope, winch control', 'About 1.25 deg/mm; holds 20 deg elevation only to about 20 deg yaw', 'Needs coordination'],
                     ['Tension-only control of the straight front', 'Snap-through at +0.5 N', 'Do not use']],
                    [.38, .44, .18], bold_first_col=True),
              Spacer(1, 8),
              callout('Decisions from today',
                      'Install at 20 degrees. Steer with the clamp 0 to 30 mm past the opening. Keep at least 1 N on every rope. Drive the ropes by '
                      'length (winch position) control, not tension control, and coordinate the up and side ropes to hold the working elevation.')]
    story.append(PageBreak())

    # ---------------- Page 2: entry + pretension
    story += [P('Tank entry with the straight low-strain shape', 'h1'),
              P('The 6 November front-only entry screen was reused unchanged: a fixed loaded shape slides along the installation axis through the bottom '
                'opening, starting fully outside the tank, and must stay at least 5 mm from the saved tank sections. The control case reproduces the 6 November '
                'value exactly (62.06 mm). Passing shapes were re-checked at 16 cells per module.'),
              table([['U4 plus M2', 'Strain', '15 deg', '20 deg', '25 deg'],
                     ['Current M (no rod)', '4.96%', 'hits tank', 'hits tank', 'hits tank'],
                     ['Rod, E 40 GPa', '0.10%'] + [f"{entry2d[('U4-M2','niti18_E40',p)]['refined16_min_clearance_mm']:.1f} mm" for p in (15, 20, 25)],
                     ['Rod, E 75 GPa', '0.09%'] + [f"{entry2d[('U4-M2','niti18_E75',p)]['refined16_min_clearance_mm']:.1f} mm" for p in (15, 20, 25)]],
                    [.28, .12, .2, .2, .2], bold_first_col=True),
              Spacer(1, 4),
              figure(RES / 'entry_screen.png', 'Figure 1  Left: the rod shape at four clamp positions through the saved tank sections at 20 degrees; the current-M low-strain '
                     'shape hits the tank. Right: clearance along the feed path for 15, 20 and 25 degrees (16 cells per module).'),
              P('3D stability needs pretension on every rope', 'h1'),
              P('The straightened states tension only the up ropes. They pass the planar stability check, but in the 3D model they are laterally unstable '
                '(minimum fixed-winch eigenvalue minus 0.20 to minus 0.50), because the 2D model cannot see sideways buckling. A 1 N pretension on all four ropes '
                'of every set stabilises every case. With it, the straightening was re-optimised:')]
    rows = [['Rod', 'Pitch', 'Offset / tangent / strain', 'Top-rope tensions N', '3D stable', 'Entry gap']]
    for v, lab in [('niti18_E40', 'E 40 GPa'), ('niti18_E75', 'E 75 GPa')]:
        for p in (15, 20, 25):
            q = pre[(v, p)]
            rows.append([lab, f'{p} deg', f"{q['offset_mm']:.2f} mm / {q['tangent_deg']:.1f} deg / {100*q['max_strain']:.2f}%",
                         ', '.join(f'{x:.1f}' for x in q['top_extra_tensions_n']), 'Yes' if q['stable_3d_fixed_winch'] else 'No',
                         f"{q['entry_min_gap_mm']:.1f} mm"])
    story += [table(rows, [.13, .09, .3, .2, .1, .18], bold_first_col=True),
              P('Conclusion: the 8 November straightening and today\'s entry results stand, provided every rope keeps at least 1 N. This becomes a control rule.', 'caption')]
    story.append(PageBreak())

    # ---------------- Page 3: min force
    story += [P('Minimum tendon force for held-elevation yaw', 'h1'),
              P('Yaw was stepped from 0 to 180 degrees by continuation, each step seeded from the previous one. At each step the optimiser minimised the largest '
                'single rope tension subject to equilibrium, the target yaw, head elevation held at the base pitch, the geometry limits, strain within 4.75% and 1 to 250 N '
                'per rope. States were solved at 4 cells per module, then re-solved at 8 cells and accepted only if stable and within 1 degree of the target. '
                'A small penalty on tension changes between steps selects a smooth allocation among the many with nearly the same peak.')]
    rows = [['Run (elevation held exactly, 5 deg steps)', 'Passing states', 'Peak rope N', 'Largest change per step']]
    for f, lab in [('minforce_niti18_E40_p20_a456_pre1_exact_smooth1.json', 'E 40 GPa, 20 deg, anchors [4,5,6], smooth'),
                   ('minforce_niti18_E40_p20_a456_pre1_exact.json', 'E 40 GPa, 20 deg, anchors [4,5,6]'),
                   ('minforce_niti18_E40_p20_a46_pre1_exact.json', 'E 40 GPa, 20 deg, anchors [4,6]'),
                   ('minforce_niti18_E75_p20_a456_pre1_exact_smooth1.json', 'E 75 GPa, 20 deg, anchors [4,5,6], smooth'),
                   ('minforce_niti18_E40_p25_a456_pre1_exact.json', 'E 40 GPa, 25 deg, anchors [4,5,6]')]:
        q = mf[f]
        rows.append([lab, f"{q['states_passing']}/{q['states_attempted']} ({abs(round(q['yaw_range_deg'][0])):.0f} to {q['yaw_range_deg'][1]:.0f} deg)",
                     f"{q['peak_n_min']:.1f} to {q['peak_n_max']:.1f}", f"{q['max_step_tension_change_n']:.1f} N"])
    story += [table(rows, [.4, .24, .16, .2], bold_first_col=True), Spacer(1, 4),
              figure(RES / 'minforce_results.png', 'Figure 2  Left: minimum peak rope tension along the held-elevation yaw sweep, against the 8 November maximum-angle '
                     'allocations. Right: rope tensions of the smooth allocation.')]
    story += bullets([
        'Peak force drops from 46 to 98 N to about 7 to 15 N with anchors [4,5,6]. Strain stays at or below 0.09%, and every state is stable.',
        'Consecutive 5 degree states move the head at most 33 to 56 mm, consistent with a smooth sweep. This is strong evidence of a continuous quasi-static '
        'path from 0 to 175 degrees, but the states between samples were not checked.',
        'Posture: 30 to 90 degrees of yaw uses sideways bending of M with 30 to 55 degrees of twist; near 180 degrees M curls up and back over itself, '
        'so the head looks back toward the base. Up to about 60 degrees the head stays within about 20 mm of its starting height.',
    ])
    story.append(PageBreak())

    # ---------------- Page 4: 3D tank
    story += [P('Full 3D tank clearance', 'h1'),
              P('All 362 solids of the tank model in tank-v2.step (external frame excluded) were triangulated: 461,524 triangles at 0.5 mm deflection. '
                'Clearance is the exact distance from the front centreline to that surface minus the 31.5 mm envelope radius. Points on the five saved 2D '
                'sections lie within 0.23 mm of the 3D mesh.'),
              table([['Entry path, straight shape, 1 N pretension', '15 deg', '20 deg', '25 deg'],
                     ['2D sections (five planes)', f"{pre[('niti18_E40',15)]['entry_min_gap_mm']:.1f} mm", f"{pre[('niti18_E40',20)]['entry_min_gap_mm']:.1f} mm", f"{pre[('niti18_E40',25)]['entry_min_gap_mm']:.1f} mm"],
                     ['Full 3D tank', f"{e3min['15']:.1f} mm", f"{e3min['20']:.1f} mm", f"{e3min['25']:.1f} mm"]],
                    [.4, .2, .2, .2], bold_first_col=True),
              P('The full-width 3D result confirms the 2D screen and closes the limitation that five planes did not cover the full 63 mm width.', 'caption')]
    rows = [['20 deg, head held at 20 deg', 's = 0 mm', 's = 30 mm', 's = 60 mm', 's = 90 mm']]
    for lab, rr in [('E 40 GPa, right', (r40, 'right')), ('E 40 GPa, left', (r40, 'left')), ('E 75 GPa, right', (r75, 'right')), ('E 75 GPa, left', (r75, 'left'))]:
        rows.append([lab] + [cell(rr[0], s, rr[1]) for s in (0, 30, 60, 90)])
    story += [KeepTogether([P('Held-elevation yaw sweep placed in the 3D tank, by clamp depth s past the opening', 'h2'),
                            table(rows, [.2, .2, .2, .2, .2], bold_first_col=True)]),
              Spacer(1, 4),
              figure(RES / 'tank3d_sweep.png', 'Figure 3  Clearance to the full 3D tank along the held-elevation yaw sweep, E 40 GPa, by clamp depth.')]
    story += bullets([
        'At 20 degrees with the clamp 0 to 30 mm past the opening, the whole sweep clears the tank by at least 12.6 mm on both sides. Clearance stays near 65 mm up to '
        'about 85 degrees of yaw and falls only in the up-and-over posture, always against the tank roof.',
        'Deeper clamp positions raise the base and bring the curled M into the roof. At 25 degrees the sweep fails at every depth tested (s = 0 to 300 mm).',
    ])
    story.append(PageBreak())

    # ---------------- Page 5: horizontal flexibility
    a6 = sp[('niti18_E40', 'a6', 'winch')]; a6b = sp[('niti18_E75', 'a6', 'winch')]
    story += [P('Horizontal flexibility: yaw vs side-rope pull', 'h1'),
              P('Starting from the straight held front at 20 degrees, only the right rope was pulled, at anchor 6 (tip), 5, 4 or all three, in small steps from the previous '
                'state at 8 cells per module. Two control modes were compared. Tension control prescribes rope forces. Winch control prescribes rope lengths: each rope '
                'is an elastic PA6 line (EA 10.4 kN) with 1 m of free length, reeled in 0.25 mm per step.'),
              callout('Tension-only control is unsafe for the straight pose',
                      'At constant tension the straight front is laterally unstable (eigenvalue minus 0.51 at E 40 GPa). Adding 0.5 N to the tip\'s right rope makes the '
                      'head snap 258 mm to 124 degrees of yaw. Under winch control the same pose is stable (eigenvalue plus 0.73). Use rope-length control or fast feedback.'),
              Spacer(1, 6)]
    rows = [['Pulled rope (winch)', 'Initial gain', 'Yaw with head at 20 plus or minus 5 deg', 'Largest yaw (elevation, rope N)', 'Largest head jump']]
    for (v, pull), lab in [(('niti18_E40', 'a6'), 'Anchor 6, E 40 GPa'), (('niti18_E75', 'a6'), 'Anchor 6, E 75 GPa'),
                           (('niti18_E40', 'all'), 'All three, E 40 GPa'), (('niti18_E40', 'a5'), 'Anchor 5, E 40 GPa'), (('niti18_E40', 'a4'), 'Anchor 4, E 40 GPa')]:
        q = sp[(v, pull, 'winch')]
        rows.append([lab, f"{q['yaw_per_mm_initial']:.2f} deg/mm", f"{q['yaw_in_band_deg']:.1f} deg ({q['pull_in_band_mm']:g} mm, {q['right_rope_in_band_n']:.0f} N)",
                     f"{q['max_yaw_deg']:.1f} deg ({q['elevation_at_max_yaw_deg']:+.0f} deg, {q['right_rope_at_max_n']:.0f} N)", f"{q['max_head_jump_mm']:.1f} mm"])
    story += [table(rows, [.2, .13, .27, .26, .14], bold_first_col=True), Spacer(1, 4),
              figure(RES / 'sidepull.png', 'Figure 4  Yaw against winch pull-in, head elevation against yaw, and tension in the pulled rope.')]
    story += bullets([
        f"The tip rope is the effective yaw actuator: about {a6['yaw_per_mm_initial']:.2f} deg per mm of pull-in, roughly 2 N per degree at small angles, smooth and stable.",
        'Anchors 4 and 5 hardly turn the head: the U section barely bends sideways, so the force compresses the front instead (up to 364 N for 12 degrees at anchor 4).',
        f"With the other ropes locked, the head droops as it yaws. It stays at 20 plus or minus 5 degrees only to about {a6['yaw_in_band_deg']:.0f} to {a6b['yaw_in_band_deg']:.0f} degrees. "
        'Further yaw at the working elevation needs the up ropes reeled in together with the side rope, as the minimum-force sweep does.',
    ])
    story.append(PageBreak())

    # ---------------- Page 6: next
    story += [P('Limitations', 'h1')]
    story += bullets([
        'All rod properties are calculated, not measured. Constant linear EA and EI; no friction, NiTi transformation, hysteresis or fatigue.',
        'The sensor head is a 500 g point mass with a provisional 63 mm envelope. Cables and ropes outside the front are not modelled.',
        'Steering states are free-space equilibria placed in the tank, not tank-aware optimised postures. The 30 to 55 degrees of twist used at mid yaw is unverified in hardware.',
        'States between the 5 degree samples, and real winch dynamics, were not checked.',
        'The 5% strain diagnostic, 250 N rope bound and 180 degree search cap are numerical limits, not hardware ratings.',
    ])
    story += [P('Next steps', 'h1'),
              table([['Priority', 'Task', 'Purpose'],
                     ['1', 'Build and test the backbone M module (test plan)', 'Measure EA, EI, buckling at the guide spacing and rod joint slip; everything above depends on these'],
                     ['2', 'Coordinated winch-control test (planned for tomorrow)', 'Drive the rope lengths through the 5 degree minimum-force poses with fine steps; check the head moves smoothly from 0 to 175 degrees at 20 degrees elevation'],
                     ['3', 'Tank-aware steering', 'Optimise postures with the 3D tank as a constraint, and check the twist limits'],
                     ['4', 'Entry, storage and sensor head', 'Real head CAD and cable envelopes, sleeve contact, rear storage and retraction'],
                     ['5', 'Rear mechanism and integrated validation', 'Stage sizing, drive and locks, then a full integrated check']],
                    [.1, .38, .52]),
              Spacer(1, 8),
              P('Sources and reproduction', 'h2'),
              P('All scripts, data and figures are in ASRC_kevin/telescopic_planar_study/backbone_20261108 (README sections 3 to 7). '
                'This report is generated by ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_09.py.')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Daily Report, 9 November 2026', author='ASRC')
    doc.build(story, onFirstPage=base.on_page, onLaterPages=base.on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
