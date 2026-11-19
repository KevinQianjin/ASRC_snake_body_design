"""Render the delivered fixture meshes and the signed coupon measurements in the pin frame."""

import argparse
import json
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch
from bench_inputs import HERE
from fixture_check import fixture
import figures as draw
from matplotlib import pyplot as plt


def family(name):
    if name.startswith(("M2_", "dowel")):
        return "hub_screw"
    if name.startswith("tab_cover"):
        return "hub_lower_sector"
    return {
        "web_coupon": "fork",
        "coupon_carrier": "hub_upper_sector",
        "pin_carriage": "gate",
        "shoulder_pin": "shoulder_pin",
        "threaded_cap": "threaded_cap",
    }[name]


def chart(path):
    moving, fixed = fixture()
    objects = moving | fixed
    fig = plt.figure(figsize=(12.6, 7.45))
    fig.text(
        0.044, 0.947, "M5 seat coupon and load fixture", fontsize=23, weight="bold"
    )
    fig.text(
        0.045,
        0.896,
        "Production shoulder pin and cap in a fixed carriage. The other carriage moves both clamped ends of one PA12 web.",
        size=11,
    )
    fig.text(0.04, 0.828, "Assembled fixture", size=13, weight="bold")
    fig.text(0.53, 0.828, "Section through the pin axis", size=13, weight="bold")
    scene = [(o, family(n)) for n, o in objects.items()]
    img = draw.render(scene, (0, -2.5, 0), (1.05, -1.7, 1.95), 14.5, 840, 660)
    ax = fig.add_axes([0.028, 0.273, 0.49, 0.535])
    ax.imshow(img)
    ax.axis("off")
    ax = fig.add_axes([0.563, 0.39, 0.39, 0.354])
    ax.set_aspect("equal")
    ax.set_xlim(-10, 10)
    ax.set_ylim(-6, 6)
    axes = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
    for name in (
        "coupon_carrier",
        "tab_cover",
        "tab_cover_left",
        "pin_carriage",
        "web_coupon",
        "dowel_0",
        "dowel_1",
        "shoulder_pin",
        "threaded_cap",
    ):
        draw.section_fill(
            ax, objects[name], axes, np.zeros(3), family(name), (-10, -6, 10, 6)
        )
    ax.set_xlabel("Along the coupon, s (mm)")
    ax.set_ylabel("Normal to web, n (mm)")
    ax.plot([-2.7, -2.7, 2.7, 2.7], [4.10, 4.95, 4.95, 4.10], lw=1, color="#394e56")
    ax.text(0, 5.22, "5.4 mm free span", ha="center", size=10)
    ax.grid(False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.046,
        0.258,
        "Two dowels locate the tabs. Four M2 screws clamp them against the carrier.",
        size=9,
    )
    fig.text(
        0.531,
        0.258,
        "The 0.60 mm shaft crosses a 0.64 mm bore waist. The cap closes the seat.",
        size=9,
    )
    labels = [
        ("fork", "Actual web gauge"),
        ("gate", "Fixed pin carriage"),
        ("hub_upper_sector", "Moving carrier"),
        ("hub_lower_sector", "Clamp covers"),
        ("shoulder_pin", "Shoulder pin"),
        ("threaded_cap", "Cap"),
    ]
    fig.legend(
        [Patch(fc=draw.COL[k]) for k, _ in labels],
        [v for _, v in labels],
        loc="lower center",
        bbox_to_anchor=(0.5, 0.135),
        ncol=6,
        frameon=False,
        handlelength=1.1,
        columnspacing=1.3,
    )
    fig.text(
        0.045,
        0.072,
        "Reference frame: s along the rib, p across the rib in its plane, n along the pin. External motion stage and load cell are omitted.",
        size=10,
    )
    fig.savefig(
        path, dpi=145, facecolor="white", metadata={"Software": "ASRC fixture renderer"}
    )
    plt.close(fig)


def curves(data, out):
    d = json.loads(data.read_text())
    fig, axs = plt.subplots(1, 3, figsize=(12.1, 4.55), sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.73, bottom=0.215, wspace=0.13)
    fig.text(
        0.045,
        0.915,
        "Expected reversal travel at three fixture settings",
        fontsize=20,
        weight="bold",
    )
    fig.text(
        0.046,
        0.829,
        "Frictionless, feature-aligned elastic model. Points are static equilibria with the full paired orientation held fixed.",
        fontsize=10.5,
    )
    for ax, record in zip(axs, d["peak_pairs"]):
        name = record["target"]
        vals = [r for r in d["load_states"] if r["target"] == name]
        unit = np.array(
            next(r["applied_force_spn_N"] for r in vals if r["multiplier"] == 1)
        )
        unit /= np.linalg.norm(unit)
        for sign, color in ((-1, "#bc6247"), (1, "#197e79")):
            rows = sorted(
                [r for r in vals if sign * r["multiplier"] > 0],
                key=lambda r: r["multiplier"],
            )
            ax.plot(
                [r["multiplier"] * record["source_force_N"] for r in rows],
                [np.dot(r["relative_translation_spn_mm"], unit) * 1000 for r in rows],
                ".-",
                color=color,
                ms=7,
                lw=1.6,
            )
        ax.axhline(0, color="#a6b1b5", lw=0.65)
        ax.axvline(0, color="#a6b1b5", lw=0.65)
        ax.set_title(
            f"{name}    {record['loaded_reversal_travel_mm'] * 1000:.1f} µm 3-D travel",
            size=11,
        )
        ax.set_xlabel("Signed pin-on-web load (N)")
        ax.grid(alpha=0.19)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].set_ylabel("Holder translation along load axis (µm)")
    fig.text(
        0.047,
        0.06,
        "The zero-load position can lie within the free play. Reapply the same +1 N reference before comparing pre- and post-cycle position.",
        size=9.5,
    )
    draw.save_svg(fig, out)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assembly", type=Path, required=True)
    p.add_argument("--curves", type=Path, required=True)
    a = p.parse_args()
    chart(a.assembly)
    curves(HERE / "results/coupon_fine.json", a.curves)
