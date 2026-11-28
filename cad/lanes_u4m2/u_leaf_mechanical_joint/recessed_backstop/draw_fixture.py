"""Draw the contact-stack sections from CAD and the corresponding U1 fixture layout."""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch, Rectangle
import numpy as np

from build_recessed import OUT, X_SCREW, Y_SCREW, near_joint, original

INK = "#243445"
PALETTE = {"PA12": "#c5d5e1", "NiTi": "#694584", "Shoulder key": "#e9a74f",
           "Backstop": "#218679", "Screw": "#485d6a", "Nut": "#748392"}


def section(ax, solids, y):
    for name, solid in solids.items():
        polygons = solid.rotate([90, 0, 0]).slice(y).to_polygons()
        for vertices in polygons:
            x, v = np.asarray(vertices).T
            twice_area = np.sum(x * np.roll(v, -1) - v * np.roll(x, -1))
            ax.fill(x, -v, fc=PALETTE[name] if twice_area > 0 else "white", ec=INK, lw=.55)
    ax.axhline(0, color=INK, ls="--", lw=.8)
    ax.grid(alpha=.13)
    ax.set(xlim=(2.8, 13), ylim=(9, -.55), aspect="equal",
           xlabel="Module x (mm)", ylabel="Depth into U1, d (mm)")


def note(ax, label, point, position, **kwargs):
    ax.annotate(label, xy=point, xytext=position, color=INK, fontsize=9,
                arrowprops={"arrowstyle": "->", "color": INK, "lw": .9}, **kwargs)


def sections():
    source = original.solid(original.read("U_lane_pass.stl"))
    source = original.frame(source, True)
    springs = original.read("U_leaf_springs.stl").split()
    blade = original.frame(original.solid(next(p for p in springs if np.all(p.centroid[:2] > 0))), True)
    boss, cuts, parts, _ = near_joint()
    result = json.loads((OUT / "verification.json").read_text())
    lip = result["stop_order_outward_mm"]["PA12_lip"]
    compression = result["total_compression_travel_mm"]
    solids = {"PA12": (source + boss) - cuts, "NiTi": blade.translate([0, 0, -compression]),
              "Shoulder key": parts["shoulder_key"], "Backstop": parts["backstop"].translate([0, 0, -lip]),
              "Screw": parts["screw"], "Nut": parts["nut"]}
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), layout="constrained")
    section(axes[0], solids, 26.4)
    section(axes[1], solids, Y_SCREW)
    axes[0].set_title("Blade and lip section  |  y = 26.40 mm")
    axes[1].set_title("Retainer section  |  y = 20.10 mm")
    note(axes[0], "Loaded shoe wing\non PA12 lip", (4.05, 1.48), (3.1, 5.3))
    note(axes[0], "0.09 mm shoe recess", (8.9, .09), (8.9, -.24), ha="center")
    note(axes[1], "Recessed M1.6 envelope", (X_SCREW, .23), (9.2, -.25), ha="center")
    note(axes[1], "0.078 mm minimum\nshoe-to-head gap", (8.1, .54), (9.6, 2.72), ha="center")
    fig.suptitle("U1 proximal joint at the nominal compression stop")
    fig.legend(handles=[Patch(fc=c, label=name) for name, c in PALETTE.items()],
               loc="outside lower center", ncols=6, frameon=False)
    fig.savefig(OUT / "U1_compression_sections.png", dpi=190)
    plt.close(fig)


def block(ax, x, y, width, depth, color):
    ax.add_patch(Rectangle((x, y), width, depth, fc=color, ec=INK, lw=1))


