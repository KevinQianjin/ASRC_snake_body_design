"""Independently check continuity, sign, twelve-rope bookkeeping, endpoint pointing and surface screening."""

import argparse
import csv
import gzip
import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from replay import plant
from pitch_reference import angle_between
from tension_report import NAMES


def data(p):
    return json.loads(p.read_text())


def run(out):
    motion = out / "yaw_pitch"
    with gzip.open(motion / "rope_tensions_every_step.csv.gz", "rt") as f:
        table = list(csv.DictReader(f))
    with gzip.open(motion / "controller_records.json.gz", "rt") as f:
        rows = json.load(f)
    with gzip.open(motion / "motion_trace.json.gz", "rt") as f:
        trace = json.load(f)
    with np.load(motion / "controller_states.npz") as src:
        Q = src["motion_z"]
        T = src["motion_tensions_N"].reshape(-1, 12)
        R = src["motion_rest_m"].reshape(-1, 12)
        zs = src["settled_z"]
        rs = src["settled_rest_m"]
    result = {}
    issues = {}

    def test(k, v):
        result[k] = bool(v)

    test("motion_alignment", len(table) == len(trace) == len(T) == len(R) == len(Q))
    test(
        "force_columns",
        np.allclose(
            T, [[float(r[k + "_N"]) for k in NAMES] for r in table], atol=1e-11, rtol=0
        ),
    )
    test(
        "rest_columns",
        np.allclose(
            R * 1000,
            [[float(r[k + "_command_mm"]) for k in NAMES] for r in table],
            atol=1e-10,
            rtol=0,
        ),
    )
    for i, r in enumerate(table):
        if (
            int(r["step"]) != i
            or int(r["target_index"]) != trace[i]["index"]
            or r["phase"] != trace[i]["phase"]
        ):
            raise ValueError("Mislabelled motion step")
    max_command_increment = float(1000 * np.max(abs(np.diff(R, axis=0))))
    test(
        "no_rope_command_step_exceeds_quarter_mm",
        max_command_increment <= 0.25 + 1.0e-8,
    )
    test(
        "all_reference_targets_are_recorded_in_sequence",
        [r["index"] for r in rows] == list(range(1380)),
    )
    with (motion / "rope_tensions_full_range.csv").open() as f:
        ranges = list(csv.DictReader(f))
    test(
        "per_rope_full_cycle_extrema_match_solver_arrays",
        [r["rope"] for r in ranges] == NAMES
        and all(
            int(r["min_step"]) == T[:, i].argmin()
            and int(r["max_step"]) == T[:, i].argmax()
            and abs(float(r["minimum_N"]) - T[:, i].min()) < 1.0e-10
            and abs(float(r["maximum_N"]) - T[:, i].max()) < 1.0e-10
            for i, r in enumerate(ranges)
        ),
    )
    proj = plant()[0]
    checkpoints = {int(i) for i in np.linspace(0, len(Q) - 1, 25)}
    summary = data(motion / "summary.json")
    for item in summary["turning_points"]:
        group = [i for i, r in enumerate(trace) if r["phase"] == item["phase"]]
        if group:
            checkpoints.add(group[-1])
    errors = []
    equilibria = []
    force_error = []
    quat_error = []
    for i in sorted(checkpoints):
        record = table[i]
        z = Q[i]
        det = proj.evaluate(z, detail=True)[2]
        length = det["rope_lengths"].ravel()
        actual = proj.planar.rope_ea * np.maximum(0.0, length + 1.0 - R[i]) / R[i]
        force_error.append(float(np.max(abs(actual - T[i]))))
        equilibria.append(float(proj.residual(proj.evaluate(z, T[i].reshape(3, 4))[1])))
        ref = np.radians(
            [float(record["target_yaw_deg"]), float(record["target_elevation_deg"])]
        )
        expected = np.array(
            [
                np.cos(ref[1]) * np.cos(ref[0]),
                np.sin(ref[1]),
                np.cos(ref[1]) * np.sin(ref[0]),
            ]
        )
        frame = proj.R0 @ det["frames"][-1]
        errors.append(
            abs(
                float(record["pointing_error_deg"])
                - angle_between(frame[:, 0], expected)
            )
        )
        orientation = Rotation.from_quat(
            [float(record["head_frame_q" + d]) for d in "xyzw"]
        ).as_matrix()
        quat_error.append(float(np.abs(orientation - frame).max()))
    test("independent_checked_winch_forces", max(force_error) < 1e-7)
    test("independent_checked_equilibria", max(equilibria) < 2e-6)
    test(
        "independent_direction_and_full_frame",
        max(errors) < 1e-7 and max(quat_error) < 1e-10,
    )
    with np.load(out / "controller_states.npz") as old:
        n = summary["prefix_settled_targets"]
        m = summary["prefix_motion_samples"]
        test(
            "old_prefix_states_and_commands_exact",
            np.array_equal(zs[:n], old["settled_z"][:n])
            and np.array_equal(rs[:n], old["settled_rest_m"][:n])
            and np.array_equal(Q[:m], old["motion_z"][:m])
            and np.array_equal(
                R[:m].reshape(-1, 3, 4), old["motion_rest_m"][:m].reshape(-1, 3, 4)
            ),
        )
    test(
        "real_withdrawal_and_neutral_return",
        rows[-1]["phase"] == "exit"
        and abs(rows[-1]["clamp_s_mm"] + 750) < 1e-8
        and abs(rows[-1]["target_elevation_deg"] - 20) < 1e-9,
    )
    Tcsv = np.genfromtxt(
        motion / "rope_tensions_at_events.csv",
        delimiter=",",
        names=True,
        dtype=None,
        encoding="utf-8",
    )
    test(
        "event_table_matches_twelve_step_tensions",
        all(
            np.allclose([r[k + "_N"] for k in NAMES], T[r["step"]], atol=1e-11, rtol=0)
            for r in Tcsv
        ),
    )
    for kind, folder in (("holds", out), ("motion", motion)):
        trans = data(folder / f"transmission_{kind}.json")
        arr = np.load(folder / f"transmission_{kind}.npz")
        mu = 0.15
        cap = arr["winch_reference_N"] * np.exp(-mu * arr["total_wrap_rad"])
        row = next(r for r in trans["conditions"] if r["mu"] == mu)
        test(
            f"{kind}_capstan_count_and_min",
            row["records_with_possible_sub_2p5_N"] == np.any(cap < 2.5, axis=1).sum()
            and abs(cap.min() - row["minimum_distal_if_winch_tight_N"]) < 1e-10,
        )
        test(
            f"{kind}_rope_geometric_length_closure",
            trans["maximum_reconstructed_rope_length_error_mm"] <= 0.0003
            and trans["maximum_piece_endpoint_error_mm"] < 1e-6,
        )
        arr.close()
    with gzip.open(motion / "rope_winch_distal_envelopes.csv.gz", "rt") as stream:
        envelopes = np.genfromtxt(
            stream, delimiter=",", names=True, dtype=None, encoding="utf-8"
        )
    with np.load(motion / "transmission_motion.npz") as archive:
        wrap = archive["total_wrap_rad"].ravel()
    winch = T.ravel()
    test(
        "friction_envelopes_match_the_motion_rope_and_wrap",
        np.array_equal(envelopes["step"], np.repeat(np.arange(len(T)), 12))
        and np.array_equal(
            envelopes["phase"], np.repeat([r["phase"] for r in trace], 12)
        )
        and np.array_equal(envelopes["rope"], np.tile(NAMES, len(T)))
        and np.array_equal(envelopes["nominal_winch_N"], winch)
        and np.allclose(
            envelopes["total_wrap_deg"], np.degrees(wrap), atol=1e-10, rtol=0
        ),
    )
    test(
        "each_reported_distal_limit_matches_the_capstan_law",
        all(
            np.allclose(
                envelopes[f"mu_{label}_distal_{side}_N"],
                winch * np.exp(sign * mu * wrap),
                atol=1.0e-10,
                rtol=0,
            )
            for mu, label in ((0.05, "0p05"), (0.15, "0p15"), (0.30, "0p30"))
            for side, sign in (("low", -1), ("high", 1))
        ),
    )
    g = data(motion / "station_motion.json")
    test("six_guide_stations_every_motion_step", g["station_records"] == 6 * len(Q))
    test(
        "complete_mesh_witness_at_each_screened_station",
        all(
            data(folder / f"solid_{kind}_0p5.json")["checks"] == 18
            for kind, folder in (("holds", out), ("motion", motion))
        ),
    )
    scaffold = data(motion / "adapter_clearance.json")
    test("adapter_poses_match_full_trace", scaffold["motion_states"] == len(Q))
    ends = data(motion / "rope_end_events.json")
    test(
        "all_selected_ends_have_finite_radius_checks",
        ends["checks"] == 24 * ends["distinct_motion_steps"]
        and ends["rope_diameter_mm"] == 2.0,
    )
    fine = data(motion / "mesh_poles.json")
    test(
        "same_actual_commands_in_16_cell_vertical_checks",
        len(fine["rows"]) == 2
        and all(
            np.allclose(
                np.ravel(v["rest_lengths_mm"]),
                R[v["step"]] * 1000,
                rtol=0,
                atol=1.0e-11,
            )
            for v in fine["rows"]
        ),
    )
    with gzip.open(motion / "guide_station_loads.csv.gz", "rt") as f:
        guides = list(csv.DictReader(f))
    with np.load(motion / "guide_hole_loads.npz") as f:
        w = f["local_wrench_CAD"]
        check_guides = True
        max_wrench_error = 0.0
        for module in ("M5", "M6"):
            for station in (-24, -12, 12, 24):
                group = [
                    r
                    for r in guides
                    if r["module"] == module and int(r["station_mm"]) == station
                ]
                by_guide = w[
                    :, (f["module"] == module) & (f["station_mm"] == station)
                ].sum(axis=1)
                observed = np.array(
                    [
                        [
                            [float(r["force_" + c + "_N"]) for c in "xyz"],
                            [float(r["moment_" + c + "_Nmm"]) for c in "xyz"],
                        ]
                        for r in group
                    ]
                )
                check_guides &= len(group) == len(Q) and [
                    int(r["step"]) for r in group
                ] == list(range(len(Q)))
                max_wrench_error = max(
                    max_wrench_error, float(np.max(abs(observed - by_guide)))
                )
        test(
            "all_eight_signed_guide_wrenches_match_holes_at_all_steps",
            check_guides and max_wrench_error < 1.0e-10,
        )
    html = (motion / "motion_viewer.html").read_text()
    fig = json.loads(
        re.search(
            r'<script id="data" type="application/json">(.*?)</script>', html, re.S
        ).group(1)
    )
    test(
        "all_viewer_tensions_match_actual_substep_to_display_precision",
        np.array_equal(fig["loads"], np.rint(T * 1000).astype(int))
        and len(fig["group"]) == len(T),
    )
    max_anchor_error = 0.0
    for i in sorted(checkpoints):
        det = proj.base.kinematic_metrics(Q[i])[1]
        for lane, ray in np.ndindex(3, 4):
            node = (lane + 4) * proj.sub
            off = proj.offsets3[lane, ray]
            end = proj.R0 @ (
                1000 * (det["points"][node] + det["frames"][node] @ off)
                + [20.0, 0.0, 0.0]
            )
            path = fig["paths"][fig["shape"][i]][lane * 4 + ray]
            max_anchor_error = max(
                max_anchor_error, float(np.max(abs(np.array(path[-3:]) / 10 - end)))
            )
    test("viewer_rope_anchors_match_physical_nodes", max_anchor_error <= 0.0500001)
    test(
        "three_neutral_comparisons_at_same_clamp",
        len(data(motion / "neutral_returns.json")) == 3,
    )
    checks = data(out / "sliding.json")
    sx = [x for hold in checks["holds"] for x in hold["cases"]]
    test(
        "steady_sliding_balance_and_material_virtual_work",
        len(sx) == 18
        and all(
            x["converged"]
            and x["residual"] < 2e-6
            and x["virtual_work_error"] < 1e-5
            and abs(x["rope_unstretched_closure_mm"]) < 1e-7
            for x in sx
        ),
    )
    sliding = data(motion / "sliding_turns.json")
    attempted = {
        (c["phase"], c["command_direction"], c["mu"]) for c in sliding["cases"]
    }
    required = {
        (ph, d, mu)
        for ph in ("right_out", "left_out", "pitch_up", "pitch_down")
        for d in ("approach", "departure")
        for mu in (0.05, 0.15)
    }
    test(
        "four_turn_sliding_cases_and_saved_force_balances",
        attempted == required
        and all(
            (not c["converged"])
            or (
                c["force_residual"] < 2e-6
                and [r["rope"] for r in c["ropes"]] == NAMES
                and all(
                    abs(r["rope_unstretched_closure_mm"]) < 1e-7
                    and r["virtual_work_error"] < 1e-5
                    for r in c["ropes"]
                )
            )
            for c in sliding["cases"]
        ),
    )
    with (motion / "sliding_turn_tensions.csv").open() as f:
        channels = list(csv.DictReader(f))
    test(
        "separate_winch_and_distal_tensions_at_the_four_turns",
        len(channels) == 12 * sliding["converged"]
        and all(
            abs(
                float(r["distal_N"])
                - float(r["winch_N"])
                * np.exp(
                    int(r["imposed_sign"])
                    * float(r["mu"])
                    * np.radians(float(r["total_turn_deg"]))
                )
            )
            < 1.0e-8
            for r in channels
        ),
    )
    for item in summary["turning_points"]:
        issues[item["phase"]] = dict(
            reached=item["endpoint_reached"],
            terminal_error_deg=item["error_to_requested_direction_deg"],
        )
    result_out = dict(
        data_checks=result,
        all_data_checks_pass=all(result.values()),
        independent_state_witnesses=len(checkpoints),
        maximum_witness_force_difference_N=max(force_error),
        maximum_observed_rope_command_increment_mm=max_command_increment,
        maximum_viewer_anchor_component_error_mm=max_anchor_error,
        maximum_guide_wrench_component_error=max_wrench_error,
        maximum_witness_residual=max(equilibria),
        maximum_witness_pose_difference_deg=max(errors),
        requested_cycle_operating_pass=summary["requested_cycle_pass"],
        pitch_endpoints=issues,
    )
    (out / "validation.json").write_text(json.dumps(result_out, indent=2) + "\n")
    if not all(result.values()):
        raise ValueError([k for k, v in result.items() if not v])
    return result_out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    print(run(p.parse_args().out))
