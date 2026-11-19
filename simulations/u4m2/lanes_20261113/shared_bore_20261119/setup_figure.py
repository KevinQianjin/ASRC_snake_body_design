"""Export true local guide setpoints and draw the old and laterally free routes at the common bore."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from shared_bore import ARCHIVE, geometry, load_rod, load_states, solve
from bellmouth_model import sample_span


def run(out, cases):
    design, rod, prof = load_rod()
    saved = load_states(ARCHIVE / "equilibria_states.npz")[0]
    rows = []
    ref = None
    for label, z, t, _ in saved:
        if label not in cases:
            continue
        for i, (ray, (left, right)) in enumerate(geometry(rod, z, t).items()):
            path, solution = solve(left, right, prof, 0.075)
            if label == "64" and ray == "up":
                ref = (left, right, path, solution)
            orig = 28 * np.array(design["rays_cad_xy"][ray])
            for side, g, d in zip(
                ("M5", "M6"), (left, right), solution["endpoint_directions"]
            ):
                # Cell axes point from the shared bore toward the pulling fixture.
                axis = np.array([-d[2], d[1], d[0]]) * (-1 if side == "M5" else 1)
                pos = np.r_[orig + [-g[2], g[1]], g[0]]
                row = dict(hold=label, ray=ray, side=side)
                row.update({f"guide_{k}_mm": v for k, v in zip("xyz", pos)})
                row.update({f"cell_axis_{k}": v for k, v in zip("xyz", axis)})
                row.update(
                    archived_tension_N=t[2, i],
                    shared_wrap_deg=float(np.degrees(solution["absolute_wrap_rad"])),
                )
                rows.append(row)
    if ref is None:
        raise ValueError("Include record 64 for the reference diagram")
    with (out / "fixture_targets.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    left, right, path, solution = ref
    direction = np.array(solution["interface_transverse_mm"])
    direction /= np.linalg.norm(direction)
    old = np.vstack(
        (
            sample_span(left, -1.0, prof[0], 0.035)[::-1],
            sample_span(right, 1.0, prof[1], 0.035)[1:],
        )
    )
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "asrc-shared-bore",
            "text.color": "#203744",
            "axes.labelcolor": "#203744",
        }
    )
    fig, axes = plt.subplots(
        1, 2, figsize=(12.3, 4.65), gridspec_kw={"width_ratios": [2.0, 1]}
    )
    fig.subplots_adjust(top=0.75, bottom=0.23, left=0.065, right=0.98, wspace=0.28)
    fig.text(
        0.04,
        0.925,
        "A 2 mm rope can move sideways through the joint",
        fontsize=19,
        weight="bold",
    )
    fig.text(
        0.042,
        0.835,
        "M5 distal disk to M6 proximal disk  |  C-up rope at fixed-winch hold 64  |  centreline projected onto the interface-offset plane",
        fontsize=10,
    )
    ax = axes[0]
    ax.axvline(0, color="#607584", lw=0.8, ls=":")
    for sgn, (depth, wall, ang, hole, rope) in zip((-1, 1), prof):
        x = np.linspace(0, depth, 301)
        s0 = depth - wall * np.sin(ang)
        r = hole + wall - np.sqrt(wall * wall - np.maximum(x - s0, 0) ** 2)
        for k in (-1, 1):
            ax.fill_between(sgn * x, k * r, k * 2.35, color="#c9c5be", lw=0)
    ax.plot(
        old[:, 0],
        old[:, 1:] @ direction,
        color="#ae655d",
        lw=1.7,
        ls="--",
        label="Previously fixed at bore centre",
    )
    ax.plot(
        path[:, 0],
        path[:, 1:] @ direction,
        color="#0d8277",
        lw=2.3,
        label="Free in the common bore",
    )
    ax.scatter([0], [0.0], s=25, color="#ae655d", zorder=4)
    ax.scatter(
        [0],
        [np.linalg.norm(solution["interface_transverse_mm"])],
        s=28,
        color="#0d8277",
        zorder=4,
    )
    ax.set(
        xlim=(-10, 8),
        ylim=(-2.1, 2.1),
        xlabel="Distance along joint axis (mm)",
        ylabel="Projected transverse offset (mm)",
    )
    ax.legend(loc="lower left", frameon=True, fontsize=8)
    ax.set_title("Local bore section and the two rope centrelines", fontsize=11)
    ax = axes[1]
    a = np.linspace(0, 2 * np.pi, 280)
    ax.fill(1.25 * np.cos(a), 1.25 * np.sin(a), color="#e9e7e3", edgecolor="#989d9b")
    dy, dz = solution["interface_transverse_mm"]
    ax.fill(
        dy + np.cos(a), dz + np.sin(a), color="#c6e7e1", edgecolor="#0d8277", lw=1.6
    )
    ax.plot([0, dy], [0, dz], color="#1d424d", lw=1.5)
    ax.scatter([0, dy], [0, dz], c=["#ae655d", "#0d8277"], s=22)
    ax.set_aspect("equal")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-1.45, 1.45)
    ax.set_xlabel("Transverse y (mm)")
    ax.set_ylabel("Transverse z (mm)")
    ax.set_title(f"At the interface: {np.hypot(dy, dz):.3f} mm offset", fontsize=11)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.043,
        0.058,
        "The model uses a continuous 2.50 mm throat across the joint chamfers. Rope diameter is 2.00 mm. The 3-D clearance check uses both CAD bodies.",
        fontsize=9.5,
    )
    dest = out / "shared_route.svg"
    fig.savefig(dest, metadata={"Date": None}, facecolor="white")
    dest.write_text("\n".join(l.rstrip() for l in dest.read_text().splitlines()) + "\n")
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cases", nargs="+", default=["0", "47", "48", "64", "141", "146"])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out, a.cases)
