"""Inverse tendon control for the D chain: shape or endpoint position targets.

Uses the existing constitutive model without changing the previous scenarios.
Candidate evaluations start from one immutable accepted plastic state.
"""
from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.dont_write_bytecode = True
import numpy as np
from scipy.optimize import lsq_linear

from snake_model_ropes import (Control, GRAVITY, HERE, ROPE_NAMES, RopeRobot,
                               State, json_value, read_json, write_json)


@dataclass
class TensionControl:
    tension_n: np.ndarray
    gravity_scale: float = 0.
    payload_kg: float = 0.
    engagement: float = 1.

    @property
    def take_up_mm(self):
        return np.zeros(4)

    def between(self, other, fraction):
        return TensionControl(
            self.tension_n + fraction*(other.tension_n-self.tension_n),
            self.gravity_scale + fraction*(other.gravity_scale-self.gravity_scale),
            self.payload_kg + fraction*(other.payload_kg-self.payload_kg))

    def as_dict(self):
        return dict(tension_n=self.tension_n.tolist(), gravity_scale=self.gravity_scale,
                    payload_kg=self.payload_kg, rope_engagement=1.)


class TensionRobot(RopeRobot):
    """Use prescribed tensions for inverse search, then recover winch lengths."""

    def virgin_state(self):
        state = super().virgin_state()
        state.control = TensionControl(np.zeros(4))
        return state

    def rope_response(self, geometry, control):
        if not isinstance(control, TensionControl):
            return super().rope_response(geometry, control)
        tension = np.asarray(control.tension_n, dtype=float)
        if tension.shape != (4,) or not np.isfinite(tension).all() or (tension < 0).any():
            raise ValueError("four finite, nonnegative tensions are required")
        path = geometry["rope_lengths"]
        rest = path/(1+tension/self.rope_ea)
        return dict(rest=rest, extension=path-rest, strain=tension/self.rope_ea,
                    tension=tension,
                    energy=float(tension @ (path-self.reference_length)),
                    gradient=tension @ geometry["rope_length_jac"])

    def equivalent_length_state(self, state, slack_margin_mm=1.):
        """Recover positive take-up/negative payout including nylon extension."""
        geo = self.geometry(state.x)
        tension = state.control.tension_n
        rest = geo["rope_lengths"]/(1+tension/self.rope_ea)
        rest = rest + np.where(tension <= 1e-8, slack_margin_mm/1000, 0.)
        commands = (self.initial_rope_lengths-rest)*1000
        ctrl = Control(commands, state.control.gravity_scale, state.control.payload_kg, 1.)
        return State(state.x.copy(), state.plastic_strain.copy(),
                     state.accumulated_plastic_strain.copy(), ctrl,
                     state.dissipated_energy_j, state.accepted_steps)

    def length_result(self, state, stage):
        return super().result(self.equivalent_length_state(state), stage)


def state_from_saved_case(case, *, force_control=True):
    control = (TensionControl(np.array(case["rope_tension_n"], dtype=float),
                              case["control"]["gravity_scale"], case["control"]["payload_kg"])
               if force_control else
               Control(np.array(case["control"]["take_up_mm"], dtype=float),
                       case["control"]["gravity_scale"], case["control"]["payload_kg"],
                       case["control"]["rope_engagement"]))
    return State(np.array(case["state_x"], dtype=float),
                 np.array(case["fiber_plastic_strain"], dtype=float),
                 np.array(case["fiber_accumulated_plastic_strain"], dtype=float),
                 control, case["summary"]["dissipated_energy_j"],
                 case["summary"]["accepted_steps"])


class TrialFailure(RuntimeError):
    pass


