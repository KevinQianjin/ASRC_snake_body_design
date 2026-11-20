"""Collect the M6 socket screens into one CSV, a summary JSON and a figure.

Inputs are the JSON files written by `m6_socket_screen.py` (coverage screen, 0.5 mm
axial span), the fine governing checks and the tilt sensitivities in `results/`.
"""

import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "cycle_closeout_20261119/results/yaw_pitch"
PARTS = ("guide", "caps", "wire_envelope")
VARIANTS = ("v3", "g020", "g025", "g030")
LABEL = {"v3": "V3, 0.15 mm bond gap", "g020": "0.20 mm", "g025": "0.25 mm (candidate)", "g030": "0.30 mm"}
COLOR = {"v3": "#eb6834", "g020": "#eda100", "g025": "#2a78d6", "g030": "#1baf7a"}


def main(screen_dir, out):
    with gzip.open(ARCHIVE / "station_motion.csv.gz", "rt") as f:
        motion = [r for r in csv.DictReader(f) if r["module"] == "M6"]
    key = lambda r: (int(r["state"]), int(r["station_mm"]))  # noqa: E731
    phase = {key(r): r["phase"] for r in motion}
    lower = {key(r): float(r["minimum_sample_lower_bound_mm"]) for r in motion}
    land = {key(r): float(r["max_land_axial_movement_mm"]) for r in motion}
    rows = []
    for f in sorted(screen_dir.glob("*.json")):
        rows += json.loads(f.read_text())["rows"]
    table = {}
    for r in rows:
        table.setdefault((r["step"], r["station_mm"]), {})[r["variant"]] = r
    if any(set(v) != set(VARIANTS) for v in table.values()):
        raise ValueError("incomplete variant set")
    flat = []
    for (step, st), v in sorted(table.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        row = dict(step=step, station_mm=st, phase=phase[(step, st)],
                   archived_sampled_lower_bound_mm=lower[(step, st)],
                   land_axial_movement_mm=land[(step, st)])
        for k in VARIANTS:
            for p in PARTS:
                row[f"{k}_{p}_gap_mm"] = round(v[k][f"{p}_gap_mm"], 7)
            row[f"{k}_contact"] = any(v[k][f"{p}_contact"] for p in PARTS)
        flat.append(row)
    with (out / "coverage_screen.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, flat[0].keys(), lineterminator="\n")
        w.writeheader()
        w.writerows(flat)
    summary = dict(station_steps=len(flat), variant_rows=len(rows), phases=sorted({r["phase"] for r in flat}))
    for st in (-12, 12):
        sub = [r for r in flat if r["station_mm"] == st]
        unscreened = [lower[(s, st)] for s in range(3405) if (s, st) not in table]
        summary[f"z{st:+d}"] = dict(
            screened_steps=len(sub), unscreened_steps=len(unscreened),
            min_archived_sampled_lower_bound_unscreened_mm=min(unscreened),
            max_land_axial_movement_all_steps_mm=max(land[(s, st)] for s in range(3405)),
            variants={k: dict(
                min_guide_gap_mm=min(r[f"{k}_guide_gap_mm"] for r in sub),
                min_any_part_gap_mm=min(min(r[f"{k}_{p}_gap_mm"] for p in PARTS) for r in sub),
                worst_step=min(sub, key=lambda r: r[f"{k}_guide_gap_mm"])["step"],
                contacts=sum(r[f"{k}_contact"] for r in sub),
                min_increase_over_v3_mm=min(r[f"{k}_guide_gap_mm"] - r["v3_guide_gap_mm"] for r in sub),
            ) for k in VARIANTS})
    # discrepancy between archived sampled bounds and exact triangle distances (0.5 mm span)
    d = [r["archived_sampled_lower_bound_mm"] - r["v3_guide_gap_mm"] for r in flat]
    summary["max_exact_below_archived_sampled_bound_mm"] = max(d)
    (out / "coverage_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    tilt = {st: json.loads((out / f"tilt_{n}.json").read_text()) for st, n in
            ((-12, "minus12_step1710"), (12, "plus12_step1709"))}
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw=dict(width_ratios=[2.2, 1, 1]))
    sub = sorted([r for r in flat if r["station_mm"] == -12], key=lambda r: r["step"])
    s = np.array([r["step"] for r in sub])
    for k in VARIANTS:
        y = np.array([min(r[f"{k}_{p}_gap_mm"] for p in PARTS) for r in sub])
        ax[0].plot(s, y * 1000, "o", ms=3, color=COLOR[k], label=LABEL[k])
    ax[0].set(xlabel="Archived motion step (0 = loaded startup, 3,404 = end of withdrawal)",
              ylabel="Smallest guide/cap/wire-to-web gap (µm)",
              title=f"M6 z = −12 mm: exact triangle gap over {len(sub)} screened steps")
    ax[0].axhline(0, color="#888", lw=1)
    ax[0].legend(title="Outer-socket land bond gap", frameon=False, fontsize=9)
    for i, st in enumerate((-12, 12)):
        rows_t = tilt[st]["rows"]
        for k, ls in (("V3", "-"), ("bond_gap_0p25", "-")):
            for axis, mk in (("CAD_x", "o"), ("CAD_y", "s")):
                r = sorted([x for x in rows_t if x["variant"] == k and x["axis"] == axis], key=lambda x: x["angle_deg"])
                a = [x["angle_deg"] for x in r]
                g = [min(x[f"{p}_gap_mm"] for p in PARTS) * 1000 for x in r]
                c = COLOR["v3" if k == "V3" else "g025"]
                ax[i + 1].plot(a, g, ls, marker=mk, ms=4, lw=1.5, color=c,
                               label=f"{'V3' if k == 'V3' else '0.25 mm'}, tilt about {axis.replace('_', ' ')}")
        ax[i + 1].axhline(0, color="#888", lw=1)
        ax[i + 1].set(xlabel="Rigid guide tilt (deg)", ylabel="Smallest gap (µm); 0 = contact",
                      title=f"M6 z = {st:+d} mm, step {tilt[st]['step']}")
    ax[2].legend(frameon=False, fontsize=8)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
        a.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "m6_socket_gap.png", dpi=150)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--screen", type=Path, default=HERE / "results/screen")
    p.add_argument("--out", type=Path, default=HERE / "results")
    a = p.parse_args()
    main(a.screen, a.out)
