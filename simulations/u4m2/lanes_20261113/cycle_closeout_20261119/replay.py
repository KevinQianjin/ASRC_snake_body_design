"""Replay the 1,200 archived targets with the M5 seat masses and the free shared C-rope path."""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
LANES = HERE.parent
ROOT = LANES.parents[2]
SHARED = LANES / "shared_bore_20261119"
BENCH = LANES / "m5_seat_bench_20261119"
BASE = LANES / "guided_validation_20261114/candidate"
sys.path.insert(0, str(SHARED))
from rebalance import SharedRod
from shared_bore import apply_bellmouth, lanes, load_rod
from closed_loop_v2 import Runner, summarize
from closed_loop_cycle import NAMES


def plant(step=0.15, cells=8, variant="niti18_E40"):
    design, base, profiles = load_rod()
    if cells != 8 or variant != "niti18_E40":
        if cells not in (8, 16) or variant not in ("niti18_E40", "niti18_E75"):
            raise ValueError(
                "Choose a guide-aligned 8/16-cell mesh and a published 1.8 mm NiTi variant"
            )
        base = apply_bellmouth(
            lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, cells, variant), design
        )
    seat = json.loads((BENCH / "results/straight_relieved.json").read_text())
    old = {
        r["station"]: r["total_g"] for r in seat["original_station_mass_breakdown_g"]
    }
    new = {r["station_mm"]: r["guide_mass_g"] for r in seat["stations"]}
    if set(old) != set(new) or set(old) != {-12, 12}:
        raise ValueError("Expected two registered M5 station replacements")
    delta = sum(new.values()) - sum(old.values()) - seat["body_removed_mass_g"]
    before = base.planar.bare_mass.copy()
    after = before.copy()
    after[4] += delta / 1000.0
    base.planar.bare_mass = after
    base.mass = base.planar.mass = np.repeat(
        (after + base.planar.rope_module_mass) / base.sub, base.sub
    )
    base.planar.weight_after = (
        np.cumsum(base.mass[::-1])[::-1] - base.mass + base.payload
    )
    meta = dict(
        previous_bare_module_g=(before * 1000).tolist(),
        updated_bare_module_g=(after * 1000).tolist(),
        original_inner_stations_g=old,
        retained_inner_stations_g=new,
        web_machining_removed_g=seat["body_removed_mass_g"],
        M5_net_added_g=delta,
        distribution="Module masses distributed uniformly over the cells of the corresponding module. The other six guide stations retain their baseline CAD masses and all module stiffness values retain their archived homogenized values.",
    )
    return SharedRod(base, profiles, step), meta


