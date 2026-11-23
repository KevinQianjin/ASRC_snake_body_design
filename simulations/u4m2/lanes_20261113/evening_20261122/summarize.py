"""Collect the evening 22 Nov 2026 bond results into results/summary.json and one figure."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
runs = json.loads((RES / "bond_duty_nh2-8.json").read_text())["runs"]
runs += json.loads((RES / "rigidland/bond_duty_nh2-8.json").read_text())["runs"]


def peak(r, k):
    e = r["envelope"][k]
    return max(e["max"], -e["min"])


env = [dict(nh=r["nh"], crown_mm=r["crown_mm"], G_MPa=r["G_MPa"], mismatch=r["mismatch"],
            **{f"peak_abs_{k}_MPa": peak(r, k) for k in ("normal", "axial_shear", "cross_shear")},
            axial_site=r["envelope"]["axial_shear"]["max_site"],
            normal_site=r["envelope"]["normal"]["max_site"]) for r in runs]
probe = []
for st in (-12, 12):
    rows = json.loads((RES / f"bond_tilt_probe_z{st}.json").read_text())["rows"]
    for crown in (0.0, 0.06):
        rs = [r for r in rows if r["crown_mm"] == crown]
        ideal = min(r["min_gap_tilted_mm"] for r in rs if r["case"] == "ideal position")
        for mode in ("rod", "midplane", "rigidland"):
            b = [r for r in rs if r["mismatch"] == mode]
            w = min(b, key=lambda r: r["min_gap_tilted_mm"])
            probe.append(dict(station_mm=st, crown_mm=crown, mismatch=mode,
                              ideal_tilt_min_gap_mm=ideal, bond_plus_tilt_min_gap_mm=w["min_gap_tilted_mm"],
                              step=w["step"], G_MPa=w["G_MPa"], worst_tilt=w["worst_tilt"],
                              bond_no_tilt_min_gap_mm=min(r["gap_no_tilt_mm"] for r in b),
                              passes_0p025mm_probe=w["min_gap_tilted_mm"] >= 0.025))
(RES / "summary.json").write_text(json.dumps(dict(mission_envelope=env, bond_plus_tilt=probe), indent=1))

blue, orange = "#2a78d6", "#eb6834"
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
labels = [("rod", "axial_shear"), ("rod", "normal"), ("midplane", "axial_shear"),
          ("midplane", "normal"), ("rigidland", "axial_shear"), ("rigidland", "normal")]
for ax, G in zip(axes, (500.0, 1500.0)):
    for j, (crown, colour, name) in enumerate(((0.0, blue, "0.25 mm uncrowned"), (0.06, orange, "0.06 mm crown"))):
        vals = [next(e[f"peak_abs_{k}_MPa"] for e in env if e["nh"] == 8 and e["crown_mm"] == crown
                     and e["G_MPa"] == G and e["mismatch"] == m) for m, k in labels]
        xs = [i + (j - 0.5) * 0.38 for i in range(len(labels))]
        ax.bar(xs, vals, 0.36, color=colour, label=name)
        for x, v in zip(xs, vals):
            ax.text(x, v * 1.08, f"{v:.1f}", ha="center", fontsize=7, color="#333")
    nh2 = next(e["peak_abs_axial_shear_MPa"] for e in env if e["nh"] == 2 and e["crown_mm"] == 0
               and e["G_MPa"] == G and e["mismatch"] == "rod")
    ax.axhline(nh2, color="#888", lw=1, ls="--")
    ax.text(5.6, nh2 * 1.08, f"Round 2 (2-point) {nh2:.1f}", ha="right", fontsize=7, color="#555")
    ax.set_yscale("log")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([f"{m}\n{k.replace('_', ' ')}" for m, k in labels], fontsize=8)
    ax.set_title(f"Assumed adhesive G = {G:.0f} MPa", fontsize=10)
    ax.grid(axis="y", color="#ddd", lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axes[0].set_ylabel("Mission peak |pad traction| (MPa), 8-point axial")
axes[0].legend(frameon=False, fontsize=8, loc="upper right")
fig.suptitle("M6 bonded-land tractions over 3,405 steps by fit-mismatch model (linear trial adhesive)", fontsize=10)
fig.tight_layout()
fig.savefig(RES / "m6_bond_tractions.png", dpi=150)
print(json.dumps(probe, indent=0)[:400])
