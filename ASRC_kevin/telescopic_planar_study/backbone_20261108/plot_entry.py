"""Figure for the entry screen: tank sections with front positions, and clearance along the path."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from backbone import HERE, STUDY

OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
cad = json.loads((STUDY / 'results/cad_sections.json').read_text())
prof = np.load(STUDY / 'results/cavity_profiles.npz')
xs, fl = prof['length_mm'], prof['floor_mm']
entry = np.array([449., np.interp(449., xs, fl)])
st = np.load(OUT / 'planar_U4_M2_states.npz')
res = {(r['configuration'], r.get('variant'), r['pitch_deg'] if isinstance(r['pitch_deg'], int) else round(r['pitch_deg'])): r
       for r in json.loads((OUT / 'entry_screen.json').read_text())['results']}
cur = np.load(OUT / 'entry_screen_curves.npz')

fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.9), gridspec_kw=dict(width_ratios=[1.35, 1]))

# A: tank sections (all five width planes) and front positions at 20 deg.
for sec in cad['sections']:
    for poly in sec['union_polygons']:
        a.add_patch(Polygon(np.asarray(poly['outer']), closed=True, fc='#d9d8d3', ec='#a9a8a3', lw=.4, alpha=.35))
pitch = 20; v = np.array([np.cos(np.radians(pitch)), np.sin(np.radians(pitch))])
def draw(sid, s, col, lw=2, alpha=1., label=None):
    p = st[sid + '_points_m'] * 1000 + entry + s * v
    a.plot(*p.T, color=col, lw=lw, alpha=alpha, solid_capstyle='round', label=label)
    a.add_patch(plt.Circle(p[-1], 31.5, fc='none', ec=col, lw=1, alpha=alpha))
rod = 'U4_M2_niti18_E40_p20_three_distal_low_strain'
none = 'U4_M2_none_p20_three_low_strain'
for k, s in enumerate([-746, -400, -150, 90]):
    draw(rod, s, ORANGE, alpha=.35 + .65 * (k == 3), label='M + 1.8 mm NiTi rod (0.10% strain): passes, 64 mm min gap' if k == 3 else None)
draw(none, -338, BLUE, label='Current M, low strain (4.96%): hits tank at s = -338 mm')
a.plot(*entry, marker='v', color=INK, ms=6)
a.annotate('bottom opening', entry, xytext=(entry[0] - 260, entry[1] - 110), fontsize=8, color=MUTED)
a.set_aspect('equal'); a.set_xlim(-250, 1650); a.set_ylim(-420, 520)
a.set_xlabel('tank length, mm'); a.set_ylabel('height, mm')
a.set_title('U4+M2 at 20°, 500 g head: front-only feed through saved tank sections\n'
            'rod shape at clamp positions s = −746, −400, −150, +90 mm (final); circle = 63 mm head envelope',
            loc='left', fontsize=9, color=INK)
a.legend(frameon=False, fontsize=7.5, loc='lower right')

# B: clearance along the path for the rod shapes (16-cell re-check curves).
for p, col in [(15, BLUE), (20, ORANGE), (25, AQUA)]:
    s = cur[f'U4-M2_niti18_E40_p{p}_s_mm']; g = cur[f'U4-M2_niti18_E40_p{p}_gap_mm']
    r = res[('U4-M2', 'niti18_E40', p)]
    b.plot(s, g, color=col, lw=2, label=f"{p}°: min {r['refined16_min_clearance_mm']:.0f} mm")
b.axhline(5, color=MUTED, lw=1, ls=(0, (4, 3)))
b.text(-760, 7, '5 mm screen limit', color=MUTED, fontsize=8)
b.set_xlabel('clamp position along installation axis s, mm (0 = interface at opening)')
b.set_ylabel('clearance of 63 mm envelope to sections, mm')
b.set_title('Clearance along the feed path, rod E 40 GPa, 16 cells/module\n'
            'curves end at the first position fully inside the cavity', loc='left', fontsize=9, color=INK)
b.grid(color=GRID, lw=.6); b.set_axisbelow(True); b.legend(frameon=False, fontsize=8, loc='upper right')
fig.tight_layout()
fig.savefig(OUT / 'entry_screen.png', dpi=170)
print('saved')
