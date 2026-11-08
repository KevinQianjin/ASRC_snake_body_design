"""Figure for the M EA/EI requirement sweep (reads results/sweep_rows.json, sweep_states.npz)."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm

OUT = Path(__file__).resolve().parent / 'results'
rows = [r for r in json.loads((OUT / 'sweep_rows.json').read_text()) if 'maximum_axis_deviation_mm' in r]
states = np.load(OUT / 'sweep_states.npz')
eis = sorted({r['ei_scale'] for r in rows})
eas = sorted({r['ea_scale'] for r in rows})
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})


def best(ei, ea):
    c = [r for r in rows if r['ei_scale'] == ei and r['ea_scale'] == ea
         and r['strain_diagnostic_pass'] and r['stable_with_1m_extra_rope']]
    return min(c, key=lambda r: (not r['all_straight_diagnostics_pass'], r['maximum_tangent_error_deg'])) if c else None


fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw=dict(width_ratios=[1.25, 1]))

# Panel A: best maximum tangent error among <=5% strain, stable solutions.
Z = np.full((len(eis), len(eas)), np.nan)
for i, ei in enumerate(eis):
    for j, ea in enumerate(eas):
        r = best(ei, ea)
        if r:
            Z[i, j] = r['maximum_tangent_error_deg']
levels = [0, 2.5, 5, 10, 20, 40, 70]
cmap = LinearSegmentedColormap.from_list('blue', ['#cde2fb', '#86b6ef', '#3987e5', '#256abf', '#184f95', '#0d366b'])
im = a.imshow(Z, cmap=cmap, norm=BoundaryNorm(levels, cmap.N), aspect='auto', origin='lower')
for i, ei in enumerate(eis):
    for j, ea in enumerate(eas):
        r = best(ei, ea)
        if not r:
            continue
        light = Z[i, j] < 5
        txt = f"{Z[i, j]:.1f}°" + ('\n✓' if r['all_straight_diagnostics_pass'] else '')
        a.text(j, i, txt, ha='center', va='center', fontsize=7.5, color=INK if light else 'white',
               fontweight='bold' if r['all_straight_diagnostics_pass'] else 'normal')
a.set_xticks(range(len(eas)), [f'×{e:g}' for e in eas])
a.set_yticks(range(len(eis)), [f'×{e:g}' for e in eis])
a.set_xlabel('M axial stiffness EA scale (×1 = 166.7 N)')
a.set_ylabel('M bending stiffness EI scale (×1 = 0.0441 N·m²)')
a.set_title('U4+M2, 20°, 500 g head: best max tangent error at ≤5% strain\n✓ = all straightness checks pass '
            '(≤10 mm offset, ≤5°, ≥95% projection, ≤5% strain, stable)', fontsize=9, loc='left', color=INK)
for s in a.spines.values():
    s.set_visible(False)
cb = fig.colorbar(im, ax=a, fraction=.04, pad=.02)
cb.set_label('max tangent error, deg', color=MUTED)
cb.outline.set_visible(False)

# Panel B: loaded shapes for anchors [4,5,6] in three representative cases.
cases = [((1, 1), 'Current M (EA ×1, EI ×1)', '#2a78d6'),
         ((1, 1000), 'Axially rigid M (EA ×1000, EI ×1)', '#eb6834'),
         ((1.25, 5), 'EA ×5, EI ×1.25 (first pass)', '#1baf7a')]
pitch = np.radians(20)
t = np.array([np.cos(pitch), np.sin(pitch)])
n = np.array([-t[1], t[0]])
L = 596
b.plot([0, L], [0, 0], color=MUTED, lw=1, ls=(0, (4, 3)))
b.text(20, 4, 'straight 20° axis', ha='left', va='bottom', color=MUTED, fontsize=8)
for (ei, ea), label, col in cases:
    sid = f'ea{ea:g}_ei{ei:g}_three_distal_low_strain'
    r = next(r for r in rows if r.get('state_id') == sid)
    p = states[sid + '_points_m'] * 1000
    s_, d_ = p @ t, p @ n
    stats = (f" — {r['maximum_axis_deviation_mm']:.0f} mm, {r['maximum_tangent_error_deg']:.1f}°, "
             f"{100*r['max_abs_axial_strain']:.1f}%")
    b.plot(s_, d_, color=col, lw=2, label=label + stats, solid_capstyle='round')
    b.plot(s_[-1], d_[-1], 'o', ms=8, color=col, mec='white', mew=2)
b.set_xlabel('distance along installation axis, mm')
b.set_ylabel('offset normal to axis, mm (up +)')
b.set_title('Loaded shapes, anchors [4,5,6], ≤5% strain mode\nlegend: max offset, max tangent error, max strain',
            fontsize=9, loc='left', color=INK)
b.grid(color=GRID, lw=.6)
b.set_axisbelow(True)
b.legend(frameon=False, fontsize=8, loc='lower left')
fig.tight_layout()
fig.savefig(OUT / 'm_stiffness_requirement.png', dpi=170)
print('saved', OUT / 'm_stiffness_requirement.png')
