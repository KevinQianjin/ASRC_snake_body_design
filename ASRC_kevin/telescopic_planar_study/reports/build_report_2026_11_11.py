"""Build Report_2026_11_11.pdf (reports/daily/): daily report for 11 November 2026.

Uses the layout helpers of build_report_2026_11_08.py; numbers are read from
the saved results in ../backbone_20261108.
"""
import json, collections
from pathlib import Path
import build_report_2026_11_08 as base
from build_report_2026_11_08 import P, bullets, table, callout, figure, Spacer, PageBreak, KeepTogether, SimpleDocTemplate, A4, mm, CONTENT_W

base.DATE = '11 November 2026'
HERE = Path(__file__).resolve().parent
BB = HERE.parent / 'backbone_20261108'
OUTPUT = HERE.parent.parent.parent / 'reports' / 'daily' / 'Report_2026_11_11.pdf'
CASES = ['nominal', 'ropeEA80pct', 'free1500mm', 'E75', 'payload550g']
LABEL = {'nominal': 'Nominal', 'ropeEA80pct': 'Rope EA -20%', 'free1500mm': 'Free rope 1.5 m', 'E75': 'Rod E 75 GPa', 'payload550g': 'Head 550 g'}


def load(folder, case):
    s = json.loads((BB / folder / f'{case}_summary.json').read_text())
    rows = [q for q in json.loads((BB / folder / f'{case}.json').read_text()) if q['status'] == 'solved']
    reasons = collections.Counter()
    for q in rows:
        if q['checks_pass']:
            continue
        st = q['phase'] == 'straighten'
        if q['min_tension_n'] < .95: reasons['tension'] += 1
        if not q['stable']: reasons['unstable'] += 1
        if q['clearance_margin_mm'] < 5: reasons['clearance'] += 1
        if not st and abs(q['yaw_error_deg']) > 1: reasons['yaw'] += 1
        if not st and abs(q['elevation_deg'] - 20) > 5: reasons['elevation'] += 1
    prefix = {}
    for leg in ('right_out', 'left_out'):
        m = 0
        for q in [q for q in rows if q['phase'] == leg]:
            if not q['checks_pass']:
                break
            m = abs(q['target_yaw_deg'])
        prefix[leg] = m
    return s, reasons, prefix


def why(reasons):
    if not reasons:
        return 'none'
    names = dict(tension='rope below 0.95 N', unstable='unstable', clearance='clearance', yaw='yaw error > 1 deg', elevation='elevation error > 5 deg')
    return ', '.join(f'{names[k]} ({v})' for k, v in reasons.most_common())


