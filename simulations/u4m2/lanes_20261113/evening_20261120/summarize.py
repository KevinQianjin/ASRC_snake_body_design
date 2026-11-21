"""Summarise the 20 Nov 2026 evening crowned-land study: screen, tilt and bond-layer metrics.

Reads results/screen/shard*.json, results/tilt/*.json and the 19 Nov reference screen;
writes results/summary.json, results/screen_steps.csv and results/m6_crowned_land.png.
"""

import csv
import glob
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
VARIANTS = ("g025", "crown040", "crown060")
CROWNS = {"g025": 0.0, "crown020": 0.02, "crown040": 0.04, "crown060": 0.06}
LAND_HALF, BOND = 0.25, 0.25


def bond_layer(c):
    """Thickness statistics of the land adhesive layer t(z) = 0.25 + c (z/0.25)^2, |z| <= 0.25 mm."""
    z = np.linspace(-LAND_HALF, LAND_HALF, 20001)
    t = BOND + c * (z / LAND_HALF) ** 2
    # Uniform-shear layer stiffness per unit width ~ integral G/t dz (series springs in thickness,
    # parallel along z). Ratio to the uncrowned 0.25 mm layer.
    k = np.trapezoid(1 / t, z) / np.trapezoid(np.full_like(z, 1 / BOND), z)
    return dict(crown_mm=c, mid_land_gap_mm=BOND, land_edge_gap_mm=BOND + c, mean_gap_mm=float(t.mean()),
                shear_stiffness_ratio_vs_uncrowned=float(k),
                nominal_shear_strain_at_0p0545mm_mid=0.0545 / BOND,
                nominal_shear_strain_at_0p0545mm_edge=0.0545 / (BOND + c))


