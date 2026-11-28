"""Check the archived-command screen independently and export event and phase summaries."""

from collections import defaultdict
import csv
import gzip
import json

import fcl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from mission_screen import (
    ALLOWANCE_MM, CAD_TO_ROD, HERE, MOTION, NAMES, ROOT, added_part_vertices,
    after_mass_update,
)
from adapter import mesh_model
from length_cycle import FastTank, LengthDrive, to_tank
from replay import plant
from tension_report import COLOURS, NICE

OUT = HERE / "results/mission"


def table(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_results():
    path = OUT / "per_step.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with np.load(OUT / "equilibria.npz") as archive, np.load(MOTION / "controller_states.npz") as source:
        steps, states = archive["steps"], archive["z"]
        commands = source["motion_rest_m"]
    assert np.array_equal(steps, np.arange(3405))
    assert len(rows) == len(states) == len(commands) == 3405
    assert [int(r["step"]) for r in rows] == steps.tolist()
    rope = np.array([[float(r[n + "_N"]) for n in NAMES] for r in rows])
    assert rope.shape == (3405, 12) and np.isfinite(rope).all()
    summary = json.loads((OUT / "mission_screen.json").read_text())
    return rows, states, commands, rope, summary


def centreline(rod, detail, clamp, height):
    world = np.vstack((np.zeros(3), (detail["points"] + [.02, 0., 0.]) @ rod.R0.T))
    return to_tank(world * 1000, 20., clamp, height)


def continuous_body_bounds(rows, states, rod, tank):
    radii = [np.linalg.norm(v, axis=1).max() for v in added_part_vertices()]
    checked = []
    previous = None
    for row, state in zip(rows, states):
        detail = rod.base.kinematic_metrics(state)[1]
        points = centreline(rod, detail, float(row["clamp_s_mm"]), tank.entry_h)
        frames = Rotation.from_matrix(rod.R0 @ detail["frames"][[0, rod.sub]])
        gap = float(row["body_tank_gap_lower_bound_mm"])
        if previous is not None:
            prev_points, prev_frames, prev_gap = previous
            displacements = np.linalg.norm(points - prev_points, axis=1)
            rigid_ends = displacements[[1, 1 + rod.sub]] + radii * (prev_frames.inv() * frames).magnitude()
            half_movement = .5 * max(displacements.max(), rigid_ends.max())
            checked.append(dict(previous_step=int(row["step"]) - 1, step=int(row["step"]), phase=row["phase"],
                                body_interpolated_gap_lower_bound_mm=float(min(prev_gap, gap) - half_movement)))
        previous = points, frames, gap
    return checked


def spot_checks(rows, states, commands, rope, summary, phase_ends):
    rod, _ = plant()
    after_mass_update(rod, summary["added_U1_mass_g"])
    drive = LengthDrive(rod)
    tank = FastTank()
    wall = fcl.CollisionObject(mesh_model(tank.mesh.vertices, tank.F))
    path = ROOT / "cad/lanes_u4m2/guides_v2/head_adapter.stl"
    adapter = trimesh.load_mesh(path)
    face = fcl.CollisionObject(mesh_model(adapter.vertices @ CAD_TO_ROD.T, adapter.faces))
    affected = {0, summary["min_rope_N"]["step"], summary["max_rope_N"]["step"]}
    affected.update(phase_ends.values())
    affected.update(summary[name]["step"] for name in (
        "max_pointing_error_deg", "minimum_adjusted_body_gap_bound_mm",
        "minimum_adjusted_adapter_gap_bound_mm", "minimum_interpolated_adapter_gap_bound_mm",
        "minimum_added_CAD_capsule_margin_mm", "maximum_equilibrium_residual",
    ))
    checks = []
    for idx in sorted(affected):
        row, state, rest = rows[idx], states[idx], commands[idx]
        clamp = float(row["clamp_s_mm"])
        detail = rod.base.kinematic_metrics(state)[1]
        trace = centreline(rod, detail, clamp, tank.entry_h)
        orient = rod.R0 @ detail["frames"][-1]
        np.testing.assert_allclose(trace[-1], [float(row[f"head_tank_{a}_mm"]) for a in "xyz"], atol=1e-7)
        face.setTransform(fcl.Transform(orient, trace[-1]))
        body_gap = tank.clearance(trace)[0] - ALLOWANCE_MM
        adapter_gap = fcl.distance(face, wall, fcl.DistanceRequest(), fcl.DistanceResult()) - ALLOWANCE_MM
        exported_body = float(row["body_tank_gap_lower_bound_mm"])
        exported_adapter = float(row["adapter_gap_lower_bound_mm"])
        # The adjusted 2 mm sampling policy may move the winning sample between nearby nodes.
        pass_check = body_gap + .1 >= exported_body and adapter_gap + 1e-6 >= exported_adapter
        tension = drive.force(state, rest)
        np.testing.assert_allclose(tension.ravel(), rope[idx], atol=1e-10, rtol=0)
        eigenvalue = drive.stability(state, rest, tension)
        checks.append(dict(step=idx, phase=row["phase"], remeasured_body_after_allowance_mm=body_gap,
                           body_gap_bound_mm=exported_body, remeasured_adapter_after_allowance_mm=adapter_gap,
                           adapter_gap_bound_mm=exported_adapter, minimum_tangent_eigenvalue=eigenvalue,
                           pass_check=bool(pass_check and eigenvalue > 1e-7)))
        print(f"Checked tank and tangent at step {idx}: {body_gap:.3f} mm, {eigenvalue:.5g}", flush=True)
    return checks, continuous_body_bounds(rows, states, rod, tank)


def plot_phases(rows, rope, phases):
    fig, axes = plt.subplots(4, 1, sharex=True, layout="constrained", figsize=(12, 8.4))
    for i, ax in enumerate(axes[:3]):
        group = "ABC"[i]
        for j, name in enumerate(NAMES[4 * i:4 * i + 4]):
            ax.plot(rope[:, 4 * i + j], color=COLOURS[j], lw=1., label=name.split("_")[1])
        ax.set(ylim=(0, 23), ylabel=f"Set {group} (N)")
    axes[0].legend(loc="upper left", ncols=4, frameon=False)
    refs = [("body_tank_gap_lower_bound_mm", "Body (sampled)", "#19596e"),
            ("adapter_gap_lower_bound_mm", "Adapter (sampled)", "#8f5331")]
    for key, name, color in refs:
        axes[3].plot([float(r[key]) for r in rows], lw=1.1, label=name, color=color)
    axes[3].axhline(5, color="#4b4d54", lw=.9, ls="--", label="5 mm threshold")
    axes[3].set(xlabel="Mission step", ylabel="Gap bound (mm)")
    axes[3].legend(loc="upper left", ncols=3, frameon=False)
    starts, labels = [], []
    for n, (phase, indices) in enumerate(phases.items()):
        a, b = indices[0], indices[-1]
        starts.append((a + b) / 2)
        labels.append(NICE[phase])
        for ax in axes:
            if n % 2 == 0:
                ax.axvspan(a, b, fc="#d2e4ec", alpha=.30, zorder=-1)
            ax.axvline(a, color="#7c8b98", lw=.55, alpha=.5)
    top = axes[0].secondary_xaxis("top")
    top.set_xticks(starts, labels=labels, rotation=30, ha="left", fontsize=8)
    for ax in axes:
        ax.set_xlim(0, len(rows) - 1)
        ax.grid(axis="y", alpha=.16)
    fig.suptitle("500 g U4+M2 mission with the nominal single-leaf U1 mass")
    fig.savefig(OUT / "mission_overview.png", dpi=180)
    plt.close(fig)


def main():
    rows, states, commands, rope, summary = read_results()
    phases = defaultdict(list)
    for i, row in enumerate(rows):
        phases[row["phase"]].append(i)
    phase_ends = {phase: indices[-1] for phase, indices in phases.items()}
    assert len(phase_ends) == 11
    gap_fields = ("body_tank_gap_lower_bound_mm", "adapter_gap_lower_bound_mm")
    sections = []
    for phase, indices in phases.items():
        block = rope[indices]
        part = [rows[i] for i in indices]
        end = part[-1]
        values = {key: min(float(r[key]) for r in part) for key in gap_fields}
        sections.append(dict(phase=phase, first_step=indices[0], last_step=indices[-1], states=len(indices),
                             min_rope_N=float(block.min()), max_rope_N=float(block.max()),
                             max_pointing_error_deg=max(float(r["pointing_error_deg"]) for r in part),
                             endpoint_target_elevation_deg=end["target_elevation_deg"],
                             endpoint_signed_pitch_deg=end["signed_forward_up_pitch_deg"], **values))
    table(OUT / "phase_summary.csv", sections)
    events = list(phase_ends.items()) + [("loaded_start", 0), ("peak_rope", summary["max_rope_N"]["step"]),
                                       ("body_gap_minimum", summary["minimum_adjusted_body_gap_bound_mm"]["step"])]
    table(OUT / "events.csv", [dict(event=name, **rows[i]) for name, i in events])
    plot_phases(rows, rope, phases)
    checks, intervals = spot_checks(rows, states, commands, rope, summary, phase_ends)
    table(OUT / "independent_spot_checks.csv", checks)
    table(OUT / "body_interpolated_bounds.csv", intervals)
    result = dict(
        independently_checked_states=len(checks),
        minimum_tangent_eigenvalue=min(checks, key=lambda item: item["minimum_tangent_eigenvalue"]),
        failed_spot_steps=[r["step"] for r in checks if not r["pass_check"]],
        interpolated_body_intervals=len(intervals),
        minimum_body_interpolated_bound=min(intervals, key=lambda r: r["body_interpolated_gap_lower_bound_mm"]),
        body_interpolated_intervals_below_5mm=sum(r["body_interpolated_gap_lower_bound_mm"] < 5 for r in intervals),
    )
    (OUT / "independent_verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
