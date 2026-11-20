"""Continue each archived friction plant through withdrawal reset, a second mission and its reset."""

import argparse
import numpy as np
from scipy.optimize import root
from study_context import (
    RESULTS,
    ROUND2,
    NAMES,
    SOURCE,
    motion_rows,
    trajectory,
    read_csv,
    write_table,
    save,
)
from replay import plant
from rope_history import contact, play
from reset_takeup import plan_reset
from pitch_reference import pointing, angle_between
from pose_map import axis

FILES = {
    "original": "coupled_s0.15_k0.15_b0.1_open",
    "endpoint_compensation": "coupled_s0.15_k0.15_b0.1_compensated",
    "matched": "takeup_plant_mu0.15",
    "active_matched": "takeup_plant_mu0.15",
    "mismatched": "takeup_plant_mu0.12",
}


def vector(row, suffix):
    return np.array([float(row[n + suffix]) for n in NAMES])


def steps(variant, arch, rest):
    if variant == "original":
        return [(i, 1.0, rest[i].ravel().copy(), "endpoint") for i in range(len(arch))]
    mu = {"matched": "0.15", "mismatched": "0.12", "active_matched": "0.15"}[variant]
    return [
        (
            int(r["step"]),
            float(r["fraction"]),
            vector(r, "_command_mm") / 1000,
            r["kind"],
        )
        for r in read_csv(ROUND2 / "rope_control" / f"takeup_commands_mu{mu}.csv.gz")
    ]


def interpolate(data, i, f):
    j = max(0, i - 1)
    if f == 1.0:
        return data[i]
    if f == 0.0:
        return data[j]
    return data[j] + f * (data[i] - data[j])


def reset_plan(plan, last_start):
    start = [v for v in plan if v[0] <= last_start]
    delta = start[-1][2] - plan[-1][2]
    n = max(1, int(np.ceil(np.max(abs(delta)) * 1000 / 0.15)))
    # The clamp stays at the withdrawn position during the neutral handover and descent.
    x = [
        (last_start, 1.0, plan[-1][2] + delta * k / n, "neutral_handover")
        for k in range(1, n + 1)
    ]
    x.extend((i, f, c, "reverse_startup") for i, f, c, _ in reversed(start[:-1]))
    return x


class FrictionPlant:
    def __init__(self, rod, z, drum, h):
        self.rod, self.ea = rod, rod.planar.rope_ea
        self.z, self.drum, self.h = z.copy(), drum.copy(), h.copy()
        self.previous = z.copy()
        self.H = None
        self.count = 0

    def advance(self, ref, theta, command, target):
        rod = self.rod
        drum = play(self.drum, command, 0.10)

        def loads(x):
            length = rod.evaluate(x, detail=True)[2]["rope_lengths"].ravel()
            return contact(length, drum, self.h, theta, self.ea, 0.15, 0.15)

        def gradient(x):
            return rod.evaluate(x, loads(x)[1].reshape(3, 4))[1]

        def tangent(x):
            _, dist, _, _, slope = loads(x)
            J = rod.control_jacobian(x)
            return rod.hessian(x, dist.reshape(3, 4)) + J.T @ (slope[:, None] * J)

        z = self.z + (ref - self.previous)
        residual = rod.residual(gradient(z))
        if residual > 5e-7:
            if self.H is None or self.count % 45 == 0:
                self.H = tangent(z)
            for limit in (55, 110):
                z = root(
                    gradient,
                    z,
                    jac=lambda _: self.H,
                    method="hybr",
                    options=dict(xtol=1e-10, maxfev=limit),
                ).x
                residual = rod.residual(gradient(z))
                if residual < 2e-6:
                    break
                self.H = tangent(z)
        if not np.isfinite(residual) or residual >= 2e-6:
            raise ArithmeticError(f"Equilibrium residual {residual}")
        pro, dist, h, _, _ = loads(z)
        slip = (h - self.h) * 1000
        self.z, self.drum, self.h, self.previous = z, drum, h, ref
        self.count += 1
        return (
            pro,
            dist,
            slip,
            residual,
            angle_between(pointing(rod, z), target / np.linalg.norm(target)),
        )