class LevelInverse:
    """Quasi-static inverse controller; every accepted step is length-controlled.

    Direct winch search uses the original forward physical model. The optional
    tension predictor also verifies every command in that model. Rejected
    trials never update the accepted history.
    Search failure is not a proof of global mechanical infeasibility.
    """

    def __init__(self, robot, force_robot, settings):
        self.robot, self.force_robot = robot, force_robot
        self.settings = copy.deepcopy(settings)
        self.target = settings["target"]
        self.search = settings["search"]
        self.screening = settings["screening"]
        self.balanced = bool(self.search.get("balanced_sides", self.search.get("balanced_side_tensions", True)))
        self.command_mode = self.search.get("parameterization", "tension") == "winch_length"
        self.n_parameters = 3 if self.balanced else 4
        self.max_tension = float(self.search["max_tension_n"])
        self.max_step = float(self.search["max_command_step_mm"] if self.command_mode else
                              self.search["max_tension_step_n"])
        self.step = float(self.search["finite_difference_mm"] if self.command_mode else
                          self.search["finite_difference_n"])
        self.max_trials = int(self.search["max_trials"])
        if min(self.max_tension, self.max_step, self.step, self.max_trials) <= 0:
            raise ValueError("search limits and finite-difference step must be positive")
        if not 0 <= self.target["minimum_forward_ratio"] <= 1:
            raise ValueError("minimum_forward_ratio must be between 0 and 1")
        if self.target["mode"] not in ("horizontal_shape", "level_tip", "tip_position"):
            raise ValueError("target.mode must be horizontal_shape, level_tip or tip_position")
        if self.target["tolerance_mm"] <= 0:
            raise ValueError("target tolerance must be positive")
        if self.target["mode"] == "horizontal_shape" and self.target["angle_tolerance_deg"] <= 0:
            raise ValueError("horizontal angle tolerance must be positive")
        if self.balanced and abs(self.target["tip_z_mm"]) > 1e-9:
            raise ValueError("a lateral target requires balanced_sides=false")
        self.trials = 0
        self.failed_trials = []

    def tensions(self, state):
        geo = self.robot.geometry(state.x)
        return self.robot.rope_response(geo, state.control)["tension"]

    def parameters(self, values):
        if self.balanced:
            return np.array([values[0], values[2], .5*(values[1]+values[3])])
        return np.array(values, dtype=float)

    def expand_controls(self, parameters):
        if self.balanced:
            top, bottom, side = parameters
            return np.array([top, side, bottom, side])
        return np.asarray(parameters, dtype=float)

    def error(self, state):
        geo = self.robot.geometry(state.x)
        points = geo["pts"]*1000
        tip = points[-1]
        y, z = self.target["tip_y_mm"], self.target["tip_z_mm"]
        if self.target["mode"] == "tip_position":
            x = self.target.get("tip_x_mm", self.robot.reference_length*1000)
            return tip-np.array([x, y, z])
        min_x = self.target["minimum_forward_ratio"]*self.robot.reference_length*1000
        if self.target["mode"] == "horizontal_shape":
            # Whole-centerline and link-direction errors, not just tip height.
            transverse = (points[1:, 1:]-np.array([y, z])).ravel()/np.sqrt(self.robot.n)
            directions = geo["frames"][1:, :, 0]
            direction_error = (directions-np.array([1., 0., 0.])).ravel()
            weight = self.target.get("angle_weight_mm", float(self.robot.length.mean()*1000))
            return np.concatenate((transverse, direction_error*weight/np.sqrt(self.robot.n),
                                   [self.target.get("reach_weight", 1.)*max(min_x-tip[0], 0.)]))
        return np.array([tip[1]-y, tip[2]-z,
                         self.target.get("reach_weight", 1.)*max(min_x-tip[0], 0.)])

    def reached(self, state):
        geo = self.robot.geometry(state.x)
        tip = geo["pts"][-1]*1000
        tol = self.target["tolerance_mm"]
        if self.target["mode"] == "tip_position":
            return bool(np.linalg.norm(self.error(state)) <= tol)
        if self.target["mode"] == "horizontal_shape":
            transverse = geo["pts"][1:, 1:]*1000-np.array([
                self.target["tip_y_mm"], self.target["tip_z_mm"]])
            directions = geo["frames"][1:, :, 0]
            tilt = np.degrees(np.arctan2(np.linalg.norm(directions[:, 1:], axis=1), directions[:, 0]))
            return bool(np.linalg.norm(transverse, axis=1).max() <= tol and
                        tilt.max() <= self.target["angle_tolerance_deg"] and
                        tip[0] >= self.target["minimum_forward_ratio"]*
                        self.robot.reference_length*1000-tol)
        return bool(np.hypot(tip[1]-self.target["tip_y_mm"],
                             tip[2]-self.target["tip_z_mm"]) <= tol and
                    tip[0] >= self.target["minimum_forward_ratio"]*
                    self.robot.reference_length*1000-tol)

    def trial(self, accepted, parameters):
        if self.trials >= self.max_trials:
            raise TrialFailure("trial budget exhausted")
        self.trials += 1
        target_tensions = self.expand_controls(parameters)
        if (target_tensions < -1e-8).any() or (target_tensions > self.max_tension+1e-8).any():
            raise TrialFailure("tension search bound exceeded")
        force_start = State(accepted.x.copy(), accepted.plastic_strain.copy(),
                            accepted.accumulated_plastic_strain.copy(),
                            TensionControl(self.tensions(accepted), accepted.control.gravity_scale,
                                           accepted.control.payload_kg),
                            accepted.dissipated_energy_j, accepted.accepted_steps)
        force_target = TensionControl(np.maximum(target_tensions, 0.),
                                      accepted.control.gravity_scale, accepted.control.payload_kg)
        try:
            predicted = self.force_robot.advance(force_start, force_target)
            equivalent = self.force_robot.equivalent_length_state(
                predicted, self.search.get("slack_margin_mm", 1.))
            commands = equivalent.control.take_up_mm
            if (commands > self.search["max_take_up_mm"]).any() or (
                    commands < -self.search["max_pay_out_mm"]).any():
                raise TrialFailure("winch travel search bound exceeded")
            # Forward verification starts from the SAME accepted plastic state,
            # not the history produced by the discarded force predictor.
            actual = self.robot.advance(accepted, equivalent.control)
            if np.max(self.tensions(actual)) > self.max_tension+1e-4:
                raise TrialFailure("forward-verified tension search bound exceeded")
            return actual
        except (RuntimeError, ValueError, FloatingPointError) as exc:
            if isinstance(exc, TrialFailure):
                raise
            raise TrialFailure(str(exc)) from exc

    def command_trial(self, accepted, parameters):
        """Direct winch search: use only the original forward physical model."""
        if self.trials >= self.max_trials:
            raise TrialFailure("trial budget exhausted")
        self.trials += 1
        commands = self.expand_controls(parameters)
        if (commands > self.search["max_take_up_mm"]+1e-8).any() or (
                commands < -self.search["max_pay_out_mm"]-1e-8).any():
            raise TrialFailure("winch travel search bound exceeded")
        target = Control(commands, accepted.control.gravity_scale, accepted.control.payload_kg, 1.)
        try:
            actual = self.robot.advance(accepted, target)
            if np.max(self.tensions(actual)) > self.max_tension+1e-4:
                raise TrialFailure("forward-verified tension search bound exceeded")
            return actual
        except (RuntimeError, ValueError, FloatingPointError) as exc:
            if isinstance(exc, TrialFailure):
                raise
            raise TrialFailure(str(exc)) from exc

    def trace_row(self, state, iteration):
        tip = self.robot.geometry(state.x)["pts"][-1]*1000
        tension = self.tensions(state)
        row = dict(iteration=iteration, trial_count=self.trials,
                   objective_error_mm=float(np.linalg.norm(self.error(state))),
                   tip_x_mm=float(tip[0]), tip_y_mm=float(tip[1]), tip_z_mm=float(tip[2]),
                   forward_ratio=float(tip[0]/(self.robot.reference_length*1000)))
        for name, force, command in zip(ROPE_NAMES, tension, state.control.take_up_mm):
            row[f"tension_{name}_n"] = float(force)
            row[f"take_up_{name}_mm"] = float(command)
        return row

    def solve(self, initial, *, progress=None):
        if initial.control.engagement != 1:
            raise ValueError("inverse control must start with locked winches")
        if np.max(self.tensions(initial)) > self.max_tension:
            raise ValueError("initial tensions already exceed the search bounds")
        current = initial
        states = [initial]
        trace = [self.trace_row(initial, 0)]
        stop = "maximum iterations reached"
        for iteration in range(1, int(self.search["max_iterations"])+1):
            if self.reached(current):
                stop = "position target reached"
                break
            if self.trials >= self.max_trials:
                stop = "trial budget exhausted"
                break
            parameters = self.parameters(current.control.take_up_mm if self.command_mode else
                                         self.tensions(current))
            parameter_min = -self.search["max_pay_out_mm"] if self.command_mode else 0.
            parameter_max = self.search["max_take_up_mm"] if self.command_mode else self.max_tension
            residual = self.error(current)
            old_error = float(np.linalg.norm(residual))
            cache = {}

            def evaluate(p):
                key = tuple(np.round(p, 9))
                if key not in cache:
                    try:
                        state = self.command_trial(current, p) if self.command_mode else self.trial(current, p)
                        cache[key] = (float(np.linalg.norm(self.error(state))), state)
                    except TrialFailure as exc:
                        self.failed_trials.append(dict(iteration=iteration, reason=str(exc)))
                        cache[key] = (np.inf, None)
                return cache[key]

            jacobian = np.zeros((len(residual), self.n_parameters))
            for j in range(self.n_parameters):
                delta = self.step if parameters[j]+self.step <= parameter_max else -self.step
                p = parameters.copy(); p[j] += delta
                _, candidate = evaluate(p)
                # A small positive probe may only reel in slack and produce no
                # force or motion. Expand the probe before declaring this
                # control direction ineffective. Every probe is still discarded
                # history-wise; only an improving forward state is committed.
                while (self.command_mode and candidate is not None and delta > 0 and
                       np.linalg.norm(self.error(candidate)-residual) < 1e-5 and
                       delta < self.max_step and parameters[j]+delta < parameter_max):
                    larger = min(2*delta, self.max_step, parameter_max-parameters[j])
                    if larger <= delta+1e-9:
                        break
                    delta = larger
                    p = parameters.copy(); p[j] += delta
                    _, candidate = evaluate(p)
                if candidate is not None:
                    jacobian[:, j] = (self.error(candidate)-residual)/delta
            damping = (self.search.get("damping_mm_per_mm", .05) if self.command_mode else
                       self.search.get("damping_mm_per_n", .02))
            matrix = np.vstack((jacobian, damping*np.eye(self.n_parameters)))
            rhs = np.concatenate((-residual, np.zeros(self.n_parameters)))
            lower = np.maximum(-self.max_step, parameter_min-parameters)
            upper = np.minimum(self.max_step, parameter_max-parameters)
            direction = lsq_linear(matrix, rhs, bounds=(lower, upper), tol=1e-10).x
            best_error, best_state = old_error, None
            improvement = self.search.get("minimum_improvement_mm", .01)
            for scale in (1., .5, .25, .125):
                p = np.clip(parameters+scale*direction, parameter_min, parameter_max)
                error, candidate = evaluate(p)
                if error < best_error-improvement:
                    best_error, best_state = error, candidate
                    break
            if best_state is None:
                # A bounded coordinate search is a fallback for plastic kinks;
                # it still evaluates each candidate from the unmodified state.
                for fraction in (.5, .25, .125, .0625):
                    for j in range(self.n_parameters):
                        for sign in (1., -1.):
                            p = parameters.copy()
                            p[j] = np.clip(p[j]+sign*self.max_step*fraction, parameter_min, parameter_max)
                            if np.allclose(p, parameters, atol=1e-9):
                                continue
                            error, candidate = evaluate(p)
                            if error < best_error-improvement:
                                best_error, best_state = error, candidate
            if best_state is None:
                stop = ("trial budget exhausted" if self.trials >= self.max_trials else
                        "no improving verified step found within local search")
                break
            current = best_state
            states.append(current)
            trace.append(self.trace_row(current, iteration))
            if progress:
                progress(trace[-1])
        # Reject stationary saddles: retain the best locally stable, physically
        # forward-verified accepted state instead of calling it a solution.
        stable = None
        for candidate in reversed(states):
            try:
                stable = self.robot.result(candidate, "inverse_level_candidate")
                current = candidate
                break
            except RuntimeError:
                continue
        if stable is None:
            raise RuntimeError("no locally stable candidate was retained")
        achieved = self.reached(current)
        if achieved:
            stop = "position target reached"
        tension = stable["rope_tension_n"]
        strain = float(np.max(stable["rope_elastic_strain"]))
        q, _ = self.robot.angles_and_strain(current.x)
        max_joint = float(np.linalg.norm(q, axis=1).max())
        within_range = (strain <= self.screening["max_rope_strain_fraction"] and
                        max_joint <= self.screening["max_joint_angle_rad"])
        points = stable["pts_m"]
        directions = stable["frames"][1:, :, 0]
        tilt = np.degrees(np.arctan2(np.linalg.norm(directions[:, 1:], axis=1), directions[:, 0]))
        transverse = points[1:, 1:]*1000
        transverse_norm = np.linalg.norm(transverse, axis=1)
        summary = dict(material=self.robot.material["id"],
                       scenario_name=self.settings["scenario_name"],
                       target_mode=self.target["mode"],
                       search_parameterization="winch_length" if self.command_mode else "tension",
                       status=("target_reached_within_screening" if within_range else
                               "target_reached_extrapolated") if achieved else "target_not_reached",
                       target_reached=achieved, within_reference_model_range=bool(within_range),
                       hardware_limits_calibrated=False,
                       stop_reason=stop, accepted_control_steps=len(states)-1,
                       forward_trial_count=self.trials,
                       payload_kg=current.control.payload_kg,
                       reference_length_mm=self.robot.reference_length*1000,
                       target_tip_y_mm=self.target["tip_y_mm"],
                       target_tip_z_mm=self.target["tip_z_mm"],
                       target_tip_x_mm=self.target.get("tip_x_mm"),
                       target_tolerance_mm=self.target["tolerance_mm"],
                       target_angle_tolerance_deg=self.target.get("angle_tolerance_deg"),
                       minimum_tip_x_mm=(self.target["minimum_forward_ratio"]*
                                        self.robot.reference_length*1000
                                        if self.target["mode"] != "tip_position" else None),
                       initial_tip_x_mm=float(self.robot.geometry(initial.x)["pts"][-1, 0]*1000),
                       initial_tip_y_mm=float(self.robot.geometry(initial.x)["pts"][-1, 1]*1000),
                       tip_x_mm=float(points[-1, 0]*1000),
                       tip_y_mm=float(points[-1, 1]*1000),
                       tip_z_mm=float(points[-1, 2]*1000),
                       forward_ratio=float(points[-1, 0]/self.robot.reference_length),
                       target_error_mm=float(np.linalg.norm(self.error(current))),
                       max_rope_strain_fraction=strain,
                       max_joint_angle_deg=float(np.degrees(max_joint)),
                       max_centerline_height_mm=float(np.max(np.abs(points[:, 1]))*1000),
                       max_centerline_transverse_mm=float(transverse_norm.max()),
                       rms_centerline_transverse_mm=float(np.sqrt(np.mean(transverse_norm**2))),
                       max_link_tilt_from_horizontal_deg=float(tilt.max()),
                       tip_tilt_from_horizontal_deg=float(tilt[-1]),
                       equilibrium_moment_residual_nm=stable["summary"]["moment_residual_nm"],
                       equilibrium_axial_residual_n=stable["summary"]["axial_force_residual_n"],
                       min_stability_eigenvalue=stable["summary"]["min_stability_eigenvalue"],
                       warnings=stable["summary"]["warnings"])
        for name, force, command in zip(ROPE_NAMES, tension, current.control.take_up_mm):
            summary[f"tension_{name}_n"] = float(force)
            summary[f"take_up_{name}_mm"] = float(command)
        return dict(summary=summary, initial_pts_m=self.robot.geometry(initial.x)["pts"],
                    final_result=stable, trajectory=trace, failed_trials=self.failed_trials,
                    initial_control=initial.control.as_dict())


