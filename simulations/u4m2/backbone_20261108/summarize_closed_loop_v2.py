"""Compare closed_loop_cycle.py (v1, saved results) with closed_loop_v2.py for the five cases."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
V1 = HERE / 'closed_loop_results'; V2 = HERE / 'closed_loop_v2_results'
CASES = ['nominal', 'E75', 'payload550g', 'free1500mm', 'ropeEA80pct']
LABEL = {'nominal': 'Nominal', 'E75': 'Rod E 75 GPa', 'payload550g': 'Head 550 g', 'free1500mm': 'Free rope 1.5 m', 'ropeEA80pct': 'Rope EA -20%'}


def v1_stats(case):
    rec = json.loads((V1 / f'{case}.json').read_text()); tr = json.loads((V1 / f'{case}_feedback.json').read_text())
    P = np.load(V1 / f'{case}_states.npz')['points']
    moves = np.linalg.norm(np.diff(P, axis=0), axis=2).max(1)
    ang = [max(abs(q['closed']['yaw_error_deg']), abs(q['closed']['elevation_error_deg'])) for q in rec]
    tmin_all = [t['minimum_tension_n'] for t in tr] + [q['closed']['minimum_tension_n'] for q in rec]
    return dict(settled_max_angle_deg=max(ang), recorded_states=len(tr) + len(rec), min_tension_n=min(tmin_all),
                below_0p95=sum(t < .95 for t in tmin_all), below_2p5=sum(t < 2.5 for t in tmin_all),
                unstable=sum(t['minimum_eigenvalue'] <= 1e-7 for t in tr), max_node_move_mm=float(moves.max()),
                steps_over_5mm=int((moves > 5).sum()), min_clearance_mm=min(q['closed']['clearance_mm'] for q in rec),
                peak_tension_n=max(q['closed']['peak_tension_n'] for q in rec),
                max_offset_mm=max(np.max(np.abs(q['offset_mm'])) for q in rec)), tr, rec


def v2_stats(case):
    s = json.loads((V2 / f'{case}_summary.json').read_text())
    rec = json.loads((V2 / f'{case}.json').read_text()); tr = json.loads((V2 / f'{case}_trace.json').read_text())
    ctrl = [t for t in tr if t['kind'] != 'start']
    tmin = [t['minimum_tension_n'] for t in ctrl] + [q['minimum_tension_n'] for q in rec]
    return dict(settled_max_angle_deg=max(s['settled']['maximum_yaw_error_deg'], s['settled']['maximum_elevation_error_deg']),
                recorded_states=len(ctrl) + len(rec), min_tension_n=min(tmin), below_0p95=sum(t < .95 for t in tmin),
                below_2p5=sum(t < 2.5 for t in tmin), unstable=s['trace']['unstable'] + s['settled']['unstable'],
                failed_checks=s['trace']['failed_checks'] + s['settled']['failed_checks'],
                max_node_move_mm=max(s['trace']['maximum_node_move_mm'], s['settled']['maximum_node_move_mm']),
                steps_over_5mm=sum(t['node_move_mm'] > 5 for t in tr), min_clearance_mm=min(s['trace']['minimum_clearance_mm'], s['settled']['minimum_clearance_mm']),
                peak_tension_n=max(s['trace']['peak_tension_n'], s['settled']['peak_tension_n']), max_offset_mm=s['settled']['maximum_offset_mm'],
                samples_not_settled=s['settled']['samples_not_settled'], pre_control_start_tension_n=s['pre_control_start']['minimum_tension_n'],
                trace_states_by_kind=s['trace_states_by_kind']), tr, rec


def main():
    out = {}; data = {}
    for c in CASES:
        a, tr1, rec1 = v1_stats(c); b, tr2, rec2 = v2_stats(c)
        out[c] = dict(v1=a, v2=b); data[c] = (tr1, rec1, tr2, rec2)
        print(f"{c:12s} v1: angle {a['settled_max_angle_deg']:.3f} minT {a['min_tension_n']:.2f} <0.95 {a['below_0p95']} <2.5 {a['below_2p5']}/{a['recorded_states']} move {a['max_node_move_mm']:.2f} >5mm {a['steps_over_5mm']}")
        print(f"{'':12s} v2: angle {b['settled_max_angle_deg']:.3f} minT {b['min_tension_n']:.2f} <0.95 {b['below_0p95']} <2.5 {b['below_2p5']}/{b['recorded_states']} move {b['max_node_move_mm']:.2f} >5mm {b['steps_over_5mm']} "
              f"unstable {b['unstable']} failed {b['failed_checks']} notsettled {b['samples_not_settled']} clear {b['min_clearance_mm']:.1f} peak {b['peak_tension_n']:.1f} offset {b['max_offset_mm']:.2f}")
    (V2 / 'comparison_v1_v2.json').write_text(json.dumps(out, indent=2))

    INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'; C1, C2 = '#d1495b', '#2a78d6'
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(2, 3, figsize=(14, 7.2))
    for ax, c in zip(axs.ravel(), CASES):
        tr1, rec1, tr2, rec2 = data[c]
        # minimum tension of every recorded state, plotted against the reference sample index
        ax.plot([t['index'] for t in tr1], [t['minimum_tension_n'] for t in tr1], '.', ms=2, color=C1, label='v1 (1.5 N target, single-step arrival)')
        ax.plot([t['index'] for t in tr2 if t['kind'] != 'start'], [t['minimum_tension_n'] for t in tr2 if t['kind'] != 'start'], '.', ms=2, color=C2, label='v2 (3 N target, tension-aware refined path)')
        ax.axhline(.95, color=INK, lw=.8, ls=(0, (4, 3))); ax.axhline(2.5, color=MUTED, lw=.8, ls=(0, (2, 2)))
        ax.text(5, 1.0, '0.95 N acceptance', fontsize=7, color=INK); ax.text(5, 2.55, '2.5 N operating floor', fontsize=7, color=MUTED)
        ax.set_ylim(0, 4.5); ax.set_title(LABEL[c], loc='left', fontsize=9.5)
        ax.set_xlabel('reference sample (straighten, insert, right, return, left, return, withdraw)'); ax.set_ylabel('lowest rope tension, N')
        ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
    axs[0, 0].legend(frameon=False, fontsize=7.5, loc='lower left', markerscale=4)
    ax = axs[1, 2]; x = np.arange(len(CASES))
    ax.bar(x - .2, [out[c]['v1']['max_node_move_mm'] for c in CASES], .38, color=C1, label='v1')
    ax.bar(x + .2, [out[c]['v2']['max_node_move_mm'] for c in CASES], .38, color=C2, label='v2')
    ax.axhline(5, color=INK, lw=.8, ls=(0, (4, 3))); ax.text(-.4, 5.15, '5 mm sampling bound', fontsize=7)
    ax.set_xticks(x, [LABEL[c] for c in CASES], rotation=20, ha='right'); ax.set_ylabel('largest node movement between recorded states, mm')
    ax.set_title('Path refinement', loc='left', fontsize=9.5); ax.legend(frameon=False, fontsize=8); ax.grid(color=GRID, lw=.6, axis='y'); ax.set_axisbelow(True)
    fig.suptitle('Closed-loop round trip: v1 (12 Nov) vs v2 (operating tension enforced, tension-aware arrival, refined path); every recorded state shown',
                 x=.01, ha='left', fontsize=10)
    fig.tight_layout(); fig.savefig(V2 / 'v1_v2_comparison.png', dpi=160); print('saved figure')


if __name__ == '__main__':
    main()
