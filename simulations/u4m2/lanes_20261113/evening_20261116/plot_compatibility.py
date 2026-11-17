"""Plot per-record minimum guide/body signed distance for V3 and the 0.25 mm bond-gap variant."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
plt.rcParams['svg.hashsalt'] = 'asrc-evening-20261116'
fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, constrained_layout=True)
colors = {'V3 (0.15 mm land gap)': '#c0392b', 'Variant (0.25 mm land gap)': '#1f6f8b'}
for (name, folder) in [('V3 (0.15 mm land gap)', 'v3_compatibility'), ('Variant (0.25 mm land gap)', 'gap0p25_compatibility')]:
    rows = json.loads((HERE / folder / 'summary_rows.json').read_text())
    by = {}
    for r in rows:
        k = int(r['state']); by.setdefault(k, []).append(r)
    idx = np.array(sorted(by))
    sd = np.array([min(r['minimum_signed_distance_mm'] for r in by[i]) for i in idx])
    gam = np.array([max(r['land_implied_shear_strain'] for r in by[i]) for i in idx])
    axes[0].plot(idx, sd * 1000, '.', ms=4, color=colors[name], label=name)
    axes[1].plot(idx, gam * 100, '.', ms=4, color=colors[name], label=name)
axes[0].axhline(0, color='k', lw=0.8)
axes[0].axhline(-5, color='0.5', lw=0.6, ls='--', label='-0.005 mm mesh tolerance (reference)')
axes[0].set_ylabel('min signed distance (um)\nnegative = body inside guide')
axes[0].set_title('500 g fixed-winch holds: all 8 M5/M6 guides per record (217 records)')
axes[0].legend(fontsize=8, loc='lower left')
axes[0].text(0.99, 0.97, 'Values at or above 30 um may be certified lower bounds (no distance query needed)', transform=axes[0].transAxes, ha='right', va='top', fontsize=8)
axes[1].set_ylabel('implied land shear strain (%)\naxial slip / nominal gap')
axes[1].set_xlabel('selected hold record index')
axes[1].legend(fontsize=8, loc='upper left')
for ax in axes:
    ax.grid(alpha=0.3)
fig.savefig(HERE / 'compatibility_comparison.svg', metadata={'Date': None})
import sys
if len(sys.argv) > 1:
    fig.savefig(sys.argv[1], dpi=80)
