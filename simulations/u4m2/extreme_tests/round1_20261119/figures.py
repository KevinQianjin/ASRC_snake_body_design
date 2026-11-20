"""Draw critical sites in registered CAD coordinates and the twelve step-aligned rope forces."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import Normalize
import numpy as np
import trimesh

from study_inputs import CAD, NAMES, read_csv

NAVY = "#16364B"
TEAL = "#007B73"
ORANGE = "#B54C21"
PURPLE = "#5A4182"


def section_xy(ax, path, z, colour):
    mesh = trimesh.load_mesh(path)
    paths = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])
    ax.add_collection(LineCollection(paths[:, :, :2], colors=colour, linewidths=0.8))
    ax.set(
        xlim=(-34, 34),
        ylim=(-34, 34),
        aspect="equal",
        xlabel="CAD x (mm)",
        ylabel="CAD y (mm)",
    )
    ax.spines[["top", "right"]].set_visible(False)


def hotspots(out):
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 8.7), layout="constrained")
    fig.suptitle(
        "Where to instrument the first loaded specimens",
        fontsize=19,
        color=NAVY,
        weight="bold",
    )
    ax = axes[0, 0]
    finest = json.loads((out / "m6_clearance.json").read_text())["resolution"][-1]
    section_xy(ax, CAD / "end_bellmouth_v1/M6_lane_anchorC.stl", -12.25, "#A4B1B7")
    section_xy(ax, CAD / "guides_v3/M6_z-12_guide.stl", -0.2499, TEAL)
    x, y, _ = finest["nominal_body_guide_witness_CAD_mm"][1]
    ax.scatter(x, y, color=ORANGE, s=55, marker="x", linewidth=2, zorder=4)
    ax.annotate(
        f"{finest['nominal_gaps_mm']['guide'] * 1000:.1f} µm",
        xy=(x, y),
        xytext=(-31, 29),
        color=ORANGE,
        arrowprops=dict(arrowstyle="-", color=ORANGE),
    )
    ax.set_title("M6  •  guide at −12 mm", loc="left", color=NAVY, weight="bold")
    ax.text(
        0,
        -0.21,
        "Straight CAD outlines. Cross marks the loaded witness.",
        transform=ax.transAxes,
        fontsize=8,
    )
    for ax, step, station in ((axes[0, 1], 1843, 12), (axes[1, 0], 2059, -12)):
        data = json.loads((out / f"m5_step_{step}_area_0p055.json").read_text())
        section_xy(
            ax,
            CAD / "retained_seat_20261118/parts/M5_machined_body.stl",
            station + 0.001,
            "#A8B3B9",
        )
        rows = [r for r in data["lands"] if r["station_mm"] == station]
        for r in rows:
            angle = np.radians(r["rib_deg"])
            xy = 19.229 * np.array([np.cos(angle), np.sin(angle)])
            force = np.linalg.norm(r["force_N"])
            ax.scatter(
                *xy,
                s=15 + 4.5 * force,
                c=[plt.cm.viridis(Normalize(0, 16)(force))],
                edgecolors="white",
                linewidth=0.5,
            )
            label = xy * 1.26
            ax.text(
                *label,
                f"{force:.2f} N",
                ha="left" if xy[0] > 0 else "right",
                va="center",
                fontsize=8,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=0.4),
            )
        ax.set_title(
            f"M5  •  {station:+d} mm, step {step:,}",
            loc="left",
            color=NAVY,
            weight="bold",
        )
        ax.text(
            0,
            -0.21,
            "Ideal-pivot force magnitudes on the nominal CAD section.",
            transform=ax.transAxes,
            fontsize=8,
        )
    ax = axes[1, 1]
    blades = trimesh.load_mesh(CAD / "guides_v2/U_leaf_springs.stl").split()
    u = json.loads((out / "u_blades.json").read_text())["solutions"]
    fine = [
        r
        for r in u
        if r["converged"]
        and r["gauge_spacing_mm"] == min(v["gauge_spacing_mm"] for v in u)
    ]
    peak = max(fine, key=lambda r: r["peak_tension_strain"])
    for blade in blades:
        xy = blade.vertices
        projected = np.c_[xy[:, 2], 0.82 * xy[:, 1] + 0.57 * xy[:, 0]]
        hot = (np.sign(blade.centroid[0]), np.sign(blade.centroid[1])) == (
            peak["blade_x_sign"],
            peak["blade_y_sign"],
        )
        ax.add_collection(
            PolyCollection(
                projected[blade.faces],
                facecolor=PURPLE if hot else "#B5A8C9",
                edgecolor="none",
            )
        )
        if hot:
            x = peak["peak_tension_z_mm"]
            zside = 1 if x > 0 else -1
            y = projected[zside * xy[:, 2] > 44, 1].mean()
            ax.scatter(x, y, marker="x", s=55, c=ORANGE, linewidths=2, zorder=4)
            ax.annotate(
                f"{peak['module']}, step {peak['step']:,}\n{100 * peak['peak_tension_strain']:.2f}% tensile",
                xy=(x, y),
                xytext=(-30, 5),
                arrowprops=dict(arrowstyle="->", color=ORANGE),
                color=ORANGE,
                fontsize=9,
            )
    ax.set_title(
        "U module  •  four separate NiTi blades", loc="left", color=NAVY, weight="bold"
    )
    ax.set(
        xlim=(-53, 53),
        ylim=(-39, 39),
        xlabel="Module CAD z (mm)",
        ylabel="Projected transverse position (mm)",
        aspect="equal",
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0,
        -0.21,
        "CAD blades in an oblique side view. Rigid-tab strain model.",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.savefig(
        out / "critical_sites.png", dpi=155, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig)


def forces(out):
    cases = read_csv(out / "five_step_poses_and_ropes.csv")
    loads = np.array([[float(r[n + "_N"]) for n in NAMES] for r in cases])
    fig, ax = plt.subplots(figsize=(11, 4), layout="constrained")
    ax.imshow(loads, aspect="auto", cmap="YlGnBu", vmin=2.5, vmax=22)
    for i, j in np.ndindex(loads.shape):
        ax.text(
            j,
            i,
            f"{loads[i, j]:.2f}",
            ha="center",
            va="center",
            color="white" if loads[i, j] > 13.5 else NAVY,
            fontsize=9,
        )
    ax.set_xticks(range(12), [n.replace("_", "\n") for n in NAMES])
    ax.set_yticks(
        range(5),
        [f"{int(r['step']):,}   {r['phase'].replace('_', ' ')}" for r in cases],
    )
    for j in [3.5, 7.5]:
        ax.axvline(j, color="white", lw=3)
    ax.set_title(
        "Twelve simultaneous rope tensions at the five selected steps",
        loc="left",
        color=NAVY,
        fontsize=16,
        weight="bold",
        pad=13,
    )
    ax.set_xlabel(
        "Nominal frictionless equilibrium, newtons. Each group follows up, right, down and left.",
        labelpad=11,
    )
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)
    fig.savefig(
        out / "five_step_tensions.png", dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    hotspots(args.out)
    forces(args.out)
