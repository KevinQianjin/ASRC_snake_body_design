"""Export eight simultaneous guide loads at every full-cycle step in each guide's CAD frame."""

import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np

from replay import plant
from guide_loads import STATIONS, record


def run(src):
    rod, _ = plant()
    with gzip.open(src / "motion_trace.json.gz", "rt") as f:
        trace = json.load(f)
    with np.load(src / "controller_states.npz") as f:
        zs = f["motion_z"]
        ts = f["motion_tensions_N"].reshape(-1, 3, 4)
    if len(trace) != len(zs) or len(ts) != len(zs):
        raise ValueError("Guide loads and controller states are not aligned")
    cache = {}
    groups = None
    rows = []
    hole = []
    joint = []
    worst_balance = 0.0
    for i, (z, T, r) in enumerate(zip(zs, ts, trace)):
        key = z.tobytes() + T.tobytes()
        if key not in cache:
            tags, h, j, resid, _ = record(rod.base, rod.profiles, z, T, True)
            cache[key] = h, j, resid
            if groups is None:
                canonical = tags
                groups = [
                    [k for k, t in enumerate(tags) if t[:2] == station]
                    for station in STATIONS
                ]
            if tags != canonical:
                raise ValueError("Hole index changed")
        h, j, wall = cache[key]
        worst_balance = max(worst_balance, wall)
        hole.append(h)
        joint.append(j)
        for (module, station), indices in zip(STATIONS, groups):
            v = h[indices].sum(axis=0)
            row = dict(
                step=i,
                target_index=r["index"],
                phase=r["phase"],
                module=module,
                station_mm=station,
            )
            row.update({f"force_{axis}_N": x for axis, x in zip("xyz", v[0])})
            row.update({f"moment_{axis}_Nmm": x for axis, x in zip("xyz", v[1])})
            row.update(force_N=np.linalg.norm(v[0]), moment_Nmm=np.linalg.norm(v[1]))
            rows.append(row)
    with gzip.open(src / "guide_station_loads.csv.gz", "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    np.savez_compressed(
        src / "guide_hole_loads.npz",
        step=np.arange(len(zs)),
        module=[t[0] for t in canonical],
        station_mm=[t[1] for t in canonical],
        lane=[t[2] for t in canonical],
        direction=[t[3] for t in canonical],
        local_wrench_CAD=np.array(hole),
        shared_wall_wrench_CAD=np.array(joint),
    )

    def extremes(group):
        return {
            name: max(group, key=lambda r: r[name])
            for name in ("force_N", "moment_Nmm")
        }

    info = dict(
        steps=len(zs),
        unique_states=len(cache),
        stations=len(rows),
        holes=len(canonical) * len(zs),
        peak_by_phase={
            ph: extremes([r for r in rows if r["phase"] == ph])
            for ph in dict.fromkeys(r["phase"] for r in rows)
        },
        peak_all=extremes(rows),
        maximum_shared_wall_force_closure_N=worst_balance,
        axes="Local deformed CAD axes. Signed force on the guide in N and moment about its centre in N mm. Hole, station and shared-wall arrays are simultaneous frictionless equilibrium loads.",
    )
    (src / "guide_loads.json").write_text(
        json.dumps(info, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    run(p.parse_args().source)