def main():
    rows = []
    for f in sorted(glob.glob(str(RES / "screen/shard*.json"))):
        rows += json.load(open(f))["rows"]
    straight = json.load(open(sorted(glob.glob(str(RES / "screen/shard*.json")))[0]))["straight"]
    steps = {}
    for r in rows:
        key = (r["station_mm"], r["step"])
        g = min(r[f"{p}_gap_mm"] for p in ("guide", "caps", "wire_envelope"))
        steps.setdefault(key, {})[r["variant"]] = dict(min_gap=g, guide=r["guide_gap_mm"], caps=r["caps_gap_mm"],
                                                     wire=r["wire_envelope_gap_mm"],
                                                     contact=any(r[f"{p}_contact"] for p in ("guide", "caps", "wire_envelope")))
    with open(RES / "screen_steps.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["station_mm", "step"] + [f"{v}_{q}" for v in VARIANTS for q in ("guide", "caps", "wire", "contact")])
        for (s, k), d in sorted(steps.items()):
            w.writerow([s, k] + [x for v in VARIANTS for x in (f"{d[v]['guide']:.6f}", f"{d[v]['caps']:.6f}",
                                                              f"{d[v]['wire']:.6f}", int(d[v]["contact"]))])
    screen = {}
    for s in (-12, 12):
        keys = [k for k in steps if k[0] == s]
        per = {}
        for v in VARIANTS:
            vals = [(steps[k][v]["min_gap"], k[1]) for k in keys]
            gain = [steps[k][v]["min_gap"] - steps[k]["g025"]["min_gap"] for k in keys]
            caps = [steps[k][v]["caps"] for k in keys]
            per[v] = dict(steps=len(keys), contacts=sum(steps[k][v]["contact"] for k in keys),
                          min_gap_mm=min(vals)[0], min_step=min(vals)[1],
                          min_gain_vs_g025_mm=min(gain), max_gain_vs_g025_mm=max(gain),
                          min_caps_gap_mm=min(caps),
                          governing_part=min(("guide", "caps", "wire"), key=lambda p: steps[(s, min(vals)[1])][v][p]))
        screen[f"z{s:+d}"] = per
    tilt = {}
    for f in sorted(glob.glob(str(RES / "tilt/bisect_*.json"))):
        d = json.load(open(f))
        st = f"z{d['station_mm']:+d}_step{d['step']}"
        tilt[st] = {}
        for v in CROWNS:
            rs = [r for r in d["rows"] if r["variant"] == v]
            tilt[st][v] = {f"{r['axis']}{'+' if r['sign'] > 0 else '-'}": dict(
                first_contact_deg=r["first_contact_deg"], gap_at_0p2deg_mm=r["gap_at_0p2deg_mm"]) for r in rs}
            xs = [abs(r["first_contact_deg"]) for r in rs if r["first_contact_deg"] is not None]
            tilt[st][v]["governing_first_contact_abs_deg"] = min(xs)
            tilt[st][v]["min_gap_within_0p2deg_mm"] = min(r["gap_at_0p2deg_mm"] for r in rs)
            tilt[st][v]["gap_at_0deg_mm"] = rs[0]["gap_at_0deg_mm"]
    inplane = {}
    for f in sorted(glob.glob(str(RES / "tilt/inplane_*.json"))):
        d = json.load(open(f))
        st = f"z{d['station_mm']:+d}_step{d['step']}"
        inplane[st] = {}
        for v in sorted({r["variant"] for r in d["rows"]}):
            rs = [r for r in d["rows"] if r["variant"] == v and r["axis"] != "CAD_z"]
            m = min(rs, key=lambda r: abs(r["first_contact_deg"]))
            g = min(rs, key=lambda r: r["gap_at_0p2deg_mm"])
            inplane[st][v] = dict(axes_sampled=sorted({r["axis"] for r in rs}),
                                  min_first_contact_deg=m["first_contact_deg"], min_axis=m["axis"],
                                  min_gap_at_0p2deg_mm=g["gap_at_0p2deg_mm"], min_gap_axis=g["axis"], min_gap_sign=g["sign"])
    out = dict(study="M6 crowned bond land, evening 20 Nov 2026", straight=straight, screen=screen, tilt=tilt, tilt_inplane=inplane,
               bond_layer={v: bond_layer(c) for v, c in CROWNS.items()})
    (RES / "summary.json").write_text(json.dumps(out, indent=2) + "\n")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    colors = {"g025": "#5b6b7a", "crown020": "#9db4c9", "crown040": "#2f7fc1", "crown060": "#d1603d"}
    for i, s in enumerate((-12, 12)):
        keys = sorted(k for k in steps if k[0] == s)
        for v in VARIANTS:
            ax[i].plot([k[1] for k in keys], [steps[k][v]["min_gap"] for k in keys], ".", ms=2.5, color=colors[v],
                       label=f"{v} (min {screen[f'z{s:+d}'][v]['min_gap_mm']:.4f} mm)")
        ax[i].set_title(f"M6 z = {s:+d} mm: exact gap on screened mission steps")
        ax[i].set_xlabel("archived mission step"); ax[i].set_ylabel("smallest part-to-body gap (mm)")
        ax[i].set_ylim(bottom=0); ax[i].legend(fontsize=8)
    labels = list(CROWNS)
    for j, st in enumerate(tilt):
        ax[2].plot([CROWNS[v] for v in labels], [tilt[st][v]["governing_first_contact_abs_deg"] for v in labels],
                   "o-", label=st.replace("_", ", "))
    ax[2].axhline(0.2, ls="--", color="k", lw=0.8, label="0.2 deg reference tilt")
    ax[2].set_xlabel("land crown at edge (mm)"); ax[2].set_ylabel("smallest first-contact rigid tilt (deg)")
    ax[2].set_title("Rigid tilt to first contact, CAD axes (bisection)"); ax[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(RES / "m6_crowned_land.png", dpi=130)
    print(json.dumps(dict(screen=screen, tilt={k: {v: t["governing_first_contact_abs_deg"] for v, t in d.items()}
                                               for k, d in tilt.items()}), indent=1))


if __name__ == "__main__":
    main()
