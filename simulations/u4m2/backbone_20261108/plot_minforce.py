"""Figure: minimum peak tendon force along held-elevation yaw sweeps, and per-rope tensions of a smooth allocation."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backbone import HERE

OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
C1, C2, C3, C4 = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
load = lambda f: [r for r in json.loads((OUT / f'{f}.json').read_text()) if r.get('ok8')]

fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.6))
runs = [('minforce_niti18_E40_p20_a456_pre1_exact_smooth1', 'E 40 GPa, 20°, anchors [4,5,6]', C1, '-'),
        ('minforce_niti18_E40_p20_a46_pre1_exact', 'E 40 GPa, 20°, anchors [4,6]', C2, '-'),
        ('minforce_niti18_E75_p20_a456_pre1_exact_smooth1', 'E 75 GPa, 20°, anchors [4,5,6]', C3, '-'),
        ('minforce_niti18_E40_p25_a456_pre1_exact', 'E 40 GPa, 25°, anchors [4,5,6]', C4, '-')]
for f, label, col, ls in runs:
    R = load(f)
    a.plot([r['yaw_deg'] for r in R], [r['peak_n'] for r in R], color=col, lw=2, ls=ls, label=label)
steer = json.loads((OUT / 'steering_summary_8cell.json').read_text())
for v, col in [('niti18_E40', C1), ('niti18_E75', C3)]:
    r = next(q for q in steer if q['variant'] == v and q['pitch_deg'] == 20 and q['direction'] == 'right_level')
    a.plot(r['angle_deg'], r['peak_tension_n'], 's', ms=8, mfc='white', mec=col, mew=2)
    a.annotate(f"8 Nov max-angle allocation: {r['peak_tension_n']:.0f} N", (r['angle_deg'], r['peak_tension_n']),
               xytext=(-8, 0), textcoords='offset points', ha='right', va='center', fontsize=8, color=INK)
a.set_xlabel('yaw with head elevation held at base pitch, deg'); a.set_ylabel('largest single tendon tension, N')
a.set_xlim(-5, 190); a.set_ylim(0, 105)
a.set_title('U4+M2 with 1.8 mm NiTi rod: minimum peak tendon force, 8 cells/module\n1 N pretension on every rope; sampled every 5° by continuation',
            loc='left', fontsize=9, color=INK)
a.grid(color=GRID, lw=.6); a.set_axisbelow(True); a.legend(frameon=False, fontsize=8, loc='center left')

R = load('minforce_niti18_E40_p20_a456_pre1_exact_smooth1')
yaw = np.array([r['yaw_deg'] for r in R]); T = np.array([r['tensions_n'] for r in R])  # (n, sets, 4)
dirs = ['up', 'right', 'down', 'left']; dcol = [C1, C2, C3, C4]; styles = {0: '-', 1: '--', 2: ':'}
for s_i, anchor in enumerate([4, 5, 6]):
    for d_i, d in enumerate(dirs):
        y = T[:, s_i, d_i]
        if y.max() < 1.5: continue
        b.plot(yaw, y, color=dcol[d_i], ls=styles[s_i], lw=2, label=f'anchor {anchor}, {d}')
b.axhline(1, color=MUTED, lw=.8, ls=(0, (2, 2))); b.text(2, 1.4, '1 N pretension (all other ropes)', fontsize=8, color=MUTED)
b.set_xlabel('yaw, deg'); b.set_ylabel('rope tension, N')
b.set_title('Rope tensions of a smooth allocation, E 40 GPa, 20°, anchors [4,5,6]\nlargest change between 5° steps 5.1 N; ropes staying at 1 N not drawn',
            loc='left', fontsize=9, color=INK)
b.grid(color=GRID, lw=.6); b.set_axisbelow(True); b.legend(frameon=False, fontsize=7.5, loc='upper right', ncol=2)
fig.tight_layout(); fig.savefig(OUT / 'minforce_results.png', dpi=170); print('saved')
