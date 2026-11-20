"""Draw the directional limits, conditional pin demand and repeated-duty comparison."""

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from study_context import RESULTS, read, read_csv


def run(root):
    limits = read(root / "strength/limits.json")["paths"]
    pin = read(root / "strength/pin_area_0.1_fine.json")
    fig, axs = plt.subplots(
        1, 3, figsize=(15.4, 5.7), gridspec_kw={"width_ratios": [1.12, 1, 1]}
    )
    ink = "#172d43"
    blue = "#096581"
    red = "#b64b31"
    muted = "#596a76"
    for ax in axs:
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.18)
    ax = axs[0]
    primary = [
        next(r for r in limits if r["path"] == p)
        for p in ("right", "left", "up", "down")
    ]

    def travel(r, key):
        return abs(r[key] - (0 if r["path"] in ("right", "left") else 20))

    x = np.arange(4)
    ax.bar(
        x,
        [travel(r, "rod_last_deg") for r in primary],
        width=0.6,
        color="#c5d0d6",
        label="Rod and controller",
    )
    bars = ax.bar(
        x,
        [travel(r, "screened_last_deg") for r in primary],
        width=0.38,
        color=blue,
        label="With guide / rope CAD",
    )
    ax.bar_label(bars, fmt="%.0f°", padding=3, fontsize=9, color=ink)
    ax.set_xticks(x, ["Right", "Left", "Up", "Down"])
    ax.set_ylabel("Heading or meridian travel from neutral (°)")
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    ax.set_title(
        "Reversible 8-cell steering travel",
        loc="left",
        weight="bold",
        color=ink,
        pad=13,
    )
    ax = axs[1]
    pts = pin["rows"]
    ax.plot(
        [-r["yaw_deg"] for r in pts],
        [r["peak_pin_bending_MPa"] for r in pts],
        "-o",
        ms=4,
        color=blue,
        label="Fixed +12 mm pivot",
    )
    ax.axhline(
        pin["reference_yield_MPa"], ls="--", color=red, label="205 MPa reference yield"
    )
    ax.set_xlabel("Leftward yaw magnitude at +20° elevation (°)")
    ax.set_ylabel("Elastic shaft bending demand (MPa)")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(
        "M5 pin under service load", loc="left", weight="bold", color=ink, pad=13
    )
    ax = axs[2]
    wear = read_csv(root / "fatigue/wear.csv.gz")
    colors = [muted, blue, red, "#327945"]
    variants = ["original", "matched", "mismatched", "active_matched"]
    for i, (n, color) in enumerate(zip(variants, colors, strict=True)):
        r = [r for r in wear if r["variant"] == n and r["block"] == "second_with_reset"]
        val = max(float(s["material_travel_mm"]) for s in r) / 1000
        ax.bar(i, val, width=0.58, color=color)
        ax.annotate(
            f"{val:.3f} m",
            xy=(i, val),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=ink,
        )
    ax.set_xticks(
        range(4),
        ["Original", "Matched\ntake-up", "Mismatched\ntake-up", "Active\nreset"],
    )
    ax.set_ylabel("Largest single-rope material travel per block (m)")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.17)
    ax.set_title(
        "Wear exposure over one block", loc="left", weight="bold", color=ink, pad=13
    )
    fig.suptitle(
        "500 g inspection front in free space and repeated service",
        x=0.055,
        y=0.97,
        ha="left",
        color=ink,
        fontsize=19,
        weight="bold",
    )
    fig.text(
        0.055,
        0.045,
        "Neutral elevation +20°. Steering limits use sampled CAD. Installed pin strength and rope endurance remain unmeasured. Each duty block includes a reset.",
        fontsize=9,
        color=muted,
    )
    fig.subplots_adjust(left=0.06, right=0.98, top=0.80, bottom=0.22, wspace=0.48)
    fig.savefig(
        root / "free_space_and_duty.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
