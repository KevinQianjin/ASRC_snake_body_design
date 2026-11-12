"""Build Report_2026_11_08.pdf (reports/daily/) from the 2026-11-08 study results.

Numbers in the report are read from the saved result files where practical;
fixed text summarises the study READMEs. Run from anywhere:
    python build_report_2026_11_08.py
"""
import json
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether)

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parent.parent
SWEEP = STUDY / 'm_axial_sweep_20261108'
BB = STUDY / 'backbone_20261108'
OUTPUT = ROOT / 'reports' / 'daily' / 'Report_2026_11_08.pdf'
DATE = '8 November 2026'

FONT_DIR = Path(os.environ.get('ASRC_REPORT_FONT_DIR', '/usr/share/fonts/truetype/crosextra'))
pdfmetrics.registerFont(TTFont('Carlito', str(FONT_DIR / 'Carlito-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Carlito-Bold', str(FONT_DIR / 'Carlito-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Carlito-Italic', str(FONT_DIR / 'Carlito-Italic.ttf')))
pdfmetrics.registerFont(TTFont('Carlito-BoldItalic', str(FONT_DIR / 'Carlito-BoldItalic.ttf')))
pdfmetrics.registerFontFamily('Carlito', normal='Carlito', bold='Carlito-Bold', italic='Carlito-Italic', boldItalic='Carlito-BoldItalic')

NAVY = colors.HexColor('#24324a')
INK = colors.HexColor('#1f1f1d')
MUTED = colors.HexColor('#5f5e5a')
RULE = colors.HexColor('#c9c8c3')
ZEBRA = colors.HexColor('#f4f3f0')

S = dict(
    title=ParagraphStyle('title', fontName='Carlito-Bold', fontSize=22, leading=26, textColor=INK, spaceAfter=4),
    subtitle=ParagraphStyle('subtitle', fontName='Carlito-Italic', fontSize=11, leading=14, textColor=MUTED, spaceAfter=8),
    h1=ParagraphStyle('h1', fontName='Carlito-Bold', fontSize=15, leading=19, textColor=INK, spaceBefore=4, spaceAfter=6),
    h2=ParagraphStyle('h2', fontName='Carlito-Bold', fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=4),
    body=ParagraphStyle('body', fontName='Carlito', fontSize=10, leading=13.4, textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    bullet=ParagraphStyle('bullet', fontName='Carlito', fontSize=10, leading=13.4, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=3),
    caption=ParagraphStyle('caption', fontName='Carlito-Italic', fontSize=9, leading=11.5, textColor=MUTED, spaceBefore=3, spaceAfter=8),
    cell=ParagraphStyle('cell', fontName='Carlito', fontSize=9, leading=11, textColor=INK),
    cellb=ParagraphStyle('cellb', fontName='Carlito-Bold', fontSize=9, leading=11, textColor=INK),
    head=ParagraphStyle('head', fontName='Carlito-Bold', fontSize=9, leading=11, textColor=colors.white),
    box=ParagraphStyle('box', fontName='Carlito', fontSize=10, leading=13.4, textColor=INK),
)
CONTENT_W = A4[0] - 40 * mm


def P(text, style='body'):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(t, S['bullet'], bulletText='•') for t in items]


def table(rows, widths, bold_first_col=False, align_right_from=None):
    data = [[Paragraph(str(c), S['head']) for c in rows[0]]]
    for r in rows[1:]:
        data.append([Paragraph(str(c), S['cellb'] if (bold_first_col and j == 0) else S['cell']) for j, c in enumerate(r)])
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1)
    style = [('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
             ('LINEBELOW', (0, 1), (-1, -1), .4, RULE), ('TOPPADDING', (0, 0), (-1, -1), 3.5),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)]
    for i in range(2, len(data), 2):
        style.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(style))
    return t


