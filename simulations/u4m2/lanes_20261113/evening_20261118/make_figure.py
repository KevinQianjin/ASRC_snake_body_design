"""Seat-clearance figure from envelope/envelope_0p025.npz. Run from this folder."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
d = np.load(HERE / "envelope/envelope_0p025.npz")
PURE, HOLD = "#2a78d6", "#eb6834"
INK, MUTED = "#0b0b0b", "#52514e"


def group(prefix_set, key):
    keys = [k for k in d.files if k.endswith("__" + key) and k.split("@")[0] in prefix_set]
    return np.concatenate([d[k] for k in keys])


pure = {"bend67.5", "bend0"}
hold = {"146", "141", "47", "64"}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED})
fig, ax = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)

# (a) V3 definition: radial gap versus plate height z.
for label, keys, c in (("Pure bend 96.2°", pure, PURE), ("Saved holds 146/141/47/64", hold, HOLD)):
    ax[0].scatter(group(keys, "z"), group(keys, "radial"), s=2, color=c, alpha=0.35, lw=0, label=label, rasterized=True)
z = np.linspace(-1.62, 1.62, 200)
for g0, ls in ((0.15, "-"), (0.25, "--")):
    ax[0].plot(z, g0 + 1.5 * np.maximum(abs(z) - 0.25, 0), color=INK, lw=1.5, ls=ls,
               label=f"V3 wall, {g0:.2f} mm land gap")
ax[0].set_ylim(-0.2, 1.6)
ax[0].set_xlabel("Height in guide plate z (mm)")
ax[0].set_ylabel("Web travel toward radial wall (mm)")
ax[0].set_title("a  V3 relieved socket (radial gap vs plate height)", loc="left", color=INK)

# (b) Bow-tie definition: perpendicular/tangential gap versus along-web distance s.
for label, keys, c in (("Pure bend 96.2°", pure, PURE), ("Saved holds", hold, HOLD)):
    s = group(keys, "s")
    need = np.maximum(group(keys, "perpendicular"), group(keys, "tangential"))
    ax[1].scatter(s, need, s=2, color=c, alpha=0.35, lw=0, label=label, rasterized=True)
s = np.linspace(-4.4, 4.4, 400)
ax[1].plot(s, 0.15 + 0.25 * np.maximum(abs(s) - 0.15, 0), color=INK, lw=1.5,
           label="Bow-tie wall: 0.3 mm land, 0.15 mm, slope 0.25")
ax[1].plot(s, 0.10 + 0.25 * np.maximum(abs(s) - 0.15, 0), color=INK, lw=1.5, ls=":",
           label="Same with 0.10 mm land clearance")
ax[1].set_ylim(-0.2, 1.2)
ax[1].set_xlabel("Distance along web from pin centre s (mm)")
ax[1].set_ylabel("Web travel toward wall (mm)")
ax[1].set_title("b  Bow-tie seat (gap vs along-web distance)", loc="left", color=INK)
for a in ax:
    a.grid(color="#e4e3df", lw=0.6)
    a.spines[["top", "right"]].set_visible(False)
    a.legend(loc="upper center", fontsize=7.5, frameon=False, markerscale=4)
fig.savefig(HERE / "seat_clearance.svg", dpi=150)
fig.savefig(HERE / "seat_clearance.png", dpi=110)
