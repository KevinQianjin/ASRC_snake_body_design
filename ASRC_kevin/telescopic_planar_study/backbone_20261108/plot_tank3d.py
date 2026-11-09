"""Figure: 3D tank clearance along the held-elevation yaw sweep vs clamp depth (20 deg, E 40 GPa)."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from backbone import HERE

OUT = HERE / 'results'
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
COL = {0: '#2a78d6', 30: '#1baf7a', 60: '#eda100', 90: '#eb6834'}
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
run = 'minforce_niti18_E40_p20_a456_pre1_exact_smooth1'
rows = json.loads((OUT / f'tank3d_sweep_{run}.json').read_text())['rows'] + \
       json.loads((OUT / f'tank3d_sweep_{run}_s0_30_60.json').read_text())['rows']
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), sharey=True)
for ax, side in zip(axes, ['right', 'left']):
    for s in [0, 30, 60, 90]:
        rr = sorted([q for q in rows if q['side'] == side and q['clamp_s_mm'] == s], key=lambda q: q['yaw_deg'])
        ax.plot([q['yaw_deg'] for q in rr], [q['clearance_mm'] for q in rr], color=COL[s], lw=2, label=f'clamp s = {s} mm')
    ax.axhline(5, color=MUTED, lw=1, ls=(0, (4, 3))); ax.axhline(0, color=INK, lw=.6)
    ax.text(2, 6.5, '5 mm screen limit', color=MUTED, fontsize=8)
    ax.set_xlabel(f'yaw to the {side}, deg (head elevation held at 20°)')
    ax.set_title(f'Yaw to the {side}: clearance of 63 mm envelope to full 3D tank', loc='left', fontsize=9, color=INK)
    ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
axes[0].set_ylabel('minimum clearance, mm')
axes[0].legend(frameon=False, fontsize=8, loc='center left')
fig.suptitle('U4+M2 with 1.8 mm NiTi rod (E 40 GPa), 20° installation, minimum-force smooth allocation, 8 cells/module',
             x=.01, ha='left', fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / 'tank3d_sweep.png', dpi=170); print('saved')
