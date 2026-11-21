"""Exact first-contact tilt of M6 outer-station guide variants (evening, 20 Nov 2026).

Extends the 19 Nov `m6_tilt.py` grid (0.05 deg steps) with a bisection of the
first-contact rigid tilt about each CAD axis and sign, to `--tol` degrees, at one
archived 500 g mission step. Guide, caps and wire envelope rotate together about the
station origin relative to the deformed M6 body (actual STL, axially refined).
Also reports the exact gap (= remaining rigid translation allowance along the
witness direction) at the +/-0.2 deg reference tilt. Rigid-body sensitivity only:
no bond compliance, guide bending or as-printed form error.
"""

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261119"))

import fcl  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from m6_socket_screen import CAD, deformed_body, gap, load_motion, load_variant, mesh_model, save  # noqa: E402
from m6_tilt import rotation  # noqa: E402


def min_gap(body, objs, R):
    out = {}
    for p, o in objs.items():
        o.setTransform(fcl.Transform(R, np.zeros(3)))
        out[p] = gap(body, o)[0]
    return min(out.values()), out


def run(a):
    t0 = time.time()
    rod, states, _ = load_motion()
    module = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    variants = {k: Path(v).resolve() for k, v in (s.split("=", 1) for s in a.variant)}
    meshes = {k: load_variant(v, a.station) for k, v in variants.items()}
    bounds = trimesh.util.concatenate([m for p in meshes.values() for m in p.values()]).bounds
    reach = np.radians(a.max_angle) * np.linalg.norm(np.abs(bounds).max(0))
    bounds = (bounds[0] - reach, bounds[1] + reach)
    detail = rod.evaluate(states[a.step], detail=True)[2]
    body, _, kept = deformed_body(module, a.station, bounds, a.spacing, rod, detail)
    rows = []
    for k, parts in meshes.items():
        objs = {p: fcl.CollisionObject(mesh_model(m.vertices, m.faces)) for p, m in parts.items()}
        g0, _ = min_gap(body, objs, np.eye(3))
        for axis in range(3):
            for sign in (-1, 1):
                ref, ref_parts = min_gap(body, objs, rotation(axis, sign * 0.2))
                lo, hi = 0.0, a.max_angle
                if min_gap(body, objs, rotation(axis, sign * hi))[0] > 0:
                    first = None  # clear over the whole bracket
                else:
                    while hi - lo > a.tol:
                        mid = 0.5 * (lo + hi)
                        if min_gap(body, objs, rotation(axis, sign * mid))[0] > 0:
                            lo = mid
                        else:
                            hi = mid
                    first = sign * hi
                rows.append(dict(variant=k, axis="CAD_" + "xyz"[axis], sign=sign, gap_at_0deg_mm=g0,
                                 last_clear_deg=sign * lo if first is not None else sign * a.max_angle,
                                 first_contact_deg=first, gap_at_0p2deg_mm=ref,
                                 part_gaps_at_0p2deg_mm=ref_parts))
        print(k, [(r["axis"], r["sign"], r["first_contact_deg"]) for r in rows if r["variant"] == k],
              f"{time.time()-t0:.0f}s", flush=True)
    save(a.out, dict(script="tilt_bisect.py", step=a.step, station_mm=a.station, spacing_mm=a.spacing,
                     tol_deg=a.tol, max_angle_deg=a.max_angle, crop_extra_mm=reach, kept_triangles=kept,
                     variants={k: str(v) for k, v in variants.items()}, rows=rows, elapsed_s=time.time() - t0))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--variant", nargs="+", required=True)
    p.add_argument("--station", type=int, default=-12)
    p.add_argument("--step", type=int, default=1710)
    p.add_argument("--spacing", type=float, default=0.25)
    p.add_argument("--tol", type=float, default=0.005)
    p.add_argument("--max-angle", type=float, default=1.0)
    run(p.parse_args())
