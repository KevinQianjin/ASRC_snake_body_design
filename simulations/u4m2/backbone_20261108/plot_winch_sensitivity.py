"""Figure: head pose sensitivity to winch position error (coordinated sweep, 20 deg)."""
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
S = json.loads((OUT / 'winch_sensitivity_summary.json').read_text())
R = {c: json.loads((OUT / f'winch_sensitivity_{c}.json').read_text()) for c in S}
fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.5), gridspec_kw=dict(width_ratios=[1, 1, 1.15]))
for case, ls in [('E40', '-'), ('E75', '--')]:
    s = S[case]; y = s['yaws']; P = R[case]['poses']
    lab = lambda t: t if case == 'E40' else None
    a.plot(y, np.maximum(s['single_1mm_yaw_deg'], s['single_1mm_elev_deg']), color=C1, ls=ls, lw=2, marker='o', ms=4, label=lab('one winch off by 1 mm'))
    a.plot(y, [max(p['random_p99']['0.5mm']['yaw_p99_deg'], p['random_p99']['0.5mm']['elev_p99_deg']) for p in P], color=C3, ls=ls, lw=2, marker='o', ms=4, label=lab('all 12 random ±0.5 mm (99%)'))
    a.plot(y, [max(p['random_p99']['1mm']['yaw_p99_deg'], p['random_p99']['1mm']['elev_p99_deg']) for p in P], color=C2, ls=ls, lw=2, marker='o', ms=4, label=lab('all 12 random ±1 mm (99%)'))
a.plot([], [], color=MUTED, ls='-', label='rod E 40 GPa'); a.plot([], [], color=MUTED, ls='--', label='rod E 75 GPa')
a.set_xlabel('yaw along the coordinated sweep, deg'); a.set_ylabel('head angle error (larger of yaw, elevation), deg')
a.set_title('Head angle error from winch position error', loc='left', fontsize=9, color=INK); a.legend(frameon=False, fontsize=7.5, loc='upper left')
s = S['E40']; y = s['yaws']
b.plot(y, s['allow_1deg_p99_mm'], color=C1, lw=2, marker='o', ms=4, label='±1°, 99% of random errors')
b.plot(y, s['allow_1deg_worst_mm'], color=C1, lw=2, ls=':', marker='o', ms=4, label='±1°, worst case')
b.plot(y, s['allow_2deg_p99_mm'], color=C2, lw=2, marker='o', ms=4, label='±2°, 99% of random errors')
b.plot(y, s['allow_2deg_worst_mm'], color=C2, lw=2, ls=':', marker='o', ms=4, label='±2°, worst case')
b.set_ylim(0, 1.15); b.set_xlabel('yaw, deg'); b.set_ylabel('allowed error on every winch, ± mm')
b.set_title('Winch accuracy needed, rod E 40 GPa (all 12 winches)', loc='left', fontsize=9, color=INK); b.legend(frameon=False, fontsize=7.5, loc='upper right')
names = list(s['mean_abs_J_yaw_deg_per_mm']); x = np.arange(len(names))
c.bar(x - .2, [s['mean_abs_J_yaw_deg_per_mm'][n] for n in names], .38, color=C1, label='yaw')
c.bar(x + .2, [s['mean_abs_J_elev_deg_per_mm'][n] for n in names], .38, color=C2, label='elevation')
c.set_xticks(x, [n.replace('a', 'A', 1).replace('_', ' ') for n in names], rotation=45, ha='right')
c.set_ylabel('mean sensitivity over the sweep, deg per mm')
c.set_title('Which winch matters: the four tip (anchor 6) ropes dominate', loc='left', fontsize=9, color=INK); c.legend(frameon=False, fontsize=8)
for ax in (a, b, c):
    ax.grid(color=GRID, lw=.6, axis='y' if ax is c else 'both'); ax.set_axisbelow(True)
fig.suptitle('Winch position error sensitivity, U4+M2 with 1.8 mm NiTi rod, 20°, head held at 20°; full nonlinear model, 8 cells/module, free space',
             x=.01, ha='left', fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / 'winch_sensitivity.png', dpi=170); print('saved')
