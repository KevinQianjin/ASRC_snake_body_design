"""Verify archived inputs, geometry registrations, returns, continuous duty and installed test evidence."""

import argparse
import hashlib
from importlib.metadata import version
from pathlib import Path
import platform
import numpy as np
from study_context import (
    CAD,
    CANDIDATE,
    NAMES,
    RESULTS,
    ROUND2,
    SOURCE,
    REVISION,
    read,
    read_csv,
    save,
    motion_rows,
    trajectory,
)
from common import ROOT
from free_space import PATHS
from cad_screen import (
    BODIES,
    RopeSurface,
    check_state,
    DESIGN,
    failed_part,
    screen_counts,
)
from replay import plant


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root):
    archived = motion_rows()
    z, _, t = trajectory()
    cases = read(SOURCE / "rope_end_events.json")["rows"]
    rod, _ = plant()
    assert rod.payload == 0.5
    surfaces = {k: RopeSurface(v) for k, v in BODIES.items()}
    comparison = []
    for i in sorted({r["step"] for r in cases}):
        fresh = check_state(
            rod, z[i], t[i].reshape(3, 4), read(DESIGN / "design.json"), surfaces, {}
        )
        previous = [r for r in cases if r["step"] == i]
        for old, new in zip(previous, fresh, strict=True):
            assert all(old[k] == new[k] for k in ("module", "end", "rope", "route"))
            comparison.append(
                abs(old["minimum_rope_gap_mm"] - new["minimum_rope_gap_mm"])
            )
    assert max(comparison) < 1e-7
    counts = {}
    mesh = {}
    geom_counts = probes = 0
    for name in PATHS:
        angles = read_csv(root / "angles" / (name + ".csv.gz"))
        a = read(root / "angles" / (name + ".json"))
        g = read(root / "geometry" / (name + ".json"))["paths"][name]
        screen = read_csv(root / "geometry" / (name + ".csv.gz"))
        assert len(angles) == len(screen) == g["cad_rows"]
        history = [
            dict(r, pass_cad=r["pass_cad"] == "True")
            for r in screen
            if r["leg"] != "return" and r["pass_ideal"] == "True"
        ]
        assert all(g[k] == v for k, v in screen_counts(history).items())
        with np.load(root / "angles" / (name + "_states.npz")) as sf:
            assert sf["z"].shape == (len(angles), 192) and np.isfinite(sf["z"]).all()
        assert a["return_to_seed"] and a["closure_state_difference"] < 1e-7
        if a["first_rejected_deg"] is not None:
            assert 0 < abs(a["first_rejected_deg"] - a["last_pass_deg"]) <= 1
        if (
            g["first_failed_CAD_deg"] is not None
            and g["last_contiguous_screened_deg"] is not None
        ):
            assert (
                abs(g["first_failed_CAD_deg"] - g["last_contiguous_screened_deg"]) <= 1
            )
        for r, s in zip(angles, screen, strict=True):
            assert (
                r["index"] == s["index"]
                and r["leg"] == s["leg"]
                and float(r["command_deg"]) == float(s["command_deg"])
            )
            gaps = {
                k: float(v)
                for k, v in s.items()
                if k.endswith(("_mm", "_wrap_margin_deg"))
            }
            assert len(gaps) == 18 + 1 + 48 and (failed_part(gaps) is None) == (
                s["pass_cad"] == "True"
            )
            ts = [float(r[n + "_N"]) for n in NAMES]
            assert min(ts) == float(r["min_N"]) and max(ts) == float(r["max_N"])
            if r["pass_ideal"] == "True":
                assert (
                    float(r["residual"]) < 2e-6
                    and float(r["tangent_min"]) > 0
                    and float(r["axis_error_deg"]) <= 1
                    and min(ts) >= 2.5
                )
        probe = root / "geometry" / (name + "_probes.csv.gz")
        if probe.is_file():
            probes += len(read_csv(probe))
        if g["last_contiguous_screened_deg"] is not None:
            rt = read(root / "return" / (name + ".json"))
            assert (
                rt["turn_deg"] == g["last_contiguous_screened_deg"]
                and rt["all_pass"]
                and rt["seed_command_difference_mm"] < 1e-6
            )
            v = read(root / "mesh" / (name + ".json"))
            assert v["command_deg"] == rt["turn_deg"] and v["head_mass_g"] == 500
            mesh[name] = v["fine_candidate"]["converged"]
        counts[name] = len(angles)
        geom_counts += len(screen)
    fatigue = read(root / "fatigue/life.json")
    wear = read_csv(root / "fatigue/wear.csv.gz")
    for name in ("matched", "mismatched", "original", "active_matched"):
        sts = fatigue["variants"][name]
        first = sts["first_open_mission"]
        both = sts["two_continuous"]
        assert (
            both["states"]
            == sts["first_with_reset"]["states"] + sts["second_with_reset"]["states"]
        )
        assert first["states"] in (3405, 7084, 10102)
        c = read(root / "service" / (name + "_closure.json"))
        assert c["first_mission_join_error_N"] < 1e-4 and len(c["boundaries"]) == 3
        for n in NAMES:
            w = {r["block"]: r for r in wear if r["variant"] == name and r["rope"] == n}
            for k in (
                "material_travel_mm",
                "drum_travel_mm",
                "sliding_direction_changes",
            ):
                np.testing.assert_allclose(
                    float(w["two_continuous"][k]),
                    float(w["first_with_reset"][k]) + float(w["second_with_reset"][k]),
                    rtol=1e-8,
                    atol=1e-6,
                )
    assert fatigue["physical_life_blocks"] is None
    strength = read(root / "strength/limits.json")
    assert strength["actual_rupture_angle_deg"] is None
    pin = read(root / "strength/pin_area_0.1_fine.json")
    assert pin["pin_grade"] is None and all(
        r["local_contact_force_residual_N"] <= 1e-4 for r in pin["rows"]
    )
    for k, j in pin["resolved_sign_changes_step_pairs"]:
        a, b = ({r["step"]: r for r in pin["rows"]}[i] for i in (k, j))
        assert (
            a["above_reference"] != b["above_reference"]
            and abs(a["yaw_deg"] - b["yaw_deg"]) <= 1
        )
    alt = read(root / "allocation/allocation.json")
    alternative_steps = read_csv(root / "allocation/archived_replay.csv.gz")
    assert len(alternative_steps) == alt["re_equilibrated_saved_out_rows"]
    assert (
        max(float(r["archive_tension_difference_N"]) for r in alternative_steps) < 1e-4
    )
    for case in alt["paths"].values():
        assert case["recovered_seed"]
        if case["first_failed_pitch_deg"] is not None:
            assert (
                abs(case["last_screened_pitch_deg"] - case["first_failed_pitch_deg"])
                <= 1
            )
    edges = read_csv(root / "mesh/fine_geometry.csv.gz")
    edge_summary = read(root / "mesh/fine_geometry.json")
    assert (
        len(edges) == len(edge_summary["samples"])
        and edge_summary["cells_per_module"] == 16
    )
    for r in edges:
        gaps = {
            k: float(v) for k, v in r.items() if k.endswith(("_mm", "_wrap_margin_deg"))
        }
        assert (
            len(gaps) == 67 and (failed_part(gaps) or "") == r["first_failed_geometry"]
        )
        assert (r["all_pass"] == "True") == (
            (r["rod_pass"] == "True") and failed_part(gaps) is None
        )
    opposite = read(root / "mesh/opposite_axis.json")
    assert opposite["mathematical_upper_bound_deg"] == 180
    assert [v["cells_per_module"] for v in opposite["cases"]] == [8, 16]
    for case in opposite["cases"]:
        assert case["max_scaled_state_return_difference"] < 1e-6
        assert [r["stage"] for r in case["rows"]] == [
            "approach",
            "trimmed",
            "recovered",
        ]
        for r in case["rows"]:
            assert len(r["gaps"]) == 67 and len(r["tensions_N"]) == 12
            assert r["first_CAD_failure"] == failed_part(r["gaps"])
            assert r["screened"] == (r["rod_pass"] and failed_part(r["gaps"]) is None)
            np.testing.assert_allclose(
                r["target_error_deg"] + r["physical_axis_separation_deg"],
                180,
                atol=1e-6,
            )
    transitions = read(root / "mesh/refined_transitions.json")
    extra = (
        read_csv(root / "mesh/refined_transitions.csv.gz")
        if transitions["extra_checked_rows"]
        else []
    )
    assert len(extra) == transitions["extra_checked_rows"]
    flags = {
        (r["path"], float(r["command_deg"])): r["all_pass"] == "True" for r in edges
    }
    for row in extra:
        gap_names = tuple(
            k
            for k in row
            if k.endswith(
                (
                    "_guide_mm",
                    "_caps_mm",
                    "_wire_envelope_mm",
                    "_rope_gap_mm",
                    "_wrap_margin_deg",
                )
            )
            or k == "adapter_nonlocal_gap_lower_bound_mm"
        )
        gaps = {k: float(row[k]) for k in gap_names}
        assert (
            len(gaps) == 67
            and (failed_part(gaps) or "") == row["first_failed_geometry"]
        )
        assert (row["all_pass"] == "True") == (
            (row["rod_pass"] == "True") and failed_part(gaps) is None
        )
        flags[row["path"], float(row["command_deg"])] = row["all_pass"] == "True"
    for path, transition in transitions["paths"].items():
        if "last_pass_deg" in transition:
            assert flags[path, transition["last_pass_deg"]]
        stop = transition.get("first_failure_deg")
        if stop is not None:
            assert (
                not flags[path, stop]
                and 0 < abs(stop - transition["last_pass_deg"]) <= 1
            )
    measurements = {
        str(p.relative_to(ROOT)): len(read_csv(p))
        for p in sorted((ROOT / "simulations").rglob("*measurements.csv"))
    }
    assert len(measurements) >= 5
    inputs = [
        SOURCE / p
        for p in (
            "controller_states.npz",
            "rope_tensions_every_step.csv.gz",
            "guide_hole_loads.npz",
            "transmission_motion.npz",
            "rope_end_events.json",
        )
    ]
    inputs.extend(
        [
            *BODIES.values(),
            CANDIDATE / "geometry_check.json",
            CAD / "guides_v2/head_adapter.stl",
            DESIGN / "design.json",
        ]
    )
    for name in ("M5", "M6"):
        for station in (-24, 24) if name == "M5" else (-24, -12, 12, 24):
            folder = (
                CANDIDATE if name == "M6" and abs(station) == 12 else CAD / "guides_v3"
            )
            inputs.extend(
                folder / f"{name}_z{station:+}_{p}.stl"
                for p in ("guide", "caps", "wire_envelope")
            )
    inputs.extend(
        ROUND2 / "rope_control" / (v + ".csv.gz")
        for v in (
            "coupled_s0.15_k0.15_b0.1_open",
            "coupled_s0.15_k0.15_b0.1_compensated",
            "takeup_plant_mu0.12",
            "takeup_plant_mu0.15",
            "takeup_commands_mu0.12",
            "takeup_commands_mu0.15",
        )
    )
    inputs.extend(
        [
            ROUND2 / "fatigue_and_strength/duty_channels.csv.gz",
            ROOT / "data/materials/rope_materials.json",
        ]
    )
    save(
        root / "verification.json",
        dict(
            source_commit=REVISION,
            python=platform.python_version(),
            packages={
                p: version(p)
                for p in (
                    "numpy",
                    "scipy",
                    "numba",
                    "trimesh",
                    "python-fcl",
                    "vtk",
                    "libigl",
                    "clarabel",
                    "cvxopt",
                    "matplotlib",
                )
            },
            baseline_motion_rows=len(archived),
            baseline_tension_rows=t.size,
            end_CAD_regression_values=len(comparison),
            max_archived_signed_gap_difference_mm=max(comparison),
            angle_rows=counts,
            geometry_rows=geom_counts,
            fine_geometry_rows=len(edges),
            extra_fine_transition_rows=len(extra),
            opposite_axis_CAD_samples=sum(len(v["rows"]) for v in opposite["cases"]),
            alternative_command_rows=len(alternative_steps),
            extra_geometry_probes=probes,
            fine_equilibrium_converged=mesh,
            physical_measurement_rows=measurements,
            archived_inputs_sha256={
                str(p.relative_to(ROOT)): digest(p) for p in inputs
            },
        ),
    )
    print(
        "Verified",
        sum(counts.values()),
        "command states,",
        len(comparison),
        "baseline rope exits and",
        len(wear),
        "wear summaries",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
