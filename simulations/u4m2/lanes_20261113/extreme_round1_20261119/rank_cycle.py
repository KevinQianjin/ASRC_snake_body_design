"""Independently join the four archived load/geometry histories by motion step and rank by failure mode."""

import argparse
from pathlib import Path

import numpy as np

from study_inputs import SOURCE, NAMES, EVENTS, load_motion, read_csv, save, write_csv


def run(out):
    rod, states, T = load_motion()
    rows = read_csv(SOURCE / "rope_tensions_every_step.csv.gz")
    count = len(rows)
    indices = np.arange(count)
    np.testing.assert_array_equal([int(r["step"]) for r in rows], indices)
    np.testing.assert_allclose(
        T, [[float(r[n + "_N"]) for n in NAMES] for r in rows], atol=1e-9, rtol=0
    )
    phase = np.array([r["phase"] for r in rows])
    gap = np.array([float(r["tank_clearance_after_allowance_mm"]) for r in rows])
    with np.load(SOURCE / "transmission_motion.npz") as data:
        np.testing.assert_array_equal(data["record"], indices)
        np.testing.assert_array_equal(
            data["rope_names"],
            [
                f"a{k}_{ray}"
                for k in (4, 5, 6)
                for ray in ("up", "right", "down", "left")
            ],
        )
        np.testing.assert_allclose(data["winch_reference_N"], T, rtol=0, atol=1e-9)
        wrap = data["total_wrap_rad"]
    # T exp(-mu*theta) = 2.5 N at fixed pose and fixed reference winch tension.
    mu_edge = np.divide(
        np.log(T / 2.5), wrap, out=np.full_like(T, np.inf), where=wrap > 1e-10
    )
    with np.load(SOURCE / "guide_hole_loads.npz") as data:
        np.testing.assert_array_equal(data["step"], indices)
        body, station = data["module"], data["station_mm"]
        hole_loads, lane, ray = (
            data["local_wrench_CAD"],
            data["lane"],
            data["direction"],
        )
    seats = list(dict.fromkeys(zip(body, station)))
    wg = np.stack(
        [hole_loads[:, (body == b) & (station == s)].sum(axis=1) for b, s in seats],
        axis=1,
    )
    seat_rows = read_csv(SOURCE / "guide_station_loads.csv.gz")
    seat_idx = {
        (r["module"], int(r["station_mm"]), int(r["step"])): r for r in seat_rows
    }
    if len(seat_idx) != len(seat_rows) or len(seat_rows) != count * len(seats):
        raise ValueError("Duplicate or missing station wrenches")
    cols = [f"force_{a}_N" for a in "xyz"] + [f"moment_{a}_Nmm" for a in "xyz"]
    for j, (b, s) in enumerate(seats):
        check = [seat_idx[b, s, i] for i in indices]
        np.testing.assert_array_equal([r["phase"] for r in check], phase)
        np.testing.assert_allclose(
            wg[:, j].reshape(count, 6),
            [[float(r[k]) for k in cols] for r in check],
            atol=1e-9,
            rtol=0,
        )
    samples = read_csv(SOURCE / "station_motion.csv.gz")
    fixed = list(dict.fromkeys((r["module"], int(r["station_mm"])) for r in samples))
    dg = np.full((count, len(fixed)), np.nan)
    for r in samples:
        i, j = int(r["state"]), fixed.index((r["module"], int(r["station_mm"])))
        if not np.isnan(dg[i, j]) or r["phase"] != phase[i]:
            raise ValueError("Invalid local gap step")
        dg[i, j] = float(r["minimum_sample_lower_bound_mm"])
    if not np.isfinite(dg).all():
        raise ValueError("Missing local gap samples")
    q = (states / rod.scale).reshape(count, 6, rod.sub, 4)
    curvature = np.linalg.norm(q[:, :, :, 1:3], axis=-1) / (
        rod.l * 1000 * (1 + q[:, :, :, 3])
    )
    module = ["U1", "U2", "U3", "U4", "M5", "M6"]
    seat_names = [f"{b} z{s:+d}" for b, s in seats]
    metrics = [
        ("rope_max_N", T, NAMES, np.argmax),
        ("rope_min_N", T, NAMES, np.argmin),
        ("guide_force_N", np.linalg.norm(wg[:, :, 0], axis=2), seat_names, np.argmax),
        (
            "guide_moment_Nmm",
            np.linalg.norm(wg[:, :, 1], axis=2),
            seat_names,
            np.argmax,
        ),
        ("adjusted_tank_gap_mm", gap[:, None], ["front/tank"], np.argmin),
        (
            "sampled_guide_gap_lower_mm",
            dg,
            [f"{b} z{s:+d}" for b, s in fixed],
            np.argmin,
        ),
        (
            "curvature_rad_per_current_mm",
            curvature.reshape(count, -1),
            [f"{m} cell {c + 1}" for m in module for c in range(rod.sub)],
            np.argmax,
        ),
        ("mu_at_distal_floor_fixed_geometry", mu_edge, NAMES, np.argmin),
    ]
    ranks = []
    for name in ["all", *dict.fromkeys(phase)]:
        ids = indices if name == "all" else indices[phase == name]
        for metric, values, labels, select in metrics:
            ii, j = np.unravel_index(select(values[ids]), values[ids].shape)
            step = int(ids[ii])
            ranks.append(
                dict(
                    phase_group=name,
                    metric=metric,
                    step=step,
                    phase=phase[step],
                    component=labels[j],
                    value=values[step, j],
                )
            )
    write_csv(out / "phase_extremes.csv", ranks)
    write_csv(out / "five_step_poses_and_ropes.csv", [rows[i] for i in EVENTS])
    write_csv(
        out / "five_step_station_wrenches.csv",
        [seat_idx[b, s, i] for i in EVENTS for b, s in seats],
    )
    write_csv(
        out / "five_step_hole_wrenches.csv",
        [
            dict(
                step=i,
                module=b,
                station_mm=s,
                rope=f"{family}_{direction}",
                **dict(zip(cols, hole_loads[i, j].ravel(), strict=True)),
            )
            for i in EVENTS
            for j, (b, s, family, direction) in enumerate(
                zip(body, station, lane, ray, strict=True)
            )
        ],
    )
    floor = {}
    for mu in (0.0, 0.05, 0.15, 0.30):
        low = T * np.exp(-mu * wrap)
        i, j = np.unravel_index(low.argmin(), low.shape)
        hits = np.flatnonzero((low < 2.5).any(axis=1))
        floor[str(mu)] = dict(
            steps_with_any_below_floor=len(hits),
            first_step=int(hits[0]) if len(hits) else None,
            channel_steps_below_floor=int((low < 2.5).sum()),
            minimum_N=low[i, j],
            step=i,
            rope=NAMES[j],
        )
    save(
        out / "cycle_screen.json",
        dict(
            steps=count,
            rope_readings=T.size,
            compared_station_rows=len(seat_rows),
            ranked_fixed_station_samples=len(samples),
            cell_curvatures=curvature.size,
            adverse_bound_by_mu=floor,
            nominal_witness_steps=EVENTS,
            operating_tension_floor_N=2.5,
            head_mass_kg=rod.payload,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out)