def callout(title, text):
    t = Table([[Paragraph(f'<b>{title}</b><br/>{text}', S['box'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), .8, NAVY), ('LINEBEFORE', (0, 0), (0, -1), 4, NAVY),
                           ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    return t


def figure(path, caption, width=CONTENT_W):
    img = Image(str(path))
    img.drawHeight = img.drawHeight * width / img.drawWidth
    img.drawWidth = width
    return KeepTogether([img, P(caption, 'caption')])


def on_page(c, doc):
    c.saveState()
    c.setFont('Carlito', 8); c.setFillColor(MUTED)
    c.drawString(20 * mm, A4[1] - 12 * mm, 'ASRC  |  FUEL TANK INSPECTION ROBOT')
    c.setStrokeColor(RULE); c.setLineWidth(.4); c.line(20 * mm, A4[1] - 13.5 * mm, A4[0] - 20 * mm, A4[1] - 13.5 * mm)
    c.drawRightString(A4[0] - 24 * mm, 12 * mm, f'Simulation review  |  {DATE}  |')
    c.setFont('Carlito-Bold', 11); c.setFillColor(INK)
    c.drawRightString(A4[0] - 20 * mm, 12 * mm, str(doc.page))
    c.restoreState()


def load():
    steer = json.loads((BB / 'results' / 'steering_summary_8cell.json').read_text())
    planar = json.loads((BB / 'results' / 'planar_summary.json').read_text())
    verify = json.loads((SWEEP / 'results' / 'verify_16cell.json').read_text())
    return steer, planar, verify


def fmt_t(sets):
    return ' ; '.join('[' + ', '.join(f'{x:.1f}' for x in s) + ']' for s in sets)


def build():
    steer, planar, verify = load()
    sd = {(r['variant'], r['pitch_deg'], r['direction']): r for r in steer}
    pl = {(r['configuration'], r['variant'], round(r['pitch_deg'])): r for r in planar}
    story = []

    # ---------------- Page 1: summary
    story += [P('ASRC Fuel Tank Robot Simulation Review', 'title'),
              P(f'M module backbone studies, {DATE}', 'subtitle'),
              P('The 6 November review identified two blocking problems for the 63 mm PA12 and NiTi front: active straightening '
                'needed far more than the 5% axial strain diagnostic, and no low-strain configuration could hold the 500 g head near the '
                '20 degree working elevation. Today\'s work traced both to the M module and tested a specific fix in simulation.'),
              P('Summary of today\'s work', 'h2')]
    story += bullets([
        '<b>M stiffness requirement sweep.</b> Scaling only the M module EA and EI for U4 plus M2 shows that axial stiffness alone '
        'leaves a 7.1 degree tangent error floor, set by M bending stiffness between anchor disks. The first passing combination is '
        'EA x5 (about 830 N) with EI x1.25 (about 0.055 N m²), anchors [4,5,6], confirmed at 16 cells per module.',
        '<b>NiTi backbone concept.</b> A central 1.8 mm NiTi rod in each M module meets both requirements: EA rises to about 102 to 191 kN '
        'and EI to 0.065 to 0.083 N m² (E 40 to 75 GPa). Rod mass, 1.58 g per module, is included.',
        '<b>Straightening with the backbone.</b> U4 plus M2 passes every straightness check at 15, 20 and 25 degrees, with about 1 to 2 mm '
        'offset and about 0.1% strain. U6 plus M3 and U8 plus M4 still fail with three or fewer anchor sets, including an exhaustive layout search.',
        '<b>Steering with the backbone.</b> At 20 degrees, U4 plus M2 reaches the 180 degree yaw search cap with world head elevation held within '
        '20 plus or minus 5 degrees, confirmed at 8 cells per module. At 15 degrees, 165 degrees is confirmed. The 6 November design found no such state.',
        '<b>Test plan.</b> A build and test plan for the backbone M module defines specimens, guide spacing, tests and pass criteria.',
    ])
    story += [Spacer(1, 4),
              table([['Item', '6 November baseline', 'With 1.8 mm NiTi backbone (simulation)'],
                     ['U4 plus M2 straightening at 20 deg, at or below 5% strain', '94.7 mm offset, 61.3 deg, fails', '1.7 mm offset, 4.0 deg, 0.10% strain, passes'],
                     ['Same, 15 and 25 deg', 'Fails', 'Passes at both'],
                     ['Yaw with head held at 20 plus or minus 5 deg', 'No solution found', '180 deg (search cap), 46 to 98 N peak tendon'],
                     ['U6 plus M3, U8 plus M4 straightening', 'Fail', 'Still fail with up to 3 anchor sets'],
                     ['Physical evidence', 'Database properties', 'Rod properties calculated only; tests not yet run']],
                    [.34, .27, .39], bold_first_col=True),
              Spacer(1, 10),
              callout('Main engineering decision',
                      'Adopt a central NiTi backbone in the M modules as the lead design for U4 plus M2, and build and test the backbone M module '
                      'before further simulation refinement. Keep U4 plus M2 as the only development length; longer fronts need additional anchor '
                      'sets inside M or a different M design.')]
    story.append(PageBreak())

    # ---------------- Page 2: root cause, EA/EI sweep
    story += [P('Why the current M module fails', 'h1'),
              P('The supplied M module has EA 166.7 N and EI 0.0441 N m². The U module EA is about 770 times higher. Tendons that lift the head '
                'compress the M modules: at 5% strain M carries only about 8.3 N, while the head and module gravity moment needs roughly 39 N of tendon '
                'tension for U4 plus M2. This was the priority 1 problem in the 6 November review.'),
              P('M stiffness requirement sweep', 'h2'),
              P('The 6 November planar kernel was reused unchanged. Only M EA (x1 to x1000) and M EI (x1 to x5) were scaled, for U4 plus M2 at 20 degrees '
                'with the 500 g head and the same four anchor layouts, optimizer, seeds and pass criteria. The unscaled case reproduces the reported '
                '6 November result (94.68 mm at 8 cells against 94.77 mm at 16 cells). The full grid of 78 combinations runs in about 2 minutes.'),
              figure(SWEEP / 'results' / 'm_stiffness_requirement.png',
                     'Figure 1  Left: best maximum tangent error at or below 5% strain over the EA and EI grid; ticks mark combinations passing all straightness '
                     'checks. Right: loaded shapes with anchors [4,5,6].'),
              P('Raising EA alone straightens the front to about 3 mm offset, but the maximum tangent error stops at about 7.1 degrees even at EA x1000. '
                'Between anchor disks the head weight produces a bending moment that varies linearly along each 96 mm M module, while the tendons apply '
                'a constant moment over that span. The residual rotation, about ΔM L / (8 EI) = 0.44 x 0.096 / (8 x 0.044) ≈ 0.12 rad (6.9 degrees), '
                'is set by M bending stiffness and matches the solver.')]
    vrows = [['EI scale', 'EA scale', 'Offset mm (16 cell)', 'Tangent deg (16 cell)', 'Strain (16 cell)', 'All checks']]
    for v in verify:
        if 'maximum_axis_deviation_mm_16cell' not in v:
            continue
        vrows.append([f"x{v['ei_scale']:g}", f"x{v['ea_scale']:g}", f"{v['maximum_axis_deviation_mm_16cell']:.2f}",
                      f"{v['maximum_tangent_error_deg_16cell']:.2f}", f"{100*v['max_abs_axial_strain_16cell']:.2f}%",
                      'Pass' if v['all_straight_diagnostics_pass_16cell'] else 'Fail'])
    story += [KeepTogether([P('Threshold cases re-solved at 16 cells per module (anchors [4,5,6])', 'h2'),
                            table(vrows, [.13, .13, .19, .2, .17, .18])]),
              P('Every 8-cell pass or fail classification was unchanged at 16 cells; the largest tangent change was 0.09 degrees.', 'caption')]
    story.append(PageBreak())

    # ---------------- Page 3: backbone concept
    story += [P('Backbone concept and sizing', 'h1'),
              P('A central superelastic NiTi rod, bonded to the M module end disks and guided laterally inside the module, adds axial and bending '
                'stiffness in parallel with the PA12 structure. It does not change the 24 mm tendon moment arm. Two moduli bracket the uncertain '
                'NiTi phase state: 40 GPa (martensite or low-modulus) and 75 GPa (austenite).'),
              table([['Property', 'M (database)', 'M + rod, E 40 GPa', 'M + rod, E 75 GPa', 'Required (sweep)'],
                     ['EA, N', '166.7', '101,954', '191,018', '833 or more'],
                     ['EI, N m² (both planes)', '0.0441', '0.0647', '0.0828', '0.055 or more'],
                     ['Module torsion, N m/rad', '0.437', '0.599', '0.740', 'Not limiting'],
                     ['Mass per M module, g', '23.948', '25.524', '25.524', '—']],
                    [.28, .17, .19, .19, .17], bold_first_col=True),
              P('Rod diameter options', 'h2'),
              table([['Rod diameter', 'Added EA, N', 'Added EI, N m²', 'M EI scale', 'Max guide spacing for 248 N', 'Surface strain, 180 deg over 192 mm'],
                     ['1.5 mm', '71k to 133k', '0.010 to 0.019', 'x1.23 to x1.42', '20 to 27 mm', '1.2%'],
                     ['<b>1.8 mm (selected)</b>', '102k to 191k', '0.021 to 0.039', 'x1.47 to x1.88', '29 to 39 mm', '1.5%'],
                     ['2.0 mm', '126k to 236k', '0.031 to 0.059', 'x1.71 to x2.34', '35 to 48 mm', '1.6%']],
                    [.18, .15, .16, .15, .18, .18]),
              P('Ranges are for E 40 to 75 GPa. Guide spacing uses pinned Euler buckling of the rod carrying twice the 124 N sum of the passing '
                'straightening tensions.', 'caption'),
              P('Engineering consequences', 'h2')]
    story += bullets([
        '1.5 mm is marginal at the lower modulus (EI x1.23 against a x1.25 requirement). 1.8 mm passes with margin at both moduli.',
        'Intermediate rod guides are needed. A 24 mm spacing gives 353 N (E 40 GPa) and 662 N (E 75 GPa) Euler loads against a 248 N design load.',
        'Both rod ends must carry axial load into the anchor disks without slip; this joint is a new critical component.',
        'A stiffer M needs more tendon force to bend. The steering study below includes this effect.',
        'Rod end fittings and guides are not yet included in the mass. Friction, NiTi transformation hysteresis and fatigue are not modelled.',
    ])
    story.append(PageBreak())

    # ---------------- Page 4: planar straightening
    story += [P('Active straightening with the backbone', 'h1'),
              P('The 6 November planar study was repeated for all three configurations at 15, 20 and 25 degrees, with the rod EA, EI and mass added '
                'to every M module. Values are the best stable result at or below 5% strain at 8 cells per module. Pass means offset at most 10 mm, '
                'tangent error at most 5 degrees, axial projection at least 95%, strain at most 5% and local stability with 1 m of extra rope.')]
    rows = [['Configuration', 'Pitch', 'Current M', 'Rod, E 40 GPa', 'Rod, E 75 GPa']]
    def cellv(cfg, v, p):
        r = pl.get((cfg, v, p))
        if r is None:
            return 'No stable result'
        s = f"{r['maximum_axis_deviation_mm']:.1f} mm, {r['maximum_tangent_error_deg']:.1f} deg, {100*r['max_abs_axial_strain']:.2f}%"
        return ('<b>Pass</b>: ' if r['all_straight_diagnostics_pass'] else 'Fail: ') + s
    for cfg in ['U4-M2', 'U6-M3', 'U8-M4']:
        for p in [15, 20, 25]:
            rows.append([cfg.replace('-', ' plus '), f'{p} deg', cellv(cfg, 'none', p), cellv(cfg, 'niti18_E40', p), cellv(cfg, 'niti18_E75', p)])
    story += [table(rows, [.14, .08, .26, .26, .26], bold_first_col=True),
              Spacer(1, 6)]
    r20 = pl[('U4-M2', 'niti18_E40', 20)]
    story += bullets([
        f"<b>U4 plus M2 passes at every pitch and both moduli</b>, always with anchors [4,5,6]. At 20 degrees and E 40 GPa the top-rope tensions are "
        f"{', '.join(f'{x:.1f}' for x in r20['top_extra_tensions_n'])} N.",
        '<b>U6 plus M3 and U8 plus M4 do not pass.</b> Every three-set layout with one set at the head was searched at 20 degrees for both moduli '
        '(28 layouts for U6 plus M3 and 55 for U8 plus M4). The closest case, U6 plus M3 with anchors [7,8,9], reached 5.04 degrees tangent error '
        'but 24.5 mm offset. The longer M sections leave longer spans between anchor disks, which the 1.8 mm rod cannot hold straight.',
        'The no-rod column reproduces the 6 November values, for example 94.68 mm at 20 degrees for U4 plus M2.',
    ])
    story += [figure(BB / 'results' / 'backbone_results.png',
                     'Figure 2  Left: U4 plus M2 actively straightened at 20 degrees, without and with the rod. Right: steering endpoints at 20 degrees, '
                     '8 cells per module; filled markers hold world head elevation within 20 plus or minus 5 degrees.')]
    story.append(PageBreak())

    # ---------------- Page 5: steering
    story += [P('Spatial steering and loaded head recovery', 'h1'),
              P('The 6 November spatial steering study was repeated for U4 plus M2 with the backbone, using the same rod kernel, bounds and acceptance '
                'rules: 0 to 250 N per rope, coarse strain bound 4.75%, 180 degree search cap, geometry, capsule and fixed-winch stability checks. '
                'Candidates are refined from 2 to 4 to 8 cells per module, with re-optimization on the finer mesh when needed. Only states passing at '
                '8 cells are reported. Held elevation means yaw with world head elevation within base pitch plus or minus 5 degrees.')]
    rows = [['Variant', 'Pitch', 'Free yaw (elevation, peak N)', 'Yaw with held elevation (elevation, peak N)', 'Up / down']]
    for v, p, label in [('none', 20, 'Current M'), ('niti18_E40', 15, 'Rod, E 40 GPa'), ('niti18_E40', 20, 'Rod, E 40 GPa'),
                        ('niti18_E40', 25, 'Rod, E 40 GPa'), ('niti18_E75', 20, 'Rod, E 75 GPa')]:
        fr = sd[(v, p, 'right')]; lv = sd.get((v, p, 'right_level')); up = sd[(v, p, 'up')]; dn = sd[(v, p, 'down')]
        cap = lambda r: '*' if r['angle_deg'] >= 179.99 else ''
        free = f"{fr['angle_deg']:.1f}{cap(fr)} deg ({fr['world_elevation_deg']:+.1f}, {fr['peak_tension_n']:.1f} N)"
        held = 'None found' if not lv or lv.get('result', 1) is None or 'angle_deg' not in lv else \
            f"<b>{lv['angle_deg']:.0f}{cap(lv)}{'†' if lv['angle_cap_deg'] < 180 else ''} deg</b> ({lv['world_elevation_deg']:+.1f}, {lv['peak_tension_n']:.1f} N)"
        story_row = [label, f'{p} deg', free, held, f"{up['angle_deg']:.1f}{cap(up)} / {dn['angle_deg']:.1f}{cap(dn)}"]
        rows.append(story_row)
    story += [table(rows, [.16, .08, .27, .31, .18], bold_first_col=True),
              P('* Reaches the 180 degree search cap; not a demonstrated mechanical limit. † At 15 degrees no 180 degree held state was stable at 8 cells; '
                '165 degrees is the largest lower cap that passed. Up and down are projected turning angles relative to the base.', 'caption')]
    story += bullets([
        '<b>The rod resolves the loaded head recovery problem in simulation.</b> The current M finds no held-elevation state; with the rod, '
        'the head is swept through the full 180 degree search range while held near the working elevation, at well under 1% strain.',
        'Strain no longer limits the result (at most 0.62%). The active limits are now tendon force, stability and the elevation band.',
        'The no-rod control reproduces the 6 November values exactly: 179.42 degrees, minus 65.67 degrees elevation, 146.48 N.',
    ])
    rows = [['Case', 'Anchors', 'Tensions per set [up, right, down, left], N']]
    for v, p, label in [('niti18_E40', 15, 'E 40 GPa, 15 deg, 165 deg'), ('niti18_E40', 20, 'E 40 GPa, 20 deg, 180 deg'),
                        ('niti18_E40', 25, 'E 40 GPa, 25 deg, 180 deg'), ('niti18_E75', 20, 'E 75 GPa, 20 deg, 180 deg')]:
        r = sd[(v, p, 'right_level')]
        rows.append([label, str(r['anchors']), fmt_t(r['tensions_n'])])
    story += [KeepTogether([P('Tendon forces for the held-elevation endpoints', 'h2'), table(rows, [.27, .13, .60], bold_first_col=True)]),
              P('These are one allocation found by the optimizer, not minimum-force solutions. The 8-cell re-optimization maximizes angle only, so '
                'tensions can rise during refinement: at 20 degrees and E 40 GPa the coarse candidate needed about 33 N peak, the 8-cell state 98 N. '
                'The 25 degree case sits near the 250 N bound and at the edge of its elevation band. Whether intermediate postures form a continuous '
                'controllable path has not been established.', 'caption')]
    story.append(PageBreak())

    # ---------------- Page 6: verification + test plan
    story += [P('Numerical verification', 'h1')]
    story += bullets([
        'All kernels are the 6 November planar and spatial rod models, reused without modification; only module properties change.',
        'Controls without the rod reproduce the 6 November planar (94.68 mm) and spatial (179.42 degrees, minus 65.67 degrees, 146.48 N) results.',
        'Spatial model with the rod: energy gradient against finite differences within 1.4e-9, and planar-to-spatial energy agreement within 5e-15.',
        'EA and EI sweep: all threshold classifications unchanged from 8 to 16 cells; largest tangent change 0.09 degrees.',
        'Steering: every reported state passes all acceptance rules at 8 cells. The 15 degree held case required a lower angle cap (165 degrees).',
        'Not modelled: friction, contact, NiTi transformation and hysteresis, printed part buckling, fatigue, rod end fittings, tank geometry.',
    ])
    story += [P('Build and test plan for the backbone M module', 'h1'),
              P('Full details are in M_BACKBONE_TEST_PLAN.md in the backbone study folder. Specimens are the current M module as a control, the M module '
                'with a 1.8 mm superelastic NiTi rod and three intermediate guides at 24 mm spacing, and a two-module M2 chain.'),
              table([['Test', 'Method', 'Pass criterion'],
                     ['Rod material', 'Tension to 6% and unload; Af by DSC or bend and free recovery', 'Moduli and Af recorded; choose 40 or 75 GPa case'],
                     ['Axial stiffness', 'Plus and minus 150 N, 5 cycles, LVDT or DIC across end disks (5 µm resolution)', 'EA at least 833 N; no joint slip'],
                     ['Bending stiffness', 'Cantilever, 0.1 to 0.6 N tip load, three orientations', 'EI at least 0.055 N m² in every plane'],
                     ['Rod buckling', 'Compress via rod end; guide spacings 20, 24, 32 mm', 'No buckling at or below 248 N'],
                     ['Torsion (optional)', 'Plus and minus 10 deg twist', 'Recorded, expected 0.60 to 0.74 N m/rad'],
                     ['Tendon-driven bending', 'M2 chain, one rope 0 to 60 N, camera', 'Curvature within 15% of model with measured EI'],
                     ['Bending fatigue', '180 deg bend over M2, 10,000 cycles', 'EI change under 10%; no slip or cracking'],
                     ['Integrated U4 plus M2', '20 deg, 500 g dummy head, anchors [4,5,6], 91.5 / 21.4 / 8.5 N', 'Offset at most 10 mm; tangent at most 5 deg']],
                    [.2, .47, .33], bold_first_col=True),
              P('Measured values should be added to a copy of module_stiffness.sqlite3 as a new module entry and the backbone studies re-run with it.', 'caption')]
    story.append(PageBreak())

    # ---------------- Page 7: next decisions
    story += [P('Problems and next decisions', 'h1'),
              table([['Priority', 'Problem', 'Required work'],
                     ['1', 'Backbone M module validation', 'Build and run the test plan. The bending stiffness, rod end joint and buckling at the guide spacing decide whether the simulated results hold.'],
                     ['2', 'Tendon force allocation', 'Search for minimum-force tension sets at held elevation, and check continuous paths between postures. Reduce the 98 N and 247 N peak cases.'],
                     ['3', 'Entry and storage', 'Re-run the front-only tank entry screen with the new low-strain straight shape; add sensor CAD, cable envelopes, sleeve contact and telescopic storage for the 63 mm front.'],
                     ['4', 'Rear mechanism', 'Select stage sizes, overlap, antirotation guides, drive and locks, using the new front reactions.'],
                     ['5', 'Integrated validation', 'Full three dimensional tank sweep with real head dimensions, then unloaded and incremental payload prototypes.'],
                     ['6', 'Longer fronts (optional)', 'U6 plus M3 and U8 plus M4 need more anchor sets inside M or a stiffer M; revisit only if U4 plus M2 reach is insufficient.']],
                    [.1, .27, .63]),
              Spacer(1, 10),
              P('Recommendation', 'h2'),
              P('Proceed with U4 plus M2, three or fewer anchor sets, and a central 1.8 mm NiTi backbone in each M module. The simulations now show '
                'straightening within the strain diagnostic at 15 to 25 degrees and full yaw at the working elevation, but every result rests on '
                'calculated rod properties. Physical module tests are the next gate. If measured bending stiffness falls below about 0.055 N m², '
                'increase the rod diameter to 2.0 mm or shorten the unsupported M spans before changing the architecture.'),
              P('The 5% strain value, 250 N tendon bound and 180 degree angle cap remain numerical diagnostics, not hardware ratings.', 'caption'),
              P('Sources and reproduction', 'h2'),
              P('Study folders: ASRC_kevin/telescopic_planar_study/m_axial_sweep_20261108 and backbone_20261108, each with a README, scripts and saved '
                'results. This report is generated by ASRC_kevin/telescopic_planar_study/reports/build_report_2026_11_08.py.')]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title='ASRC Fuel Tank Robot Simulation Review, 8 November 2026', author='ASRC')
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print('wrote', OUTPUT)


if __name__ == '__main__':
    build()
