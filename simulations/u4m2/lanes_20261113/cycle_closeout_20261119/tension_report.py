"""Write all twelve model tensions, rest lengths, rope lengths and head axes for every accepted motion step."""

import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from replay import plant
from pitch_reference import angle_between, target_axis

NAMES = [f"{a}_{r}" for a in "ABC" for r in ("up", "right", "down", "left")]
NICE = {
    "straighten": "Straighten",
    "entry": "Insert",
    "right_out": "Right turn",
    "right_return": "Right return",
    "left_out": "Left turn",
    "left_return": "Left return",
    "pitch_up": "Pitch up",
    "pitch_up_return": "Up return",
    "pitch_down": "Pitch down",
    "pitch_down_return": "Down return",
    "exit": "Withdraw",
}
COLOURS = ["#006b92", "#c45109", "#107647", "#7c4994"]


def write_rows(path, rows):
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def save_svg(fig, path):
    fig.savefig(path, metadata={"Date": None})
    # Matplotlib separates path coordinates at both line breaks and trailing spaces.
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def run(source):
    with gzip.open(source / "motion_trace.json.gz", "rt") as f:
        motion = json.load(f)
    with gzip.open(source / "controller_records.json.gz", "rt") as f:
        records = json.load(f)
    with np.load(source / "controller_states.npz") as f:
        zs = f["motion_z"]
        R = f["motion_rest_m"].reshape(-1, 12)
        T = f["motion_tensions_N"].reshape(-1, 12)
    rod, _ = plant()
    E = rod.base.planar.rope_ea
    np.testing.assert_allclose(T, [r["tensions_n"] for r in motion], atol=0)
    if not (len(zs) == len(R) == len(T) == len(motion)) or np.min(T) <= 0:
        raise ValueError(
            "Unaligned motion archive or slack rope; invert length from geometry for slack states"
        )
    # Under the simulated uniform-tension Hookean law, this is exactly the internal end-to-end length.
    geom = (R * (1.0 + T / E) - 1.0) * 1000.0
    rows = []
    cached = {}
    for i, (r, z) in enumerate(zip(motion, zs)):
        key = z.tobytes()
        if key not in cached:
            det = rod.base.kinematic_metrics(z)[1]
            frame = rod.R0 @ det["frames"][-1]
            cached[key] = (frame[:, 0], Rotation.from_matrix(frame).as_quat())
        axis, quaternion = cached[key]
        ph = r["phase"]
        if ph.startswith("pitch"):
            yaw = 0.0
            el = r["target_signed_pitch_deg"]
            want = target_axis(el)
        else:
            yaw = (r["yaw_deg"] + r["yaw_error_deg"] + 180) % 360 - 180
            el = r["elevation_deg"] + r["elevation_error_deg"]
            y, p = np.radians([yaw, el])
            want = np.array([np.cos(p) * np.cos(y), np.sin(p), np.cos(p) * np.sin(y)])
        rec = dict(
            step=i,
            target_index=r["index"],
            phase=ph,
            substep=r["kind"],
            clamp_s_mm=r["clamp_s_mm"],
            target_yaw_deg=yaw,
            target_elevation_deg=el,
            physical_yaw_deg=r["yaw_deg"],
            physical_elevation_deg=r["elevation_deg"],
            signed_forward_up_pitch_deg=float(np.degrees(np.arctan2(axis[1], axis[0]))),
            pointing_error_deg=angle_between(axis, want),
            tank_clearance_after_allowance_mm=r["clearance_mm"] - 1.5,
            fixed_winch_min_eigenvalue=r["minimum_eigenvalue"],
        )
        rec.update(
            {f"head_tank_{c}_mm": r["head_tank_mm"][k] for k, c in enumerate("xyz")},
            **{f"head_axis_{c}": axis[k] for k, c in enumerate("xyz")},
            **{f"head_frame_q{c}": quaternion[k] for k, c in enumerate("xyzw")},
        )
        rec.update({f"{name}_N": T[i, k] for k, name in enumerate(NAMES)})
        rec.update(
            {f"{name}_command_mm": 1000 * R[i, k] for k, name in enumerate(NAMES)}
        )
        rec.update(
            {f"{name}_internal_path_mm": geom[i, k] for k, name in enumerate(NAMES)}
        )
        rows.append(rec)
    checks = []
    for i in np.unique(np.linspace(0, len(zs) - 1, 21).astype(int)):
        exact = rod.evaluate(zs[i], detail=True)[2]["rope_lengths"].ravel() * 1000
        checks.append(float(np.max(abs(exact - geom[i]))))
    if max(checks) > 1.0e-6:
        raise ValueError("Recorded tensions and commands do not reproduce rod lengths")
    write_rows(source / "rope_tensions_every_step.csv.gz", rows)
    events = [("Loaded start", 0)]
    for ph in dict.fromkeys(r["phase"] for r in rows):
        use = [i for i, r in enumerate(rows) if r["phase"] == ph]
        events.append((NICE[ph], use[-1]))
    im, jm = np.unravel_index(T.argmax(), T.shape)
    il, jl = np.unravel_index(T.argmin(), T.shape)
    events += [("Peak rope tension", im), ("Lowest rope tension", il)]
    erows = []
    for name, i in events:
        r = rows[i]
        out = dict(
            event=name,
            step=i,
            phase=r["phase"],
            target_yaw_deg=r["target_yaw_deg"],
            target_elevation_deg=r["target_elevation_deg"],
            achieved_yaw_deg=r["physical_yaw_deg"],
            achieved_elevation_deg=r["physical_elevation_deg"],
            signed_pitch_deg=r["signed_forward_up_pitch_deg"],
            pointing_error_deg=r["pointing_error_deg"],
        )
        out.update({n + "_N": T[i, k] for k, n in enumerate(NAMES)})
        erows.append(out)
    write_rows(source / "rope_tensions_at_events.csv", erows)
    ends = {r["phase"]: n for n, r in enumerate(rows)}
    comparisons = [
        ("up_return_vs_left_return", "left_return", "pitch_up_return"),
        ("down_return_vs_left_return", "left_return", "pitch_down_return"),
        ("withdrawn_vs_straightened", "straighten", "exit"),
    ]
    returns = []
    for name, first, last in comparisons:
        if first not in ends or last not in ends:
            continue
        a, b = ends[first], ends[last]
        # Centres use tank coordinates; only compare the same clamp position.
        start, end = rows[a], rows[b]
        if abs(start["clamp_s_mm"] - end["clamp_s_mm"]) > 1e-8:
            continue
        aa = [start["head_axis_" + c] for c in "xyz"]
        bb = [end["head_axis_" + c] for c in "xyz"]
        dp = [
            end["head_tank_" + c + "_mm"] - start["head_tank_" + c + "_mm"]
            for c in "xyz"
        ]
        returns.append(
            dict(
                comparison=name,
                reference_step=a,
                return_step=b,
                clamp_mm=start["clamp_s_mm"],
                tip_position_change_mm=np.linalg.norm(dp),
                tip_displacement_xyz_mm=dp,
                pointing_change_deg=angle_between(aa, bb),
                max_rope_tension_change_N=np.max(abs(T[b] - T[a])),
                max_command_change_mm=1000 * np.max(abs(R[b] - R[a])),
            )
        )
    (source / "neutral_returns.json").write_text(
        json.dumps(returns, indent=2, allow_nan=False) + "\n"
    )
    by_phase = []
    for ph in dict.fromkeys(r["phase"] for r in rows):
        idx = [i for i, r in enumerate(rows) if r["phase"] == ph]
        for k, name in enumerate(NAMES):
            lo = idx[np.argmin(T[idx, k])]
            hi = idx[np.argmax(T[idx, k])]
            by_phase.append(
                dict(
                    phase=ph,
                    rope=name,
                    anchor={"A": "U4", "B": "M5", "C": "M6"}[name[0]],
                    minimum_N=T[lo, k],
                    min_step=lo,
                    maximum_N=T[hi, k],
                    max_step=hi,
                )
            )
    write_rows(source / "rope_tensions_by_phase.csv", by_phase)
    peak_phases = [
        r
        for r in by_phase
        if r["rope"] == NAMES[jm] and T[im, jm] - r["maximum_N"] <= 1.0e-6
    ]
    peak_observations = ", ".join(
        f"{NICE[r['phase']]} at step {r['max_step']:,}" for r in peak_phases
    )
    table = [
        "# Twelve-rope tension at the ends of the motion phases",
        "",
        "Values are in newtons. A terminates at U4, B at M5 and C at M6. The four directions are fixed in the rod frame. Positive pitch is upwards from horizontal. The nominal frictionless model gives uniform tension along each rope. Actual distal forces depend on friction.",
        "",
        "Each group below lists **up / right / down / left**. All twelve individual values are also stored in separate columns in the CSV files.",
        "",
        "| Event | Step | Requested yaw / pitch (deg) | Actual elevation (deg) | Pointing error (deg) | A (N) | B (N) | C (N) |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for r in erows:

        def group(letter):
            return " / ".join(
                f"{r[f'{letter}_{n}_N']:.2f}" for n in ("up", "right", "down", "left")
            )

        table.append(
            f"| {r['event']} | {r['step']} | {r['target_yaw_deg']:.1f} / {r['target_elevation_deg']:.1f} | {r['achieved_elevation_deg']:.3f} | {r['pointing_error_deg']:.3f} | {group('A')} | {group('B')} | {group('C')} |"
        )
    table += [
        "",
        f"The {NAMES[jm].replace('_', ' ')} rope reached {T[im, jm]:.3f} N during {peak_observations}. Phase peak values within 0.000001 N are grouped here.",
        "",
        "At a vertical target the head axis defines pointing accuracy. Azimuth is indeterminate at the pole. The horizontal-plane yaw field in the CSV is retained as a kinematic diagnostic.",
        "",
        "[Every accepted substep](rope_tensions_every_step.csv.gz) · [Individual event tensions](rope_tensions_at_events.csv) · [Phase extrema and step numbers](rope_tensions_by_phase.csv) · [Separate winch and anchor forces with assumed friction at four turns](sliding_turn_tensions.csv) · [Cycle summary](summary.json)",
        "",
        "![Rope tensions through yaw and pitch](rope_tensions.svg)",
        "",
        "![Side views and all twelve loads at both vertical turning points](pitch_poles.svg)",
    ]
    all_ranges = []
    table.extend(
        [
            "",
            "## Range of each individual rope over the entire cycle",
            "",
            "| Rope | Minimum (N) | Step at minimum | Maximum (N) | Step at maximum | Phase at maximum |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for k, name in enumerate(NAMES):
        low, high = int(T[:, k].argmin()), int(T[:, k].argmax())
        item = dict(
            rope=name,
            minimum_N=float(T[low, k]),
            min_step=low,
            min_phase=rows[low]["phase"],
            maximum_N=float(T[high, k]),
            max_step=high,
            max_phase=rows[high]["phase"],
        )
        all_ranges.append(item)
        table.append(
            f"| {name.replace('_', ' ')} | {item['minimum_N']:.3f} | {low} | {item['maximum_N']:.3f} | {high} | {NICE[item['max_phase']]} |"
        )
    write_rows(source / "rope_tensions_full_range.csv", all_ranges)
    table.extend(
        [
            "",
            "[Full-precision ranges for the twelve ropes](rope_tensions_full_range.csv)",
        ]
    )
    (source / "ROPE_TENSIONS.md").write_text("\n".join(table) + "\n")
    plot(rows, T, source / "rope_tensions.svg")
    plot_verticals(rod, zs, rows, T, source)
    data = dict(
        steps=len(rows),
        targets=len(records),
        rope_values=int(T.size),
        matching_length_witnesses=len(checks),
        maximum_length_reconstruction_error_mm=max(checks),
        global_min=dict(
            rope=NAMES[jl], step=int(il), N=float(T[il, jl]), phase=motion[il]["phase"]
        ),
        global_max=dict(
            rope=NAMES[jm], step=int(im), N=float(T[im, jm]), phase=motion[im]["phase"]
        ),
        phases_at_global_peak_within_1e_6_N=[
            dict(phase=r["phase"], step=int(r["max_step"]), N=float(r["maximum_N"]))
            for r in peak_phases
        ],
    )
    (source / "rope_trace_validation.json").write_text(
        json.dumps(data, indent=2) + "\n"
    )


def plot(rows, T, path):
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "ASRC-tension-2026",
            "font.family": "DejaVu Sans",
            "font.size": 10,
        }
    )
    fig, axs = plt.subplots(
        4,
        1,
        figsize=(13.0, 8.8),
        sharex=True,
        gridspec_kw={"height_ratios": [0.8, 1, 1, 1]},
    )
    x = np.arange(len(rows))
    phases = [r["phase"] for r in rows]
    starts = [0, *[i for i in range(1, len(rows)) if phases[i] != phases[i - 1]]]
    for j, (left, right) in enumerate(zip(starts, starts[1:] + [len(rows)])):
        for ax in axs:
            if j % 2 == 0:
                ax.axvspan(left, right, color="#edf2f4", alpha=0.85, zorder=-3)
        axs[-1].text(
            (left + right) / 2,
            -0.12,
            NICE[phases[left]],
            rotation=42,
            ha="right",
            va="top",
            transform=axs[-1].get_xaxis_transform(),
            fontsize=8.3,
        )
    axs[0].plot(
        x,
        [r["target_yaw_deg"] for r in rows],
        color="#444d5d",
        lw=1.55,
        label="Commanded yaw",
    )
    axs[0].plot(
        x,
        [r["physical_elevation_deg"] for r in rows],
        color="#ab447b",
        lw=1.65,
        label="Achieved elevation",
    )
    axs[0].set_ylabel("Angle (deg)")
    axs[0].legend(loc="upper left", ncol=2, fontsize=9)
    axs[0].set_yticks([-175, -90, 0, 90, 175])
    for k, letter in enumerate("ABC"):
        ax = axs[k + 1]
        for j, colour in enumerate(COLOURS):
            ax.plot(
                x, T[:, k * 4 + j], color=colour, lw=1.35, ls=("--" if j == 3 else "-")
            )
        ax.axhline(2.5, color="#58636e", ls=":", lw=0.85)
        ax.set_ylabel(f"{letter} tension (N)")
        ax.set_ylim(bottom=0)
    for ph, mark in (("pitch_up", "+90°"), ("pitch_down", "−90°")):
        if ph not in phases:
            continue
        idx = max(i for i, phase in enumerate(phases) if phase == ph)
        for ax in axs:
            ax.axvline(idx, color="#647780", lw=0.7, ls=":", zorder=0)
        axs[0].plot(
            idx, rows[idx]["physical_elevation_deg"], "o", color="#ab447b", ms=3.8
        )
        axs[0].annotate(
            mark,
            (idx, rows[idx]["physical_elevation_deg"]),
            xytext=(3, 5),
            textcoords="offset points",
            fontsize=8,
        )
        for k in range(3):
            j = int(np.argmax(T[idx, 4 * k : 4 * k + 4]))
            y = T[idx, 4 * k + j]
            axs[k + 1].plot(idx, y, "o", color=COLOURS[j], ms=3.9)
            axs[k + 1].annotate(
                f"{y:.2f}",
                (idx, y),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
                color=COLOURS[j],
            )
    for ax in axs:
        ax.grid(axis="y", color="#d9dfe4", lw=0.55)
        ax.spines[["top", "right"]].set_visible(False)
    axs[-1].set_xlim(0, len(rows) - 1)
    axs[-1].tick_params(labelbottom=False)
    fig.suptitle(
        "Twelve-rope tension through the complete 500 g cycle",
        x=0.075,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    fig.legend(
        [Line2D([0], [0], color=c, lw=2) for c in COLOURS],
        ["Up", "Right", "Down", "Left"],
        loc="upper right",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.986, 0.99),
    )
    fig.text(
        0.075,
        0.02,
        "Horizontal position is accepted motion-step number. Dotted lines mark the 2.5 N operating floor. Panels use independent tension scales.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.08, right=0.982, top=0.925, bottom=0.14, hspace=0.24)
    save_svg(fig, path)
    plt.close(fig)


def plot_verticals(rod, zs, rows, tensions, source):
    """Draw the two executed vertical endpoints at the same longitudinal and vertical scale."""
    from transmission import material_path

    groups = [
        (phase, goal, [i for i, r in enumerate(rows) if r["phase"] == phase])
        for phase, goal in (("pitch_up", 90), ("pitch_down", -90))
    ]
    if any(not group for _, _, group in groups):
        return
    fig = plt.figure(figsize=(11.5, 7.65))
    layout = fig.add_gridspec(
        2,
        2,
        height_ratios=[2.1, 1.0],
        left=0.075,
        right=0.985,
        top=0.86,
        bottom=0.10,
        hspace=0.27,
        wspace=0.18,
    )
    curves = []
    for k, (_, goal, group) in enumerate(groups):
        step = group[-1]
        z = zs[step]
        r = rows[step]
        det = rod.base.evaluate(z, detail=True)[2]
        ends = rod.endpoints(z[rod.local])
        conv = lambda v: (np.asarray(v) + [20.0, 0.0, 0.0]) @ rod.R0.T
        mid = np.vstack((np.zeros(3), conv(1000 * det["points"])))
        axis = rod.R0 @ det["frames"][-1, :, 0]
        tip = mid[-1] + 38 * axis
        ax = fig.add_subplot(layout[0, k])
        curves.append((ax, np.vstack((mid, tip))))
        for g, j in np.ndindex(3, 4):
            q = conv(material_path(rod, det, ends, g, j)[0])
            ax.plot(
                q[:, 0],
                q[:, 1],
                color=COLOURS[j],
                lw=0.8,
                alpha=0.55,
                ls=("--" if j == 3 else "-"),
            )
        ax.plot(mid[:34, 0], mid[:34, 1], color="#245871", lw=2.5)
        ax.plot(mid[33:, 0], mid[33:, 1], color="#117965", lw=2.5)
        ax.plot(0, 0, "s", color="#243b45", ms=4)
        ax.annotate(
            "Clamp", (0, 0), xytext=(0, -14), textcoords="offset points", fontsize=8
        )
        ax.annotate(
            "",
            xy=tip[:2],
            xytext=mid[-1, :2],
            arrowprops=dict(arrowstyle="-|>", lw=2.5, color="#a44930"),
        )
        for g, txt in enumerate(("A · U4", "B · M5", "C · M6")):
            i = (4 + g) * rod.sub + 1
            ax.plot(mid[i, 0], mid[i, 1], "o", color="#243b45", ms=3.5)
            ax.annotate(
                txt,
                mid[i, :2],
                xytext=((-12 if g == 0 else 8), (9 if g != 1 else -10)),
                textcoords="offset points",
                fontsize=8,
                color="#243b45",
            )
        ax.set_title(
            f"Requested {goal:+d}°   |   Step {step}",
            loc="left",
            fontsize=14,
            fontweight="bold",
            color="#183f48",
        )
        ax.set_xlabel("Forward from clamp (mm)", fontsize=9)
        if k == 0:
            ax.set_ylabel("Height from clamp (mm)", fontsize=9)
        ax.grid(color="#e4e9ea", lw=0.65)
        ax.spines[["top", "right"]].set_visible(False)
        table_ax = fig.add_subplot(layout[1, k])
        table_ax.axis("off")
        vals = [
            [n.title(), *[f"{tensions[step, g * 4 + j]:.2f}" for g in range(3)]]
            for j, n in enumerate(("up", "right", "down", "left"))
        ]
        tab = table_ax.table(
            cellText=vals,
            colLabels=["Rope direction", "A (N)", "B (N)", "C (N)"],
            cellLoc="center",
            bbox=[0, 0.0, 1.0, 0.76],
        )
        tab.auto_set_font_size(False)
        tab.set_fontsize(10)
        for (row, col), cell in tab.get_celld().items():
            cell.set_edgecolor("#d2dcdf")
            cell.set_linewidth(0.5)
            if row == 0:
                cell.set_facecolor("#e9f1f1")
                cell.get_text().set_weight("bold")
            if row != 0 and col == 0:
                cell.get_text().set_color(COLOURS[row - 1])
        table_ax.text(
            0,
            0.91,
            f"Elevation {r['physical_elevation_deg']:+.3f}°    ·    Direction error {r['pointing_error_deg']:.3f}°",
            fontsize=10.3,
            weight="bold",
            color="#203c43",
            transform=table_ax.transAxes,
        )
    union = np.vstack([p for _, p in curves])
    x0, x1 = union[:, 0].min() - 43, union[:, 0].max() + 60
    y0, y1 = union[:, 1].min() - 55, union[:, 1].max() + 52
    for ax, _ in curves:
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal", adjustable="box")
    fig.text(
        0.075,
        0.955,
        "Rope loads at the two vertical turning points",
        fontsize=20,
        fontweight="bold",
        color="#193840",
    )
    fig.text(
        0.075,
        0.906,
        "500 g head  ·  Both drawings use the same side view and scale.  ·  The arrow shows the head axis.",
        fontsize=11,
        color="#485d64",
    )
    fig.text(
        0.075,
        0.038,
        "Tensions are the nominal frictionless closed-loop results. Rope directions are fixed to the rod. Right and left paths can overlap in this view.",
        fontsize=9,
        color="#485d64",
    )
    save_svg(fig, source / "pitch_poles.svg")
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    run(p.parse_args().source)