def probe(material="ss304_annealed"):
    data = read_json(HERE/"rope_results_tip500g/comparison.json")
    catalog = {m["id"]: m for m in data["material_catalog"]["materials"]}
    robot = TensionRobot(data["config"], catalog[material], catalog["nylon_pa6_reference"])
    case = next(c for c in data["cases"] if c["summary"]["material"] == material and
                c["summary"]["stage"] == "tip_payload_500g")
    state = state_from_saved_case(case)
    for tension in (150., 200., 250., 300., 400., 500., 600., 800.):
        try:
            state = robot.advance(state, TensionControl(np.array([tension, 0., 0., 0.]), 1., .5))
        except RuntimeError as exc:
            print("FAILED", tension, str(exc), flush=True)
            break
        pts = robot.geometry(state.x)["pts"]
        q, _ = robot.angles_and_strain(state.x)
        length_state = robot.equivalent_length_state(state)
        print(json.dumps(dict(tension=tension, tip_mm=(pts[-1]*1000).tolist(),
                              take_up_mm=length_state.control.take_up_mm.tolist(),
                              max_joint_deg=float(np.degrees(np.linalg.norm(q, axis=1)).max()))), flush=True)


def plot_results(output, results, source, settings):
    os.environ.setdefault("MPLCONFIGDIR", str(output/".mplconfig"))
    os.environ.setdefault("XDG_CACHE_HOME", str(output/".cache"))
    (Path(os.environ["XDG_CACHE_HOME"])/"fontconfig").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = {m["id"]:m["label"] for m in source["material_catalog"]["materials"]}
    fig, axes = plt.subplots(1, len(results), figsize=(6*len(results), 6), squeeze=False,
                             layout="constrained")
    length = results[0]["summary"]["reference_length_mm"]
    low_y = min(float(np.min(r["final_result"]["pts_m"][:, 1])) for r in results)*1000
    low_y = min(low_y, min(float(np.min(r["initial_pts_m"][:, 1])) for r in results)*1000)
    for ax, result in zip(axes[0], results):
        s = result["summary"]
        start = np.asarray(result["initial_pts_m"])*1000
        end = np.asarray(result["final_result"]["pts_m"])*1000
        ax.plot(start[:, 0], start[:, 1], label="Before inverse control", color="#2563eb", lw=2)
        ax.plot(end[:, 0], end[:, 1], label="Best verified candidate", color="#ea580c", lw=2)
        y = settings["target"]["tip_y_mm"]
        if settings["target"]["mode"] == "tip_position":
            ax.scatter(settings["target"].get("tip_x_mm", length), y, marker="x", s=70,
                       color="#15803d", label="Target tip (XY projection)")
        else:
            ax.plot([s["minimum_tip_x_mm"], length], [y, y], "--", color="#15803d", lw=3,
                    label="Target tip region")
        ax.scatter([end[-1, 0]], [end[-1, 1]], color="#ea580c", zorder=5)
        ax.set(title=f"{labels[s['material']]}\n{s['status']}", xlabel="X forward (mm)",
               ylabel="Y height (mm)", xlim=(-.05*length, 1.05*length),
               ylim=(min(low_y-.05*length, -.1*length), max(y+.1*length, .1*length)))
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, loc="lower right")
    fig.suptitle("Inverse winch control | "+describe_target(settings["target"], length)+" | XY view")
    fig.savefig(output/"inverse_level.png", dpi=170)
    plt.close(fig)


