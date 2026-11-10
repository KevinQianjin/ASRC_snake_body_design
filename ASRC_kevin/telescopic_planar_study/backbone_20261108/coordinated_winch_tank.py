"""3D tank clearance of the coordinated-winch motion, including states between the 5 deg poses.

Every `--every`-th sub-step of coordinated_winch.py (forward sweep) is placed in
the full 3D tank (tank3d_screen.py) with the clamp at depth s, yawing right and
left, and the exact clearance of the 63 mm envelope is measured.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json, argparse
import numpy as np
from backbone import spatial_rod, HERE
from coordinated_winch import RUNS, ANCH
from tank3d_screen import Tank, to_tank

OUT = HERE / 'results'


def main(case, nsub, every, depths):
    runname, variant, pitch = RUNS[case]
    tag = f'coordwinch_{runname}_n{nsub}'
    data = json.loads((OUT / f'{tag}.json').read_text()); st = np.load(OUT / f'{tag}_states.npz')
    r = spatial_rod(4, 2, ANCH, pitch, 8, variant); tank = Tank()
    rows = []
    for q in data['rows'][::every]:
        z = st[f"s{q['step']}_z"]
        _, _, world = r.metrics(z, np.asarray(q['tensions_n']))
        world = world * 1000
        for s in depths:
            for side, sgn in (('right', +1), ('left', -1)):
                g, pt, frac = tank.clearance(to_tank(world, pitch, s, tank.entry_h, sgn))
                rows.append(dict(step=q['step'], yaw_deg=q['yaw_deg'], clamp_s_mm=s, side=side, clearance_mm=g, critical_point_mm=pt.tolist()))
    (OUT / f'{tag}_tank.json').write_text(json.dumps(rows, indent=1, default=float))
    for s in depths:
        for side in ('right', 'left'):
            rr = [x for x in rows if x['clamp_s_mm'] == s and x['side'] == side]
            w = min(rr, key=lambda x: x['clearance_mm'])
            print(f"{case} s={s:g} {side:5s}: {sum(x['clearance_mm'] >= 5 for x in rr)}/{len(rr)} states clear (>=5 mm); "
                  f"worst {w['clearance_mm']:.1f} mm at yaw {w['yaw_deg']:.1f}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', default='E40'); ap.add_argument('--nsub', type=int, default=20)
    ap.add_argument('--every', type=int, default=4); ap.add_argument('--depths', type=float, nargs='+', default=[0, 30])
    a = ap.parse_args(); main(a.case, a.nsub, a.every, a.depths)
