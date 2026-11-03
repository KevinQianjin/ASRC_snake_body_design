"""Maintain a horizontal centerline while applying self-weight and 500 g.

This starts with a virgin backbone and controls every accepted load increment,
unlike recovering the pre-existing sagged/plastically deformed loaded state.
No previous configuration, simulation, or material database is overwritten.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np

from snake_model_ropes import Control, HERE, ROPE_NAMES, RopeRobot, read_json, write_json
from snake_model_ropes_level import (LevelInverse, TensionRobot, describe_target, save_results,
                                    state_from_saved_case)


def hold_during_loading(robot, force_robot, settings, load_settings, *, progress=None):
    """Stop at first missed load target; never substitute a partial-load success."""
    settings = copy.deepcopy(settings)
    settings["search"]["max_iterations"] = load_settings["max_iterations_per_load"]
    settings["search"]["max_trials"] = load_settings["max_trials_per_load"]
    initial = robot.virgin_state()
    state = initial
    last_level_state = initial
    last_level_payload = 0.
    last_level_gravity = 0.
    gravity_steps = int(load_settings["gravity_steps"])
    payload_steps = int(load_settings["payload_steps"])
    requested_payload = float(load_settings["payload_kg"])
    if min(gravity_steps, payload_steps) <= 0 or requested_payload < 0:
        raise ValueError("positive load step counts and nonnegative payload are required")
    schedule = [("self_weight", i, i/gravity_steps, 0.) for i in range(1, gravity_steps+1)]
    schedule += [("payload", i, 1., requested_payload*i/payload_steps)
                 for i in range(1, payload_steps+1)]
    trace, loads, failed_trials = [], [], []
    final = LevelInverse(robot, force_robot, settings).solve(initial)
    stopped = False
    load_error = None
    requested_gravity, attempted_payload = 0., 0.
    total_trials = 0
    for load_index, (phase, phase_index, gravity, payload) in enumerate(schedule, 1):
        requested_gravity, attempted_payload = gravity, payload
        control = Control(state.control.take_up_mm.copy(), gravity, payload, 1.)
        try:
            loaded = robot.advance(state, control)
        except RuntimeError as exc:
            stopped = True
            load_error = str(exc)
            break
        controller = LevelInverse(robot, force_robot, settings)
        candidate = controller.solve(loaded)
        total_trials += controller.trials
        for row in candidate["trajectory"]:
            trace.append(dict(load_index=load_index, phase=phase, phase_index=phase_index,
                              gravity_scale=gravity, payload_kg=payload, **row))
        failed_trials.extend(dict(load_index=load_index, **row) for row in candidate["failed_trials"])
        state = state_from_saved_case(candidate["final_result"], force_control=False)
        final = candidate
        s = candidate["summary"]
        loads.append(dict(load_index=load_index, phase=phase, phase_index=phase_index,
                          gravity_scale=gravity, payload_kg=payload,
                          target_reached=s["target_reached"],
                          within_reference_model_range=s["within_reference_model_range"],
                          tip_x_mm=s["tip_x_mm"], tip_y_mm=s["tip_y_mm"], tip_z_mm=s["tip_z_mm"],
                          max_centerline_transverse_mm=s["max_centerline_transverse_mm"],
                          max_link_tilt_deg=s["max_link_tilt_from_horizontal_deg"],
                          max_tension_n=max(s[f"tension_{name}_n"] for name in ROPE_NAMES),
                          stop_reason=s["stop_reason"]))
        for name in ROPE_NAMES:
            loads[-1][f"take_up_{name}_mm"] = s[f"take_up_{name}_mm"]
            loads[-1][f"tension_{name}_n"] = s[f"tension_{name}_n"]
        if progress:
            progress(loads[-1])
        if s["target_reached"]:
            last_level_state = state
            last_level_gravity, last_level_payload = gravity, payload
        else:
            stopped = True
            break
    completed = (not stopped and np.isclose(state.control.gravity_scale, 1.) and
                 np.isclose(state.control.payload_kg, requested_payload) and
                 final["summary"]["target_reached"])
    s = final["summary"]
    s["correction_stop_reason"] = s["stop_reason"]
    s.update(scenario_name=load_settings["scenario_name"],
             gravity_scale=state.control.gravity_scale,
             control_procedure="hold_during_progressive_loading_from_virgin_state",
             requested_payload_kg=requested_payload,
             requested_gravity_scale=1., requested_load_applied=bool(
                 np.isclose(state.control.gravity_scale, 1.) and
                 np.isclose(state.control.payload_kg, requested_payload)),
             completed_requested_loading=bool(completed), target_reached=bool(completed),
             status=("hold_target_reached_within_screening" if s["within_reference_model_range"] else
                     "hold_target_reached_extrapolated") if completed else "hold_target_not_reached_at_requested_load",
             stop_reason="requested payload held at target" if completed else (
                 "load equilibrium failed before position correction" if load_error else
                 "loading stopped at first unachieved position target"),
             attempted_payload_kg=attempted_payload, attempted_gravity_scale=requested_gravity,
             last_level_payload_kg=last_level_payload, last_level_gravity_scale=last_level_gravity,
             load_increment_count=len(loads), forward_trial_count=total_trials)
    s["initial_tip_x_mm"] = float(robot.geometry(initial.x)["pts"][-1, 0]*1000)
    s["initial_tip_y_mm"] = float(robot.geometry(initial.x)["pts"][-1, 1]*1000)
    final["stopped_load_initial_control"] = final["initial_control"]
    final["initial_control"] = initial.control.as_dict()
    final["initial_pts_m"] = robot.geometry(initial.x)["pts"]
    final["trajectory"] = trace or [dict(load_index=0, phase="initial", phase_index=0,
                                         gravity_scale=0., payload_kg=0.,
                                         **LevelInverse(robot, force_robot, settings).trace_row(initial, 0))]
    final["loads"] = loads
    final["failed_trials"] = failed_trials
    final["load_equilibrium_error"] = load_error
    final["last_level_result"] = robot.result(last_level_state, "last_level_load")
    final["last_level_summary"] = LevelInverse(robot, force_robot, settings).solve(last_level_state)["summary"]
    return final


def plot_hold(output, results, source, settings):
    os.environ.setdefault("MPLCONFIGDIR", str(output/".mplconfig"))
    os.environ.setdefault("XDG_CACHE_HOME", str(output/".cache"))
    (Path(os.environ["XDG_CACHE_HOME"])/"fontconfig").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = {m["id"]:m["label"] for m in source["material_catalog"]["materials"]}
    fig, axes = plt.subplots(2, len(results), figsize=(6*len(results), 8),
                             squeeze=False, layout="constrained")
    length = results[0]["summary"]["reference_length_mm"]
    all_y = np.concatenate([np.asarray(r["final_result"]["pts_m"])[:, 1]*1000 for r in results] +
                           [np.asarray(r["last_level_result"]["pts_m"])[:, 1]*1000 for r in results])
    tol = settings["target"]["tolerance_mm"]
    extent = max(float(np.abs(all_y).max()), 2*tol)*1.25
    max_tilt = max(r["summary"]["max_link_tilt_from_horizontal_deg"] for r in results)
    angle_tol = settings["target"].get("angle_tolerance_deg", 1.)
    for column, (ax, result) in enumerate(zip(axes[0], results)):
        s = result["summary"]
        best = np.asarray(result["final_result"]["pts_m"])*1000
        last = np.asarray(result["last_level_result"]["pts_m"])*1000
        ax.plot([0, length], [0, 0], ":", color="#64748b", label="Unloaded reference")
        ax.plot(last[:, 0], last[:, 1], color="#2563eb", lw=2, label="Last load meeting horizontal target")
        ax.plot(best[:, 0], best[:, 1], color="#ea580c", lw=2, label="Last verified load candidate")
        ax.fill_between([0, length], [-tol, -tol], [tol, tol], color="#15803d", alpha=.2,
                        label=f"Horizontal centerline band (+/- {tol:g} mm)")
        ax.scatter(best[-1, 0], best[-1, 1], color="#ea580c", zorder=4)
        ax.set(title=f"{labels[s['material']]} | 500 g reached: {s['target_reached']}\n"
                     f"Shown candidate: gravity {s['gravity_scale']:.2f}, payload {s['payload_kg']*1000:g} g",
               xlabel="X forward (mm)", ylabel="Y height (mm; vertical scale magnified)",
               xlim=(-.03*length, 1.03*length), ylim=(-extent, extent))
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, loc="lower left")
        angle_ax = axes[1, column]
        for case, label, color in ((result["last_level_result"], "Last achieved load", "#2563eb"),
                                   (result["final_result"], "Verified candidate", "#ea580c")):
            frames = np.asarray(case["frames"])[1:, :, 0]
            angles = np.degrees(np.arctan2(np.linalg.norm(frames[:, 1:], axis=1), frames[:, 0]))
            angle_ax.plot(np.arange(1, len(angles)+1), angles, color=color, label=label)
        angle_ax.axhline(angle_tol, color="#15803d", ls="--", label="Angle tolerance")
        angle_ax.set(xlabel="Module index from base", ylabel="Tilt from +X (deg)",
                     ylim=(0, max(max_tilt, 2*angle_tol)*1.2), xlim=(1, len(best)-1))
        angle_ax.grid(alpha=.2)
        angle_ax.legend(fontsize=8)
    fig.suptitle("Hold horizontal shape during loading | "+describe_target(settings["target"]))
    fig.savefig(output/"hold_horizontal.png", dpi=170)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE/"rope_config_hold_horizontal.json")
    parser.add_argument("--material", default="all")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    load_settings = read_json(args.config)
    settings = read_json(HERE/load_settings["inverse_settings"])
    settings["target"].update(load_settings.get("target", {}))
    settings["scenario_name"] = load_settings["scenario_name"]
    settings["load_procedure"] = load_settings
    source_path = (HERE/load_settings["source_results"]).resolve()
    source = read_json(source_path)
    output = (args.output_dir or HERE/load_settings["output_directory"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    preserved = {}
    for folder in ("rope_results", "rope_results_tip500g"):
        for path in (HERE/folder).iterdir():
            if path.is_file():
                preserved[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("snake_model.py", "craft_data.py", "rope_config.json", "rope_config_tip500g.json"):
        preserved[name] = hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    catalog = {m["id"]:m for m in source["material_catalog"]["materials"]}
    materials = load_settings["materials"] if args.material == "all" else args.material.split(",")
    results = []
    print("Hold target:", describe_target(settings["target"]), flush=True)
    print("Start with virgin backbone; compensate self-weight, then progressively add 500 g.")
    print("Numerical search bounds are not hardware ratings; stop at first missed load target.", flush=True)
    for material in materials:
        config = copy.deepcopy(source["config"])
        config["scenario_name"] = load_settings["scenario_name"]
        robot = RopeRobot(config, catalog[material], catalog[config["ropes"]["material"]])
        force_robot = TensionRobot(config, catalog[material], catalog[config["ropes"]["material"]])
        print(f"\n{material}: {robot.n} modules, {robot.reference_length*1000:.1f} mm", flush=True)

        def progress(row):
            print(f"  {row['phase']} {row['phase_index']:2d}: gravity={row['gravity_scale']:.2f} "
                  f"payload={row['payload_kg']*1000:.1f} g X={row['tip_x_mm']:.2f} mm "
                  f"Y={row['tip_y_mm']:.3f} mm T_max={row['max_tension_n']:.2f} N "
                  f"target={row['target_reached']}", flush=True)

        result = hold_during_loading(robot, force_robot, settings, load_settings, progress=progress)
        results.append(result)
        s = result["summary"]
        print("  RESULT:", s["status"], flush=True)
        print(f"  Last held load: gravity={s['last_level_gravity_scale']:.2f}, "
              f"payload={s['last_level_payload_kg']*1000:.1f} g", flush=True)
        print(f"  Candidate load: gravity={s['gravity_scale'] if 'gravity_scale' in s else result['final_result']['control']['gravity_scale']:.2f}, "
              f"payload={s['payload_kg']*1000:.1f} g", flush=True)
        label = "target commands" if s["target_reached"] else "candidate commands (NOT a 500 g target solution)"
        print(f"  {label} [mm, top/right/bottom/left]:",
              "/".join(f"{s[f'take_up_{name}_mm']:+.3f}" for name in ROPE_NAMES), flush=True)
    for name, expected in preserved.items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"preserved simulation changed: {name}")
    save_results(output, source_path, source, settings, results, preserved)
    with (output/"load_steps.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        import csv
        rows = [dict(material=r["summary"]["material"], **row) for r in results for row in r["loads"]]
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    with (output/"last_level_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        rows = [dict(gravity_scale=r["last_level_result"]["control"]["gravity_scale"],
                     **r["last_level_summary"]) for r in results]
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    if not args.no_plots:
        plot_hold(output, results, source, settings)
    print(f"\nSaved hold-horizontal results: {output}")
    print("Existing no-payload and 500 g simulations preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
