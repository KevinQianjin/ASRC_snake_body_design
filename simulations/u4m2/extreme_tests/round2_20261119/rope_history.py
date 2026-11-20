"""Two elastic material spans per rope, static traction, sliding, drum play and delayed distal tension feedback."""

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import root
from common import OUT, SOURCE, NAMES, motion_rows, trajectory, write_table, save
from replay import plant
from closed_loop_cycle import FeedbackDrive
from length_cycle import FastTank
from pitch_reference import angle_between, pointing
from pose_map import centreline, clearance, axis
from guide_loads import record as guide_record

FREE = 1.0


def contact(length, rest, h, wrap, ea, mu_s, mu_k):
    """h is the unstretched material distal to the lumped friction site. Lengths in metres."""
    prox = np.maximum(0.0, ea * (FREE / (rest - h) - 1))
    dist = np.maximum(0.0, ea * (length / h - 1))
    lim = np.exp(mu_s * wrap)
    mode = np.where(
        dist > lim * prox + 1e-10, 1, np.where(prox > lim * dist + 1e-10, -1, 0)
    )
    ratio = np.exp(mode * mu_k * wrap)
    b = rest * (1 + ratio) - length - FREE * ratio
    c = rest - length - FREE
    x = np.maximum(
        0.0, -2 * c / (b + np.sqrt(np.maximum(0.0, b * b - 4 * rest * ratio * c)))
    )
    sliding = mode != 0
    prox = np.where(sliding, ea * x, prox)
    dist = np.where(sliding, ratio * ea * x, dist)
    material = np.where(sliding, length / (1 + dist / ea), h)
    slope = np.where(
        sliding,
        ratio
        * ea
        / (1 + ratio * x)
        / (FREE / (1 + x) ** 2 + length * ratio / (1 + ratio * x) ** 2),
        ea / h,
    )
    return prox, dist, material, mode, np.where(dist > 0, slope, 0.0)


def play(previous, command, width_mm):
    half = width_mm / 2000
    return np.clip(previous, command - half, command + half)


