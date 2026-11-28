"""Export the three M6 fixture target cases and a mounting and instrumentation sketch."""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def targets():
    decision = json.loads((RESULTS / "M6_decision.json").read_text())
    baseline = json.loads((RESULTS / "crown_local_0.18.json").read_text())
    source = HERE.parent / "evening_20261125/results/rod_steps.npz"
    with np.load(source) as data:
        rows = [dict(
            step=step, station_z_mm=int(z),
            **{f"D1_relative_rotation_vector_{a}_deg": v
               for a, v in zip("xyz", np.degrees(data["end_rotvec"][step]))},
            **{f"{kind}_{a}_{unit}": v for (kind, a, unit), v in zip(
                ((kind, a, unit) for kind, unit in (("force", "N"), ("moment", "Nmm")) for a in "xyz"),
                data["station_wrench"][step, j])},
        ) for step in decision["convergence"]["selected_steps"] for j, z in enumerate(data["stations_mm"])]
    sites = [dict(site=name, x_mm=x, y_mm=y, z_mm=z)
             for name, (x, y, z) in baseline["gauge_centers_mm"].items()]
    for name, table in (("m6_target_wrenches.csv", rows), ("m6_crown_gauge_locations.csv", sites)):
        with (RESULTS / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, list(table[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(table)


def fixture_sketch():
    ink, grey, green, purple = "#294459", "#dce4e9", "#218679", "#744585"
    fig, ax = plt.subplots(figsize=(11.2, 4.8), layout="constrained")
    ax.set(xlim=(-78, 84), ylim=(-36.5, 31), aspect="equal")
    ax.axis("off")
    for z in (-48, 48):
        ax.add_patch(Rectangle((z - 1.7, -16), 3.4, 32, ec=ink, fc=grey))
    for x0, w in ((-60., 10.3), (49.7, 10.3)):
        ax.add_patch(Rectangle((x0, -11.5), w, 23, ec=ink, fc="#b5cbd7"))
    for z in (-44.9, 40.9):
        ax.plot([z, z], [-17, 23], color=ink, ls="--", lw=.85, alpha=.8)
    ax.annotate("", (40.9, 22), (-44.9, 22), arrowprops={"arrowstyle": "<->", "color": ink})
    ax.text(-2, 24.4, "85.8 mm between model master locations", ha="center", color=ink)
    ax.plot([-48, 48], [0, 0], color="#647688", ls="--", lw=.9)
    ax.plot([-33, 33], [0, 0], color="#3e72a0", lw=2)
    for sign in (-1, 1):
        for y in (-1, 1):
            ax.plot([48 * sign, 34 * sign, 23 * sign, 20.3 * sign, 10 * sign, 0],
                    [11 * y, 12 * y, 8 * y, 9.5 * y, 14 * y, 10 * y],
                    color=ink, lw=1.1, alpha=.8)
        z = sign * 12
        ax.add_patch(Rectangle((z - 2, -16.5), 4, 33, ec=green, fc=green, alpha=.26))
        ax.annotate("", xy=(z, -15), xytext=(z, -25),
                    arrowprops={"arrowstyle": "-|>", "lw": 1.8, "color": green})
        ax.text(z, -30.5, f"z = {z:+d} mm\nApply F and M", ha="center", va="top", fontsize=9, color=green)
        ax.plot(20.3 * sign, 9.5, "o", mfc="white", mec=purple, mew=1.5)
    ax.text(-70, 12.5, "Fixed mount", ha="center", va="bottom", color=ink, fontsize=9)
    ax.plot([-71, -60], [-12, -12], color=ink, lw=1.3)
    ax.text(68, 14, "Rotation stage\nwith free translation", ha="center", va="bottom", color=ink, fontsize=9)
    ax.annotate("", (69, -13.5), (54, -13.5), arrowprops={"arrowstyle": "<->", "color": ink})
    ax.annotate("Optical strain targets\nat both arch crowns", (-20.3, 9.5), (-41, -27),
                ha="center", va="top", fontsize=9, color=purple,
                arrowprops={"arrowstyle": "->", "color": purple})
    ax.annotate("Ø1.80 mm NiTi, 66 mm\nbetween sleeve tips", (28, 0), (41, -25),
                ha="center", va="top", fontsize=9, color=ink,
                arrowprops={"arrowstyle": "->", "color": ink})
    fig.suptitle("M6 bench setup  |  force and rotation application points", color=ink, fontsize=15)
    fig.savefig(RESULTS / "M6_bench_fixture.png", dpi=190)
    plt.close(fig)


if __name__ == "__main__":
    targets()
    fixture_sketch()
