"""Render the actual exported assembly, exploded single seat and dimensional cross-section."""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Patch
from matplotlib.path import Path as MPath
import numpy as np
from numba import njit
from PIL import Image

import build as b
import joint as j

HERE = Path(__file__).resolve().parent
sys.path.insert(
    0,
    str(HERE.parents[2] / "simulations/u4m2/lanes_20261113/m5_retained_seat_20261118"),
)
from clearance import read_parts, station_parts

COL = {
    "body": "#c8beb0",
    "fork": "#e9a23a",
    "gate": "#36a496",
    "shoulder_pin": "#357eae",
    "threaded_cap": "#224b6b",
    "rope_arm": "#bd694b",
    "hub_upper_sector": "#899ba1",
    "hub_lower_sector": "#a4b4b8",
    "lap_screw": "#43545c",
    "hub_screw": "#43545c",
}
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "svg.hashsalt": "asrc-m5-retained-seat",
        "axes.edgecolor": "#b7c1c6",
        "text.color": "#203744",
        "axes.labelcolor": "#203744",
        "xtick.color": "#4b6572",
        "ytick.color": "#4b6572",
    }
)


@njit
def raster(vertices, faces, colours, depth, image):
    height, width = depth.shape
    for k in range(len(faces)):
        v = vertices[faces[k]]
        a, b, c = v[0], v[1], v[2]
        det = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if det >= -1e-11:
            continue
        for y in range(
            max(0, int(np.ceil(min(a[1], b[1], c[1])))),
            min(height, 1 + int(np.floor(max(a[1], b[1], c[1])))),
        ):
            for x in range(
                max(0, int(np.ceil(min(a[0], b[0], c[0])))),
                min(width, 1 + int(np.floor(max(a[0], b[0], c[0])))),
            ):
                u = ((x - a[0]) * (c[1] - a[1]) - (y - a[1]) * (c[0] - a[0])) / det
                w = ((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) / det
                if u >= 0 and w >= 0 and u + w <= 1:
                    z = a[2] + u * (b[2] - a[2]) + w * (c[2] - a[2])
                    if z > depth[y, x]:
                        depth[y, x] = z
                        image[y, x] = colours[k]


def render(objects, centre, view, scale, width, height):
    direction = np.array(view) / np.linalg.norm(view)
    right = np.cross((0, 0, 1), direction)
    right /= np.linalg.norm(right)
    up = np.cross(direction, right)
    axes = np.stack((right, -up, direction))
    height *= 2
    width *= 2
    depth = np.full((height, width), -1e5)
    img = np.full((height, width, 3), 255, np.uint8)
    lights = [
        direction + 0.60 * up - 0.52 * right,
        0.7 * direction + 0.4 * right - 0.3 * up,
    ]
    lights = [v / np.linalg.norm(v) for v in lights]
    for obj, key in objects:
        m = obj.to_mesh64()
        xyz = m.vert_properties[:, :3]
        f = np.asarray(m.tri_verts, dtype=np.int64)
        screen = (xyz - centre) @ axes.T
        screen[:, :2] *= height / (2 * scale)
        screen[:, :2] += [width / 2, height / 2]
        d = xyz[f[:, 1:]] - xyz[f[:, :1]]
        norm = np.cross(d[:, 0], d[:, 1])
        norm /= np.maximum(1e-15, np.linalg.norm(norm, axis=1)[:, None])
        shade = (
            0.54
            + 0.39 * np.maximum(0, norm @ lights[0])
            + 0.14 * np.maximum(0, norm @ lights[1])
        )
        col = np.array(matplotlib.colors.to_rgb(COL[key])) * 255
        raster(screen, f, np.uint8(np.clip(shade[:, None] * col, 0, 255)), depth, img)
    jumps = np.maximum(
        abs(depth - np.roll(depth, 1, axis=1)), abs(depth - np.roll(depth, 1, axis=0))
    )
    mask = (depth > -1e4) & (jumps > 0.70)
    img[mask] = np.uint8(img[mask] * 0.77)
    return np.asarray(
        Image.fromarray(img).resize((width // 2, height // 2), Image.Resampling.LANCZOS)
    )


def section_fill(ax, solid, axes, pivot, key, window):
    o = solid.transform(np.column_stack((axes, -axes @ pivot)))
    x0, y0, x1, y1 = window
    frame = b.md.CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0))
    loops = (o.slice(0) ^ frame).to_polygons()
    if not loops:
        return
    paths = []
    for loop in loops:
        if len(loop) > 2:
            paths.append(
                MPath(
                    np.vstack([loop, loop[0]]),
                    [MPath.MOVETO]
                    + [MPath.LINETO] * (len(loop) - 1)
                    + [MPath.CLOSEPOLY],
                )
            )
    if paths:
        ax.add_patch(
            PathPatch(
                MPath.make_compound_path(*paths),
                facecolor=COL[key],
                edgecolor="#34474f",
                lw=0.65,
            )
        )


def save_svg(figure, path):
    figure.savefig(path, facecolor="white", metadata={"Date": None})
    # Matplotlib pads path commands at line ends. Newlines separate SVG commands.
    path.write_text(
        "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
    )


def main():
    parts = read_parts(HERE / "parts")
    body = b.load(HERE / "parts/M5_machined_body.stl")
    images = HERE / "figures"
    images.mkdir(exist_ok=True)
    cut = b.box((-40, -40, -32), (40, 0, 32))
    all_objects = [(body - cut, "body")]
    for z in j.STATIONS:
        all_objects += [
            (s.translate((0, 0, z)), f) for _, f, s in station_parts(parts, z)
        ]
    module = render(all_objects, (0, 0, 0), (1.8, -2.2, 0.80), 58, 790, 720)
    z = 12
    a = 67.5
    local = body.translate((0, 0, -z)).rotate((0, 0, -a))
    web = local ^ b.box((10, -1.505, -4.15), (29, 1.505, 4.15))
    exploded = [
        (web, "body"),
        (parts["fork_+12"].translate((4.5, 0, -5.8)), "fork"),
        (parts["gate_+12"].translate((0, 6.5, 1.0)), "gate"),
        (parts["shoulder_pin"].translate((0, -9, 0)), "shoulder_pin"),
        (parts["threaded_cap"].translate((0, 13, 0)), "threaded_cap"),
    ]
    detail = render(exploded, (19, 1.9, -1.2), (1.10, -1.15, 0.88), 13.5, 920, 720)
    fig = plt.figure(figsize=(12.8, 6.7))
    ax1 = fig.add_axes([0.025, 0.197, 0.43, 0.57])
    ax2 = fig.add_axes([0.46, 0.19, 0.525, 0.595])
    for ax, img in ((ax1, module), (ax2, detail)):
        ax.imshow(img)
        ax.axis("off")
    fig.text(0.045, 0.938, "M5 retained rotating guide", size=23, weight="bold")
    fig.text(
        0.047,
        0.888,
        "Two replaceable stations on the machined M5 body  |  nominal CAD in the straight configuration",
        size=11,
    )
    fig.text(
        0.05, 0.804, "A   Station positions at -12 and +12 mm", size=12, weight="bold"
    )
    fig.text(
        0.50,
        0.804,
        "B   Exploded view of one +12 mm mounting site",
        size=12,
        weight="bold",
    )
    fig.text(
        0.05,
        0.16,
        "The front half of the body is cut away between the end disks.",
        size=9,
    )
    fig.text(
        0.50,
        0.16,
        "The web stays in place. The fork, pin, gate and cap are offset for viewing.",
        size=9,
    )
    labels = [
        ("body", "M5 web"),
        ("fork", "Fork"),
        ("gate", "Sliding gate"),
        ("shoulder_pin", "Shoulder pin"),
        ("threaded_cap", "Threaded thrust cap"),
        ("rope_arm", "Rope arm"),
        ("hub_upper_sector", "Hub sector"),
    ]
    fig.legend(
        [Patch(fc=COL[k]) for k, v in labels],
        [v for k, v in labels],
        loc="lower center",
        bbox_to_anchor=(0.50, 0.025),
        ncol=7,
        frameon=False,
        columnspacing=1.55,
        handlelength=1.25,
    )
    fig.savefig(images / "assembly_exploded.png", dpi=160, facecolor="white")
    plt.close(fig)
    pivot = np.array([j.R_PIVOT, 0.0, 0.0])
    w = j.web_axes(z)
    section_objects = [
        (web, "body"),
        (parts["fork_+12"], "fork"),
        (parts["gate_+12"], "gate"),
        (parts["shoulder_pin"], "shoulder_pin"),
        (parts["threaded_cap"], "threaded_cap"),
    ]
    fig = plt.figure(figsize=(12.6, 6.65))
    fig.text(0.05, 0.94, "How the retained seat carries load", size=23, weight="bold")
    fig.text(
        0.05,
        0.885,
        "Sections through the same +12 mm web pivot  |  dimensions in millimetres",
        size=11,
    )
    ax = fig.add_axes([0.055, 0.22, 0.55, 0.575])
    az = fig.add_axes([0.675, 0.22, 0.27, 0.575])
    A = np.stack((-w[:, 2], w[:, 1], w[:, 0]))
    B = np.stack((w[:, 0], w[:, 1], w[:, 2]))
    for part, name in section_objects:
        section_fill(ax, part, A, pivot, name, (-4.65, -2.1, 4.90, 2.10))
        section_fill(az, part, B, pivot, name, (-2.2, -1.90, 2.20, 1.90))
    ax.set(
        xlim=(-4.68, 5.0),
        ylim=(-2.45, 2.45),
        aspect="equal",
        xlabel="Distance along the pin axis (mm)",
        ylabel="Across the web (mm)",
    )
    az.set(
        xlim=(-2.3, 2.3),
        ylim=(-2.05, 2.05),
        aspect="equal",
        xlabel="Distance along the web (mm)",
        ylabel="Across the web (mm)",
    )
    for axes in [ax, az]:
        axes.spines[["top", "right"]].set_visible(False)
    ax.set_title(
        "A   Pin, relieved bore and thrust faces",
        loc="left",
        fontsize=12,
        weight="bold",
        pad=10,
    )
    az.set_title(
        "B   Fork cavity at the pin waist",
        loc="left",
        fontsize=12,
        weight="bold",
        pad=10,
    )
    ann = dict(
        arrowprops=dict(arrowstyle="->", color="#293e49", lw=1.0),
        fontsize=9,
        ha="center",
        va="center",
        bbox=dict(
            boxstyle="round,pad=.15", facecolor="white", alpha=0.94, edgecolor="none"
        ),
    )
    ax.annotate(
        "Crowned bore\n0.64 mm at waist", xy=(0, 0.32), xytext=(-0.40, 1.82), **ann
    )
    ax.annotate("0.60 mm shaft", xy=(-0.5, -0.29), xytext=(-1.4, -1.80), **ann)
    ax.annotate(
        "Spherical thrust face\n0.020 mm radial clearance",
        xy=(1.42, 0.53),
        xytext=(2.50, 1.83),
        **ann,
    )
    az.annotate("0.20 mm wall gap", xy=(0.03, 0.85), xytext=(0.58, 1.65), **ann)
    az.annotate("0.30 mm land", xy=(0.14, -0.95), xytext=(-0.45, -1.72), **ann)
    fig.legend(
        [Patch(fc=COL[k]) for k, v in labels[:5]],
        [v for k, v in labels[:5]],
        loc="lower center",
        bbox_to_anchor=(0.5, 0.107),
        ncol=5,
        frameon=False,
    )
    fig.text(
        0.05,
        0.06,
        "The pin passes through the web. The two thrust faces limit axial travel. The flared polymer walls provide room for the web to rotate.",
        size=10,
    )
    save_svg(fig, images / "seat_sections.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