def simulate(out, mu_s, mu_k, width, control, coupled, feedforward=False):
    tag = (
        ("coupled" if coupled else "fixed")
        + f"_s{mu_s:g}_k{mu_k:g}_b{width:g}_"
        + ("compensated" if feedforward else "feedback" if control else "open")
    )
    z0, R0, T0 = trajectory()
    R0 = R0.reshape(-1, 12)
    rows = motion_rows()
    L0 = np.array(
        [[float(r[n + "_internal_path_mm"]) / 1000 for n in NAMES] for r in rows]
    )
    wrap = np.load(SOURCE / "transmission_motion.npz")["total_wrap_rad"]
    rod, _ = plant()
    drive = FeedbackDrive(rod)
    ea = drive.ea
    np.testing.assert_allclose(ea * (L0 + FREE - R0) / R0, T0, atol=2e-7)
    tank = FastTank() if coupled else None
    h = L0[0] / (1 + T0[0] / ea)
    drum = R0[0].copy()
    comp = np.zeros(12)
    prior_command = R0[0].copy()
    last_prox = T0[0].copy()
    desired_material = h.copy()
    last = T0[0]
    z = z0[0]
    tangent = None
    trace = []
    worst_res = 0.0
    total_slide = np.zeros(12)
    previous_mode = np.zeros(12, int)
    changes = np.zeros(12, int)
    for i, row in enumerate(rows):
        if control and i:
            # A single observation per archived substep; no assumed seconds per sample.
            correction = (0.035 if feedforward else 0.13) * (last - T0[i - 1])
            comp = np.clip(comp + np.clip(correction, -0.25, 0.25), -4.0, 4.0)
        command = R0[i] + comp / 1000
        if feedforward:
            # Infer the sliding side from the desired material transfer. Intentionally under-estimate
            # friction and backlash so that this is not an inverse crime.
            desired = L0[i] / (1 + T0[i] / ea)
            direction = np.sign(desired - desired_material)
            assumed_limiter = np.exp(0.12 * wrap[i])
            target_prox = np.where(
                abs(desired - desired_material) > 1e-9,
                T0[i] * assumed_limiter ** (-direction),
                np.clip(last_prox, T0[i] / assumed_limiter, T0[i] * assumed_limiter),
            )
            spool = desired + FREE / (1 + target_prox / ea) + comp / 1000
            desired_command = spool + np.sign(spool - drum) * 0.08 / 2000
            command = prior_command + np.clip(
                desired_command - prior_command, -0.00025, 0.00025
            )
            desired_material = desired
        prior_command = command
        drum = play(drum, command, width)
        current = L0[i]
        residual = None
        if coupled:
            seed = z + (z0[i] - z0[i - 1]) if i else z

            def evaluate(x, derivative=False):
                L = rod.evaluate(x, detail=True)[2]["rope_lengths"].ravel()
                _, T, _, _, slope = contact(L, drum, h, wrap[i], ea, mu_s, mu_k)
                if derivative:
                    J = rod.control_jacobian(x)
                    return rod.hessian(x, T.reshape(3, 4)) + J.T @ (slope[:, None] * J)
                return rod.evaluate(x, T.reshape(3, 4))[1]

            if tangent is None or i % 45 == 0:
                tangent = evaluate(seed, True)
            fit = root(
                evaluate,
                seed,
                jac=lambda _: tangent,
                method="hybr",
                options=dict(xtol=1e-9, maxfev=55),
            )
            residual = rod.residual(evaluate(fit.x))
            if residual >= 2e-6:
                tangent = evaluate(fit.x, True)
                fit = root(
                    evaluate,
                    fit.x,
                    jac=lambda _: tangent,
                    method="hybr",
                    options=dict(xtol=1e-9, maxfev=110),
                )
                residual = rod.residual(evaluate(fit.x))
            if residual >= 2e-6:
                print(tag, "stopped", i, residual, flush=True)
                break
            z = fit.x
            current = rod.evaluate(z, detail=True)[2]["rope_lengths"].ravel()
        pro, last, material, mode, _ = contact(
            current, drum, h, wrap[i], ea, mu_s, mu_k
        )
        last_prox = pro
        transfer = (material - h) * 1000
        total_slide += abs(transfer)
        changes += (mode != 0) & (previous_mode != 0) & (mode != previous_mode)
        previous_mode = np.where(mode != 0, mode, previous_mode)
        h = material
        outrow = dict(
            step=i,
            phase=row["phase"],
            target_index=row["target_index"],
            pointing_error_deg=None,
            tank_gap_mm=None,
            residual=residual,
            M5_zminus12_force_N=None,
            M5_zplus12_force_N=None,
            M5_zminus12_moment_Nmm=None,
            M5_zplus12_moment_Nmm=None,
        )
        if coupled:
            yaw = float(row["target_yaw_deg"])
            pitch = float(row["target_elevation_deg"])
            outrow["pointing_error_deg"] = angle_between(
                pointing(rod, z), axis(yaw, pitch)
            )
            outrow["tank_gap_mm"] = clearance(
                tank, centreline(rod, z), float(row["clamp_s_mm"])
            )
            tags, fields, _, _, _ = guide_record(
                rod.base, rod.profiles, z, last.reshape(3, 4), True
            )
            for st, part in ((-12, "minus"), (12, "plus")):
                ids = [j for j, v in enumerate(tags) if v[:2] == ("M5", st)]
                force, moment = fields[ids].sum(0)
                outrow[f"M5_z{part}12_force_N"] = np.linalg.norm(force)
                outrow[f"M5_z{part}12_moment_Nmm"] = np.linalg.norm(moment)
            worst_res = max(worst_res, residual)
        for j, n in enumerate(NAMES):
            outrow[n + "_prox_N"] = pro[j]
            outrow[n + "_dist_N"] = last[j]
            outrow[n + "_drum_mm"] = drum[j] * 1000
            outrow[n + "_slip_mm"] = transfer[j]
        trace.append(outrow)
        if coupled and i % 500 == 0:
            print(tag, i, min(last), flush=True)
    if not trace:
        raise RuntimeError("No accepted states")

    def channel_extreme(suffix, fn):
        return fn((r[n + suffix], r["step"], n) for r in trace for n in NAMES)

    def first(check):
        return next((r["step"] for r in trace if check(r)), None)

    res = dict(
        tag=tag,
        mu_s=mu_s,
        mu_k=mu_k,
        play_width_mm=width,
        distal_feedback=control,
        feedforward=feedforward,
        whole_rod_equilibrium=coupled,
        states=len(trace),
        expected=len(rows),
        peak_equilibrium_residual=worst_res if coupled else None,
        minimum_distal=channel_extreme("_dist_N", min),
        maximum_proximal=channel_extreme("_prox_N", max),
        first_floor_breach=first(lambda r: min(r[n + "_dist_N"] for n in NAMES) < 2.5),
        states_below_floor=sum(
            min(r[n + "_dist_N"] for n in NAMES) < 2.5 for r in trace
        ),
        transfer_travel_mm=dict(zip(NAMES, total_slide)),
        sliding_reversals=dict(zip(NAMES, changes)),
    )
    if coupled:
        res.update(
            maximum_pointing_error=max(
                (r["pointing_error_deg"], r["step"]) for r in trace
            ),
            first_pointing_breach=first(lambda r: r["pointing_error_deg"] > 1),
            minimum_tank_gap=min((r["tank_gap_mm"], r["step"]) for r in trace),
            first_tank_breach=first(lambda r: r["tank_gap_mm"] < 5),
            m5_maxima={
                k: max((r[k], r["step"]) for r in trace)
                for k in trace[0]
                if k.startswith("M5_")
            },
        )
    if coupled or mu_s == 0.18 and control:
        write_table(out / "rope_control" / (tag + ".csv.gz"), trace)
    if coupled:
        save(out / "rope_control" / (tag + ".json"), res)
    print(tag, "states", len(trace), "min", res["minimum_distal"], flush=True)
    return res


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--mode", choices=("sweep", "coupled"), required=True)
    p.add_argument("--feedback", action="store_true")
    p.add_argument("--compensated", action="store_true")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "coupled":
        simulate(
            a.out, 0.15, 0.15, 0.10, a.feedback or a.compensated, True, a.compensated
        )
    else:
        sweep = [simulate(a.out, 0.15, 0.15, 0.10, True, False, True)]
        for mu in (0.0, 0.05, 0.15, 0.17, 0.30):
            for feedback in (False, True):
                sweep.append(
                    simulate(a.out, mu, mu, 0.0 if mu == 0 else 0.10, feedback, False)
                )
        for width in (0.0, 0.10, 0.25):
            for feedback in (False, True):
                sweep.append(simulate(a.out, 0.18, 0.15, width, feedback, False))
        save(
            a.out / "rope_control" / "transmission_sensitivity.json",
            sorted(sweep, key=lambda r: r["tag"]),
        )
