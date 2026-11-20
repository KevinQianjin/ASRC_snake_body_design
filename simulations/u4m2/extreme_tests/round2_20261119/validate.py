"""Check the delivered archive against independent geometry, force, equilibrium and coverage records."""

import argparse
import hashlib
from importlib.metadata import version
from pathlib import Path
import platform
import numpy as np
from common import (
    input_file,
    BASE,
    CAD,
    CANDIDATE,
    EV,
    LANES,
    NAMES,
    OUT,
    R1,
    ROOT,
    SOURCE,
    read,
    read_csv,
    save,
)
from duty import rainflow
from replay import plant
from rope_history import FREE


def source_revision_path(path):
    """Identify inputs by their repository path at BASE, including relocated round-one data."""
    if path.is_relative_to(R1):
        path = LANES / "extreme_round1_20261119/results" / path.relative_to(R1)
    return path.relative_to(ROOT).as_posix()


def run(out):
    base = read_csv(input_file(out, "m6_guides", "m6_all_steps.csv.gz"))
    lookup = {(int(r["station_mm"]), int(r["step"])): r for r in base}
    assert len(lookup) == len(base) == 6810
    matched = {}
    for f in sorted(
        [*(EV / "closure").glob("*.json"), *(EV / "screen").glob("*.json")]
    ):
        obj = read(f)
        if not isinstance(obj, dict):
            continue
        for r in obj.get("rows", []):
            if (
                r.get("variant") not in ("bond_gap_0p25", "g025")
                or r.get("axial_span_mm") != 0.5
            ):
                continue
            key = (r["station_mm"], r["step"])
            new = lookup[key]
            matched[key] = max(
                abs(float(new[k]) - r[k])
                for k in ("guide_gap_mm", "caps_gap_mm", "wire_envelope_gap_mm")
            )
    if len(matched) < 1217 or max(matched.values()) > 1e-6:
        raise ValueError("Previous full triangle records disagree")
    fine = read(input_file(out, "m6_guides", "m6_fine_exact.json"))
    assert len(fine) == 8
    stiffness = read(input_file(out, "m6_guides", "m6_support.json"))
    fine_stiff = read(input_file(out, "m6_guides", "m6_support_refined.json"))
    assert (
        len(stiffness["lands"]) == 96
        and len(stiffness["cases"]) == len(fine_stiff["cases"]) == 24
    )
    assert max(v["land_wrench_residual"] for v in stiffness["cases"]) < 2e-5
    changed = read(input_file(out, "motion_limits", "disturbed_holds.json"))
    controls = [v for v in changed if v["scenario"] == "control"]
    assert len(controls) == 7 and all(v["converged"] for v in controls)
    for v in controls:
        with np.load(SOURCE / "controller_states.npz") as f:
            T = f["motion_tensions_N"][v["step"]]
        np.testing.assert_allclose(T, v["tension_N"], atol=2e-5)
    uc = read(input_file(out, "u_structure", "u_assembly.json"))
    balanced = [v for v in uc["cases"] if v["status"] == "balanced"]
    assert len(uc["cases"]) == 36 and balanced
    assert max(abs(v["axial_residual_N"]) for v in balanced) < 1e-5
    uc_check = read(input_file(out, "u_structure", "u_interpolation_check.json"))
    assert len(uc_check) == 4 and all(v["converged"] for v in uc_check)
    m5 = read(input_file(out, "m5_structure", "m5_local.json"))
    assert len(m5) == 16
    for v in m5:
        if v["converged"]:
            assert v["contact_force_residual_N"] < 1e-4
    yield_checks = read(input_file(out, "m5_structure", "pin_yield_brackets.json"))
    assert {v["step"] for v in yield_checks} == {1843, 2059}
    for v in yield_checks:
        assert v["lower_bending_MPa"] < v["catalog_yield_MPa"] <= v["upper_bending_MPa"]
        if v["status"] == "refined":
            assert 0 < v["upper_scale"] - v["lower_scale"] <= 0.02
            assert all(
                a["converged"] and a["force_residual_N"] < 1e-4
                for a in v["probe_solutions"]
            )
    ropes = {}
    for name in ("open", "feedback", "compensated"):
        tag = "coupled_s0.15_k0.15_b0.1_" + name
        r = read(input_file(out, "rope_control", tag + ".json"))
        trace = read_csv(input_file(out, "rope_control", tag + ".csv.gz"))
        assert (
            r["states"] == len(trace) == 3405 and len({v["phase"] for v in trace}) == 11
        )
        assert r["peak_equilibrium_residual"] < 2e-6
        forces = np.array([[float(v[n + "_dist_N"]) for n in NAMES] for v in trace])
        assert forces.min() >= 0 and abs(forces.min() - r["minimum_distal"][0]) < 1e-8
        assert np.count_nonzero(forces.min(1) < 2.5) == r["states_below_floor"]
        ropes[name] = dict(samples=forces.size, residual=r["peak_equilibrium_residual"])
    take = read(input_file(out, "rope_control", "takeup.json"))
    m = next(v for v in take if v["actual_mu"] == v["assumed_mu"])
    assert (
        m["original_endpoint_equilibria_checked"] == 3405
        and m["original_endpoints_over_2e_6_residual"] == 0
    )
    assert max(v["max_command_increment_mm"] for v in take) <= 0.25
    takeup_plant = {}
    ea = plant()[0].planar.rope_ea
    with np.load(SOURCE / "controller_states.npz") as archive:
        initial_force = archive["motion_tensions_N"][0].ravel()
        initial_drum = archive["motion_rest_m"][0].ravel()
    initial_material = initial_drum - FREE / (1 + initial_force / ea)
    for estimated in (0.12, 0.15):
        tag = f"takeup_plant_mu{estimated:g}"
        run_result = read(input_file(out, "rope_control", tag + ".json"))
        trace = read_csv(input_file(out, "rope_control", tag + ".csv.gz"))
        endpoints = [r for r in trace if r["kind"] in ("initial", "endpoint")]
        assert len(trace) == run_result["all_substeps"]["states"]
        assert len(endpoints) == run_result["original_endpoints"]["states"]
        assert [int(r["step"]) for r in endpoints] == list(range(len(endpoints)))
        if run_result["stopped_at"] is None:
            assert (
                len(trace) == run_result["expected_substeps"] and len(endpoints) == 3405
            )
        actual = np.array([[float(r[n + "_dist_N"]) for n in NAMES] for r in trace])
        np.testing.assert_allclose(
            actual.min(), run_result["all_substeps"]["minimum_distal_N"][0], atol=1e-8
        )
        assert (
            np.count_nonzero(actual.min(1) < 2.5)
            == run_result["all_substeps"]["below_tension_floor"]
        )
        assert max(float(r["residual"]) for r in trace) < 2e-6
        prefix = (
            np.array([[float(r[n + "_slip_mm"]) for n in NAMES] for r in trace]).cumsum(
                axis=0
            )
            / 1000
        )
        paid = (
            np.array([[float(r[n + "_drum_mm"]) for n in NAMES] for r in trace]) / 1000
        )
        proximal = np.array([[float(r[n + "_prox_N"]) for n in NAMES] for r in trace])
        taut = (actual > 1e-8) & (proximal > 1e-8)
        material_error = abs(
            paid - initial_material - prefix - FREE / (1 + proximal / ea)
        )
        max_closure = np.max(material_error[taut]) * 1000
        assert max_closure < 1e-6
        takeup_plant[str(estimated)] = dict(
            substeps=len(trace),
            original_endpoints=len(endpoints),
            failed_solve=run_result["stopped_at"],
            worst_taut_material_closure_mm=max_closure,
        )
    paths = read(input_file(out, "motion_limits", "pose_paths.json"))
    bounds = read(input_file(out, "motion_limits", "pose_boundary_checks.json"))
    assert len(paths) == 22 and len({r["yaw_deg"] for r in paths}) == 11
    assert len({v["source_step"] for v in bounds["withdrawal_connections"]}) == 11
    assert len(bounds["source_slices"]) == len(bounds["withdrawal_connections"]) == 22
    pose_table = read_csv(input_file(out, "motion_limits", "pose_steps.csv.gz"))
    retrace = dict(
        pairs=0,
        maximum_force_difference_N=0.0,
        maximum_command_difference_mm=0.0,
        maximum_clearance_difference_mm=0.0,
        maximum_axis_error_difference_deg=0.0,
    )
    for v in paths:
        rows = [
            r
            for r in pose_table
            if (int(r["yaw_deg"]), int(r["branch_end_deg"]))
            == (v["yaw_deg"], v["end_deg"])
        ]
        assert len({r["source_step"] for r in rows}) == 1
        assert (
            sum(r["leg"] == "out" and r["free_pass"] == "True" for r in rows)
            == v["forward_samples"]
        )
        assert sum(r["leg"] == "return" for r in rows) == v["reverse_samples"]
        out_poses = {
            r["target_pitch_deg"]: r
            for r in rows
            if r["leg"] == "out" and r["free_pass"] == "True"
        }
        for reverse in (
            r for r in rows if r["leg"] == "return" and r["free_pass"] == "True"
        ):
            forward = out_poses[reverse["target_pitch_deg"]]
            retrace["pairs"] += 1
            groups = {
                "maximum_force_difference_N": [n + "_N" for n in NAMES],
                "maximum_command_difference_mm": [n + "_command_mm" for n in NAMES],
                "maximum_clearance_difference_mm": [
                    f"gap_depth_{d}_mm" for d in (-15, 15, 45)
                ],
                "maximum_axis_error_difference_deg": ["axis_error_deg"],
            }
            for key, fields in groups.items():
                change = max(abs(float(forward[f]) - float(reverse[f])) for f in fields)
                retrace[key] = max(retrace[key], change)
        for r in rows:
            forces = [float(r[n + "_N"]) for n in NAMES]
            assert abs(min(forces) - float(r["minimum_N"])) < 1e-8
            assert abs(max(forces) - float(r["maximum_N"])) < 1e-8
            if r["free_pass"] == "True":
                assert float(r["residual"]) < 2e-6 and float(r["axis_error_deg"]) <= 1
    assert retrace["maximum_force_difference_N"] < 1e-3
    assert retrace["maximum_command_difference_mm"] < 1e-8
    assert retrace["maximum_clearance_difference_mm"] < 0.01
    assert retrace["maximum_axis_error_difference_deg"] < 0.002
    linked = [
        v
        for v in bounds["withdrawal_connections"]
        if v.get("command_closure_mm") is not None
    ]
    for v in linked:
        assert v["command_closure_mm"] < 1e-7 and v["tension_closure_N"] < 1e-3
    timed = read(input_file(out, "motion_limits", "timed_response.json"))
    assert len(timed) == 24
    duty = read(input_file(out, "fatigue_and_strength", "duty.json"))
    channels = read_csv(input_file(out, "fatigue_and_strength", "duty_channels.csv.gz"))
    counts = read_csv(input_file(out, "fatigue_and_strength", "rainflow.csv.gz"))
    assert len(channels) == 3405 and len(counts) == duty["counts"]
    for k in channels[0].keys() - {"phase", "step"}:
        series = np.array([float(r[k]) for r in channels])
        cycles = rainflow(series)
        assert np.isclose(
            2 * np.sum(cycles[:, 0] * cycles[:, 2]),
            np.sum(abs(np.diff(series))),
            rtol=1e-9,
            atol=1e-8,
        )
    required = [
        SOURCE / s
        for s in (
            "controller_states.npz",
            "rope_tensions_every_step.csv.gz",
            "guide_hole_loads.npz",
            "transmission_motion.npz",
        )
    ]
    required += [
        ROOT / "data/materials/module_stiffness.sqlite3",
        ROOT / "data/materials/rope_materials.json",
        CAD / "end_bellmouth_v1/M6_lane_anchorC.stl",
        CAD / "guides_v2/U_lane_pass.stl",
        CAD / "guides_v2/U_leaf_springs.stl",
        CAD / "guides_v2/head_adapter.stl",
        CAD / "guides_v3/design.json",
        R1 / "u_blades.json",
        R1 / "m5_step_1843_area_0p055.json",
        R1 / "m5_step_2059_area_0p055.json",
        *sorted(CANDIDATE.glob("*.stl")),
    ]
    versions = {
        p: version(p)
        for p in (
            "numpy",
            "scipy",
            "trimesh",
            "python-fcl",
            "numba",
            "vtk",
            "cvxopt",
            "triangle",
            "shapely",
        )
    }
    save(
        out / "verification" / "validation.json",
        dict(
            source_revision=BASE,
            python=platform.python_version(),
            packages=versions,
            input_sha256={
                source_revision_path(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in required
            },
            archived_station_steps_independently_matched=len(matched),
            maximum_archived_FCL_discrepancy_mm=max(matched.values()),
            full_CAD_station_steps=len(base),
            fine_CAD_cases=len(fine),
            balanced_axial_cases=len(balanced),
            finite_pin_converged=sum(v["converged"] for v in m5),
            finite_pin_attempted=len(m5),
            whole_rod_replays=ropes,
            free_rod_takeup_replays=takeup_plant,
            combined_paths=len(paths),
            combined_pose_samples=len(pose_table),
            outward_return_observables=retrace,
            withdrawal_connections_verified=len(linked),
            conditional_yield_brackets_refined=sum(
                x["status"] == "refined" for x in yield_checks
            ),
            rainflow_variation_identity_channels=duty["channels"],
        ),
    )
    print(
        "validated 500 g round two", len(matched), "previous station steps", flush=True
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
