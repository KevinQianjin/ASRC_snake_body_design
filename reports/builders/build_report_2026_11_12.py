"""Build reports/daily/Report_2026_11_12.pdf: daily report for 12 November 2026.

Uses the layout helpers of build_report_2026_11_08.py; numbers are read from
the saved closed-loop results (v1, v2, v3) beside their source.
"""
import json
from pathlib import Path
import build_report_2026_11_08 as base
from build_report_2026_11_08 import P, bullets, table, callout, figure, Spacer, PageBreak, KeepTogether, SimpleDocTemplate, A4, mm, CONTENT_W

base.DATE = '12 November 2026'
HERE = Path(__file__).resolve().parent
BB = base.BB
OUTPUT = HERE.parent / 'daily' / 'Report_2026_11_12.pdf'
CASES = ['nominal', 'E75', 'payload550g', 'free1500mm', 'ropeEA80pct']
LABEL = {'nominal': 'Nominal', 'E75': 'Rod E 75 GPa', 'payload550g': 'Head 550 g', 'free1500mm': 'Free rope 1.5 m', 'ropeEA80pct': 'Rope EA -20%'}
J = lambda p: json.loads((BB / p).read_text())


def build():
    v1 = {c: J(f'closed_loop_results/{c}_summary.json') for c in CASES}
    c12 = J('closed_loop_v2_results/comparison_v1_v2.json')
    c23 = J('closed_loop_v3_results/comparison_v1_v2_v3.json')
    v2s = {c: J(f'closed_loop_v2_results/{c}_summary.json') for c in CASES}
    v3s = {c: J(f'closed_loop_v3_results/{c}_summary.json') for c in CASES}
    fro = J('closed_loop_v3_results/fixed_reference_only/payload550g_summary.json')
    fro_tr = [t for t in J('closed_loop_v3_results/fixed_reference_only/payload550g_trace.json') if t['kind'] != 'start']
    fro_bad = [t for t in fro_tr if max(abs(t['yaw_error_deg']), abs(t['elevation_error_deg'])) > 1]
    fro_max = max(max(abs(t['yaw_error_deg']), abs(t['elevation_error_deg'])) for t in fro_tr)
    ref = J('length_cycle_results_pre3_tol1/nominal_summary.json'); ref_old = J('length_cycle_results_pre3/nominal_summary.json')
    four = ['nominal', 'E75', 'free1500mm', 'ropeEA80pct']
    story = []

    # ---------------- Page 1
    story += [P('ASRC Fuel Tank Robot Daily Report', 'title'),
              P('Closed-loop control: operating pretension, refined path and an exact 20 degree reference, 12 November 2026', 'subtitle'),
              P('This morning the team completed the first closed-loop round trip (v1): head-angle and rope-tension feedback with nominal-model gains, '
                'passing all settled checks in five cases, and reorganised the repository. Two items were left open: rope tension during command '
                'transitions (down to 0.57 N, with the controller aiming at only 1.5 N), and node movement above the 5 mm sampling bound. '
                'Today\'s work closed both, then removed a reference error that caused most of the remaining angle error during motion.'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        '<b>Project renewed after the reorganisation.</b> Links (45 Markdown files) and model tests checked; the new M end-disk coupon moved next to the STL it '
        'loads (cad/previews/u4m2/); model data paths refreshed. No other problems found.',
        '<b>Closed loop v2: operating pretension and refined path.</b> Same model, reference, gains and cases. The correction keeps every rope at 3 N or more; '
        'tensions are predicted before each new command and a small pre-correction is added if any would fall below 3 N; every move is subdivided until no '
        f"point moves more than 4.5 mm, and every intermediate state is solved and checked. Lowest rope tension in any recorded state: "
        f"{min(c12[c]['v2']['min_tension_n'] for c in CASES):.2f} N (v1: {min(c12[c]['v1']['min_tension_n'] for c in CASES):.2f} N); largest node move "
        f"{max(c12[c]['v2']['max_node_move_mm'] for c in CASES):.1f} mm (v1: {max(c12[c]['v1']['max_node_move_mm'] for c in CASES):.1f} mm).",
        f"<b>Closed loop v3: exact 20 degree reference.</b> The 0 and 5 degree yaw poses of the 3 N reference had been accepted at 16 to 17 degrees. Regenerated at "
        f"exactly 20 degrees; the reference cycle's largest elevation error fell from {ref_old['maximum_elevation_error_deg']:.2f} to {ref['maximum_elevation_error_deg']:.2f} degrees. "
        '<b>Four of five cases now pass every check in every recorded state.</b>',
        '<b>Correction during moves</b> was tried for the 550 g head at large yaw and made it worse; it is not recommended.',
    ])
    rows = [['Case', 'v1: lowest tension / largest move', 'v2', 'v3: states > 1 deg in motion', 'v3: all checks, every state']]
    for c in CASES:
        a, b, d3 = c12[c]['v1'], c12[c]['v2'], c23[c]['v3']
        allpass = d3['angle_failures_in_motion'] == 0 and d3['other_failures'] == 0
        rows.append([LABEL[c], f"{a['min_tension_n']:.2f} N / {a['max_node_move_mm']:.1f} mm", f"{b['min_tension_n']:.2f} N / {b['max_node_move_mm']:.1f} mm",
                     f"{d3['angle_failures_in_motion']} (max {d3['max_angle_error_in_motion_deg']:.2f} deg)", '<b>Pass</b>' if allpass else 'Angle in motion only'])
    story += [Spacer(1, 4), table(rows, [.17, .24, .18, .23, .18], bold_first_col=True), Spacer(1, 8),
              callout('Decisions from today',
                      'Use the v2 control sequence (3 N correction target, tension-aware arrival, refined path) with the exact 20 degree reference (v3). '
                      'Do not correct during moves. The remaining 550 g large-yaw angle error needs gains that adapt to measured responses, '
                      'not more frequent correction.')]
    story.append(PageBreak())

    # ---------------- Page 2: v2
    story += [P('Closed loop v2: operating pretension and refined path', 'h1'),
              P('The controller still observes only head yaw, elevation and the 12 rope tensions; plant parameters are not used. Changes to the control '
                'sequence of v1:')]
    story += bullets([
        '<b>Operating tension.</b> The correction keeps every predicted rope tension at 3 N or more (v1: 1.5 N). A sample is settled at an angle error of at most '
        '0.2 degrees and a measured minimum tension of at least 2.5 N.',
        '<b>Tension-aware arrival.</b> Before each new command, tensions are predicted from the measured tensions and the nominal gains; if any would fall below 3 N, '
        'a pre-correction of at most 0.5 mm per rope is added that disturbs the head angles as little as possible.',
        '<b>Refined path.</b> Every move is applied in rope steps of at most 0.25 mm, halved until no centreline node moves more than 4.5 mm. Every intermediate state '
        'is solved from the previous one and checked (stability, tension, geometry, strain, 3D tank clearance), and checked against the target interpolated along the move.',
    ])
    rows = [['Case', 'v1 lowest tension', 'v1 states below 2.5 N', 'v2 lowest tension', 'v2 states below 2.5 N', 'Largest node move v1 / v2', 'v2 peak tension']]
    for c in CASES:
        a, b = c12[c]['v1'], c12[c]['v2']
        rows.append([LABEL[c], f"{a['min_tension_n']:.2f} N", f"{a['below_2p5']} of {a['recorded_states']}", f"<b>{b['min_tension_n']:.2f} N</b>",
                     f"<b>{b['below_2p5']}</b> of {b['recorded_states']}", f"{a['max_node_move_mm']:.2f} / <b>{b['max_node_move_mm']:.2f}</b> mm", f"{b['peak_tension_n']:.1f} N"])
    story += [table(rows, [.15, .12, .15, .12, .15, .17, .14], bold_first_col=True), Spacer(1, 4),
              figure(BB / 'closed_loop_v2_results' / 'v1_v2_comparison.png',
                     'Figure 1  Lowest rope tension of every recorded state, v1 (red) and v2 (blue), and the largest node movement between recorded states.')]
    story += bullets([
        'Every recorded state of every case stays above the 2.5 N operating floor; no state is unstable or fails geometry, strain or tank clearance; all samples settle '
        'within 0.2 degrees (v1 550 g: 0.70 degrees). Cost: peak rope tension 25 to 27 N.',
        'Remaining in v2: temporary angle error during motion, at the straightening-to-insertion hand-off in every case (up to 3.3 degrees) and at 155 to 175 '
        'degrees yaw with the 550 g head (up to 2.85 degrees).',
    ])
    story.append(PageBreak())

    # ---------------- Page 3: v3
    story += [P('Closed loop v3: exact 20 degree reference', 'h1'),
              P('The hand-off error came from the reference itself: the 0 and 5 degree poses of the 3 N yaw sweep had been accepted on the fine mesh at 16.9 and '
                '16.1 degrees, because acceptance allowed plus or minus 5 degrees. The sweep was regenerated requiring the fine-mesh elevation within 1 degree of 20 '
                '(all 36 poses now at 20.0 degrees), and the reference cycle and nominal gains were rebuilt from it.')]
    rows = [['Case', 'States > 1 deg in motion, v2 / v3', 'Largest angle in motion, v2 / v3', 'Lowest tension v3', 'Peak tension v2 / v3', 'Correction used v2 / v3']]
    for c in CASES:
        b, d3 = c23[c]['v2'], c23[c]['v3']
        rows.append([LABEL[c], f"{b['angle_failures_in_motion']} / <b>{d3['angle_failures_in_motion']}</b>",
                     f"{b['max_angle_error_in_motion_deg']:.2f} / <b>{d3['max_angle_error_in_motion_deg']:.2f}</b> deg", f"{d3['min_tension_n']:.2f} N",
                     f"{b['peak_tension_n']:.1f} / {d3['peak_tension_n']:.1f} N", f"{b['max_offset_mm']:.2f} / {d3['max_offset_mm']:.2f} mm"])
    story += [table(rows, [.15, .19, .19, .13, .17, .17], bold_first_col=True),
              P('v3 results shown with correction during moves enabled (0.5 degree threshold, kept only if the measured error decreases); it was used only in the '
                '75 GPa and 550 g cases.', 'caption')]
    rows = [['Head 550 g', 'States > 1 deg in motion', 'Largest'],
            ['v2 (old reference)', str(c23['payload550g']['v2']['angle_failures_in_motion']), f"{c23['payload550g']['v2']['max_angle_error_in_motion_deg']:.2f} deg"],
            ['v3, fixed reference only', str(len(fro_bad)), f'{fro_max:.2f} deg'],
            ['v3, fixed reference + guarded correction during moves', str(c23['payload550g']['v3']['angle_failures_in_motion']), f"{c23['payload550g']['v3']['max_angle_error_in_motion_deg']:.2f} deg"],
            ['v3, unguarded first attempt (diagnostic)', '872', '6.82 deg']]
    story += [KeepTogether([P('Head 550 g: four versions', 'h2'), table(rows, [.55, .25, .2], bold_first_col=True)]), Spacer(1, 4),
              figure(BB / 'closed_loop_v3_results' / 'v2_v3_comparison.png',
                     'Figure 2  Angle error against the interpolated target and lowest rope tension for every recorded state, v2 (orange) and v3 (blue).')]
    story += bullets([
        f"<b>Nominal, 75 GPa rod, 1.5 m free rope and rope EA -20% pass every check in every recorded state</b>: angle error during motion at most "
        f"{max(c23[c]['v3']['max_angle_error_in_motion_deg'] for c in four):.2f} degrees, rope tension at least {min(c23[c]['v3']['min_tension_n'] for c in four):.2f} N, "
        f"node move at most {max(c23[c]['v3']['max_node_move_mm'] for c in four):.1f} mm. Peak tension falls to {min(c23[c]['v3']['peak_tension_n'] for c in four):.1f} to "
        f"{max(c23[c]['v3']['peak_tension_n'] for c in four):.1f} N because the controller no longer fights a wrong reference.",
        '<b>Head 550 g:</b> temporary angle error remains at 155 to 175 degrees yaw. The nominal gains have the wrong sign there for the heavier head: a correction '
        'for 0.2 degrees moves the head about 1 degree the other way, so correcting more often adds overshoot. These states pass every tension, stability, geometry '
        'and clearance check, and all samples settle within 0.2 degrees.',
    ])
    story.append(PageBreak())

    # ---------------- Page 4
    story += [P('Limitations', 'h1')]
    story += bullets([
        'Quasi-static model with ideal measurements: no motor dynamics, sampling time, sensor noise or delay, friction, backlash or NiTi hysteresis. Positive static '
        'stiffness does not establish dynamic closed-loop stability.',
        'The five cases were used while developing the controller changes; they are not an independent validation set.',
        'Rod properties are calculated, not measured; the head is a 500 g point mass with a 63 mm envelope; tank clearance is sampled at recorded states.',
    ])
    story += [P('Next steps', 'h1'),
              table([['Priority', 'Task', 'Purpose'],
                     ['1', 'Online gain update', 'Update the controller gains from measured head-angle responses (for example a Broyden update) to remove the 550 g large-yaw error'],
                     ['2', 'Dynamics and sensing', 'Winch speed and travel limits, control update rate, sensor noise and delay; repeat the five cases'],
                     ['3', 'Build and test the backbone M module', 'Continuous 96 mm module, full-length rod: stiffness, buckling, end-joint slip (test plan, end-disk coupon)'],
                     ['4', 'Rope and winch calibration', 'Measured rope stiffness, free length and friction'],
                     ['5', 'Head CAD, entry, storage, rear mechanism', 'As in the roadmap']],
                    [.1, .32, .58]),
              Spacer(1, 6),
              P('Scripts and data: simulations/u4m2/backbone_20261108 (README sections 12 and 13; closed_loop_v2.py, summarize_closed_loop_v2.py, test_closed_loop_v2.py, '
                'min_force_sweep.py --elev-tol; results in closed_loop_v2_results, closed_loop_v3_results and length_cycle_results_pre3_tol1). '
                'This report is generated by reports/builders/build_report_2026_11_12.py.', 'caption')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Daily Report, 12 November 2026', author='ASRC')
    doc.build(story, onFirstPage=base.on_page, onLaterPages=base.on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
