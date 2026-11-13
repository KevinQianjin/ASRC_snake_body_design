"""Build reports/daily/Report_2026_11_13.pdf: daily report for 13 November 2026.

Uses the layout helpers of build_report_2026_11_08.py. Numbers are read from the saved
results of the lane study (simulations/u4m2/lanes_20261113), the shared-hole baseline
(simulations/u4m2/backbone_20261108) and the CAD check files (cad/lanes_u4m2).
"""
import json
from pathlib import Path
import build_report_2026_11_08 as base
from build_report_2026_11_08 import P, bullets, table, callout, figure, Spacer, PageBreak, KeepTogether, SimpleDocTemplate, A4, mm, CONTENT_W

base.DATE = '13 November 2026'
HERE = Path(__file__).resolve().parent
BB = base.BB
LN = base.ROOT / 'simulations' / 'u4m2' / 'lanes_20261113'
CAD = base.ROOT / 'cad' / 'lanes_u4m2'
OUTPUT = HERE.parent / 'daily' / 'Report_2026_11_13.pdf'
CASES = ['nominal', 'E75', 'payload550g', 'free1500mm', 'ropeEA80pct']
LABEL = {'nominal': 'Nominal', 'E75': 'Rod E 75 GPa', 'payload550g': 'Head 550 g', 'free1500mm': 'Free rope 1.5 m', 'ropeEA80pct': 'Rope EA -20%'}
TAG = 'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1'
J = lambda p: json.loads(Path(p).read_text())


def moving(trace):
    tr = [t for t in trace if t['kind'] != 'start']
    errs = [max(abs(t['yaw_error_deg']), abs(t['elevation_error_deg'])) for t in tr]
    return sum(e > 1 for e in errs), max(errs)


