"""Replay a precomputed reversal schedule with free whole-rod equilibrium and persistent friction on all twelve ropes."""

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import root

from common import (
    input_file,
    NAMES,
    OUT,
    SOURCE,
    motion_rows,
    read_csv,
    save,
    trajectory,
    write_table,
)
from guide_loads import record as guide_record
from active_reset_pin_inputs import save_active_reset_inputs
from length_cycle import FastTank
from pitch_reference import angle_between, pointing
from pose_map import axis, centreline, clearance
from replay import plant
from rope_history import contact, play


def run(out, estimate):
    tag = f"takeup_plant_mu{estimate:g}"
    plan = read_csv(
        input_file(out, "rope_control", f"takeup_commands_mu{estimate:g}.csv.gz")
    )
    archive = motion_rows()
    states, drum0, forces = trajectory()
    wrap = np.load(SOURCE / "transmission_motion.npz")["total_wrap_rad"]
    rod, _ = plant()
    ea = rod.planar.rope_ea
    tank = FastTank()
    drum = drum0[0].ravel()
    lengths = rod.evaluate(states[0], detail=True)[2]["rope_lengths"].ravel()
    material = lengths / (1 + forces[0] / ea)
    clamp = np.array([float(r["clamp_s_mm"]) for r in archive])
    axes = np.array(
        [
            axis(float(r["target_yaw_deg"]), float(r["target_elevation_deg"]))
            for r in archive
        ]
    )
    z = previous_reference = states[0]
    rows = []
    active_states = []
    active_distal_tensions = []
    active_hole_wrenches = []
    active_hole_tags = None
    tangent = None
    failure = None
    for substep, command in enumerate(plan):
        i = int(command["step"])
        j = max(0, i - 1)
        f = float(command["fraction"])
        reference = states[j] + f * (states[i] - states[j])
        theta = wrap[j] + f * (wrap[i] - wrap[j])
        drum = play(
            drum,
            np.array([float(command[n + "_command_mm"]) for n in NAMES]) / 1000,
            0.10,
        )

        def loads(x):
            L = rod.evaluate(x, detail=True)[2]["rope_lengths"].ravel()
            return contact(L, drum, material, theta, ea, 0.15, 0.15)

        def gradient(x):
            t = loads(x)[1]
            return rod.evaluate(x, t.reshape(3, 4))[1]

        def stiffness(x):
            _, t, _, _, slope = loads(x)
            J = rod.control_jacobian(x)
            return rod.hessian(x, t.reshape(3, 4)) + J.T @ (slope[:, None] * J)

        seed = z + (reference - previous_reference)
        residual = rod.residual(gradient(seed))
        if residual > 5e-7:
            if tangent is None or substep % 45 == 0:
                tangent = stiffness(seed)
            for limit in (55, 110):
                fit = root(
                    gradient,
                    seed,
                    jac=lambda _: tangent,
                    method="hybr",
                    options=dict(xtol=1e-10, maxfev=limit),
                )
                seed = fit.x
                residual = rod.residual(gradient(seed))
                if residual < 2e-6:
                    break
                tangent = stiffness(seed)
        if residual >= 2e-6 or not np.isfinite(residual):
            failure = dict(
                substep=substep, step=i, kind=command["kind"], residual=residual
            )
            break
        z = seed
        previous_reference = reference
        pro, dist, updated, _, _ = loads(z)
        transfer = (updated - material) * 1000
        material = updated
        desired_axis = axes[j] + f * (axes[i] - axes[j])
        desired_axis /= np.linalg.norm(desired_axis)
        row = dict(
            substep=substep,
            step=i,
            phase=archive[i]["phase"],
            kind=command["kind"],
            fraction=f,
            residual=residual,
            pointing_error_deg=angle_between(pointing(rod, z), desired_axis),
            tank_gap_mm=clearance(
                tank, centreline(rod, z), clamp[j] + f * (clamp[i] - clamp[j])
            ),
            maximum_scaled_state_shift=np.max(abs(z - reference)),
        )
        tags, fields, _, _, _ = guide_record(
            rod.base, rod.profiles, z, dist.reshape(3, 4), True
        )
        if active_hole_tags is None:
            active_hole_tags = tags
        elif tags != active_hole_tags:
            raise ValueError("Guide-hole labels or order changed during active-reset replay")
        for st, suffix in ((-12, "minus"), (12, "plus")):
            idx = [k for k, v in enumerate(tags) if v[:2] == ("M5", st)]
            force, moment = fields[idx].sum(0)
            row[f"M5_z{suffix}12_force_N"] = np.linalg.norm(force)
            row[f"M5_z{suffix}12_moment_Nmm"] = np.linalg.norm(moment)
        for k, n in enumerate(NAMES):
            row[n + "_prox_N"] = pro[k]
            row[n + "_dist_N"] = dist[k]
            row[n + "_drum_mm"] = drum[k] * 1000
            row[n + "_slip_mm"] = transfer[k]
        rows.append(row)
        active_states.append(z.copy())
        active_distal_tensions.append(dist.reshape(3, 4).copy())
        active_hole_wrenches.append(fields.copy())
        if substep % 1000 == 0:
            print(tag, substep, "/", len(plan), "archive", i, flush=True)
    if not rows:
        raise RuntimeError(f"No accepted equilibrium: {failure}")
    ends = [r for r in rows if r["kind"] in ("initial", "endpoint")]

    def metrics(samples):
        return dict(
            states=len(samples),
            minimum_distal_N=min(
                (r[n + "_dist_N"], r["step"], r["substep"], n)
                for r in samples
                for n in NAMES
            ),
            maximum_proximal_N=max(
                (r[n + "_prox_N"], r["step"], r["substep"], n)
                for r in samples
                for n in NAMES
            ),
            below_tension_floor=sum(
                min(r[n + "_dist_N"] for n in NAMES) < 2.5 for r in samples
            ),
            maximum_pointing_error_deg=max(
                (r["pointing_error_deg"], r["step"], r["substep"]) for r in samples
            ),
            above_pointing_allowance=sum(r["pointing_error_deg"] > 1 for r in samples),
            minimum_tank_gap_mm=min(
                (r["tank_gap_mm"], r["step"], r["substep"]) for r in samples
            ),
            below_gap_allowance=sum(r["tank_gap_mm"] < 5 for r in samples),
            maximum_residual=max(r["residual"] for r in samples),
            m5_maxima={
                k: max(r[k] for r in samples) for k in samples[0] if k.startswith("M5_")
            },
        )

    write_table(out / "rope_control" / (tag + ".csv.gz"), rows)
    pin_inputs_path = out / "rope_control" / (tag + "_pin_inputs.npz")
    save_active_reset_inputs(
        pin_inputs_path,
        rows,
        active_states,
        active_distal_tensions,
        active_hole_tags,
        active_hole_wrenches,
    )
    summary = dict(
        pin_inputs_file=pin_inputs_path.name,
        assumed_mu=estimate,
        plant_mu_static=0.15,
        plant_mu_kinetic=0.15,
        plant_play_mm=0.10,
        expected_substeps=len(plan),
        expected_archive_steps=len(archive),
        stopped_at=failure,
        all_substeps=metrics(rows),
        original_endpoints=metrics(ends),
    )
    save(out / "rope_control" / (tag + ".json"), summary)
    print(
        tag,
        len(rows),
        "equilibria, minimum distal force",
        summary["all_substeps"]["minimum_distal_N"],
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--estimate", type=float, choices=[0.12, 0.15], default=0.15)
    args = p.parse_args()
    run(args.out, args.estimate)
