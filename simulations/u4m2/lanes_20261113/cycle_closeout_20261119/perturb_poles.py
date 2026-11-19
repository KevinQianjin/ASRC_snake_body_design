"""Test the two vertical commands with historical 500 g stiffness variations and local angle/tension feedback."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np

from replay import plant
from pitch_reference import (
    angle_between,
    angular_error,
    pitch_axes,
    pointing,
    position,
    target_axis,
)
from closed_loop_cycle import FeedbackDrive
from closed_loop_v2 import qp, adapt_scale
from length_cycle import FastTank, to_tank


def matched_commands(rest, tensions, nominal_ea, assumed_ea):
    """Choose the unstretched lengths for the same stretched paths and nominal tensions."""
    return rest * (1.0 + tensions / nominal_ea) / (1.0 + tensions / assumed_ea)


def soft_rope_check(rod, drive, start, rest, nominal_tensions, goal):
    """At one vertical hold, move from the unchanged commands to the material-matched lengths."""
    finish = matched_commands(rest, nominal_tensions, rod.planar.rope_ea, drive.ea)
    delta = (finish - rest) * 1000
    steps = max(1, int(np.ceil(np.max(abs(delta)) / 0.25)))
    rows = []
    z = start
    for k in range(steps + 1):
        command = rest + (finish - rest) * (k / steps)
        z = drive.solve(z, command)
        if z is None:
            break
        tension = drive.force(z, command)
        rows.append(
            dict(
                increment=k,
                tension_N=tension.ravel().tolist(),
                error_to_vertical_deg=angle_between(
                    pointing(rod, z), target_axis(goal)
                ),
                minimum_tangent=drive.stability(z, command, tension),
                residual=rod.residual(drive.energy(z, command)[1]),
                largest_tension_difference_from_nominal_N=float(
                    np.max(abs(tension - nominal_tensions))
                ),
            )
        )
    return dict(
        adjustment_mm=delta.ravel().tolist(),
        requested_increments=steps,
        maximum_step_mm=float(np.max(abs(delta)) / steps),
        solved_increments=max(0, len(rows) - 1),
        samples=rows,
        states_below_2p5_N=sum(1 for r in rows if min(r["tension_N"]) < 2.5),
    )


def run(src, plan):
    with (src / "rope_tensions_at_events.csv").open() as f:
        stops = {
            r["event"]: int(r["step"])
            for r in csv.DictReader(f)
            if r["event"] in ("Pitch up", "Pitch down")
        }
    with np.load(src / "controller_states.npz") as f:
        zs = f["motion_z"]
        commands = f["motion_rest_m"]
        forces = f["motion_tensions_N"].reshape(-1, 3, 4)
    tank = FastTank()
    result = []
    for event, idx in stops.items():
        goal = 90.0 if event == "Pitch up" else -90.0
        with np.load(plan / ("pitch_up.npz" if goal > 0 else "pitch_down.npz")) as f:
            j = int(np.flatnonzero(f["pitch_deg"] == goal).item())
            B = f["B"][j]
            feed = f["rest_m"][j]
        for label, variant, ea in (
            ("M backbone modulus 75 GPa", "niti18_E75", 1.0),
            ("Rope axial stiffness -20%", "niti18_E40", 0.8),
        ):
            rod, _ = plant(variant=variant)
            drive = FeedbackDrive(rod, ea_scale=ea)
            R = commands[idx].copy()
            offset = 1000 * (R - feed).ravel()
            initial = zs[idx]
            drive.stability(initial, R, drive.force(initial, R))
            z = drive.solve(initial, R)
            uncorrected = z
            history = []
            failure = None
            damping = 1.0
            prior = None
            if z is None:
                failure = "Initial fixed-command equilibrium did not converge"
            for it in range(17):
                if z is None:
                    break
                T = drive.force(z, R)
                eig = drive.stability(z, R, T)
                axis = pointing(rod, z)
                miss = angular_error([0.0, goal], pitch_axes(axis))
                norm = float(np.max(abs(miss)))
                d = rod.base.kinematic_metrics(z)[1]
                world = (
                    np.vstack((np.zeros(3), d["points"] + [0.02, 0.0, 0.0]))
                    @ rod.R0.T
                    * 1000.0
                )
                gap = tank.clearance(to_tank(world, 20.0, 15.0, tank.entry_h))[0] - 1.5
                residual = rod.residual(drive.energy(z, R)[1])
                angle = angle_between(axis, target_axis(goal))
                row = dict(
                    iteration=it,
                    tensions_N=T.ravel().tolist(),
                    offset_mm=offset.tolist(),
                    head_mm=position(rod, z).tolist(),
                    target_axis_error_deg=angle,
                    controlled_error_deg=miss.tolist(),
                    min_tangent=eig,
                    residual=residual,
                    tank_after_allowance_mm=gap,
                    geometry_pass=bool(
                        rod.geometry_constraints(z).min() >= -1.0e-7
                        and np.max(abs(d["q"][:, 3])) <= 0.05
                    ),
                )
                row["settled_and_mechanical_pass"] = bool(
                    angle <= 0.2
                    and T.min() >= 2.5
                    and T.max() <= 250
                    and eig > 1.0e-7
                    and residual < 2.0e-6
                    and row["geometry_pass"]
                    and gap >= 5.0
                )
                history.append(row)
                if row["settled_and_mechanical_pass"] or it == 16:
                    break
                damping = adapt_scale(prior, norm, damping)
                prior = norm
                dx, feasible = qp(B[:2], B[2:], T.ravel(), miss, offset, 3.0, 0.25)
                if not feasible:
                    failure = "Correction QP infeasible"
                    break
                dx = damping * dx
                offset += dx
                R = feed + offset.reshape(3, 4) / 1000
                z = drive.solve(z, R)
                if z is None:
                    failure = "Corrected fixed-command equilibrium did not converge"
            result.append(
                dict(
                    event=event,
                    step=idx,
                    perturbation=label,
                    rod_variant=variant,
                    rope_EA_scale=ea,
                    history=history,
                    stopped_reason=failure,
                    passed=bool(history and history[-1]["settled_and_mechanical_pass"]),
                    commands_attempted=it if history else 0,
                )
            )
            if ea != 1.0 and uncorrected is not None:
                result[-1]["material_matched_winch_check"] = soft_rope_check(
                    rod, drive, uncorrected, commands[idx], forces[idx], goal
                )
    summary = dict(
        scope="Endpoint-only stiffness sensitivity. Start from the actual nominal winch commands at each vertical target, hold the total payload at 500 g and let the original nominal pitch gains correct up to 16 times. This does not replay the complete trajectory with the perturbed plant.",
        material_matched_scope="A separate frictionless fixed-hold calculation uses the nominal force in each taut rope and assumes its axial stiffness is known. It solves every intermediate winch command with a 0.25 mm increment limit. An initial or intermediate force below the operating floor remains a failure for that adjustment path. No material stiffness was measured.",
        cases=result,
    )
    (src / "perturbed_poles.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    a = p.parse_args()
    run(a.source, a.plan)