def build():
    st_sh, st_ln = J(BB / 'results/startup_niti18_E40_p20_pre3.json'), J(LN / 'results_lanes/startup_niti18_E40_p20_pre3.json')
    sw_sh = [x for x in J(BB / f'results/{TAG}.json') if 'peak_n' in x]
    sw_ln = [x for x in J(LN / f'results_lanes/{TAG}.json') if 'peak_n' in x]
    ref_sh, ref_ln = J(BB / 'length_cycle_results_pre3_tol1/nominal_summary.json'), J(LN / 'length_cycle_results_lanes/nominal_summary.json')
    cl_sh = {c: J(BB / f'closed_loop_v3_results/{c}_summary.json') for c in CASES}
    cl_ln = {c: J(LN / f'closed_loop_lanes_results/{c}_summary.json') for c in CASES}
    mv_sh = moving(J(BB / 'closed_loop_v3_results/fixed_reference_only/payload550g_trace.json'))
    mv_ln = moving(J(LN / 'closed_loop_lanes_results/payload550g_trace.json'))
    chords = J(LN / 'results_lanes/rope_chord_by_yaw.json')
    design, check, spring = J(CAD / 'lane_design.json'), J(CAD / 'assembly_check.json'), J(CAD / 'spring_strip.json')
    pk = lambda L: max(x['peak_n'] for x in L)
    eig = lambda L, k: min(x[k] for x in L)
    m_clear = [v for k, v in design['M_lane_clearance_mm'].items() if k[0] in 'BC']
    u_clear = list(design['U_lane_clearance_mm'].values())
    by = {c['yaw_deg']: c for c in chords}
    story = []

    # ---------------- Page 1: summary
    story += [P('ASRC Fuel Tank Robot Daily Report', 'title'),
              P('Separate rope lanes, lane-routed 3D modules and a complete build package, 13 November 2026', 'subtitle'),
              P('Until today the model routed all three rope sets through the same four holes at 24 mm, which three 2 mm ropes cannot share. '
                'Today each set got its own lane, the whole simulation pipeline was re-run with it, and the 3D model was renewed to match: '
                'lane holes, rope anchors, a backbone hole sized to the 1.8 mm rod, module joints, end parts and a step-by-step build guide.'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        f"<b>Rope lanes (radial spread).</b> Set A (anchored at U4) at 21 mm, B (M5) at 24 mm, C (M6) at 27 mm, on the same up/right/down/left rays. "
        f"Startup, yaw sweep, reference round trip and closed loop were re-run. Everything passes; peak rope force falls from {pk(sw_sh):.1f} to {pk(sw_ln):.1f} N "
        f"and the smallest stability margin rises from {eig(sw_sh, 'fixed_winch_eig'):.3f} to {eig(sw_ln, 'fixed_winch_eig'):.3f}.",
        '<b>Rope-path limit found.</b> Ropes are guided only at the end disks, so inside a bent module each rope is a straight chord. '
        f"M5 bends {by[0.0]['M5']['bend_deg']:.0f} deg at the 0 deg hold but up to {max(c['M5']['bend_deg'] for c in chords):.0f} deg when steering; "
        f"beyond about 15 deg yaw its ropes leave the strip-free corridor ({min(m_clear):.1f}-{max(m_clear):.1f} mm) and would rub the M spring strips.",
        '<b>3D model renewed</b> (cad/lanes_u4m2). The STEP spring strips lie exactly on the rope rays, so the bodies were re-clocked (U -45 deg, M -22.5 deg). '
        'Solid end disks keep only working holes; Ø1.85 mm backbone bore with 15 mm grip per end; rope anchors; joint holes.',
        '<b>Build package.</b> Base interface and head adapter added; spring pockets, dowel holes and rope-A anchors corrected; an automatic whole-assembly '
        f"check passes ({'all pass' if check['all_pass'] else 'FAILS'}); BUILD_GUIDE.md covers printing to tensioning.",
        '<b>Repository.</b> The lane simulation moved to its own folder, simulations/u4m2/lanes_20261113, reusing the solver in backbone_20261108 unchanged.',
    ])
    rows = [['Check (3 N pretension, 20 deg)', 'Shared 24 mm holes', 'Lanes 21/24/27 mm'],
            ['Startup, 32 states', f"all pass, peak {max(x['peak_n'] for x in st_sh):.1f} N", f"all pass, peak {max(x['peak_n'] for x in st_ln):.1f} N"],
            [f'Yaw holds 0-175 deg ({len(sw_ln)} poses)', f"peak {pk(sw_sh):.1f} N, min eig {eig(sw_sh, 'fixed_winch_eig'):.3f}",
             f"all pass, peak {pk(sw_ln):.1f} N, min eig {eig(sw_ln, 'fixed_winch_eig'):.3f}"],
            ['Reference round trip', f"all pass, peak {ref_sh['peak_tension_n']:.1f} N, clearance {ref_sh['minimum_clearance_mm']:.1f} mm",
             f"all pass ({ref_ln['states']} states), peak {ref_ln['peak_tension_n']:.1f} N, clearance {ref_ln['minimum_clearance_mm']:.1f} mm"],
            ['Closed loop, 5 cases, settled samples', 'all pass', 'all pass'],
            ['Head 550 g, states above 1 deg while moving', f'{mv_sh[0]} (max {mv_sh[1]:.2f} deg)', f'{mv_ln[0]} (max {mv_ln[1]:.2f} deg)']]
    story += [Spacer(1, 4), table(rows, [.34, .33, .33], bold_first_col=True), Spacer(1, 8),
              callout('Decisions from today',
                      'Adopt separate rope lanes (A 21, B 24, C 27 mm) and the re-clocked, lane-routed modules as the current design. '
                      'Limit first hardware tests to plus or minus 15 deg yaw until rope guides are added inside M5/M6 and modelled. '
                      'Build from cad/lanes_u4m2/BUILD_GUIDE.md.')]
    story.append(PageBreak())

    # ---------------- Page 2: simulation
    story += [P('Simulation with separate rope lanes', 'h1'),
              P('lanes.py gives every anchor set its own rope offset inside a copy of the pinned spatial kernel; the pinned files are not changed. '
                'With all radii at 24 mm it reproduces the pinned kernel to 1e-14 (energy) and 1e-16 (gradient); with lanes, the finite-difference gradient '
                'error is 2e-8. lanes_study.py then runs the unchanged pipeline (startup, minimum-force yaw sweep, reference round trip, controller gains, '
                'closed loop) with the lanes installed.')]
    rows = [['Case', 'Shared holes v3: angle / tension (settled)', 'Lanes: angle / tension (settled)', 'Lanes: failed checks']]
    for c in CASES:
        a, b = cl_sh[c]['settled'], cl_ln[c]['settled']
        rows.append([LABEL[c], f"{max(a['maximum_yaw_error_deg'], a['maximum_elevation_error_deg']):.2f} deg / {a['minimum_tension_n']:.2f}-{a['peak_tension_n']:.1f} N",
                     f"{max(b['maximum_yaw_error_deg'], b['maximum_elevation_error_deg']):.2f} deg / {b['minimum_tension_n']:.2f}-{b['peak_tension_n']:.1f} N",
                     str(b['failed_checks'])])
    story += [table(rows, [.18, .3, .3, .22], bold_first_col=True),
              P('Closed loop with gains rebuilt from the lane reference, no correction during moves. Angle = largest yaw or elevation error of a settled sample.', 'caption'),
              figure(LN / 'results_lanes' / 'lanes_overview.png',
                     'Figure 1  Left: peak and mean rope tension of the 20 deg yaw holds, shared holes (red) and lanes (blue). Right: largest offset of a straight rope '
                     'from its lane inside M5 and M6, against the corridor clearance of the re-clocked M body (green), and the M5 bend angle.')]
    story += bullets([
        f"<b>Lanes help slightly everywhere.</b> Peak tensions are about 1 N lower in the holds and 1-3 N lower in closed loop (the 75 GPa case is unchanged). "
        f"The 550 g head's moving error at 174-178 deg yaw shrinks from {mv_sh[0]} to {mv_ln[0]} states above 1 deg (max {mv_sh[1]:.1f} to {mv_ln[1]:.1f} deg) but does not vanish; "
        'online gain updating remains the fix.',
        f"<b>Rope chords.</b> U modules bend at most 7.3 deg and their ropes stay within 0.2 mm of the lane. M5 rope offset: {by[0.0]['M5']['max_chord_offset_mm']:.1f} mm at the 0 deg hold, "
        f"{by[15.0]['M5']['max_chord_offset_mm']:.1f} mm at 15 deg, {by[25.0]['M5']['max_chord_offset_mm']:.0f} mm at 25 deg and "
        f"{max(c['M5']['max_chord_offset_mm'] for c in chords):.0f} mm at 175 deg. The shared-hole layout has the same problem. Rod strain at the largest bend is about 1.7%.",
    ])
    story.append(PageBreak())

    # ---------------- Page 3: CAD
    story += [P('Renewed 3D model: lane-routed modules', 'h1'),
              P('Built by cad/lanes_u4m2/build_lane_modules.py from the STEP-derived meshes, which stay untouched.')]
    story += bullets([
        f"<b>Re-clocking was required.</b> In both STEP bodies the spring strips lie on the 0/90/180/270 deg rays, where the ropes must run: without it every lane "
        f"passes through material. Rotating U by -45 deg and M by -22.5 deg gives every straight rope {min(u_clear + m_clear):.1f}-{max(u_clear):.1f} mm of clearance, "
        'and puts U\'s stiff leaf-spring direction vertical, as the simulation assumes.',
        '<b>Solid end disks.</b> Every 3 mm end disk is a full round plate; notches, strip-root relief slots, U diagonal slots and the unused U centre hole are filled. '
        'Left: 12 rope holes (2.5 mm, only for sets that still pass), 4 joint holes, U leaf-spring pockets, M backbone bore.',
        f"<b>Backbone hole matches the rod.</b> M5/M6: Ø{design['rod_bore_d']} mm bore for the Ø{design['rod_d']} mm NiTi rod, with a 6 mm sleeve inside each end disk "
        f"giving {design['rod_support_length_per_end_mm']:.0f} mm of grip per end, so the rod is clamped in rotation and bends with the module.",
        '<b>Rope anchors.</b> With 3 mm between lanes a crimp cannot sit on a lane. Each rope loops through a groove on its anchor disk\'s outer face and back down a '
        'return hole, and is crimped on the inside: B and C loop sideways (5 mm), A loops inward (3.5 mm) to stay clear of the U4 leaf springs.',
        '<b>Joints.</b> Rigid disk-to-disk: 2 dowel pins (left/right) set the clocking so every rope hole lines up, 2 M2 screws (up/down) clamp, nuts inside the module.',
    ])
    story += [figure(CAD / 'lane_disks.png', 'Figure 2  End disks: U1-U3, U4 distal (A anchors), M5 distal (B anchors), M6 distal (C anchors). Dots: lane centres A 21 / B 24 / C 27 mm.')]
    story.append(PageBreak())

    # ---------------- Page 4: build package
    story += [P('Build package and assembly check', 'h1')]
    parts = check['parts']
    rows = [['Part', 'Qty', 'Volume, cm3', 'Role']]
    for f, q, role in (('base_interface', 1, '20 mm block on the rear beam; guides all 12 ropes into U1; 4 x M3 inserts'),
                       ('U_lane_pass.stl', 3, 'U1-U3'), ('U4_lane_anchorA.stl', 1, 'U4, anchors rope set A'),
                       ('M5_lane_anchorB.stl', 1, 'M5, anchors set B, rod bore'), ('M6_lane_anchorC.stl', 1, 'M6, anchors set C, rod bore'),
                       ('head_adapter', 1, '6 mm plate: closes the C anchors, rod-end relief, 4 x M3 inserts for the head')):
        rows.append([f.replace('.stl', ''), str(q), f"{parts[f]['volume_mm3'] / 1000:.1f}", role])
    story += [table(rows, [.25, .07, .13, .55], bold_first_col=True), Spacer(1, 4)]
    story += bullets([
        f"<b>Purchased:</b> 16 NiTi leaf-spring strips about 6.0 x 1.1 x {spring['length_mm']:.0f} mm; one Ø1.8 x 192 mm NiTi rod; 12 lengths of Ø2 mm PA6 "
        'monofilament (1.51 / 1.60 / 1.70 m for A / B / C); 12 crimp sleeves; 14 Ø2 x 8 mm dowels; 14 M2 x 10 screws and nuts; 8 M3 heat-set inserts; epoxy.',
        '<b>Corrections made while writing the guide:</b> leaf-spring pockets re-opened (through on the proximal disk so the strip slides in, blind on the distal disk); '
        'dowel holes made Ø1.9 pilots for reaming (a Ø2 pin in the Ø2.2 screw hole would not locate); rope A\'s anchor turned inward (a sideways block came within '
        '0.3 mm of the U4 leaf springs); hole chamfers reduced so a wall stays between lanes at the 3 mm pitch.',
    ])
    rows = [['Automatic check (build_ends_and_check.py)', 'Result']]
    rows.append(['7 joints: 4 joint holes open and aligned', 'pass' if all(j['joint_holes_open_and_aligned'] for j in check['joints']) else 'FAIL'])
    rows.append(['12 ropes: clear path base to anchor, groove, return hole, no hole beyond', 'pass' if all(all(v.values()) for v in check['ropes'].values()) else 'FAIL'])
    rows.append(['Rod: bore open through M5 and M6, U4 centre solid', 'pass' if all(v for v in check['rod'].values() if isinstance(v, bool)) else 'FAIL'])
    rows.append(['Leaf springs shifted 1.5 mm: no contact; M2 nut fits at every joint hole', 'pass' if all(v == 0 for v in check['clearance_mm3'].values()) else 'FAIL'])
    rows.append(['Largest radius of any part', f"{max(check['envelope_mm'].values()):.2f} mm (same as the STEP bodies)"])
    story += [table(rows, [.7, .3], bold_first_col=True), Spacer(1, 4),
              figure(CAD / 'end_parts.png', 'Figure 3  Base interface (front and rear faces) and head adapter (rear and front faces).')]
    story.append(PageBreak())

    # ---------------- Page 5
    story += [P('Limitations', 'h1')]
    story += bullets([
        'Ropes are modelled as straight chords between end disks. Results beyond about 15 deg yaw assume rope paths the current M body cannot give without intermediate guides.',
        'The CAD is checked geometrically only, in the straight pose. Printed strength (0.5 mm walls between rope holes, anchor bridges), rope friction and the '
        'stiffness of the re-clocked bodies with filled disk slots are untested.',
        'The printed parts are heavier than the model: M5/M6 about +5 g each, U +1.3 g each, plus about 1.3 g of joint hardware per joint; the head adapter (17 g) '
        'counts toward the 500 g head. The simulation has not been re-run with these masses.',
        'Quasi-static model with ideal measurements; the five closed-loop cases were used during development and are not an independent validation set.',
        'No wiring path through the modules; base and head mounting patterns are placeholders.',
    ])
    story += [P('Next steps', 'h1'),
              table([['Priority', 'Task', 'Purpose'],
                     ['1', 'Rope guides in M5/M6', 'Add intermediate guides and route the ropes through them in the model (per-cell chords) to allow steering beyond 15 deg yaw'],
                     ['2', 'Update masses, re-run', 'Use the printed part masses and joint hardware in the model; repeat the lane pipeline'],
                     ['3', 'Online gain update', 'Remove the remaining 550 g large-yaw transient'],
                     ['4', 'Print and test', 'One U and one M module: stiffness vs model, 0.5 mm walls, anchor at 50 N, rope friction (BUILD_GUIDE.md section 10)'],
                     ['5', 'Interfaces', 'Real rear-beam and head mounting patterns; head wiring path']],
                    [.1, .28, .62]),
              Spacer(1, 6),
              P('Scripts and data: simulations/u4m2/lanes_20261113 (lanes.py, lanes_study.py, rope_chord_check.py, lanes_figures.py, README); '
                'cad/lanes_u4m2 (build_lane_modules.py, build_ends_and_check.py, plot_disks.py, BUILD_GUIDE.md, README). '
                'This report is generated by reports/builders/build_report_2026_11_13.py.', 'caption')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Daily Report, 13 November 2026', author='ASRC')
    doc.build(story, onFirstPage=base.on_page, onLaterPages=base.on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
