"""Validate inputs, output coverage, convergence flags, assemblies, and the laboratory-data status."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from bench_inputs import CAD, HERE, ROOT


def read(p):
    def invalid(v):
        raise ValueError(f"Nonfinite numerical value {v} in {p.name}")

    return json.loads(p.read_text(), parse_constant=invalid)


def verify(seat, ropes):
    checks = {}

    def check(name, value):
        checks[name] = bool(value)

    prov = read(seat / "provenance.json")
    for k in ("source_sha256", "generated_CAD_sha256"):
        check(
            k,
            all(
                hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
                for n, h in prov[k].items()
            ),
        )
    saved = read(seat / "summary.json")
    cases = saved["fixture_cases"]
    check(
        "six_shell_cases_at_both_resolutions",
        len(cases) == 6 and saved["coupled_sites_per_mesh"] == 48,
    )
    for level in ("middle", "fine"):
        obj = [read(p) for p in (seat / f"coupled_{level}").glob("*.json")]
        check(
            f"{level}_common_guide_closure",
            len(obj) == 6
            and all(
                v["status"] == "converged"
                and len(v["last_sites"]) == 8
                and v["history"][-1]["maximum_translation_mismatch_mm"] < 0.001
                and v["history"][-1]["maximum_moment_mismatch_Nmm"] < 0.02
                and max(x["contact"]["force_residual_N"] for x in v["last_sites"])
                < 0.005
                for v in obj
            ),
        )
    vals = read(seat / "coupled_cad_fine.json")["stations"]
    refined = read(seat / "coupled_cad_refined_targets.json")["stations"]
    refined += read(seat / "coupled_cad_refined_transverse.json")["stations"]
    check("loaded_station_coverage", len(vals) == 12 and len(refined) == 6)
    check(
        "removing_hub_material_does_not_reduce_fixed_pose_gap",
        all(
            r["relieved"]["nearest_unintended"]["gap_mm"]
            >= r["original"]["nearest_unintended"]["gap_mm"] - 2e-6
            for r in vals + refined
        ),
    )
    check(
        "unintended_solid_intersection_count_zero",
        saved["nominal_cad_interference_unintended"] == 0,
    )
    final_straight = read(seat / "straight_relieved.json")
    check(
        "straight_assembly_pairs",
        sum(s["pairs"] for s in final_straight["stations"]) == 1980
        and not any(s["intersections"] for s in final_straight["stations"]),
    )
    streams = [read(seat / f"coupon_{lvl}.json") for lvl in ("middle", "fine", "finer")]
    check(
        "calculated_coupon_states",
        all(
            len(s["load_states"]) == 27
            and all(
                r["converged"] and r["force_residual_N"] < 0.005
                for r in s["load_states"]
            )
            for s in streams
        ),
    )
    bench = read(seat / "fixture_clearance.json")
    check(
        "fixture_nominal_sweeps",
        bench["static_internal_pairs"] == 94
        and bench["cross_group_pairs_per_pose"] == 40
        and not bench["unloaded_internal_positive_overlaps"]
        and not bench["unintended_contact_pairs"]
        and not bench["uncertified_subintervals"]
        and all(v["intersection"] is None for v in bench["installation"]),
    )
    check(
        "actual_gauge_from_four_ribs",
        max(
            read(CAD / "parts/manifest.json")["inspection"][
                "registered_gauge_difference_by_source_rib_mm3"
            ].values()
        )
        < 1.0e-4,
    )
    with (seat / "load_program.csv").open(newline="") as f:
        prog = list(csv.DictReader(f))
    check(
        "program_phases",
        len(prog) == 66
        and len({(r["target"], r["direction"], r["phase"]) for r in prog}) == 66,
    )
    geo = read(ropes / "summary.json")["frozen_shared_bore"]
    check(
        "four_C_ropes_all_held_poses",
        geo["held_poses"] == 217
        and geo["route_checks"] == 868
        and geo["two_end_CAD_checks"] == 1736,
    )
    check(
        "frozen_rope_geometric_criteria",
        geo["cad_failures_outside_minus_0005_mm"] == 0
        and geo["less_than_one_degree_margin"] == 0,
    )
    rr = read(ropes / "rebalanced_summary.json")
    n = rr["solved"]
    check(
        "complete_model_replay_of_saved_winch_holds",
        n == 217 and rr["complete"] and not rr["failed_or_missing"],
    )
    with np.load(ropes / "rebalanced_states.npz", allow_pickle=False) as p:
        check(
            "full_saved_state_shapes",
            p["z"].shape == (n, 192)
            and all(
                p[k].shape == (n, 3, 4)
                for k in ("tensions_n", "rope_lengths_mm", "winch_rest_lengths_mm")
            )
            and all(np.isfinite(p[k]).all() for k in p.files),
        )
    check(
        "rebalanced_CAD_and_tank",
        rr["end_CAD_failures_at_minus_0005_mm"] == 0
        and rr["tank_envelope"]["clearance_failures"] == 0,
    )
    loads = read(ropes / "guide_load_summary.json")
    with np.load(ropes / "guide_hole_loads.npz", allow_pickle=False) as archive:
        with (ropes / "guide_station_loads.csv").open(newline="") as f:
            station_rows = list(csv.DictReader(f))
        archive_module = archive["hole_module"]
        archive_station = archive["station_mm"]
        forces = archive["hole_wrench_CAD"]
        matches = np.array_equal(archive["hold"], np.arange(217))
        for row in station_rows:
            idx = int(row["hold"])
            select = (archive_module == row["module"]) & (
                archive_station == int(row["station_mm"])
            )
            component = np.array(
                [
                    [float(row[f"{name}_{axis}_{unit}"]) for axis in "xyz"]
                    for name, unit in (("force", "N"), ("moment", "Nmm"))
                ]
            )
            matches &= np.count_nonzero(select) == int(row["holes"]) and np.allclose(
                forces[idx, select].sum(axis=0), component, rtol=0, atol=1e-9
            )
        check(
            "simultaneous_load_table",
            len(station_rows) == 1736
            and matches
            and forces.shape == (217, 48, 2, 3)
            and np.isfinite(forces).all()
            and archive["joint_wall_wrench_CAD"].shape == (217, 4, 2, 3)
            and loads["hole_records"] == 10416,
        )
    motion = loads["joint_virtual_work_at_hold_64_C_up"]
    check(
        "joint_force_and_moment_verified",
        motion["force_error_N"] < 1e-3
        and motion["moment_error_Nmm"] < 1e-3
        and loads["maximum_wall_force_normal_check_error_N"] < 0.005,
    )
    tangent = read(ropes / "tangent_check_64.json")
    check(
        "independent_fixed_winch_tangent",
        len(tangent) == 2
        and all(
            max(x["relative_tangent_vector_error"] for x in t["checks"]) < 0.01
            for t in tangent
        ),
    )
    transferred = read(seat / "shared_load_case/comparison.json")
    res146 = read(seat / "shared_load_case/146.json")
    src = res146["shared_rod_boundary"]["SHA256"]
    scored = transferred["stations"]
    check(
        "new_rod_boundary_146",
        res146["status"] == "converged"
        and res146["case"] == "146"
        and all(
            hashlib.sha256((ropes / name).read_bytes()).hexdigest() == value
            for name, value in src.items()
        )
        and res146["history"][-1]["maximum_translation_mismatch_mm"] < 0.001
        and res146["history"][-1]["maximum_moment_mismatch_Nmm"] < 0.02
        and all(s["contact"]["force_residual_N"] < 0.005 for s in res146["last_sites"])
        and len(scored) == 2
        and all(len(s["holes"]) == 8 for s in scored),
    )
    hs = read(seat / "hardware_status.json")
    hr = read(ropes / "hardware_status.json")
    check(
        "unmeasured_hardware_makes_no_pass_claim",
        all(
            hs[k]["status"] == "awaiting_measurements" and hs[k]["rows"] == 0
            for k in ("coupon", "metrology", "cage")
        )
        and hr["status"] == "awaiting_measurements"
        and hr["samples"] == 0,
    )
    return dict(
        passed=all(checks.values()),
        checks=checks,
        scope="Data integrity, numerical checks and nominal CAD within the documented models. Hardware fixtures, material strength, fatigue and dynamic control have separate acceptance tests.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seat", type=Path, default=HERE / "results")
    p.add_argument(
        "--ropes", type=Path, default=HERE.parent / "shared_bore_20261119/results"
    )
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    record = verify(a.seat, a.ropes)
    a.out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["checks"]))
    raise SystemExit(not record["passed"])
