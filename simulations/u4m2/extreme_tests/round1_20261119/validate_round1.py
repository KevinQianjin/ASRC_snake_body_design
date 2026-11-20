"""Verify result coverage, source identity, independent force closures and mesh sensitivity."""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
from scipy.spatial.transform import Rotation

from study_inputs import (
    CAD,
    CYCLE,
    LANES,
    ROOT,
    SOURCE,
    NAMES,
    EVENTS,
    load_motion,
    read_csv,
    save,
)

BASE_COMMIT = "89b32a97c40b39ec5a988f716d2a5e70a262dc21"


def verify_inputs():
    files = [
        SOURCE / n
        for n in (
            "controller_states.npz",
            "rope_tensions_every_step.csv.gz",
            "guide_station_loads.csv.gz",
            "guide_hole_loads.npz",
            "transmission_motion.npz",
            "station_motion.csv.gz",
            "solid_motion_0p5.json",
        )
    ]
    files += [
        CAD / n
        for n in (
            "guides_v2/U_leaf_springs.stl",
            "guides_v2/spring_strip.json",
            "end_bellmouth_v1/M6_lane_anchorC.stl",
            "end_bellmouth_v1/M5_lane_anchorB.stl",
            "retained_seat_20261118/parts/M5_machined_body.stl",
            "guides_v3/M6_z-12_guide.stl",
            "guides_v3/M6_z-12_caps.stl",
            "guides_v3/M6_z-12_wire_envelope.stl",
        )
    ]
    files += [
        LANES / n
        for n in (
            "m5_large_rotation_20261118/study.py",
            "m5_large_rotation_20261118/shell.py",
            "evening_20261118/pin_seat.py",
            "guide_web_compatibility.py",
            "cad_surface_refinement.py",
            "m5_seat_bench_20261119/results/straight_relieved.json",
            "p3_pin_fixture_20261119/witness_measurements.csv",
        )
    ]
    files += [CYCLE / n for n in ("replay.py", "sliding.py", "adapter.py")]
    hashes = {}
    for file in files:
        path = file.relative_to(ROOT).as_posix()
        blob = subprocess.check_output(
            ["git", "rev-parse", f"{BASE_COMMIT}:{path}"], cwd=ROOT, text=True
        ).strip()
        actual = subprocess.check_output(
            ["git", "hash-object", str(file)], cwd=ROOT, text=True
        ).strip()
        if actual != blob:
            raise ValueError(f"Changed source input: {path}")
        hashes[path] = hashlib.sha256(file.read_bytes()).hexdigest()
    return hashes


