"""Combine the coverage screen and the low-margin closure screen (V3 vs 0.25 mm candidate).

Writes results/closure_summary.json: per station and phase, the smallest exact gap of
each variant over every exactly checked step, and the archived sampled lower bound of
the steps that remain unchecked.
"""

import csv
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "cycle_closeout_20261119/results/yaw_pitch"
PARTS = ("guide", "caps", "wire_envelope")
NAME = {"v3": "V3", "g025": "bond_gap_0p25", "V3": "V3", "bond_gap_0p25": "bond_gap_0p25"}


def main():
    with gzip.open(ARCHIVE / "station_motion.csv.gz", "rt") as f:
        motion = [r for r in csv.DictReader(f) if r["module"] == "M6" and abs(int(r["station_mm"])) == 12]
    phase = {(int(r["state"]), int(r["station_mm"])): r["phase"] for r in motion}
    lower = {(int(r["state"]), int(r["station_mm"])): float(r["minimum_sample_lower_bound_mm"]) for r in motion}
    best = {}
    for f in sorted((HERE / "results/screen").glob("*.json")) + sorted((HERE / "results/closure").glob("*.json")):
        for r in json.loads(f.read_text())["rows"]:
            if r["variant"] not in NAME:
                continue
            k = (r["step"], r["station_mm"])
            gap = min(r[f"{p}_gap_mm"] for p in PARTS)
            hit = any(r[f"{p}_contact"] for p in PARTS)
            best.setdefault(k, {})[NAME[r["variant"]]] = (gap, hit)
    out = {}
    for st in (-12, 12):
        rows = {k: v for k, v in best.items() if k[1] == st}
        phases = {}
        for (step, _), v in rows.items():
            ph = phases.setdefault(phase[(step, st)], dict(checked=0))
            ph["checked"] += 1
            for name, (gap, hit) in v.items():
                cur = ph.get(name)
                if cur is None or gap < cur["min_gap_mm"]:
                    ph[name] = dict(min_gap_mm=gap, step=step)
                ph.setdefault(name + "_contacts", 0)
                ph[name + "_contacts"] += hit
        unchecked = [lower[(s, st)] for s in range(3405) if (s, st) not in rows]
        out[f"z{st:+d}"] = dict(
            exactly_checked_steps=len(rows),
            unchecked_steps=len(unchecked),
            min_archived_sampled_lower_bound_unchecked_mm=min(unchecked) if unchecked else None,
            candidate_min_gap_mm=min(v["bond_gap_0p25"][0] for v in rows.values()),
            v3_min_gap_mm=min(v["V3"][0] for v in rows.values()),
            candidate_contacts=sum(v["bond_gap_0p25"][1] for v in rows.values()),
            phases=phases,
        )
    (HERE / "results/closure_summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: {x: y for x, y in v.items() if x != "phases"} for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
