"""Hold the preceding pose during backlash/friction-side transfer and then advance the nominal path."""

import argparse
from pathlib import Path
import numpy as np
from common import OUT, SOURCE, NAMES, trajectory, motion_rows, save, write_table
from replay import plant
from rope_history import contact, play, FREE


def run(out):
    states, R, T = trajectory()
    R = R.reshape(-1, 12)
    rows = motion_rows()
    wrap = np.load(SOURCE / "transmission_motion.npz")["total_wrap_rad"]
    rod, _ = plant()
    ea = rod.planar.rope_ea
    L = np.array(
        [[float(r[n + "_internal_path_mm"]) / 1000 for n in NAMES] for r in rows]
    )
    data = []
    summary = []
    for estimated in (0.12, 0.15, 0.18):
        actual_mu = 0.15
        width = 0.10
        estimated_width = 0.10 if estimated == 0.15 else 0.08
        h = L[0] / (1 + T[0] / ea)
        drum = command = R[0].copy()
        lastprox = T[0].copy()
        minimum = np.inf
        peak_error = 0.0
        largest = 0.0
        holds = 0
        bad = 0
        motionbad = 0
        bad_span = 0
        worst = None
        sliding = np.zeros(12)

        def advance(step, label, Lk, angle, desired_drum, target):
            nonlocal \
                h, \
                drum, \
                command, \
                minimum, \
                peak_error, \
                largest, \
                holds, \
                bad, \
                worst, \
                lastprox, \
                sliding
            # An inverse play command only when positive physical spool motion is required.
            wanted = np.where(
                abs(desired_drum - drum) > 1e-12,
                desired_drum + np.sign(desired_drum - drum) * estimated_width / 2000,
                command,
            )
            largest = max(largest, float(np.max(abs(wanted - command)) * 1000))
            command = wanted
            drum = play(drum, command, width)
            pro, dist, new, mode, _ = contact(
                Lk, drum, h, angle, ea, actual_mu, actual_mu
            )
            sliding += abs(new - h) * 1000
            h = new
            j = int(dist.argmin())
            if dist[j] < minimum:
                minimum = dist[j]
                worst = (step, label, NAMES[j])
            bad += int(min(dist) < 2.5)
            peak_error = max(peak_error, float(np.max(abs(dist - target))))
            lastprox = pro
            return pro, dist

        commands = []

        def record_command(step, kind, fraction):
            if estimated in (0.12, 0.15):
                row = dict(step=step, kind=kind, fraction=fraction)
                row.update(
                    {n + "_command_mm": x * 1000 for n, x in zip(NAMES, command)}
                )
                commands.append(row)

        record_command(0, "initial", 1.0)
        previous_desired = h.copy()
        if estimated == actual_mu:
            initial_row = dict(step=0, phase=rows[0]["phase"])
            for j, name in enumerate(NAMES):
                initial_row[name + "_prox_N"] = T[0, j]
                initial_row[name + "_dist_N"] = T[0, j]
                initial_row[name + "_drum_mm"] = drum[j] * 1000
            data.append(initial_row)
        for i in range(1, len(L)):
            desired = L[i] / (1 + T[i] / ea)
            direct = np.sign(desired - previous_desired)
            direct = np.where(abs(desired - previous_desired) > 1e-12, direct, 0)

            # At unchanged material allocation either side can remain inside the static cone.
            def proximal(t, theta):
                bound = np.exp(estimated * theta)
                return np.where(
                    direct == 0,
                    np.clip(lastprox, t / bound, t * bound),
                    t * bound ** (-direct),
                )

            before = previous_desired + FREE / (
                1 + proximal(T[i - 1], wrap[i - 1]) / ea
            )
            initial = drum.copy()
            n = (
                int(np.ceil(np.max(abs(before - initial)) * 1000 / 0.145))
                if np.max(abs(before - initial)) > 1e-9
                else 0
            )
            for k in range(1, n + 1):
                advance(
                    i,
                    "take_up",
                    L[i - 1],
                    wrap[i - 1],
                    initial + (before - initial) * k / n,
                    T[i - 1],
                )
                record_command(i, "take_up", 0.0)
                holds += 1
            desired_end = desired + FREE / (1 + proximal(T[i], wrap[i]) / ea)
            start_drum = drum.copy()
            # Additional interpolation is a fixed-geometry sensitivity between saved equilibria.
            n = max(
                1, int(np.ceil(np.max(abs(desired_end - start_drum)) * 1000 / 0.145))
            )
            for k in range(1, n + 1):
                f = k / n
                pro, dist = advance(
                    i,
                    "move",
                    L[i - 1] + f * (L[i] - L[i - 1]),
                    wrap[i - 1] + f * (wrap[i] - wrap[i - 1]),
                    start_drum + (desired_end - start_drum) * f,
                    T[i - 1] + f * (T[i] - T[i - 1]),
                )
                record_command(i, "endpoint" if k == n else "move", f)
                if k < n:
                    bad_span += 1
            motionbad += int(min(dist) < 2.5)
            previous_desired = desired
            if estimated == actual_mu:
                row = dict(step=i, phase=rows[i]["phase"])
                for j, name in enumerate(NAMES):
                    row[name + "_prox_N"] = pro[j]
                    row[name + "_dist_N"] = dist[j]
                    row[name + "_drum_mm"] = drum[j] * 1000
                data.append(row)
        if commands:
            write_table(
                out / "rope_control" / f"takeup_commands_mu{estimated:g}.csv.gz",
                commands,
            )
        summary.append(
            dict(
                assumed_mu=estimated,
                actual_mu=actual_mu,
                assumed_play_mm=estimated_width,
                actual_play_mm=width,
                added_preload_steps=holds,
                added_motion_interpolations=bad_span,
                min_distal_N=minimum,
                limiting_state=worst,
                failed_steps_including_added=bad,
                archived_states_below_floor=motionbad,
                peak_force_tracking_error_N=peak_error,
                max_command_increment_mm=largest,
                transfer_travel_mm=sliding,
            )
        )
    residuals = [
        rod.residual(
            rod.evaluate(
                z, np.array([row[name + "_dist_N"] for name in NAMES]).reshape(3, 4)
            )[1]
        )
        for z, row in zip(states, data, strict=True)
    ]
    matched = next(v for v in summary if v["assumed_mu"] == v["actual_mu"])
    matched["original_endpoint_equilibria_checked"] = len(residuals)
    matched["peak_whole_rod_residual_at_original_endpoints"] = max(residuals)
    matched["original_endpoints_over_2e_6_residual"] = sum(v >= 2e-6 for v in residuals)
    write_table(out / "rope_control" / "takeup_endpoints.csv.gz", data)
    save(out / "rope_control" / "takeup.json", summary)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