def check(out):
    def read(name):
        return json.loads((out / name).read_text())

    inputs = verify_inputs()
    rod, states, T = load_motion()
    phase = read_csv(out / "phase_extremes.csv")
    events = read_csv(out / "five_step_poses_and_ropes.csv")
    assert [int(r["step"]) for r in events] == list(EVENTS)
    for i, r in zip(EVENTS, events):
        np.testing.assert_allclose(
            [float(r[n + "_N"]) for n in NAMES], T[i], rtol=0, atol=1e-9
        )
    assert len(read_csv(out / "five_step_hole_wrenches.csv")) == 5 * 48
    assert len(read_csv(out / "five_step_station_wrenches.csv")) == 5 * 8
    assert len({(r["phase_group"], r["metric"]) for r in phase}) == len(phase) == 96
    screen = read("cycle_screen.json")
    assert (
        screen["rope_readings"] == T.size
        and screen["compared_station_rows"] == len(T) * 8
    )
    m6 = read("m6_clearance.json")["resolution"]
    assert [r["axial_mesh_span_mm"] for r in m6] == [0.5, 0.25, 0.125]
    baseline = json.loads((SOURCE / "solid_motion_0p5.json").read_text())
    for r in baseline["rows"]:
        if r["tag"] == "M6_z-12":
            np.testing.assert_allclose(
                m6[0]["nominal_gaps_mm"][r["part"]],
                r["complete_mesh_distance_mm"],
                atol=1e-8,
            )
    for level in m6:
        gap = level["nominal_gaps_mm"]["guide"]
        lo, hi = level["clear_to_contact_bracket_mm"]
        assert lo < gap < hi and hi - lo < 0.000201 and len(level["cases"]) == 90
        for row in level["cases"]:
            if (
                abs(row["translation_mm"])
                < min(level["nominal_gaps_mm"].values()) - 1e-8
            ):
                assert not row["intersects"]
    m5_checks = []
    for step in (1843, 2059):
        levels = [read(f"m5_step_{step}_area_{a}.json") for a in ("0p1", "0p055")]
        for result in levels:
            assert result["status"] == "converged" and len(result["lands"]) == 8
            assert (
                result["minimum_oriented_area_ratio"] > 0
                and result["free_residual_inf"] < 3e-5
            )
            assert (
                result["force_balance_N"] < 1e-4 and result["moment_balance_Nmm"] < 3e-3
            )
            for c in result["inputs"]["stations"]:
                raw = next(
                    r
                    for r in read_csv(out / "five_step_station_wrenches.csv")
                    if int(r["step"]) == step
                    and int(r["station_mm"]) == c["station_mm"]
                    and r["module"] == "M5"
                )
                for name, units, key in [
                    ("force", "N", "F_CAD_N"),
                    ("moment", "Nmm", "M_CAD_Nmm"),
                ]:
                    np.testing.assert_allclose(
                        c[key],
                        [float(raw[f"{name}_{a}_{units}"]) for a in "xyz"],
                        atol=1e-8,
                    )
        best = [
            max(v["lands"], key=lambda r: np.linalg.norm(r["force_N"])) for v in levels
        ]
        forces = [np.linalg.norm(r["force_N"]) for r in best]
        m5_checks.append(
            dict(
                step=step,
                pivot_F_N_coarse_fine=forces,
                peak_location_agrees=all(
                    best[0][key] == best[1][key] for key in ("station_mm", "rib_deg")
                ),
                fine_pivot=best[1],
                peak_force_change_percent=100 * abs(forces[0] / forces[1] - 1),
                peak_tensile_strain_coarse_fine=[
                    v["surface_extremes"]["principal_tensile"]["strain"] for v in levels
                ],
                peak_compressive_strain_coarse_fine=[
                    v["surface_extremes"]["principal_compressive"]["strain"]
                    for v in levels
                ],
            )
        )
    cases = read("pitch_sliding.json")
    channels = read_csv(out / "pitch_sliding_channels.csv")
    assert (
        len(cases) == 24
        and all(c["converged"] for c in cases)
        and len(channels) == 24 * 12
    )
    friction = []
    for c in cases:
        step, mu = c["step"], c["mu"]
        data = [r for r in channels if int(r["step"]) == step and float(r["mu"]) == mu]
        assert [r["rope"] for r in data] == NAMES
        np.testing.assert_allclose(
            [float(r["nominal_N"]) for r in data], T[step], rtol=0, atol=1e-8
        )
        assert max(abs(float(r["rest_error_mm"])) for r in data) < 1e-6
        assert max(abs(float(r["virtual_work_error"])) for r in data) < 1e-6
        if mu == 0:
            np.testing.assert_allclose(
                [float(r["distal_N"]) for r in data], T[step], rtol=0, atol=2e-5
            )
        assert abs(c["min_distal_N"] - min(float(r["distal_N"]) for r in data)) < 1e-9
    for step in (2348, 2432):
        sweep = sorted([c for c in cases if c["step"] == step], key=lambda c: c["mu"])
        j = next(i for i, c in enumerate(sweep) if c["below_floor"])
        friction.append(
            dict(step=step, last_passing=sweep[j - 1], first_below_floor=sweep[j])
        )
    u = read("u_blades.json")["solutions"]
    assert len(u) == 36
    u_groups = []
    for step in (2819, 1510, 1498):
        sols = [r for r in u if r["step"] == step]
        fine = [r for r in sols if r["gauge_spacing_mm"] == 0.5]
        assert len(fine) == 4 and all(r["converged"] for r in fine)
        forces = np.sum([r["force_in_proximal_CAD_N"] for r in fine], axis=0)
        a = max(fine, key=lambda r: r["peak_tension_strain"])
        for r in fine:
            if r["peak_tension_strain"] + 1e-6 < r["geometric_extension_lower_bound"]:
                raise ValueError(
                    "Recovered outer fibre falls below the CAD extension bound"
                )
            assert (
                max(r["endpoint_residual_mm"]) < 2e-5
                and r["orthogonality_error"] < 1e-5
            )
        R = Rotation.from_rotvec(a["disk_rotation_deg"], degrees=True).as_matrix()
        end_cell = int(a["module"][1:]) * rod.sub - 1
        eps = (states[step] / rod.scale).reshape(-1, 4)[end_cell, 3]
        other = [r for r in sols if r["gauge_spacing_mm"] == 1 and r["converged"]]
        nearest = max(
            abs(
                r["peak_tension_strain"]
                - next(
                    v["peak_tension_strain"]
                    for v in fine
                    if (r["blade_x_sign"], r["blade_y_sign"])
                    == (v["blade_x_sign"], v["blade_y_sign"])
                )
            )
            for r in other
        )
        u_groups.append(
            dict(
                step=step,
                module=a["module"],
                max_tensile_strain=a["peak_tension_strain"],
                min_compressive_strain=min(r["peak_compression_strain"] for r in fine),
                peak_tensile_site_CAD=dict(
                    x_sign=a["blade_x_sign"],
                    y_sign=a["blade_y_sign"],
                    z_mm=a["peak_tension_z_mm"],
                ),
                max_geometric_extension_bound=max(
                    r["geometric_extension_lower_bound"] for r in fine
                ),
                maximum_single_strip_end_force_N=max(
                    np.linalg.norm(r["force_in_proximal_CAD_N"]) for r in fine
                ),
                total_four_strip_axial_force_trial_N=forces @ R[:, 2],
                whole_U_last_cell_axial_constitutive_N=eps * rod.K[end_cell, 3] / rod.l,
                largest_1_to_0p5mm_tensile_change_percentage_points=100 * nearest,
            )
        )
    witness = read_csv(LANES / "p3_pin_fixture_20261119/witness_measurements.csv")
    data = dict(
        baseline_commit=BASE_COMMIT,
        source_sha256=inputs,
        python=platform.python_version(),
        versions={
            k: version(k)
            for k in [
                "numpy",
                "scipy",
                "numba",
                "trimesh",
                "vtk",
                "shapely",
                "matplotlib",
                "python-fcl",
                "cvxopt",
                "triangle",
                "manifold3d",
            ]
        },
        head_kg=rod.payload,
        physical_P3_specimen_rows=len(witness),
        rank_rows=len(phase),
        fixed_geometry_gap_change_um=[
            1000 * (b["nominal_gaps_mm"]["guide"] - a["nominal_gaps_mm"]["guide"])
            for a, b in zip(m6, m6[1:])
        ],
        m5_mesh_comparison=m5_checks,
        coupled_pitch_solutions=len(cases),
        pitch_floor_brackets=friction,
        u_solutions_attempted=len(u),
        u_solutions_converged=sum(v["converged"] for v in u),
        u_rejected_continuation_steps=sum(len(v["rejected_continuation"]) for v in u),
        u_cases=u_groups,
    )
    save(out / "validation.json", data)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.out)
    print("Verified source identity, coverage, equilibrium and mesh comparisons.")