def as_relative(path):
    return str(path.resolve().relative_to(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(out, runner, records, settled, rest):
    with gzip.open(out / "controller_records.json.gz", "wt", encoding="utf-8") as f:
        json.dump(records, f, separators=(",", ":"), allow_nan=False)
    with gzip.open(out / "motion_trace.json.gz", "wt", encoding="utf-8") as f:
        json.dump(runner.trace, f, separators=(",", ":"), allow_nan=False)
    np.savez_compressed(
        out / "controller_states.npz",
        settled_z=np.array(settled),
        settled_rest_m=np.array(rest),
        motion_z=np.array(runner.trace_states),
        motion_rest_m=np.array(runner.trace_rest),
        motion_tensions_N=np.array([r["tensions_n"] for r in runner.trace]),
    )
    with (out / "phase_results.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "phase",
                "targets",
                "motion_states_including_start",
                "unsettled_targets",
                "motion_failures_excluding_start",
                "max_settled_angle_error_deg",
                "max_motion_angle_error_deg",
                "min_motion_tension_N",
                "max_motion_tension_N",
                "min_motion_tank_after_allowance_mm",
            ]
        )
        for phase in dict.fromkeys(r["phase"] for r in records):
            rows = [r for r in records if r["phase"] == phase]
            tr = [r for r in runner.trace if r["phase"] == phase]
            sc = [r for r in tr if r["kind"] != "start"] or tr
            err = lambda r: max(
                abs(a)
                for a in r.get(
                    "controlled_errors_deg",
                    (r["yaw_error_deg"], r["elevation_error_deg"]),
                )
            )
            w.writerow(
                [
                    phase,
                    len(rows),
                    len(tr),
                    sum(err(r) > 0.2 or not r["operating_tension_pass"] for r in rows),
                    sum(
                        not r["checks_pass"] or not r["operating_tension_pass"]
                        for r in sc
                        if r["kind"] != "start"
                    ),
                    max(map(err, rows)),
                    max(map(err, sc)),
                    min(r["minimum_tension_n"] for r in sc),
                    max(r["peak_tension_n"] for r in sc),
                    min(r["clearance_mm"] for r in sc) - 1.5,
                ]
            )


def controller_settings(a):
    """Apply the same nominal controller limits to yaw and pitch missions."""
    a.rope_step = 0.25
    a.node_step = 4.5
    a.max_depth = 8
    a.max_iter = 16
    a.precomp_limit = 0.5
    a.tension_target = 3.0
    a.settle_tension = 2.5
    a.mid_tol = None
    a.mid_max = 4


def run(a):
    a.out.mkdir(parents=True, exist_ok=True)
    rod, masses = plant(a.step)
    ref = BASE / "reference"
    gains = BASE / "closed_loop/nominal_gains.npz"
    a.ref = ref
    a.gains = gains
    controller_settings(a)
    runner = Runner("nominal", a, rod=rod)
    reference = json.loads((ref / "nominal.json").read_text())
    expected = len(reference)
    if expected != 1200:
        raise ValueError("Unexpected reference coverage")
    path = [
        ref / "nominal.json",
        ref / "nominal_states.npz",
        gains,
        BENCH / "results/straight_relieved.json",
        LANES / "morning_20261116/fixed_winch_holds/mass_model.json",
    ]
    common = dict(
        expected_targets=expected,
        head_g=500.0,
        cells_per_module=8,
        rope_diameter_mm=2.0,
        cone_spacing_mm=a.step,
        lanes_mm=[21, 24, 28],
        rope_order=NAMES,
        inputs_sha256={as_relative(p): digest(p) for p in path},
        mass=masses,
        plant="Finite bellmouths, shared C-passage, frictionless conservative energy; retained M5 inner station CAD masses; prescribed quasi-static clamp travel.",
    )
    rows = []
    zs = []
    rests = []

    def checkpoint(i, record, z, rest, model):
        rows.append(record)
        zs.append(z.copy())
        rests.append(rest.copy())
        if (i + 1) % 50 == 0 or i == 0:
            with (a.out / "progress.json").open("w") as f:
                json.dump(
                    dict(
                        last_settled_index=i,
                        phase=record["phase"],
                        trace=len(model.trace),
                    ),
                    f,
                )

    try:
        runner.run(checkpoint)
        stopped = None
    except (RuntimeError, ValueError, ArithmeticError) as exc:
        stopped = str(exc)
        print("Stopped:", stopped, flush=True)
    if rows:
        pack(a.out, runner, rows, zs, rests)
    summary = (
        summarize("nominal", rows, runner.trace, a, expected)
        if len(runner.trace) > 1 and rows
        else {}
    )
    if "settings" in summary:
        summary["settings"]["reference"] = as_relative(ref)
        summary["settings"]["gains"] = as_relative(gains)
    summary.update(
        common,
        stopped_reason=stopped,
        targets_executed=len(rows),
        max_motion_residual=max((r["residual"] for r in runner.trace), default=None),
        motion_max_angle_error_deg=max(
            (
                max(abs(r["yaw_error_deg"]), abs(r["elevation_error_deg"]))
                for r in runner.trace
                if r["kind"] != "start"
            ),
            default=None,
        ),
    )
    (a.out / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    if (a.out / "progress.json").exists():
        (a.out / "progress.json").unlink()
    print(len(rows), len(runner.trace), summary.get("settled"), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=float, default=0.15)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args())
