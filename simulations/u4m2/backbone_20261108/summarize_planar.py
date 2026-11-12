"""Print and save best <=5% strain, stable planar result per configuration, variant and pitch."""
import json
from backbone import HERE
OUT = HERE / 'results'
summary = []
for tag in ['U4_M2', 'U6_M3', 'U8_M4']:
    rows = json.loads((OUT / f'planar_{tag}_rows.json').read_text())
    fails = [r for r in rows if r['status'] != 'best_local_stationary_solution_found']
    print(tag, 'unsolved rows:', len(fails), sorted({(r['architecture'], r['status']) for r in fails}))
    ok = [r for r in rows if 'maximum_axis_deviation_mm' in r and r['strain_diagnostic_pass'] and r['stable_with_1m_extra_rope']]
    for v in ['none', 'niti18_E40', 'niti18_E75']:
        for p in [15, 20, 25]:
            c = [r for r in ok if r['variant'] == v and round(r['pitch_deg']) == p]
            if not c:
                print(f'  {v:10s} {p}: none'); continue
            b = min(c, key=lambda r: (not r['all_straight_diagnostics_pass'], r['maximum_axis_deviation_mm'] + 2 * r['maximum_tangent_error_deg']))
            summary.append({k: b[k] for k in ['configuration', 'variant', 'pitch_deg', 'architecture', 'anchors', 'maximum_axis_deviation_mm',
                            'maximum_tangent_error_deg', 'axial_projection_fraction', 'max_abs_axial_strain', 'all_straight_diagnostics_pass',
                            'top_extra_tensions_n', 'module_mass_with_rod_g', 'state_id']})
            print(f"  {v:10s} {p}: {b['architecture']:12s} {str(b['anchors']):12s} off {b['maximum_axis_deviation_mm']:6.2f} tan {b['maximum_tangent_error_deg']:5.2f} "
                  f"proj {b['axial_projection_fraction']:.3f} strain {100*b['max_abs_axial_strain']:5.2f}% PASS={b['all_straight_diagnostics_pass']} T {[round(t,1) for t in b['top_extra_tensions_n']]}")
(OUT / 'planar_summary.json').write_text(json.dumps(summary, indent=1, default=float))