def fixture():
    fig = plt.figure(figsize=(11.2, 7.1), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.12, 1])
    side, face, notes = fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])
    side.set(xlim=(-55, 156), ylim=(-25, 34), aspect="equal")
    side.axis("off")
    block(side, -21, -10, 18, 8, "#e5ebee")
    block(side, 102, -10, 37, 8, "#e5ebee")
    block(side, 0, -2, 7, 23, PALETTE["PA12"])
    block(side, 89, -2, 7, 23, PALETTE["PA12"])
    block(side, 106, 13, 17, 10, "#d6ece7")
    block(side, 128, 13, 16, 10, "#e8dcee")
    side.plot([-7, 4], [18, 18], color=INK, ls="--", lw=.75)
    side.plot([-6, -6, 0], [-2, 4, 4], color=INK, lw=1.4)
    side.plot([96, 113, 113], [4, 4, -2], color=INK, lw=1.4)
    side.plot([4, 92], [18, 18], color=PALETTE["NiTi"], lw=2.6, solid_capstyle="round")
    side.plot([96, 106], [18, 18], color=INK)
    side.plot([123, 128], [18, 18], color=INK)
    side.plot([0, 0, 96, 96], [22, 31, 31, 22], color=INK, lw=.7, alpha=.5)
    side.annotate("", (96, 31), (0, 31), arrowprops={"arrowstyle": "<->", "color": INK})
    side.text(48, 32, "96.00 mm datum-to-datum", color=INK, ha="center", fontsize=10)
    side.text(47, 21.8, "94 mm NiTi blade", color=PALETTE["NiTi"], ha="center", fontsize=10)
    note(side, "Fixed base + flange clamp", (-12, -5), (-47, -16))
    note(side, "Access to shoe and screw\nthrough relieved fixture plate", (0, 15), (-48, 27))
    note(side, "Preloaded linear guide\nand flange clamp", (111, -6), (92, -17))
    side.text(114.5, 18, "Load cell", ha="center", va="center", fontsize=8)
    side.text(136, 18, "Drive", ha="center", va="center", fontsize=8)
    side.text(48, -12, "Sensor line through blade ends\nClamp through offset coupon flanges",
              ha="center", va="center", fontsize=9, color=INK)
    face.set(aspect="equal", xlim=(-3.3, 21), ylim=(7.5, 31.5),
             xlabel="Module x (mm)", ylabel="Module y (mm)")
    face.set_title("Coupon mating face  |  fixture interface")
    block(face, -1.9, 9.5, 16.5, 5.5, PALETTE["PA12"])
    for x in (1.2, 11.5):
        face.add_patch(Circle((x, 12.5), 1.6, fc="white", ec=INK))
        face.text(x, 10.0, f"{x:.1f}", fontsize=8, ha="center")
    face.plot(7.5, 26.4, marker="+", color=PALETTE["NiTi"], ms=13)
    face.plot(X_SCREW, Y_SCREW, marker="+", color=INK, ms=9)
    note(face, "Force line\n(7.5, 26.4)", (7.5, 26.4), (13.1, 28.8))
    note(face, "Near screw\n(6.4, 20.1)", (X_SCREW, Y_SCREW), (12.4, 22.5))
    note(face, "2 × Ø3.20\ny = 12.50", (12.9, 13.2), (14.5, 16.9))
    face.grid(alpha=.12)
    notes.axis("off")
    notes.text(0, .96, "Fixture setup", transform=notes.transAxes, va="top", fontsize=12, weight="bold", color=INK)
    labels = [
        "Use two plates registered in the same x/y orientation.",
        "Position the force line through the thick blade ends.",
        "Keep openings for the +Y key/shoe and +X nut.",
        "Relieve the fixture locally around the blade, screw",
        "and shoe. Use removable actual mating CAD for",
        "a separate stacked face check after free-fit setup.",
        "Track each blade end, shoe and head relative to PA12.",
        "Verify zero and travel on a rigid calibration link.",
    ]
    for i, line in enumerate(labels):
        notes.text(0, .82 - i * .092, line, transform=notes.transAxes, va="top", fontsize=10, color=INK)
    fig.suptitle("U1 single-leaf bench fixture  |  aligned push/pull shakedown", fontsize=15, color=INK)
    fig.savefig(OUT / "U1_bench_fixture.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    sections()
    fixture()
