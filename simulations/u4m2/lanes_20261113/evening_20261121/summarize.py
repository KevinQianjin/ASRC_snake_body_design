"""Summarise the 21 November evening M6 full-mission certification (nominal and 0.2 deg tilt)."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119/results/m6_guides/m6_all_steps.csv.gz"
SCREEN20 = HERE.parent / "evening_20261120/results/screen_steps.csv"
P = ["guide_gap_mm", "caps_gap_mm", "wire_envelope_gap_mm"]
PROBE = 0.025  # Round 2 combined probe: 0.025 mm offset with 0.2 deg tilt


def nominal():
    r2 = pd.read_csv(ROUND2)
    scr = pd.read_csv(SCREEN20)
    out, tables = {}, {}
    for st in (-12, 12):
        g = pd.read_csv(RES / f"full/g025_all_steps_{st:+d}.csv.gz")
        c = pd.read_csv(RES / f"full/crown060_all_steps_{st:+d}.csv.gz")
        b = r2[r2.station_mm == st].sort_values("step").reset_index(drop=True)
        s = scr[scr.station_mm == st].set_index("step")
        mg, mc = g[P].min(axis=1), c[P].min(axis=1)
        tables[st] = pd.DataFrame(dict(step=c.step, phase=c.phase, g025=mg, crown060=mc))
        out[str(st)] = dict(
            steps=len(c),
            phases=int(c.phase.nunique()),
            g025_reproduces_round2_max_abs_mm=float(np.abs(g[P].values - b[P].values).max()),
            crown060_matches_20nov_screen_max_abs_mm=float(
                np.abs(c.set_index("step").loc[s.index, "guide_gap_mm"].values - s.crown060_guide.values).max()),
            screen20_steps=len(s),
            new_steps_certified=int(len(c) - len(s)),
            g025_min=[float(mg.min()), int(c.step[mg.idxmin()])],
            crown060_min=[float(mc.min()), int(c.step[mc.idxmin()])],
            crown060_min_outside_screen20=float(mc[~c.step.isin(s.index)].min()),
            crown060_contacts=int((mc <= 0).sum()),
            per_part_gain_min_mm=dict(zip(P, (c[P].values - g[P].values).min(0).round(6).tolist())),
            per_part_gain_max_mm=dict(zip(P, (c[P].values - g[P].values).max(0).round(6).tolist())),
            crown060_phase_minima=c.assign(m=mc).groupby("phase").m.min().round(5).to_dict(),
        )
    return out, tables


def tilt(name):
    out, tables = {}, {}
    for st in (-12, 12):
        files = sorted((RES / "tilt").glob(f"{name}_z{st}_shard*.json"))
        if not files:
            continue
        docs = [json.load(open(f)) for f in files]
        nsh = docs[0]["nshards"]
        rows = [r for d in docs for r in d["rows"]]
        inv = np.asarray(next(d["step_to_shape"] for d in docs if d["step_to_shape"]))
        shapes = pd.DataFrame(rows).set_index("shape").sort_index()
        complete = len(files) == nsh and len(shapes) == docs[0]["unique_shapes_total"]
        steps = shapes.reindex(inv).reset_index(drop=True)
        steps.insert(0, "step", np.arange(len(inv)))
        tables[st] = steps
        tcols = [c for c in shapes.columns if c.startswith(("inplane_", "CAD_z"))]
        worst = steps.loc[steps.min_tilted_gap_mm.idxmin()]
        below = steps[steps.min_tilted_gap_mm < PROBE]
        out[str(st)] = dict(
            shards=f"{len(files)}/{nsh}", unique_shapes=len(shapes), complete=bool(complete),
            steps_covered=int(steps.min_tilted_gap_mm.notna().sum()),
            tilts=len(tcols), angle_deg=docs[0]["angle_deg"], spacing_mm=docs[0]["spacing_mm"],
            crop_faces=docs[0]["crop_faces"],
            exact_queries=sum(d["exact_queries"] for d in docs),
            pruned_queries=sum(d["pruned_queries"] for d in docs),
            elapsed_s=[d["elapsed_s"] for d in docs],
            min_tilted_gap=dict(gap_mm=float(worst.min_tilted_gap_mm), step=int(worst.step),
                                axis=worst.min_axis, sign=int(worst.min_sign), part=worst.min_part),
            contacts_at_tilt=int((steps.min_tilted_gap_mm <= 0).sum()),
            steps_below_probe_0p025mm=int(len(below)),
            steps_below_probe_list=below.step.tolist()[:200],
            per_tilt_min_mm={c: float(shapes[c].min()) for c in tcols},
            limiting_part_counts=steps.min_part.value_counts().to_dict(),
        )
    return out, tables


def figure(nom, tilts):
    fig, ax = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    for k, st in enumerate((-12, 12)):
        a = ax[k]
        t = nom[st]
        a.plot(t.step, t.g025, lw=0.8, color="#888888", label="0.25 mm uncrowned, nominal")
        a.plot(t.step, t.crown060, lw=0.8, color="#1f5fbf", label="0.06 mm crown, nominal")
        for name, color, lab in (("crown060", "#d0701a", "0.06 mm crown, worst of 26 tilts at 0.2°"),
                                 ("g025", "#7a3d9a", "0.25 mm uncrowned, worst of 26 tilts at 0.2°")):
            if st in tilts.get(name, {}):
                s = tilts[name][st]
                a.plot(s.step, s.min_tilted_gap_mm, lw=0.8, color=color, label=lab)
        a.axhline(PROBE, ls="--", lw=0.8, color="k")
        a.axhline(0, lw=0.6, color="k")
        a.set_ylabel(f"z = {st:+d} mm\nexact gap (mm)")
        a.grid(alpha=0.3)
    ax[0].legend(fontsize=7, ncol=2, loc="upper right")
    ax[1].set_xlabel("archived mission step (3,405 states, 11 phases)")
    ax[0].set_title("M6 outer-socket clearance over the full 500 g mission (rigid CAD); dashed: 0.025 mm probe offset")
    fig.tight_layout()
    fig.savefig(RES / "m6_full_mission_tilt.png", dpi=130)


def main():
    nsum, ntab = nominal()
    tsum, ttab = {}, {}
    for name in ("crown060", "g025"):
        s, t = tilt(name)
        if s:
            tsum[name], ttab[name] = s, t
            pd.concat([v.assign(station_mm=k) for k, v in t.items()]).to_csv(
                RES / f"tilt_steps_{name}.csv.gz", index=False, float_format="%.6g")
    figure(ntab, ttab)
    summary = dict(nominal=nsum, tilt_0p2deg=tsum, probe_offset_mm=PROBE)
    (RES / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
