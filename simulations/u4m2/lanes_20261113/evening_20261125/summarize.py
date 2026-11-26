"""Tables and figure for the 25 Nov evening mission envelope (reads results/ only)."""
import json, sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PREV = HERE.parent / "evening_20261124/results"


def envelope_table(doc, label):
    print(f"\n### {label}: mesh {doc['mesh']['tets']} tets, {doc['mesh']['dofs']} DOF\n")
    print("| G, crown | Peak axial: mission max (step, phase) / step 1,709 | Area-mean axial: max / 1,709 | Peak normal: max / 1,709 "
          "| Area-mean normal: max | Max slip | Guide−land rotation | Socket non-rigid, ends |")
    print("|---|---|---|---|---:|---:|---:|---:|")
    out = []
    for c in doc["cases"]:
        E = {k: v for k, v in c["envelope"].items() if not k.startswith("patch")}
        def mx(q):
            k = max(E, key=lambda k: E[k][q]["max"]); return E[k][q], k
        def at(q):
            return max(E[k][q]["at_1709"] for k in E)
        pa, ka = mx("peak_axial_MPa"); ma, kma = mx("mean_axial_MPa"); pn, kn = mx("peak_normal_MPa"); mn, _ = mx("mean_normal_MPa")
        sl, _ = mx("slip"); rr, _ = mx("rel_rot_deg"); se, _ = mx("sock_end")
        print(f"| {c['G_MPa']:.0f} MPa, {c['crown_mm']} mm | **{pa['max']:.2f}** ({pa['step']}, {pa['phase']}, {ka}) / {at('peak_axial_MPa'):.2f} "
              f"| **{ma['max']:.2f}** ({ma['step']}, {kma}) / {at('mean_axial_MPa'):.2f} | {pn['max']:.1f} ({pn['step']}) / {at('peak_normal_MPa'):.1f} "
              f"| {mn['max']:.2f} | {sl['max'] * 1000:.2f} µm | {rr['max']:.3f}° | {se['max']:.3f} mm |")
        out.append(dict(G=c["G_MPa"], crown=c["crown_mm"], peak_axial=pa, mean_axial=ma, peak_normal=pn,
                        ratio_peak_axial=pa["max"] / at("peak_axial_MPa"), ratio_mean_axial=ma["max"] / at("mean_axial_MPa"),
                        ratio_peak_normal=pn["max"] / at("peak_normal_MPa")))
    for o in out:
        print(f"- G {o['G']:.0f}, crown {o['crown']}: mission/1,709 ratio peak axial {o['ratio_peak_axial']:.3f}, "
              f"mean axial {o['ratio_mean_axial']:.3f}, peak normal {o['ratio_peak_normal']:.3f}")
    return out


def main():
    q5 = json.loads((RES / "mission_envelope.json").read_text())
    envelope_table(q5, "q5")
    q3p = RES / "q3/mission_envelope.json"
    if q3p.exists():
        q3 = json.loads(q3p.read_text())
        envelope_table(q3, "q3")
        print("\nq5 -> q3 change of mission maxima (per land, max over lands):")
        for c5, c3 in zip(q5["cases"], q3["cases"]):
            for q in ("peak_axial_MPa", "mean_axial_MPa", "peak_normal_MPa"):
                m5 = max(v[q]["max"] for k, v in c5["envelope"].items() if not k.startswith("patch"))
                m3 = max(v[q]["max"] for k, v in c3["envelope"].items() if not k.startswith("patch"))
                print(f"  G {c5['G_MPa']:.0f} crown {c5['crown_mm']} {q}: {m5:.2f} -> {m3:.2f} ({(m3 / m5 - 1) * 100:+.1f}%)")
    # figure: per-step max-over-lands peak and area-mean axial shear, G 500 / 1500 uncrowned
    fig, ax = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for G, col in ((500, "C0"), (1500, "C3")):
        d = np.load(RES / f"mission_G{G}_c00.npz")
        lands = sorted({k.split("__")[0] for k in d.files if "@" in k})
        pk = np.max([d[f"{l}__peak"][:, 1] for l in lands], 0)
        mn = np.max([d[f"{l}__mean"][:, 1] for l in lands], 0)
        ax[0].plot(pk, col, lw=0.8, label=f"G = {G} MPa, uncrowned")
        ax[1].plot(mn, col, lw=0.8, label=f"G = {G} MPa, uncrowned")
        phase = d["phase"]
    sw = RES / "probe_sweep.json"
    if sw.exists():
        S = json.loads(sw.read_text())
        for cr, st, col, ls in ((0.0, -12, "C0", "-"), (0.0, 12, "C1", "-"), (0.06, -12, "C2", "--"), (0.06, 12, "C4", "--")):
            rr = [r for r in S["rows"] if r["crown_mm"] == cr and r["station_mm"] == st]
            ax[2].plot([r["step"] for r in rr], [r["min_gap_tilted_mm"] for r in rr], col, ls=ls, lw=0.8,
                       label=f"{'crowned' if cr else 'uncrowned'}, z = {st:+d} mm")
        ax[2].axhline(0.025, color="k", lw=0.6, ls=":"); ax[2].set_ylabel("worst gap of 26 tilts\n±0.2° (mm)")
        ax[2].legend(fontsize=7, ncol=2)
    for b in np.flatnonzero(np.diff(phase)) + 0.5:
        for a_ in ax: a_.axvline(b, color="0.8", lw=0.5)
    ax[0].set_ylabel("max land-edge peak\naxial shear (MPa)"); ax[1].set_ylabel("max area-mean\naxial shear (MPa)")
    ax[0].axvline(1709, color="k", lw=0.6, ls="--"); ax[0].legend(fontsize=7); ax[2].set_xlabel("mission step")
    ax[0].set_title("Bonded M6 guides over the 500 g yaw/pitch mission (linear solid body, q5 mesh, superposition)")
    fig.tight_layout(); fig.savefig(RES / "mission_envelope.png", dpi=110)


if __name__ == "__main__":
    main()
