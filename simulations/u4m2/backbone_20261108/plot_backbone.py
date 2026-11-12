"""Figure: U4+M2 with and without the 1.8 mm NiTi backbone (planar straightening, held-elevation yaw)."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backbone import HERE

OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
rows = json.loads((OUT / 'planar_U4_M2_rows.json').read_text())
states = np.load(OUT / 'planar_U4_M2_states.npz')
steer = json.loads((OUT / 'steering_summary_8cell.json').read_text())

fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.6))

# A: best <=5% strain loaded shape at 20 deg, without and with the rod.
def best(variant, pitch):
    c = [r for r in rows if r.get('variant') == variant and round(r.get('pitch_deg', 0)) == pitch and 'maximum_axis_deviation_mm' in r
         and r['strain_diagnostic_pass'] and r['stable_with_1m_extra_rope']]
    return min(c, key=lambda r: (not r['all_straight_diagnostics_pass'], r['maximum_axis_deviation_mm'] + 2 * r['maximum_tangent_error_deg']))

pitch = np.radians(20); t = np.array([np.cos(pitch), np.sin(pitch)]); n = np.array([-t[1], t[0]])
a.plot([0, 596], [0, 0], color=MUTED, lw=1, ls=(0, (4, 3)))
a.text(20, 4, 'straight 20° axis', color=MUTED, fontsize=8)
for v, label, col in [('none', 'Current M', BLUE), ('niti18_E40', 'M + 1.8 mm NiTi rod, E 40 GPa', ORANGE), ('niti18_E75', 'M + 1.8 mm NiTi rod, E 75 GPa', AQUA)]:
    r = best(v, 20)
    p = states[r['state_id'] + '_points_m'] * 1000
    a.plot(p @ t, p @ n, color=col, lw=2, solid_capstyle='round',
           label=f"{label}: {r['maximum_axis_deviation_mm']:.0f} mm, {r['maximum_tangent_error_deg']:.1f}°, {100*r['max_abs_axial_strain']:.2f}%, anchors {r['anchors']}")
    a.plot((p @ t)[-1], (p @ n)[-1], 'o', ms=8, color=col, mec='white', mew=2)
a.set_xlabel('distance along installation axis, mm'); a.set_ylabel('offset normal to axis, mm (up +)')
a.set_title('U4+M2, 20°, 500 g head: actively straightened shape at ≤5% strain\nlegend: max offset, max tangent error, max strain',
            loc='left', fontsize=9, color=INK)
a.grid(color=GRID, lw=.6); a.set_axisbelow(True); a.legend(frameon=False, fontsize=7.5, loc='lower left')

# B: steering endpoints at 20 deg, 8 cells/module: yaw vs world head elevation.
b.axhspan(15, 25, color='#f0efec', zorder=0)
b.text(5, 25.8, 'held-elevation band 20 ± 5°', color=MUTED, fontsize=8)
b.axhline(0, color=MUTED, lw=.6)
pts = [('none', 'right', BLUE, 'Current M, free yaw'),
       ('niti18_E40', 'right', ORANGE, 'Rod E40, free yaw'), ('niti18_E40', 'right_level', ORANGE, 'Rod E40, held elevation'),
       ('niti18_E75', 'right', AQUA, 'Rod E75, free yaw (overlaps E40)'), ('niti18_E75', 'right_level', AQUA, 'Rod E75, held elevation')]
for v, d, col, label in pts:
    r = next(q for q in steer if q['variant'] == v and q['pitch_deg'] == 20 and q['direction'] == d)
    filled = d == 'right_level'
    b.plot(r['angle_deg'], r['world_elevation_deg'], 'o' if filled else 's', ms=9, color=col if filled else 'white',
           mec=col, mew=2, label=f"{label}: {r['angle_deg']:.0f}° yaw, {r['world_elevation_deg']:+.1f}° elev, {r['peak_tension_n']:.0f} N peak")
b.annotate('Current M: no held-elevation\nsolution found', (75, 20), ha='center', va='center', fontsize=8, color=BLUE)
b.set_xlim(0, 195); b.set_ylim(-75, 35)
b.set_xlabel('yaw (head heading in horizontal plane), deg'); b.set_ylabel('world head elevation, deg')
b.set_title('Steering endpoints at 20°, 8 cells/module, ≤5% strain\n180° is the search cap, not a mechanical limit',
            loc='left', fontsize=9, color=INK)
b.grid(color=GRID, lw=.6); b.set_axisbelow(True); b.legend(frameon=False, fontsize=7.5, loc='lower left')
fig.tight_layout()
fig.savefig(OUT / 'backbone_results.png', dpi=170)
print('saved')
