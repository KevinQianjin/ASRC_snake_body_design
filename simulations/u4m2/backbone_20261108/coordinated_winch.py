"""Coordinated winch (rope-length) control along the held-elevation yaw sweep.

Combines min_force_sweep.py (5 deg minimum-force poses) and side_pull.py
(fixed-winch rope model). For every stored 8-cell pose the winch length of each
of the 12 ropes is computed (linear elastic PA6 rope, 1 m free length). The
winches then move ALL rope lengths together, linearly from one pose's values
to the next, in N small sub-steps per 5 deg segment. Each equilibrium is solved
by continuation from the previous state, so the result is the quasi-static
motion a length-controlled drive would produce, including between the poses.

Checks at every sub-step: yaw, world head elevation, head movement per
sub-step (snap-through detector), rope tensions (slack = 0 N), strain,
geometry limits, fixed-winch stability. At the end of each segment the state
is compared with the stored pose. Optionally the sweep is driven backwards
(--reverse) to check reversibility (no hysteresis between branches).

Free space; tank clearance of the intermediate states is checked separately
(coordinated_winch_tank.py). Friction, winch dynamics and NiTi hysteresis are
not modelled.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse
import numpy as np
from backbone import spatial_rod, HERE
from side_pull import Winch

OUT = HERE / 'results'
ANCH = [4, 5, 6]


def load_poses(run):
    st = np.load(OUT / f'{run}_states.npz')
    yaws = sorted(float(k[1:-3]) for k in st.files if k.endswith('_z8'))
    return [(y, st[f'y{y:g}_z8'], st[f'y{y:g}_T8']) for y in yaws]


def run(runname, variant, pitch, nsub, reverse):
    r = spatial_rod(4, 2, ANCH, pitch, 8, variant)
    poses = load_poses(runname)
    # Winch lengths of every pose, and a self-check that each stored pose is a winch equilibrium.
    Rs = []
    for y, z, T in poses:
        w = Winch(r, z, T); Rs.append(w.R.copy())
    order = list(range(len(poses)))
    if reverse:
        order = order[::-1]
    y0, z, T0 = poses[order[0]]
    w = Winch(r, z, T0)
    rows, states, prev_head = [], {}, None
    seg_end = []
    step = 0

    def record(zc, Tc, seg_from, seg_to, frac):
        nonlocal prev_head, step
        m, _, _ = r.metrics(zc, Tc, stability=True)
        head = np.array(m['head_world_mm'])
        jump = None if prev_head is None else float(np.linalg.norm(head - prev_head))
        prev_head = head
        rows.append(dict(step=step, from_yaw=seg_from, to_yaw=seg_to, fraction=frac,
                         commanded_yaw_deg=seg_from + (seg_to - seg_from) * frac,
                         yaw_deg=m['yaw_deg'], world_elevation_deg=m['world_elevation_deg'], head_world_mm=m['head_world_mm'],
                         head_move_mm=jump, tensions_n=np.asarray(Tc).tolist(), min_tension_n=float(np.min(Tc)),
                         peak_n=float(np.max(Tc)), max_strain=m['max_abs_axial_strain'], geometry_pass=m['geometry_pass'],
                         stable=m['stable_fixed_winch'], fixed_winch_eig=m['minimum_fixed_winch_eigenvalue'],
                         twist_deg=m['total_material_twist_deg']))
        states[f's{step}_z'] = zc
        step += 1
        return m

    record(z, T0, y0, y0, 0.)
    failed = None
    for a, b in zip(order[:-1], order[1:]):
        ya, yb = poses[a][0], poses[b][0]
        for k in range(1, nsub + 1):
            w.R = Rs[a] + (Rs[b] - Rs[a]) * (k / nsub)
            zn, Tn = w.solve(z)
            if zn is None:
                failed = dict(from_yaw=ya, to_yaw=yb, fraction=k / nsub, reason='no converged equilibrium from previous state')
                break
            z = zn
            m = record(z, Tn, ya, yb, k / nsub)
        if failed:
            print(f'{runname}: STOP between {ya:g} and {yb:g} deg: {failed["reason"]}', flush=True)
            break
        # Compare with the stored pose b.
        mb, _, _ = r.metrics(poses[b][1], poses[b][2])
        dh = float(np.linalg.norm(np.array(m['head_world_mm']) - np.array(mb['head_world_mm'])))
        seg_end.append(dict(yaw=yb, yaw_error_deg=m['yaw_deg'] - mb['yaw_deg'], head_error_mm=dh,
                            elevation_deg=m['world_elevation_deg'], stored_elevation_deg=mb['world_elevation_deg'],
                            max_tension_error_n=float(np.max(np.abs(np.asarray(rows[-1]['tensions_n']) - poses[b][2])))))
        seg = [q for q in rows if q['from_yaw'] == ya and q['to_yaw'] == yb]
        print(f"{runname}{' rev' if reverse else ''}: {ya:5.0f} -> {yb:5.0f}  elev {min(q['world_elevation_deg'] for q in seg):5.1f}..{max(q['world_elevation_deg'] for q in seg):5.1f}  "
              f"max move {max(q['head_move_mm'] for q in seg):5.2f} mm  min T {min(q['min_tension_n'] for q in seg):4.2f}  peak T {max(q['peak_n'] for q in seg):5.1f}  "
              f"stable {all(q['stable'] for q in seg)}  geom {all(q['geometry_pass'] for q in seg)}  end: yaw err {seg_end[-1]['yaw_error_deg']:+.2f} head err {dh:.1f} mm", flush=True)
    tag = f'coordwinch_{runname}_n{nsub}' + ('_rev' if reverse else '')
    (OUT / f'{tag}.json').write_text(json.dumps(dict(run=runname, variant=variant, pitch_deg=pitch, substeps=nsub, reverse=reverse,
                                                      failed=failed, segment_ends=seg_end, rows=rows), indent=1, default=float))
    np.savez_compressed(OUT / f'{tag}_states.npz', **states)
    ok = [q for q in rows]
    mv = [q['head_move_mm'] for q in ok if q['head_move_mm'] is not None]
    print(f"SUMMARY {tag}: steps {len(ok)}  yaw {min(q['yaw_deg'] for q in ok):.1f}..{max(q['yaw_deg'] for q in ok):.1f}  "
          f"elev {min(q['world_elevation_deg'] for q in ok):.2f}..{max(q['world_elevation_deg'] for q in ok):.2f}  max head move/sub-step {max(mv):.2f} mm (median {np.median(mv):.2f})  "
          f"min rope T {min(q['min_tension_n'] for q in ok):.2f} N  peak {max(q['peak_n'] for q in ok):.1f} N  all stable {all(q['stable'] for q in ok)}  "
          f"all geometry {all(q['geometry_pass'] for q in ok)}  min eig {min(q['fixed_winch_eig'] for q in ok):.3f}  failed {failed}", flush=True)


RUNS = {'E40': ('minforce_niti18_E40_p20_a456_pre1_exact_smooth1', 'niti18_E40', 20),
        'E75': ('minforce_niti18_E75_p20_a456_pre1_exact_smooth1', 'niti18_E75', 20)}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', default='E40', choices=list(RUNS))
    ap.add_argument('--nsub', type=int, default=20, help='winch sub-steps per 5 deg segment')
    ap.add_argument('--reverse', action='store_true')
    a = ap.parse_args()
    run(*RUNS[a.case], a.nsub, a.reverse)
