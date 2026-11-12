"""Re-solve selected 8-cell sweep states at 16 cells per module with identical tensions."""
import json, sys
import numpy as np
from run_sweep import ScaledRod, OUT, finer_seed

CASES = [(1, 1000), (1.25, 3), (1.25, 5), (1.5, 5), (2, 5), (3, 3), (5, 3)]  # (EI scale, EA scale)
rows = [r for r in json.load(open(OUT / 'sweep_rows.json')) if 'maximum_axis_deviation_mm' in r]
out = []
for ei, ea in CASES:
    r8 = min([r for r in rows if r['ei_scale'] == ei and r['ea_scale'] == ea and r['architecture'] == 'three_distal'
              and r['strain_mode'] == 'low_strain'], key=lambda r: r['maximum_tangent_error_deg'])
    D = np.array(r8['top_extra_tensions_n'])
    c = ScaledRod(4, 2, r8['anchors'], sub=8, ea_scale=ea, ei_scale=ei)
    f = ScaledRod(4, 2, r8['anchors'], sub=16, ea_scale=ea, ei_scale=ei)
    x8 = c.solve_ramped(D, c.straight_seed())
    x16 = f.solve_ramped(D, finer_seed(x8, c, f)) if x8 is not None else None
    if x16 is None:
        out.append(dict(ei_scale=ei, ea_scale=ea, status='16-cell solve failed')); continue
    m, p, _ = f.metrics(x16, D, geometry=True)
    keep = ['maximum_axis_deviation_mm', 'maximum_tangent_error_deg', 'axial_projection_fraction', 'max_abs_axial_strain',
            'stable_with_1m_extra_rope', 'all_straight_diagnostics_pass', 'tip_pitch_deg']
    row = dict(ei_scale=ei, ea_scale=ea, anchors=r8['anchors'], tensions_n=D.tolist(),
               **{k + '_8cell': r8[k] for k in keep}, **{k + '_16cell': m[k] for k in keep})
    out.append(row)
    print(f"EI x{ei:g} EA x{ea:g}: 8-cell {r8['maximum_axis_deviation_mm']:.2f} mm/{r8['maximum_tangent_error_deg']:.2f} deg "
          f"pass {r8['all_straight_diagnostics_pass']} | 16-cell {m['maximum_axis_deviation_mm']:.2f} mm/"
          f"{m['maximum_tangent_error_deg']:.2f} deg strain {100*m['max_abs_axial_strain']:.2f}% pass {m['all_straight_diagnostics_pass']}")
(OUT / 'verify_16cell.json').write_text(json.dumps(out, indent=1, default=float))