def run(name, out):
    archive = motion_rows()
    states, rest, T = trajectory()
    plan = steps(name, archive, rest)
    trace = read_csv(ROUND2 / "rope_control" / (FILES[name] + ".csv.gz"))
    if len(trace) != len(plan):
        raise ValueError("Incomplete first mission")
    stop = max(i for i, r in enumerate(archive) if r["phase"] == "straighten")
    if (
        archive[-1]["clamp_s_mm"] != archive[stop]["clamp_s_mm"]
        or archive[0]["clamp_s_mm"] != archive[stop]["clamp_s_mm"]
    ):
        raise ValueError("Reset requires the withdrawn clamp")
    reset = reset_plan(plan, stop)
    rod, _ = plant()
    wrap = np.load(SOURCE / "transmission_motion.npz")["total_wrap_rad"]
    axes = np.array(
        [
            axis(float(r["target_yaw_deg"]), float(r["target_elevation_deg"]))
            for r in archive
        ]
    )
    h0 = rod.evaluate(states[0], detail=True)[2]["rope_lengths"].ravel() / (
        1 + T[0] / rod.planar.rope_ea
    )
    h = h0 + sum(vector(r, "_slip_mm") for r in trace) / 1000
    drum = vector(trace[-1], "_drum_mm") / 1000
    plant2 = FrictionPlant(rod, states[-1], drum, h)
    pro, dist, _, _, _ = plant2.advance(states[-1], wrap[-1], plan[-1][2], axes[-1])
    join = max(
        np.max(abs(pro - vector(trace[-1], "_prox_N"))),
        np.max(abs(dist - vector(trace[-1], "_dist_N"))),
    )
    if join > 1e-4:
        raise ValueError(f"Final archived equilibrium did not reproduce ({join} N)")
    protocol = "At -750 mm, bridge the neutral commands then reverse all startup commands, retaining drum and material history."
    if name == "active_matched":
        reset = plan_reset(
            archive,
            plan,
            stop,
            rest,
            T,
            wrap,
            rod.planar.rope_ea,
            plant2.drum,
            pro,
            NAMES,
        )
        protocol = "At the withdrawn clamp, preload the proper friction side before each reversed startup movement. Equalize proximal force and remove command bias at the hanging start."
        write_table(
            out / "active_reset_commands.csv.gz",
            (
                dict(
                    step=i,
                    fraction=f,
                    kind=k,
                    **{
                        n + "_command_mm": v * 1000
                        for n, v in zip(NAMES, c, strict=True)
                    },
                )
                for i, f, c, k in reset
            ),
        )
    records = []
    boundaries = []
    for block, sequence, reset_leg in [
        (1, reset, True),
        (2, plan, False),
        (2, reset, True),
    ]:
        for k, (i, f, c, kind) in enumerate(sequence):
            ref = interpolate(states, i, f)
            pro, dist, slip, res, error = plant2.advance(
                ref, interpolate(wrap, i, f), c, interpolate(axes, i, f)
            )
            r = dict(
                block=block,
                step=i,
                fraction=f,
                kind=kind,
                phase="reset" if reset_leg else archive[i]["phase"],
                pointing_error_deg=error,
                residual=res,
            )
            for n, a, b, v, d in zip(NAMES, pro, dist, slip, plant2.drum, strict=True):
                (
                    r[n + "_prox_N"],
                    r[n + "_dist_N"],
                    r[n + "_slip_mm"],
                    r[n + "_drum_mm"],
                ) = a, b, v, d * 1000
            records.append(r)
            if k % 2000 == 0:
                print(name, block, r["phase"], k, len(sequence), flush=True)
        boundaries.append(
            dict(
                block=block,
                leg="reset" if reset_leg else "mission",
                count=len(sequence),
                material_mm=(1000 * plant2.h).tolist(),
                drum_mm=(1000 * plant2.drum).tolist(),
                maximum_material_offset_from_initial_mm=np.max(abs(plant2.h - h0))
                * 1000,
                maximum_drum_offset_from_initial_mm=np.max(
                    abs(plant2.drum - rest[0].ravel())
                )
                * 1000,
                initial_state_difference=np.max(abs(plant2.z - states[0])),
                state=plant2.z.tolist(),
            )
        )
        write_table(out / (name + "_extension.csv.gz"), records)
        save(
            out / (name + "_closure.json"),
            dict(
                variant=name,
                first_mission_join_error_N=join,
                boundaries=boundaries,
                reset_protocol=protocol,
            ),
        )
    a, b = boundaries[0], boundaries[-1]
    closure = dict(
        material_mm=np.max(abs(np.subtract(a["material_mm"], b["material_mm"]))),
        drum_mm=np.max(abs(np.subtract(a["drum_mm"], b["drum_mm"]))),
        scaled_state=np.max(abs(np.subtract(a["state"], b["state"]))),
    )
    print("reset-end drift", name, closure, flush=True)


if __name__ == "__main__":
    from pathlib import Path

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "variants",
        nargs="+",
        choices=("original", "matched", "mismatched", "active_matched"),
    )
    p.add_argument("--out", type=Path, default=RESULTS / "service")
    a = p.parse_args()
    for v in a.variants:
        run(v, a.out)
