"""Winch command table for the coordinated yaw sweep: rope pull-in (mm, relative to the
straight 0 deg pose; positive = reeled in) for each of the 12 ropes at every 5 deg pose."""
import json, csv
import numpy as np
from backbone import spatial_rod, HERE
from coordinated_winch import RUNS, ANCH, load_poses
from side_pull import Winch

OUT = HERE / 'results'
DIRS = ['up', 'right', 'down', 'left']
for case, (run, variant, pitch) in RUNS.items():
    r = spatial_rod(4, 2, ANCH, pitch, 8, variant)
    poses = load_poses(run)
    R = np.array([Winch(r, z, T).R for _, z, T in poses])            # (n, 3, 4) unstretched lengths, m
    pull = (R[0] - R) * 1000                                          # mm reeled in relative to yaw 0
    yaw = np.array([p[0] for p in poses])
    names = [f'a{a}_{d}' for a in ANCH for d in DIRS]
    with open(OUT / f'coordwinch_{case}_winch_table.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['yaw_deg'] + [n + '_pull_in_mm' for n in names] + [n + '_tension_n' for n in names])
        for i, (y, z, T) in enumerate(poses):
            w.writerow([f'{y:g}'] + [f'{v:.3f}' for v in pull[i].ravel()] + [f'{v:.3f}' for v in np.asarray(T).ravel()])
    P = pull.reshape(len(yaw), -1)
    rate = np.abs(np.diff(P, axis=0)) / np.diff(yaw)[:, None]
    info = dict(case=case, ropes=names, travel_range_mm={n: [float(P[:, j].min()), float(P[:, j].max())] for j, n in enumerate(names)},
                max_rate_mm_per_deg={n: float(rate[:, j].max()) for j, n in enumerate(names)},
                largest_travel_mm=float(np.ptp(P, axis=0).max()), largest_rate_mm_per_deg=float(rate.max()))
    (OUT / f'coordwinch_{case}_winch_travel.json').write_text(json.dumps(info, indent=1))
    print(case, 'largest winch travel %.1f mm, largest rate %.2f mm/deg' % (info['largest_travel_mm'], info['largest_rate_mm_per_deg']))
    for j, n in enumerate(names):
        print(f'   {n:9s} travel {P[:, j].min():7.1f} .. {P[:, j].max():6.1f} mm   max rate {rate[:, j].max():.2f} mm/deg')
