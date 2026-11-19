"""Draw cuts through the actual returning web and the closest hub surface in the 67.5 degree fixture bend."""

import argparse
import json
from pathlib import Path

from remaining_body import (
    CAD,
    b,
    collider,
    fcl,
    md,
    np,
    partition,
    read_parts,
    station_parts,
    mapped_points,
)
from figures import COL, Patch, plt, section_fill, save_svg


def nearest(a, b_):
    result = fcl.DistanceResult()
    dist = fcl.distance(
        fcl.CollisionObject(collider(a)),
        fcl.CollisionObject(collider(b_)),
        fcl.DistanceRequest(enable_nearest_points=True),
        result,
    )
    return dist, np.array(result.nearest_points)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads((args.results / "remaining_body_fine.json").read_text())
    record = next(r for r in evidence["previous_tip_comparison"] if r["station"] == 12)
    whole = next(
        r for r in evidence["rows"] if r["station"] == 12 and r["case"] == "bend67.5"
    )
    mesh = np.load(args.cache / "mesh_0p025.npz")
    state = np.load(args.cache / "bend67.5_0p025.npz")
    ribs = []
    for win, tag, verts, faces, weights in partition(mesh, 0.25):
        if win == 12 or tag != "rib_7":
            continue
        xyz = mapped_points(verts, weights, tag, state["fields"], {})
        xyz = (xyz - state["C12"]) @ state["R12"]
        ribs.append(
            md.Manifold(
                md.Mesh64(
                    np.ascontiguousarray(xyz),
                    np.array(faces, dtype=np.uint64, order="C", copy=True),
                )
            )
        )
    parts = {
        name: solid for name, _, solid in station_parts(read_parts(CAD / "parts"), 12)
    }
    old = b.place(b.saddle(12, radial_limit=None)[0], -22.5)
    fork = parts["fork_0"]
    hub = parts["hub_0"]
    old_rib = max(ribs, key=lambda solid: (solid ^ old).volume())
    match = old_rib ^ old
    if (
        abs(match.volume() - record["old_intersection_mm3"]) > 1e-6
        or abs(old_rib.min_gap(fork, 1) - record["revised_pair_gap_mm"]) > 1e-6
    ):
        raise ValueError("Drawn parts do not reproduce the published fork check")
    hub_rib = min(ribs, key=lambda ob: ob.min_gap(hub, 1))
    gap, point = nearest(hub_rib, hub)
    if abs(gap - whole["closest_lower_bound"][1]) > 1e-6:
        raise ValueError("Drawn parts do not reproduce the hub gap")
    er = np.array([np.cos(np.radians(-22.5)), np.sin(np.radians(-22.5)), 0])
    ez = np.array([0, 0, 1])
    normal = np.cross(er, ez)
    axes = np.stack([er, ez, normal])
    rotated = match.transform(np.column_stack((axes, [0, 0, 0])))
    bounds = rotated.bounding_box()
    section = max(
        np.linspace(bounds[2], bounds[5], 61), key=lambda h: rotated.slice(h).area()
    )
    pivot = normal * section
    fig, axs = plt.subplots(1, 3, figsize=(13.0, 5.1))
    fig.subplots_adjust(left=0.057, right=0.98, top=0.77, bottom=0.25, wspace=0.29)
    fig.text(
        0.055,
        0.925,
        "Where the returning M5 web meets the guide",
        fontsize=20,
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.855,
        "+12 mm station   |   96.19° fixture bend about 67.5°   |   sections through the loaded CAD",
        fontsize=11,
    )
    COL["overlap"] = "#b52d42"
    COL["hub_upper_sector"] = "#668898"
    window = (21.6, -2.6, 29.4, 3.5)
    for ax, metal, title in zip(
        axs[:2], (old, fork), ("A  Original outer fork tip", "B  Shortened fork")
    ):
        section_fill(ax, old_rib, axes, pivot, "body", window)
        section_fill(ax, metal, axes, pivot, "fork", window)
        if ax is axs[0]:
            section_fill(ax, match, axes, pivot, "overlap", window)
        ax.set(
            xlim=(window[0], window[2]),
            ylim=(window[1], window[3]),
            aspect="equal",
            xlabel="Radial distance (mm)",
        )
        ax.set_title(title, loc="left", fontweight="bold", fontsize=12, pad=10)
    axs[0].set_ylabel("Local axial position (mm)")
    axs[0].text(
        0.03,
        0.96,
        f"3-D overlap   {match.volume():.3f} mm³",
        transform=axs[0].transAxes,
        va="top",
        fontsize=10,
    )
    axs[1].text(
        0.03,
        0.96,
        f"3-D clearance   {record['revised_pair_gap_mm']:.3f} mm",
        transform=axs[1].transAxes,
        va="top",
        fontsize=10,
    )
    mid = point.mean(axis=0)
    gy = (point[0] - point[1]) / gap
    gx = er - er.dot(gy) * gy
    gx /= np.linalg.norm(gx)
    zoom = np.stack((gx, gy, np.cross(gx, gy)))
    win = (-0.37, -0.23, 0.37, 0.24)
    ax = axs[2]
    section_fill(ax, hub_rib, zoom, mid, "body", win)
    section_fill(ax, hub, zoom, mid, "hub_upper_sector", win)
    ax.plot(
        [0, 0], [-gap / 2, gap / 2], color="#a02038", lw=1.3, marker="o", markersize=2.4
    )
    ax.annotate(
        f"{gap:.3f} mm",
        xy=(0, 0),
        xytext=(0.065, 0.136),
        fontsize=11,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": "#a02038"},
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
    )
    ax.set(
        xlim=(win[0], win[2]),
        ylim=(win[1], win[3]),
        aspect="equal",
        xlabel="Distance from closest pair (mm)",
    )
    ax.set_title(
        "C  Remaining rib-to-hub gap",
        loc="left",
        fontweight="bold",
        fontsize=12,
        pad=10,
    )
    for ax in axs:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
    handles = [
        Patch(facecolor=COL[key], label=label)
        for key, label in [
            ("body", "Returning M5 web"),
            ("fork", "Polymer fork"),
            ("overlap", "Shared volume"),
            ("hub_upper_sector", "Aluminium hub"),
        ]
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.115),
        ncol=4,
        frameon=False,
        fontsize=10,
    )
    fig.text(
        0.055,
        0.065,
        "A and B use the same plane and scale. C is a separate, magnified cut through the two closest points.",
        fontsize=10,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    save_svg(fig, args.out)
    plt.close(fig)


if __name__ == "__main__":
    main()
