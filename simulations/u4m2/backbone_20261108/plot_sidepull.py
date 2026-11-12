"""Figure: yaw vs side-rope pull-in (winch control), U4+M2 with NiTi rod at 20 deg."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backbone import HERE
OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
COL = {'a6': '#2a78d6', 'a5': '#eb6834', 'a4': '#1baf7a', 'all': '#eda100'}
LAB = {'a6': 'right rope at anchor 6 (tip)', 'a5': 'right rope at anchor 5', 'a4': 'right rope at anchor 4', 'all': 'all three right ropes'}
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.4))
for pull in ['a6', 'a5', 'a4', 'all']:
    for v, ls in [('niti18_E40', '-'), ('niti18_E75', '--')]:
        R = [q for q in json.loads((OUT / f'sidepull_winch_{v}_p20_{pull}.json').read_text()) if 'yaw_deg' in q]
        dl = [q['pull_in_mm'] for q in R]; y = [q['yaw_deg'] for q in R]
        el = [q['world_elevation_deg'] for q in R]; t = [max(q['right_rope_n']) for q in R]
        lab = LAB[pull] if v == 'niti18_E40' else None
        a.plot(dl, y, color=COL[pull], ls=ls, lw=2, label=lab)
        b.plot(y, el, color=COL[pull], ls=ls, lw=2)
        c.plot(y, t, color=COL[pull], ls=ls, lw=2)
a.plot([], [], color=MUTED, ls='-', label='E 40 GPa'); a.plot([], [], color=MUTED, ls='--', label='E 75 GPa')
a.set_xlabel('right rope pulled in at the winch, mm'); a.set_ylabel('yaw (heading in horizontal plane), deg')
a.set_title('Yaw vs winch pull-in', loc='left', fontsize=9, color=INK); a.legend(frameon=False, fontsize=7.5, loc='upper left')
b.axhspan(15, 25, color='#f0efec', zorder=0); b.text(1, 26, 'working band 20 ± 5°', fontsize=8, color=MUTED)
b.set_xlabel('yaw, deg'); b.set_ylabel('world head elevation, deg (not held)')
b.set_title('Head droops as it yaws (other ropes held at fixed length)', loc='left', fontsize=9, color=INK)
c.set_xlabel('yaw, deg'); c.set_ylabel('tension in the pulled right rope, N'); c.set_ylim(0, 200)
c.set_title('Rope tension needed', loc='left', fontsize=9, color=INK)
for ax in (a, b, c):
    ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
fig.suptitle('U4+M2 with 1.8 mm NiTi rod, 20°, start: straight held front (1 N pretension); winch (rope-length) control, 8 cells/module, free space',
             x=.01, ha='left', fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / 'sidepull.png', dpi=170); print('saved')
