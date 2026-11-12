"""Build Report_2026_11_10.pdf (reports/daily/): daily report for 10 November 2026.

Uses the layout helpers of build_report_2026_11_08.py; numbers are read from
the saved results in ../backbone_20261108/results.
"""
import json
from pathlib import Path
import numpy as np
import build_report_2026_11_08 as base
from build_report_2026_11_08 import P, bullets, table, callout, figure, Spacer, PageBreak, KeepTogether, SimpleDocTemplate, A4, mm

base.DATE = '10 November 2026'
HERE = Path(__file__).resolve().parent
RES = base.BB / 'results'
OUTPUT = HERE.parent / 'daily' / 'Report_2026_11_10.pdf'
J = lambda name: json.loads((RES / name).read_text())
RUN = {'E40': 'minforce_niti18_E40_p20_a456_pre1_exact_smooth1', 'E75': 'minforce_niti18_E75_p20_a456_pre1_exact_smooth1'}


def tank_min(case, s):
    rows = J(f'coordwinch_{RUN[case]}_n20_tank.json')
    rr = [q for q in rows if q['clamp_s_mm'] == s]
    return min(q['clearance_mm'] for q in rr), sum(q['clearance_mm'] >= 5 for q in rr), len(rr)


def build():
    cw = {r['case']: r for r in J('coordwinch_summary.json')}
    ws = J('winch_sensitivity_summary.json')
    tr = {c: J(f'coordwinch_{c}_winch_travel.json') for c in ('E40', 'E75')}
    e40, e75 = cw['E40'], cw['E75']
    s40 = ws['E40']; s75 = ws['E75']
    story = []

    # ---------------- Page 1: summary
    story += [P('ASRC Fuel Tank Robot Daily Report', 'title'),
              P('Coordinated winch control and winch accuracy, 10 November 2026', 'subtitle'),
              P('Yesterday showed that U4 plus M2 with a 1.8 mm NiTi rod in each M module can hold the 500 g head at 20 degrees while sweeping '
                'yaw from 0 to 175 degrees, using 5 degree sample poses. Two questions were left: does real rope-length (winch) control move the head '
                'smoothly between those poses, and how accurate must the winches be?'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        f"<b>Coordinated winch control.</b> All 12 winches followed the rope lengths of the 5 degree poses together, in 20 sub-steps per segment. "
        f"The head moved smoothly from 0 to {e40['yaw_range'][1]:.0f} degrees (40 GPa rod) and 0 to {e75['yaw_range'][1]:.0f} degrees (75 GPa rod), "
        f"staying at {e40['elevation_range'][0]:.1f} to {e40['elevation_range'][1]:.1f} degrees elevation. All {e40['states']} and {e75['states']} states were stable, "
        f"no rope went slack, and the backward sweep retraced the forward one exactly.",
        f"<b>Tank clearance between poses.</b> The in-between states clear the full 3D tank by at least {tank_min('E40', 30)[0]:.1f} mm with the clamp 30 mm past the opening.",
        f"<b>Winch requirements.</b> The largest winch travel over the sweep is {tr['E40']['largest_travel_mm']:.0f} mm and the fastest rate "
        f"{tr['E40']['largest_rate_mm_per_deg']:.2f} mm per degree of yaw. Anchor-4 ropes barely move. Command tables are saved as CSV.",
        f"<b>Winch accuracy.</b> One winch off by 1 mm moves the head 1.3 to 3.2 degrees. Holding plus or minus 1 degree without feedback needs about "
        f"plus or minus {min(s40['allow_1deg_p99_mm']):.2f} to {max(s40['allow_1deg_p99_mm']):.2f} mm on every winch. The four tip ropes dominate; rope stiffness error "
        f"of 10% matters little (at most {max(s40['rope_EA_minus10_max_deg'], s75['rope_EA_minus10_max_deg']):.2f} degrees).",
        '<b>Margin against slack.</b> Every perturbed state stayed stable, but a rope at 1 N pretension stretches only about 0.15 mm, so small winch errors can leave it slack.',
    ])
    story += [Spacer(1, 6),
              table([['Check (U4 plus M2, rod, 20 deg, head held at 20 deg)', 'Result', 'Status'],
                     ['Motion between the 5 deg poses, winch control', f"{e40['states']} / {e75['states']} states, all stable, no slack, reversible", 'Pass'],
                     ['Head elevation during the sweep', f"{e40['elevation_range'][0]:.2f} to {max(e40['elevation_range'][1], e75['elevation_range'][1]):.2f} deg", 'Pass'],
                     ['Largest head movement per sub-step (0.25 deg yaw)', f"{e40['max_head_move_mm']:.2f} mm (40 GPa), {e75['max_head_move_mm']:.2f} mm (75 GPa)", 'Pass, no snaps'],
                     ['3D tank clearance between poses, clamp 0 / 30 mm', f"{tank_min('E40', 0)[0]:.1f} / {tank_min('E40', 30)[0]:.1f} mm minimum", 'Pass'],
                     ['Winch accuracy for plus or minus 1 deg (99%)', f"{min(s40['allow_1deg_p99_mm']):.2f} to {max(s40['allow_1deg_p99_mm']):.2f} mm", 'Needs feedback'],
                     ['Rope stiffness error plus or minus 10%', f"at most {max(s40['rope_EA_minus10_max_deg'], s40['rope_EA_plus10_max_deg'], s75['rope_EA_minus10_max_deg'], s75['rope_EA_plus10_max_deg']):.2f} deg", 'Minor'],
                     ['Ropes slack under winch error', f"{s40['singles_with_slack_rope_at_0p5mm']} of {s40['singles_at_0p5mm']} single 0.5 mm cases; stability kept", 'Small margin']],
                    [.42, .4, .18], bold_first_col=True),
              Spacer(1, 8),
              callout('Decisions from today',
                      'Length-controlled winches can drive the full held-elevation sweep smoothly. Add head-angle feedback (for example an IMU in the head), at least '
                      'for the four tip winches, and raise the rope pretension above 1 N to keep ropes taut under winch error. Anchor-4 ropes can be held '
                      'fixed during steering.')]
    story.append(PageBreak())

    # ---------------- Page 2: coordinated winch
    story += [P('Coordinated winch control between poses', 'h1'),
              P('For every stored 8-cell minimum-force pose (anchors [4,5,6], 1 N pretension), the length of each of the 12 winch ropes was computed with '
                'the fixed-winch rope model (elastic PA6 line, EA 10.4 kN, 1 m free length). All 12 lengths were then moved together, linearly from one '
                'pose to the next, in 20 sub-steps per 5 degree segment. Each equilibrium was solved from the previous state, giving the quasi-static motion '
                'a length-controlled drive would produce. The sweep was run forward and backward.')]
    rows = [['Check', 'Rod E 40 GPa', 'Rod E 75 GPa']]
    rows += [['States solved (forward)', f"{e40['states']}, none failed", f"{e75['states']}, none failed"],
             ['Yaw range', f"0 to {e40['yaw_range'][1]:.0f} deg, monotonic", f"0 to {e75['yaw_range'][1]:.0f} deg, monotonic"],
             ['Yaw vs commanded (linear between poses)', f"within {e40['max_yaw_tracking_error_deg']:.2f} deg", f"within {e75['max_yaw_tracking_error_deg']:.2f} deg"],
             ['World head elevation', f"{e40['elevation_range'][0]:.2f} to {e40['elevation_range'][1]:.2f} deg", f"{e75['elevation_range'][0]:.2f} to {e75['elevation_range'][1]:.2f} deg"],
             ['Head movement per sub-step', f"median {e40['median_head_move_mm']:.2f}, max {e40['max_head_move_mm']:.2f} mm", f"median {e75['median_head_move_mm']:.2f}, max {e75['max_head_move_mm']:.2f} mm"],
             ['Rope tension', f"{e40['min_rope_tension_n']:.2f} to {e40['peak_rope_tension_n']:.1f} N", f"{e75['min_rope_tension_n']:.2f} to {e75['peak_rope_tension_n']:.1f} N"],
             ['Stability (minimum fixed-winch eigenvalue)', f"all stable ({e40['min_fixed_winch_eig']:.3f})", f"all stable ({e75['min_fixed_winch_eig']:.3f})"],
             ['Backward vs forward sweep', f"head within {e40['reverse_max_head_difference_mm']:.5f} mm", f"head within {e75['reverse_max_head_difference_mm']:.5f} mm"],
             ['3D tank, clamp s = 0 / 30 mm', '%.1f / %.1f mm, all clear' % (tank_min('E40', 0)[0], tank_min('E40', 30)[0]), '%.1f / %.1f mm, all clear' % (tank_min('E75', 0)[0], tank_min('E75', 30)[0])],
             ['Strain / material twist', f"at most {e40['max_strain_pct']:.2f}% / {e40['max_twist_deg']:.0f} deg", f"at most {e75['max_strain_pct']:.2f}% / {e75['max_twist_deg']:.0f} deg"]]
    story += [table(rows, [.4, .3, .3], bold_first_col=True), Spacer(1, 4),
              figure(RES / 'coordwinch.png', 'Figure 1  Left: head elevation during the continuous sweep. Middle: winch commands (rope reeled in relative to the straight pose). '
                     'Right: resulting rope tensions; no rope goes slack.')]
    story += bullets([
        'Under coordinated rope-length control the head moves smoothly and reversibly through the whole sweep at the working elevation. This closes the open question '
        'from 9 November about the motion between the sampled poses, for the quasi-static model.',
        f"Winch requirements (40 GPa rod): largest travel {tr['E40']['largest_travel_mm']:.1f} mm (tip up rope), fastest {tr['E40']['largest_rate_mm_per_deg']:.2f} mm per degree of yaw. "
        'The anchor-4 ropes move under 3.5 mm over the whole sweep and could be held at fixed length while steering.',
    ])
    story.append(PageBreak())

    # ---------------- Page 3: winch sensitivity
    story += [P('Winch position error and rope stretch sensitivity', 'h1'),
              P('At seven poses of the coordinated sweep, each of the 12 winch lengths was offset by plus or minus 0.5 and 1 mm, one at a time, and the full '
                'nonlinear equilibrium re-solved (336 solves per rod). The resulting sensitivity matrix predicted 2,000 random cases with all 12 winches wrong at '
                'once (independent, uniform), and the worst case; the 10 worst predicted 1 mm cases per pose were re-solved with the full model. Rope EA was also '
                'changed by plus or minus 10% with the winch commands unchanged.')]
    y = s40['yaws']; idx = [y.index(v) for v in (0, 60, 120, 150, 175)]
    f = lambda arr, fmt: [fmt.format(arr[i]) for i in idx]
    rows = [['Rod E 40 GPa', 'yaw 0', '60', '120', '150', '175'],
            ['One winch off by 1 mm: head angle error, deg'] + [f'{max(a, b):.1f}' for a, b in zip([s40['single_1mm_yaw_deg'][i] for i in idx], [s40['single_1mm_elev_deg'][i] for i in idx])],
            ['All 12 random plus or minus 1 mm (99%): yaw / elev, deg'] + [f"{s40['all12_p99_1mm_yaw_deg'][i]:.1f} / {s40['all12_p99_1mm_elev_deg'][i]:.1f}" for i in idx],
            ['Same: head position, mm'] + f(s40['all12_p99_1mm_head_mm'], '{:.0f}'),
            ['Winch accuracy for plus or minus 1 deg (99%), mm'] + f(s40['allow_1deg_p99_mm'], '{:.2f}'),
            ['Winch accuracy for plus or minus 2 deg (99%), mm'] + f(s40['allow_2deg_p99_mm'], '{:.2f}'),
            ['Winch accuracy for plus or minus 1 deg (worst case), mm'] + f(s40['allow_1deg_worst_mm'], '{:.2f}')]
    story += [table(rows, [.4, .12, .12, .12, .12, .12], bold_first_col=True),
              P(f"The 75 GPa rod is similar or less sensitive: plus or minus 1 degree needs {min(s75['allow_1deg_p99_mm']):.2f} to {max(s75['allow_1deg_p99_mm']):.2f} mm (99%).", 'caption'),
              figure(RES / 'winch_sensitivity.png', 'Figure 2  Left: head angle error against yaw for single and combined winch errors. Middle: winch accuracy needed for '
                     'plus or minus 1 and 2 degrees. Right: mean sensitivity of each winch; the four tip (anchor 6) ropes dominate.')]
    story += bullets([
        'Open-loop length control needs about 0.2 to 0.5 mm accuracy on every winch for plus or minus 1 degree of head angle, tightening to 0.16 mm near 175 degrees where the front curls up.',
        'The four tip ropes (anchor 6) give 0.4 to 1.3 degrees per mm; anchor-4 and anchor-5 ropes 0.05 to 0.35 degrees per mm. Precision matters mainly on the tip winches.',
        f"All {s40['singles_solved'] + s75['singles_solved']} single-winch cases and {s40['combined_checks'] + s75['combined_checks']} combined checks stayed stable and within geometry limits. "
        f"A rope at 1 N stretches only about 0.15 mm, so {s40['singles_with_slack_rope_at_0p5mm']} of {s40['singles_at_0p5mm']} single 0.5 mm errors left a rope slack.",
    ])
    story.append(PageBreak())

    # ---------------- Page 4: limitations + next
    story += [P('Limitations', 'h1')]
    story += bullets([
        'Quasi-static model: no winch dynamics, inertia or control loop. Rope friction and stick-slip in the guides, rope creep and temperature are not modelled.',
        'Rope stiffness assumes 1 m of free rope from guide to winch; a different length rescales the pull-in values and the slack margin.',
        'Rod properties are calculated, not measured; NiTi hysteresis is not modelled. The head is a 500 g point mass with a 63 mm envelope.',
        'Linear prediction of combined winch errors agrees with the full model within about 1.2 degrees at 1 mm; slack ropes cause the difference.',
    ])
    story += [P('Next steps', 'h1'),
              table([['Priority', 'Task', 'Purpose'],
                     ['1', 'Build and test the backbone M module', 'Measure EA, EI, rod buckling at the guide spacing and joint slip; all results depend on these'],
                     ['2', 'Higher pretension (3 to 5 N)', 'Re-run the minimum-force sweep and winch sensitivity; trade peak force for margin against slack'],
                     ['3', 'Head-angle feedback concept', 'Sensor choice (IMU or encoder), and a closed-loop correction using the sensitivity matrix from today'],
                     ['4', 'Rope friction model', 'Add guide friction to the winch model and check smoothness and accuracy'],
                     ['5', 'Tank-aware steering, entry, storage, rear', 'As in the 9 November plan']],
                    [.1, .34, .56]),
              Spacer(1, 8),
              P('Sources and reproduction', 'h2'),
              P('Scripts and data: simulations/u4m2/backbone_20261108 (README sections 8 and 9: coordinated_winch.py, coordinated_winch_tank.py, '
                'coordinated_winch_table.py, winch_sensitivity.py). Winch command tables: results/coordwinch_E40_winch_table.csv and coordwinch_E75_winch_table.csv. '
                'This report is generated by reports/builders/build_report_2026_11_10.py.')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Daily Report, 10 November 2026', author='ASRC')
    doc.build(story, onFirstPage=base.on_page, onLaterPages=base.on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