def build():
    old = {c: load('length_cycle_results', c) for c in CASES}
    new = {c: load('length_cycle_results_pre3', c) for c in CASES}
    five = {c: load('length_cycle_results_pre5', c) for c in CASES}
    st3 = json.loads((BB / 'results' / 'startup_niti18_E40_p20_pre3.json').read_text())
    n3 = new['nominal'][0]
    story = []

    # ---------------- Page 1
    story += [P('ASRC Fuel Tank Robot Daily Report', 'title'),
              P('Model data, prototype files and the round-trip cycle with 3 N pretension, 11 November 2026', 'subtitle'),
              P('Today started from the team\'s new length-controlled round-trip study and the design limitation list on main. In that study, no scenario '
                'passed every check: the nominal cycle had an unstable startup and rope tension dipping to 0.71 N. Today\'s work kept the model parameters '
                'unchanged and fixed the rope-length commands.'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        '<b>Reviewed the newest results.</b> Round-trip cycle (straighten, insert, sweep right and back, sweep left and back, withdraw) and the design '
        'limitations. The failures came from the commands (pretension margin, startup) and from open-loop calibration, not from the geometry.',
        '<b>Model data sheet.</b> All model inputs exported from the code: continuous 96 mm modules with no pin joint, one 1.8 mm NiTi rod along the full '
        'length of each M module, module mass, EA, EI and torsion, rope, winch, tank and numerical settings (model_data/MODEL_DATA.md, JSON and CSV).',
        '<b>Prototype files marked.</b> The moving_prototype/full_length files (84 mm shells, 12 mm pin joints, separate rods with a free joint) do not '
        'match the design and are marked to be ignored. Nothing in them was changed apart from the notice.',
        '<b>Stable startup.</b> The head is raised from natural sag (minus 57 degrees, all ropes at 3 N) to 20 degrees through held states with every rope at 3 N or more. '
        f"All {len(st3)} states are stable (peak rope {max(q['peak_n'] for q in st3):.1f} N).",
        f"<b>Round trip with 3 N pretension.</b> Same parameters, new commands. The nominal cycle now passes every check: {n3['failed_checks']} of {n3['states']} "
        f"samples fail (11 November: {old['nominal'][0]['failed_checks']} of {old['nominal'][0]['states']}). The rope EA minus 20% case also passes. The other three "
        'sensitivity cases fail only on open-loop calibration.',
    ])
    rows = [['Case (same open-loop commands)', '11 Nov: 1 N, payout start', '11 Nov: 3 N, stable startup', 'Remaining failure type']]
    for c in CASES:
        so, ro, _ = old[c]; sn, rn, pn = new[c]
        rows.append([LABEL[c], f"{so['failed_checks']} of {so['states']} fail",
                     f"<b>{sn['failed_checks']} of {sn['states']} fail</b>" + (f" (clean to {pn['right_out']:.0f} deg)" if sn['failed_checks'] else ''),
                     why(rn)])
    story += [Spacer(1, 4), table(rows, [.2, .22, .28, .3], bold_first_col=True), Spacer(1, 8),
              callout('Decisions from today',
                      'Use a 3 N minimum on every rope and the held-state startup. Do not raise the floor to 5 N without finer pose spacing. '
                      'Treat the remaining failures as a calibration and feedback problem: add head-angle and rope-tension feedback, or recompute '
                      'commands from measured stiffness, head mass and rope data. Ignore the full_length prototype files.')]
    story.append(PageBreak())

    # ---------------- Page 2: method + nominal
    story += [P('Round trip with 3 N pretension and a stable startup', 'h1'),
              P('Model parameters are unchanged from the data sheet: U4+M2, continuous 96 mm modules, full-length 1.8 mm NiTi rod at E 40 GPa, 500 g head, '
                'PA6 ropes with 1 m free length, 20 degree installation, anchors [4,5,6], 8 cells per module. The cycle script and acceptance checks are the team\'s '
                'from this morning; only the rope-length commands are new.')]
    story += bullets([
        '<b>Startup (startup_sweep.py).</b> Start outside the tank (clamp s = minus 750 mm) in natural sag with every rope at 3 N. Raise the held head elevation '
        'in 2.5 degree steps to 20 degrees, minimising the largest rope force with all ropes at 3 N or more; every state is checked for stability, geometry, '
        'strain and elevation on the 8-cell mesh.',
        '<b>Yaw sweep (min_force_sweep.py).</b> Minimum-force poses every 5 degrees from 0 to 175 degrees with the head held at 20 degrees and every rope at '
        '3 N or more, starting from the startup end state.',
        '<b>Cycle (length_cycle.py).</b> Rope lengths of these states drive all 12 winches; each step is solved from the previous state. Acceptance: '
        'rope 0.95 to 250 N, stable, tank clearance at least 5 mm after a 1.5 mm allowance, yaw error at most 1 degree, elevation 20 plus or minus 5 degrees.',
    ])
    story += [table([['Nominal cycle, 3 N', 'Result'],
                     ['Samples / failures', f"{n3['states']} / {n3['failed_checks']}"],
                     ['Yaw reached with all checks passing', f"0 to 175 deg, right and left"],
                     ['Minimum / peak rope tension', f"{n3['minimum_tension_n']:.2f} N / {n3['peak_tension_n']:.1f} N"],
                     ['Minimum stability eigenvalue', f"{n3['minimum_eigenvalue']:.3f} (11 Nov: {old['nominal'][0]['minimum_eigenvalue']:.3f}, unstable)"],
                     ['Minimum tank clearance', f"{n3['minimum_clearance_mm']:.1f} mm ({n3['minimum_clearance_mm'] - 1.5:.1f} mm after allowance)"],
                     ['Largest yaw / elevation error', f"{n3['maximum_yaw_error_deg']:.2f} deg / {n3['maximum_elevation_error_deg']:.2f} deg"],
                     ['Head return error at zero yaw', f"{n3.get('return_head_error_mm', 0):.4f} mm"]],
                    [.45, .55], bold_first_col=True),
              Spacer(1, 6),
              figure(BB / 'length_cycle_results_pre3' / 'cycle_comparison.png',
                     'Figure 1  Round trip with 3 N pretension, all five cases: yaw, elevation, tank clearance, peak and minimum rope force, stability. '
                     'Red dashed lines are acceptance limits.', width=CONTENT_W * .5)]
    story.append(PageBreak())

    # ---------------- Page 3: sensitivity, 5 N, limits, next
    story += [P('Sensitivity cases and the 5 N comparison', 'h1')]
    rows = [['Case', '3 N: failures', 'Min rope N', 'Max yaw / elev error, deg', 'Clean outbound yaw', '5 N: failures']]
    for c in CASES:
        sn, rn, pn = new[c]; s5 = five[c][0]
        rows.append([LABEL[c], str(sn['failed_checks']), f"{sn['minimum_tension_n']:.2f}", f"{sn['maximum_yaw_error_deg']:.1f} / {sn['maximum_elevation_error_deg']:.1f}",
                     f"{pn['right_out']:.0f} deg", str(s5['failed_checks'])])
    story += [table(rows, [.18, .13, .13, .22, .16, .18], bold_first_col=True), Spacer(1, 4)]
    story += bullets([
        '<b>No case has an unstable state, and the startup is stable in all five.</b> The startup and stability problems of the original cycle are removed.',
        '<b>Remaining failures are open-loop calibration.</b> A stiffer rod or heavier head moves the head off target (up to 6 to 9 degrees). A longer free rope '
        'stretches less for the same commands, so tension drops below 0.95 N, mainly during insertion and withdrawal. More pretension does not fix these; '
        'feedback or recalibrated commands do.',
        '<b>5 N is worse than 3 N.</b> The 5 N pose sequence re-allocates 13.4 N between the 50 and 55 degree poses, and length interpolation cannot follow it: '
        'all 48 nominal failures lie between 51.9 and 53.9 degrees. The 3 N sequence changes at most 5.8 N between poses. 3 N is the recommended floor.',
        '<b>Known imperfection.</b> During insertion and withdrawal the head sits at about 17 degrees, not 20, because the 0 degree pose of the 3 N sweep was '
        'accepted on the fine mesh within the plus or minus 5 degree band. It is inside the acceptance limit; requiring exact elevation on the fine mesh would remove it.',
    ])
    story += [P('Limitations', 'h1')]
    story += bullets([
        'Quasi-static, frictionless model: no dynamics, rope friction, winch backlash, NiTi hysteresis or fatigue. Rod properties are calculated, not measured.',
        'The head is a 500 g point mass with a 63 mm envelope; actual head CAD and external cables are not included. Withdrawal is rigid translation of the front.',
        'Sensitivity cases replay identical commands for assumed parameter changes; they are not measured probabilities.',
    ])
    story += [P('Next steps', 'h1'),
              table([['Priority', 'Task', 'Purpose'],
                     ['1', 'Closed-loop cycle simulation', 'Correct rope lengths from head angle and rope tension (sensitivity matrix from 10 Nov); re-run the 75 GPa, 550 g and 1.5 m cases to within 1 deg and 0.95 N'],
                     ['2', 'Exact elevation at every pose', 'Tighten the 8-cell acceptance of the yaw-sweep poses so insertion holds 20 deg'],
                     ['3', 'Build and test the backbone M module', 'Continuous 96 mm module with full-length rod: EA, EI, buckling, end-joint slip; replace assumed values'],
                     ['4', 'Rope and winch calibration', 'Measured rope EA, free length and friction; command recalibration'],
                     ['5', 'Head CAD, entry, storage, rear mechanism', 'As in the design limitation list']],
                    [.1, .32, .58]),
              Spacer(1, 6),
              P('Scripts and data: ASRC_kevin/telescopic_planar_study/backbone_20261108 (README section 10; startup_sweep.py, min_force_sweep.py --seed-startup, '
                'length_cycle.py --source/--startup/--out, summarize_cycle_run.py; results in length_cycle_results_pre3 and length_cycle_results_pre5; '
                'model_data/MODEL_DATA.md). This report is generated by ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_11.py.', 'caption')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Daily Report, 11 November 2026', author='ASRC')
    doc.build(story, onFirstPage=base.on_page, onLaterPages=base.on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
