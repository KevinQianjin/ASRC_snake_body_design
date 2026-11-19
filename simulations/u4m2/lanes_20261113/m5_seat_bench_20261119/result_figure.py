"""Show the actual section of the hub cut and its effect on assembled clearances."""

import argparse
import json
from pathlib import Path

import numpy as np
from bench_inputs import CAD
from clearance import b
import figures as draw
from matplotlib import pyplot as plt
from matplotlib.patches import Patch


def figure(source, out):
    rows = json.loads(source.read_text())["stations"]
    fig = plt.figure(figsize=(12.1, 5.0))
    fig.text(
        0.047,
        0.919,
        "A small inner-edge cut moves the closest approach",
        size=20,
        weight="bold",
    )
    fig.text(
        0.048,
        0.838,
        "Retained M5 guide at ±12 mm  |  actual hub CAD section and nominal coupled-equilibrium distances",
        size=10.5,
    )
    ax = fig.add_axes([0.074, 0.24, 0.30, 0.49])
    angle = np.radians(-11.4)
    er = np.array([np.cos(angle), np.sin(angle), 0])
    ez = np.array([0, 0, 1])
    axes = np.stack([er, ez, np.cross(er, ez)])
    box = (7.70, 1.27, 8.10, 1.67)
    for part, k in [
        ("retained_seat_20261118", "fork"),
        ("m5_hub_relief_20261119", "gate"),
    ]:
        obj = b.load(CAD.parent / part / "parts/hub_upper_sector.stl")
        draw.section_fill(ax, obj, axes, np.zeros(3), k, box)
    ax.set(
        xlim=(box[0], box[2]),
        ylim=(box[1], box[3]),
        xlabel="Radius (mm)",
        ylabel="Axial position (mm)",
    )
    ax.set_aspect("equal")
    ax.set_title("Upper hub sector at −11.4°", size=11)
    ax = fig.add_axes([0.49, 0.245, 0.475, 0.48])
    names = ["bend67.5", "bend0", "146", "141", "47", "64"]
    for offset, v, color in (
        (-0.15, "original", draw.COL["fork"]),
        (0.15, "relieved", draw.COL["gate"]),
    ):
        vlist = [
            min(r[v]["nearest_unintended"]["gap_mm"] for r in rows if r["case"] == n)
            for n in names
        ]
        ax.bar(np.arange(len(names)) + offset, vlist, width=0.30, color=color)
        for i, h in enumerate(vlist):
            if i < 2 and v == "relieved":
                ax.text(i + offset, h + 0.0015, f"{h:.3f}", ha="center", size=8)
    ax.set_xticks(
        range(len(names)), ["Bend\n67.5°", "Bend\n0°", "146", "141", "47", "64"]
    )
    ax.set_ylabel("Closest unintended gap (mm)")
    ax.set_title("Whole module, smaller of both station gaps", size=11)
    ax.grid(axis="y", alpha=0.21)
    ax.spines[["right", "top"]].set_visible(False)
    fig.legend(
        [Patch(fc=draw.COL["fork"]), Patch(fc=draw.COL["gate"])],
        ["Original hub edge", "0.15 mm chamfer"],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.52, 0.115),
    )
    fig.text(
        0.047,
        0.053,
        "Four saved 500 g holds and two prescribed pure bends. Distances exclude the intended pin and thrust-cap bearing interfaces.",
        size=9.5,
    )
    draw.save_svg(fig, out)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    figure(a.source, a.out)
