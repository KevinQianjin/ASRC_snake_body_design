"""Front-only tank entry screen for the backbone low-strain straightened shapes.

Reuses path_check() from stiffness_63mm_20261106/postprocess.py unchanged:
a fixed actively tensioned equilibrium shape translates along the installation
axis through the bottom opening (x = 449 mm), starting with the whole front
and head outside the tank (s = -nominal length - 150 mm). Clearance to the five
saved CAD width sections must stay >= 5 mm (63 mm envelope), with a final
placement fully inside the sampled cavity. Passing shapes are re-solved at
16 cells per module with the same tensions and re-checked.

Same limitations as 2026-11-06: five width planes (628-668 mm) do not span the
full 616.5-679.5 mm front width; no sleeve, storage, rope take-up, retraction
or changing-shape deployment; actual head CAD unknown.
"""
import json
import numpy as np
from backbone import planar_rod, HERE, STUDY
from postprocess import path_check, OLD
from lightweight_path_check import Obstacles
from refine_front import finer_seed
from front_solver import write_csv

OUT = HERE / 'results'
CFG = {'U4-M2': (4, 2), 'U6-M3': (6, 3), 'U8-M4': (8, 4)}


def eligible(r):
    return ('maximum_axis_deviation_mm' in r and r['strain_mode'] == 'low_strain' and r['strain_diagnostic_pass']
            and r['stable_with_1m_extra_rope'] and not r['nonlocal_capsule_overlap'] and not r['local_radius_curvature_exceeded'])


def pick(rows, variant, pitch):
    c = [r for r in rows if r.get('variant') == variant and round(r['pitch_deg']) == pitch and eligible(r)]
    return min(c, key=lambda r: (not r['all_straight_diagnostics_pass'],
                                 r['maximum_axis_deviation_mm'] + .5 * max(0, r['nominal_front_length_mm'] - r['axial_projection_mm']))) if c else None


def main():
    cad = json.loads((OLD / 'results/cad_sections.json').read_text())
    obstacles = Obstacles(cad['sections'])
    profiles = np.load(OLD / 'results/cavity_profiles.npz')

    # Control: reproduce the 2026-11-06 U4+M2 20 deg shape-only path result.
    old_rows = json.loads((STUDY / 'stiffness_63mm_20261106/results/representatives.json').read_text())
    old_states = np.load(STUDY / 'stiffness_63mm_20261106/results/U4_M2_states.npz')
    old_paths = json.loads((STUDY / 'stiffness_63mm_20261106/results/front_only_path_screen.json').read_text())
    ref = next(r for r in old_rows if r['configuration'] == 'U4-M2' and r['pitch_deg'] == 20 and r['strain_mode'] == 'shape_only')
    res, _, _ = path_check(ref, old_states[ref['state_id'] + '_points_m'], obstacles, profiles)
    expected = next(p for p in old_paths if p['state_id'] == ref['state_id'] and p['configuration'] == 'U4-M2')
    control_err = abs(res['minimum_sampled_envelope_clearance_mm'] - expected['minimum_sampled_envelope_clearance_mm'])
    assert control_err < 1e-9, control_err
    print(f"control U4-M2 20 deg shape_only: {res['minimum_sampled_envelope_clearance_mm']:.2f} mm (6 Nov saved value reproduced)")

    results, curves = [], {}
    for cfg, (u, m) in CFG.items():
        tag = f'U{u}_M{m}'
        rows = json.loads((OUT / f'planar_{tag}_rows.json').read_text())
        states = np.load(OUT / f'planar_{tag}_states.npz')
        for variant in ['none', 'niti18_E40', 'niti18_E75']:
            for pitch in [15, 20, 25]:
                row = pick(rows, variant, pitch)
                if row is None:
                    results.append(dict(configuration=cfg, variant=variant, pitch_deg=pitch, status='no_eligible_low_strain_shape'))
                    print(cfg, variant, pitch, 'no eligible shape'); continue
                pts = states[row['state_id'] + '_points_m']
                res, s, gap = path_check(row, pts, obstacles, profiles)
                res.update(variant=variant, maximum_axis_deviation_mm=row['maximum_axis_deviation_mm'],
                           maximum_tangent_error_deg=row['maximum_tangent_error_deg'],
                           all_straight_diagnostics_pass=row['all_straight_diagnostics_pass'], cells_per_module=8)
                # 16-cell same-tension re-check for passing shapes.
                if res['front_only_continuous_translation_screen_pass']:
                    c8 = planar_rod(u, m, row['anchors'], pitch, 8, variant)
                    f16 = planar_rod(u, m, row['anchors'], pitch, 16, variant)
                    D = np.array(row['top_extra_tensions_n'])
                    x8 = c8.solve_ramped(D, c8.straight_seed())
                    x16 = f16.solve_ramped(D, finer_seed(x8, c8, f16)) if x8 is not None else None
                    if x16 is None:
                        res['refined16_status'] = 'solve_failed'
                    else:
                        r16, p16, _ = f16.metrics(x16, D, geometry=True)
                        r16.update(state_id=row['state_id'] + '_16', architecture=row['architecture'], strain_mode='low_strain')
                        q, s, gap = path_check(r16, p16, obstacles, profiles)
                        res.update(refined16_status='ok', refined16_min_clearance_mm=q['minimum_sampled_envelope_clearance_mm'],
                                   refined16_lower_bound_mm=q['conservative_translation_clearance_lower_bound_mm'],
                                   refined16_pass=q['front_only_continuous_translation_screen_pass'], refined16_final_s_mm=q['final_s_mm'],
                                   refined16_max_strain=r16['max_abs_axial_strain'], refined16_offset_mm=r16['maximum_axis_deviation_mm'])
                key = f'{cfg}_{variant}_p{pitch}'
                curves[key + '_s_mm'] = s; curves[key + '_gap_mm'] = gap
                results.append(res)
                print(f"{cfg} {variant:10s} {pitch} {row['architecture']:12s} offset {row['maximum_axis_deviation_mm']:6.1f} "
                      f"strain {100*row['max_abs_axial_strain']:5.2f}%  min gap {res['minimum_sampled_envelope_clearance_mm']:7.2f} "
                      f"pass {res['front_only_continuous_translation_screen_pass']}  final s {res['final_s_mm']}  first fail {res['first_failed_sample_s_mm']}"
                      + (f"  | 16-cell gap {res.get('refined16_min_clearance_mm', float('nan')):.2f} pass {res.get('refined16_pass')}" if 'refined16_status' in res else ''),
                      flush=True)
    (OUT / 'entry_screen.json').write_text(json.dumps(dict(control_abs_error_mm=control_err, results=results), indent=1, default=float))
    write_csv(OUT / 'entry_screen.csv', [r for r in results if 'minimum_sampled_envelope_clearance_mm' in r])
    np.savez_compressed(OUT / 'entry_screen_curves.npz', **curves)


if __name__ == '__main__':
    main()
