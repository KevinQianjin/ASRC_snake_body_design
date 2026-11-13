"""Overview figure for the lane study: results_lanes/lanes_overview.png and results_lanes/rope_chord_by_yaw.json.

Left: peak and summed rope tension of the 20-degree yaw holds, shared 24 mm holes vs lanes 21/24/27 mm.
Right: M5 and M6 bend angle and the largest offset of a straight rope chord from its lane, against the
straight-corridor clearance of the re-clocked M body (cad/lanes_u4m2/lane_design.json).
Usage (from this folder): python lanes_figures.py
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json
from pathlib import Path
import numpy as np
import lanes
lanes.install()
import backbone  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
TAG = 'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1'
SHARED = lanes.BACKBONE_DIR / 'results' / f'{TAG}.json'
LANES = HERE / 'results_lanes' / f'{TAG}.json'
STATES = HERE / 'results_lanes' / f'{TAG}_states.npz'
CAD = HERE.parents[2] / 'cad' / 'lanes_u4m2' / 'lane_design.json'


def chord_by_yaw():
    r = backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8, 'niti18_E40')
    d = np.load(STATES); rows = []
    for k in sorted([k for k in d if k.endswith('_z8')], key=lambda k: float(k[1:-3])):
        _, _, det = r.evaluate(d[k], d[k.replace('_z8', '_T8')], detail=True); p, F = det['points'], det['frames']
        row = dict(yaw_deg=float(k[1:-3]))
        for j, name in ((4, 'M5'), (5, 'M6')):
            i0, i1 = j * 8, j * 8 + 8; dev = 0.
            for s in range(3):
                if r.routes[s, j] == 0: continue
                for rope in range(4):
                    off = r.offsets3[s, rope]; a = p[i0] + F[i0] @ off; b = p[i1] + F[i1] @ off
                    for i in range(i0 + 1, i1):
                        n = F[i][:, 0]; t = np.dot(p[i] - a, n) / np.dot(b - a, n); q = a + t * (b - a)
                        dev = max(dev, 1000 * float(np.linalg.norm(F[i].T @ (q - p[i]) - off)))
            ang = float(np.degrees(np.arccos(np.clip((np.trace(F[i0].T @ F[i1]) - 1) / 2, -1, 1))))
            row[name] = dict(bend_deg=round(ang, 2), max_chord_offset_mm=round(dev, 2))
        rows.append(row)
    return rows


def main():
    sh = {x['yaw_target_deg']: x for x in json.loads(SHARED.read_text()) if 'peak_n' in x}
    la = {x['yaw_target_deg']: x for x in json.loads(LANES.read_text()) if 'peak_n' in x}
    rows = chord_by_yaw()
    (HERE / 'results_lanes' / 'rope_chord_by_yaw.json').write_text(json.dumps(rows, indent=1))
    clr = {k: v for k, v in json.loads(CAD.read_text())['M_lane_clearance_mm'].items() if k[0] in 'BC'}  # A ends at U4
    cmin, cmax = min(clr.values()), max(clr.values())
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    y = sorted(la); ys = sorted(sh)
    ax[0].plot(ys, [sh[k]['peak_n'] for k in ys], color='#c0504d', label='Peak, shared 24 mm holes')
    ax[0].plot(y, [la[k]['peak_n'] for k in y], color='#1f4e79', label='Peak, lanes 21/24/27 mm')
    ax[0].plot(ys, [sh[k]['sum_n'] / 12 for k in ys], color='#c0504d', ls='--', label='Mean of 12 ropes, shared')
    ax[0].plot(y, [la[k]['sum_n'] / 12 for k in y], color='#1f4e79', ls='--', label='Mean of 12 ropes, lanes')
    ax[0].set_xlabel('Yaw target (deg), head held at 20 deg elevation'); ax[0].set_ylabel('Rope tension (N)'); ax[0].grid(alpha=.3); ax[0].legend(fontsize=8)
    ax[0].set_title('Minimum-force yaw holds', fontsize=10)
    yy = [r_['yaw_deg'] for r_ in rows]
    ax[1].axhspan(cmin, cmax, color='#9bbb59', alpha=.25, label=f'M corridor clearance {cmin:.1f}-{cmax:.1f} mm')
    ax[1].plot(yy, [r_['M5']['max_chord_offset_mm'] for r_ in rows], color='#1f4e79', label='M5 rope offset from lane')
    ax[1].plot(yy, [r_['M6']['max_chord_offset_mm'] for r_ in rows], color='#4f81bd', ls='--', label='M6 rope offset from lane')
    ax[1].set_xlabel('Yaw target (deg)'); ax[1].set_ylabel('Largest rope offset (mm)'); ax[1].grid(alpha=.3)
    a2 = ax[1].twinx(); a2.plot(yy, [r_['M5']['bend_deg'] for r_ in rows], color='#7f7f7f', lw=.9, label='M5 bend (right axis)')
    a2.set_ylabel('M5 bend angle (deg)')
    h1, l1 = ax[1].get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels(); ax[1].legend(h1 + h2, l1 + l2, fontsize=8, loc='upper left')
    ax[1].set_title('Ropes guided only at end disks: offset inside M5/M6', fontsize=10)
    plt.tight_layout(); plt.savefig(HERE / 'results_lanes' / 'lanes_overview.png', dpi=150)
    print('wrote lanes_overview.png;', 'first yaw with M5 offset above min clearance:',
          next((r_['yaw_deg'] for r_ in rows if r_['M5']['max_chord_offset_mm'] > cmin), None))


if __name__ == '__main__':
    main()
