"""Per-step rod rotations for the whole archived 500 g yaw/pitch mission (3,405 states).

For every motion state this stores what ``evening_20261124/body_bond.rod_rotations`` returns:
the rod's relative D0 -> D1 end rotation (rotation vector, D0 frame) and the local rotations over
[st - 12, st + 12] mm at the two guide stations, plus the archived station wrenches. These are the
only step-dependent inputs of the linear bonded-body model, so ``mission_envelope.py`` can
superpose unit solutions instead of solving 3,405 systems. Output: results/rod_steps.npz.
"""
import sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261124"))
import body_bond as BB  # noqa: E402

_rod = _zs = None


def _init():
    global _rod, _zs
    _rod, _zs, _ = BB.CB.load_motion()


def one(s):
    r = BB.rod_rotations(_rod, _rod.kinematic_metrics(_zs[s])[1])
    return s, r["end_rotvec"], r["local"][-12], r["local"][12]


def main():
    t0 = time.monotonic()
    rod, zs, _ = BB.CB.load_motion()
    n = len(zs)
    end = np.zeros((n, 3)); loc = np.zeros((n, 2, 3))
    with Pool(4, initializer=_init) as p:
        for k, (s, e, a, b) in enumerate(p.imap_unordered(one, range(n), chunksize=16)):
            end[s] = e; loc[s, 0] = a; loc[s, 1] = b
            if k % 500 == 0:
                print(k, f"{time.monotonic() - t0:.0f}s", flush=True)
    W = np.stack([BB.CB.station_wrenches("M6", st) for st in BB.STATIONS], 1)  # (n, 2, 6)
    np.savez_compressed(HERE / "results/rod_steps.npz", end_rotvec=end, local_rotvec=loc,
                        stations_mm=np.array(BB.STATIONS), station_wrench=W)
    print("done", f"{time.monotonic() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
