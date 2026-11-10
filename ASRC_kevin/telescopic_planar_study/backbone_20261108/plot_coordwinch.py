"""Figure: coordinated winch control along the held-elevation yaw sweep (E 40 GPa, 20 deg)."""
import json, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backbone import HERE
from coordinated_winch import RUNS

OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
C1, C2, C3, C4 = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
DCOL = {'up': C1, 'right': C2, 'down': C3, 'left': C4}; LS = {'a4': '-.', 'a5': '--', 'a6': '-'}
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
fig, (a, b, c) = plt.subplots(1, 3, figsize=(14, 4.5))

# A: head elevation between poses (both rods) and head movement per sub-step
for case, col in [('E40', C1), ('E75', C2)]:
    R = json.loads((OUT / f'coordwinch_{RUNS[case][0]}_n20.json').read_text())['rows']
    y = [q['yaw_deg'] for q in R]
    a.plot(y, [q['world_elevation_deg'] for q in R], color=col, lw=2, label=f"rod E {case[1:]} GPa ({len(R)} states)")
a.axhspan(15, 25, color='#f0efec', zorder=0); a.text(3, 24.2, 'working band 20 ± 5°', fontsize=8, color=MUTED)
a.set_ylim(14, 26); a.set_xlabel('yaw, deg'); a.set_ylabel('world head elevation, deg')
a.set_title('Head elevation stays at 19.2–20.1° between poses', loc='left', fontsize=9, color=INK)
a.legend(frameon=False, fontsize=8, loc='lower right')

# B: winch command table (pull-in relative to the straight pose), E40
rows = list(csv.DictReader(open(OUT / 'coordwinch_E40_winch_table.csv')))
yaw = np.array([float(r['yaw_deg']) for r in rows])
for an in ['a6', 'a5', 'a4']:
    for d in ['up', 'right', 'down', 'left']:
        v = np.array([float(r[f'{an}_{d}_pull_in_mm']) for r in rows])
        if np.ptp(v) < 3: continue
        b.plot(yaw, v, color=DCOL[d], ls=LS[an], lw=2, label=f'anchor {an[1]}, {d}')
b.axhline(0, color=MUTED, lw=.6)
b.set_xlabel('yaw, deg'); b.set_ylabel('rope reeled in at the winch, mm (negative = paid out)')
b.set_title('Winch commands, rod E 40 GPa (ropes moving < 3 mm not drawn)', loc='left', fontsize=9, color=INK)
b.legend(frameon=False, fontsize=7.5, ncol=2, loc='upper left')

# C: rope tensions during the continuous motion, E40
R = json.loads((OUT / f'coordwinch_{RUNS["E40"][0]}_n20.json').read_text())['rows']
y = np.array([q['yaw_deg'] for q in R]); T = np.array([q['tensions_n'] for q in R])
for si, an in enumerate(['a4', 'a5', 'a6']):
    for di, d in enumerate(['up', 'right', 'down', 'left']):
        if T[:, si, di].max() < 1.5: continue
        c.plot(y, T[:, si, di], color=DCOL[d], ls=LS[an], lw=1.8)
c.axhline(1, color=MUTED, lw=.8, ls=(0, (2, 2))); c.text(60, 1.35, '1 N pretension', fontsize=8, color=MUTED)
c.set_ylim(0, 16); c.set_xlabel('yaw, deg'); c.set_ylabel('rope tension, N')
c.set_title('Resulting rope tensions: no rope goes slack (min 0.71 N)', loc='left', fontsize=9, color=INK)
for ax in (a, b, c):
    ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
fig.suptitle('Coordinated winch (rope-length) control: all 12 winches move together through the 5° poses, 20 sub-steps per segment, 8 cells/module',
             x=.01, ha='left', fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / 'coordwinch.png', dpi=170); print('saved')
