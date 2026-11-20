"""Make an installed motion map and full-mission twelve-rope force comparison from the checked tables."""

import argparse
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import input_file, OUT, NAMES, read, read_csv


def run(out):
    table = read_csv(input_file(out, "motion_limits", "pose_steps.csv.gz"))
    paths = read(input_file(out, "motion_limits", "pose_paths.json"))
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.3), sharey=True)
    for ax, depth in zip(axes, (-15, 15, 45)):
        for branch in paths:
            yaw = branch["yaw_deg"]
            end = branch["end_deg"]
            local = [
                r
                for r in table
                if r["leg"] == "out"
                and int(r["yaw_deg"]) == yaw
                and int(r["branch_end_deg"]) == end
            ]
            ax.scatter(
                [yaw] * len(local),
                [float(r["target_pitch_deg"]) for r in local],
                s=11,
                color="#c1c6cd",
                marker=".",
            )
            p = branch["depths"][str(depth)]["last_retraceable_deg"]
            if p is not None:
                ax.plot(
                    [yaw, yaw], [20, p], lw=3.2, color="#137f72", solid_capstyle="butt"
                )
                ax.scatter(yaw, p, color="#10534e", s=12)
            gap_failures = [
                r
                for r in local
                if r["free_pass"] == "True" and float(r[f"gap_depth_{depth}_mm"]) < 5
            ]
            if gap_failures:
                ax.scatter(
                    yaw,
                    float(gap_failures[0]["target_pitch_deg"]),
                    color="#c9473d",
                    marker="x",
                    s=32,
                    zorder=3,
                )
            if branch["depths"][str(depth)]["connector_min_mm"] < 5 and end > 0:
                ax.scatter(
                    yaw,
                    20,
                    facecolors="none",
                    edgecolors="#b1640d",
                    marker="^",
                    s=44,
                    zorder=4,
                )
            unsolved = [r for r in local if r["free_pass"] != "True"]
            if unsolved:
                ax.scatter(
                    yaw,
                    float(unsolved[0]["target_pitch_deg"]),
                    facecolors="none",
                    edgecolors="#704a87",
                    marker="D",
                    s=41,
                    zorder=4,
                )
        ax.axhline(20, color="#78828a", ls=":", lw=0.8)
        ax.set(
            title=f"Clamp {depth:+d} mm",
            xlabel="Yaw (degrees)",
            xticks=[-175, -90, 0, 90, 175],
            ylim=(-98, 98),
            yticks=[-90, -60, -30, 0, 20, 45, 69, 90],
        )
        ax.grid(axis="y", color="#e5e8eb", lw=0.6)
    axes[0].set_ylabel("Commanded elevation (degrees)")
    handles = [
        plt.Line2D(
            [],
            [],
            color="#137f72",
            lw=4,
            label="Contiguous interval with a solved return",
        ),
        plt.Line2D([], [], color="#c1c6cd", marker=".", lw=0, label="Sampled"),
        plt.Line2D(
            [],
            [],
            color="#c9473d",
            marker="x",
            lw=0,
            label="First tank gap below 5 mm",
        ),
    ]
    handles += [
        plt.Line2D(
            [],
            [],
            linestyle="none",
            marker="^",
            markerfacecolor="none",
            markeredgecolor="#b1640d",
            label="Depth connector below 5 mm",
        ),
        plt.Line2D(
            [],
            [],
            linestyle="none",
            marker="D",
            markerfacecolor="none",
            markeredgecolor="#704a87",
            label="First rejected free-space command",
        ),
    ]
    fig.suptitle("Combined yaw and pitch at three insertion depths", fontsize=16)
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
    fig.tight_layout(rect=[0, 0.13, 1, 0.94])
    (out / "motion_limits").mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "motion_limits" / "combined_motion.png", dpi=150)
    plt.close(fig)
    base = "coupled_s0.15_k0.15_b0.1_"
    openloop = read_csv(input_file(out, "rope_control", base + "open.csv.gz"))
    feedback = read_csv(input_file(out, "rope_control", base + "compensated.csv.gz"))
    take = [
        r
        for r in read_csv(input_file(out, "rope_control", "takeup_plant_mu0.12.csv.gz"))
        if r["kind"] in ("initial", "endpoint")
    ]
    matched = [
        r
        for r in read_csv(input_file(out, "rope_control", "takeup_plant_mu0.15.csv.gz"))
        if r["kind"] in ("initial", "endpoint")
    ]
    fig, axes = plt.subplots(3, 4, figsize=(13.8, 7.5), sharex=True, sharey="row")
    for k, (a, n) in enumerate(zip(axes.ravel(), NAMES)):
        for curve, color, label in (
            (openloop, "#bb5747", "Original commands"),
            (feedback, "#536992", "Compensated feedback"),
            (matched, "#949a9e", "Take-up, matched"),
            (take, "#17806d", "Take-up, estimated friction"),
        ):
            a.plot(
                [int(r["step"]) for r in curve],
                [float(r[n + "_dist_N"]) for r in curve],
                color=color,
                label=label,
                lw=0.9,
            )
        a.axhline(2.5, ls="--", color="#2d3135", lw=0.7)
        a.set_title(n.replace("_", " ").title(), loc="left", fontsize=11)
        a.grid(axis="y", color="#e5e8eb", lw=0.6)
        if k % 4 == 0:
            a.set_ylabel("Distal force (N)")
        if k >= 8:
            a.set_xlabel("Mission step")
    fig.suptitle(
        "Tension on all twelve ropes during one 500 g inspection cycle", fontsize=16
    )
    h, l = axes[0, 0].get_legend_handles_labels()
    h.append(plt.Line2D([], [], color="#2d3135", ls="--", lw=0.9))
    l.append("2.5 N floor")
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False)
    fig.tight_layout(rect=[0, 0.055, 1, 0.95])
    (out / "rope_control").mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "rope_control" / "twelve_rope_forces.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