def save_results(output, source_path, source, settings, results, preservation):
    body = dict(created_utc=datetime.now(timezone.utc).isoformat(), settings=settings,
                source_results=str(source_path),
                source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                source_config=source["config"], material_catalog=source["material_catalog"],
                preserved_simulations=preservation, results=results)
    write_json(output/"inverse_results.json", body)
    summaries = [r["summary"] for r in results]
    with (output/"inverse_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader(); writer.writerows(summaries)
    with (output/"control_trace.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["material", *results[0]["trajectory"][0]]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for row in result["trajectory"]:
                writer.writerow(dict(material=result["summary"]["material"], **row))
    with sqlite3.connect(output/"inverse_results.sqlite3") as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL,
                settings_json TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                catalog_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
                material TEXT NOT NULL, status TEXT NOT NULL, target_reached INTEGER NOT NULL,
                tip_x_mm REAL NOT NULL, tip_y_mm REAL NOT NULL, tip_z_mm REAL NOT NULL,
                summary_json TEXT NOT NULL, result_json TEXT NOT NULL);
        """)
        cursor = con.execute("INSERT INTO runs(created_utc,settings_json,source_sha256,catalog_json) VALUES(?,?,?,?)",
                             (body["created_utc"], json.dumps(settings), body["source_sha256"],
                              json.dumps(source["material_catalog"], ensure_ascii=False)))
        for result in results:
            s = result["summary"]
            con.execute("""INSERT INTO results(run_id,material,status,target_reached,
                tip_x_mm,tip_y_mm,tip_z_mm,summary_json,result_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (cursor.lastrowid, s["material"], s["status"], int(s["target_reached"]),
                         s["tip_x_mm"], s["tip_y_mm"], s["tip_z_mm"],
                         json.dumps(s, ensure_ascii=False),
                         json.dumps(result, default=json_value, ensure_ascii=False)))
    return body


def describe_target(target, length_mm=None):
    if target["mode"] == "horizontal_shape":
        return (f"whole centerline within {target['tolerance_mm']:g} mm of X axis; "
                f"all link tilts <= {target['angle_tolerance_deg']:g} deg")
    if target["mode"] == "tip_position":
        return (f"tip XYZ = ({target.get('tip_x_mm', length_mm)}, {target['tip_y_mm']}, "
                f"{target['tip_z_mm']}) mm; tolerance {target['tolerance_mm']:g} mm")
    return (f"tip Y/Z = {target['tip_y_mm']}/{target['tip_z_mm']} mm; "
            f"forward reach >= {100*target['minimum_forward_ratio']:g}%")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--material", default="all")
    parser.add_argument("--config", type=Path, default=HERE/"rope_config_level.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--target-mm", type=float, nargs=3, metavar=("X", "Y", "Z"),
                        help="override target with a full XYZ tip position in mm")
    args = parser.parse_args(argv)
    if args.probe:
        probe("ss304_annealed" if args.material == "all" else args.material)
        return 0
    settings = read_json(args.config)
    if args.target_mm is not None:
        x, y, z = args.target_mm
        settings["target"].update(mode="tip_position", tip_x_mm=x, tip_y_mm=y, tip_z_mm=z)
        settings["search"]["balanced_sides"] = False
    source_path = (HERE/settings["initial_results"]).resolve()
    source = read_json(source_path)
    output = (args.output_dir or HERE/settings["output_directory"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    preserved = {}
    for folder in ("rope_results", "rope_results_tip500g"):
        for path in (HERE/folder).iterdir():
            if path.is_file():
                preserved[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("snake_model.py", "craft_data.py", "rope_config.json", "rope_config_tip500g.json"):
        preserved[name] = hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    catalog = {m["id"]:m for m in source["material_catalog"]["materials"]}
    materials = settings["materials"] if args.material == "all" else args.material.split(",")
    results = []
    print("Inverse target:", describe_target(settings["target"]))
    print("Tension and travel bounds are numerical search bounds, not rated hardware limits.")
    print("A failed local search is not a proof of global infeasibility.", flush=True)
    for material in materials:
        case = next(c for c in source["cases"] if c["summary"]["material"] == material and
                    c["summary"]["stage"] == settings["initial_stage"])
        config = copy.deepcopy(source["config"])
        config["scenario_name"] = settings["scenario_name"]
        robot = RopeRobot(config, catalog[material], catalog[config["ropes"]["material"]])
        force_robot = TensionRobot(config, catalog[material], catalog[config["ropes"]["material"]])
        controller = LevelInverse(robot, force_robot, settings)
        initial = state_from_saved_case(case, force_control=False)
        print(f"\n{material}: source stage {settings['initial_stage']}, payload {initial.control.payload_kg*1000:.1f} g", flush=True)

        def progress(row):
            print(f"  step {row['iteration']:2d}: X={row['tip_x_mm']:.2f} mm "
                  f"Y={row['tip_y_mm']:.2f} mm Z={row['tip_z_mm']:.2f} mm "
                  f"error={row['objective_error_mm']:.2f} mm "
                  f"Ttop={row['tension_top_n']:.2f} N", flush=True)

        result = controller.solve(initial, progress=progress)
        result["initial_source_stage"] = settings["initial_stage"]
        results.append(result)
        s = result["summary"]
        print("  RESULT:", s["status"], "|", s["stop_reason"], flush=True)
        label = "target commands" if s["target_reached"] else "best-candidate commands (NOT a target solution)"
        print(f"  {label} [mm, top/right/bottom/left]:",
              "/".join(f"{s[f'take_up_{name}_mm']:+.3f}" for name in ROPE_NAMES), flush=True)
        print("  tension [N, top/right/bottom/left]:",
              "/".join(f"{s[f'tension_{name}_n']:.3f}" for name in ROPE_NAMES), flush=True)
        if not s["within_reference_model_range"]:
            print("  Screening: candidate exceeds rope-strain or per-module angle reference range.", flush=True)
    for name, expected in preserved.items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"preserved simulation file changed: {name}")
    save_results(output, source_path, source, settings, results, preserved)
    if not args.no_plots:
        plot_results(output, results, source, settings)
    print(f"\nSaved inverse results: {output}")
    print("Previous scenarios and simulation files unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
