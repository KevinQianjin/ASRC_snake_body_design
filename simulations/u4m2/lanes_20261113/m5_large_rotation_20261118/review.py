"""Summarise the saved M5 equilibria, numerical checks and comparable mesh pairs."""

import argparse
import hashlib
from io import StringIO
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from study import ARCHIVE, CASES, HERE, HOLES, KAPPA, LANES, LENGTH, STATIONS_CSV, archive_loads, save
from shell import E, NU, baseline

ROOT = HERE.parents[3]
VARIANTS = ("bare", "point", "bond")
LINEAR_NAMES = {"bare": "none", "point": "ball", "bond": "rigid_bond"}
LABELS = {"bare": "Bare ribs", "point": "Rotating seat", "bond": "Rigid bond"}
COLORS = {"bare": "#253b53", "point": "#007f72", "bond": "#b54c2d"}
REFERENCE = LANES / "evening_20261117/rib_joint_3d/rib_joint_3d_results.json"
EXPECTED = {
    (v, c)
    for v in VARIANTS
    for c in ("bend0", "bend67.5", *map(str, CASES))
    if c.startswith("bend") or v != "bare"
}


def measures(row):
    metrics = {
        k: row[k]
        for k in (
            "tangent_EI_Nmm2",
            "tangent_GJ_Nmm2",
            "applied_couple_Nmm",
            "max_abs_surface_strain",
            "minimum_oriented_area_ratio",
        )
        if k in row
    }
    for key in ("distal_force_N", "distal_moment_Nmm", "proximal_force_N", "proximal_moment_Nmm"):
        metrics[key] = float(np.linalg.norm(row[key]))
    if row["lands"]:
        for name, values in (
            ("peak_land_force_N", [np.linalg.norm(x["force_N"]) for x in row["lands"]]),
            ("peak_land_moment_Nmm", [np.linalg.norm(x["land_moment_Nmm"]) for x in row["lands"]]),
            ("peak_rotation_deg", [x["relative_rotation_deg"] for x in row["lands"]]),
            ("peak_inplane_rotation_deg", [abs(x["inplane_rotation_deg"]) for x in row["lands"]]),
            ("peak_socket_3d_mm", [x["socket_travel_3d_mm"] for x in row["lands"]]),
            ("peak_socket_inplane_mm", [x["socket_travel_inplane_mm"] for x in row["lands"]]),
        ):
            metrics[name] = max(values)
    return metrics


def difference(first, second):
    a, b = measures(first), measures(second)
    changes = {k: abs(b[k] - a[k]) for k in a if k in b}
    checks = {}
    for key, cutoff in (
        ("tangent_EI_Nmm2", 0),
        ("peak_land_force_N", 0.1),
        ("peak_land_moment_Nmm", 1.0),
        ("distal_force_N", 0.1),
        ("proximal_force_N", 0.1),
        ("distal_moment_Nmm", 1.0),
        ("proximal_moment_Nmm", 1.0),
    ):
        if key not in changes:
            continue
        if max(abs(a[key]), abs(b[key])) < cutoff:
            checks[key] = dict(
                absolute_change=changes[key],
                relative_percent=None,
                status="near zero (absolute difference reported)",
            )
        else:
            pct = 100.0 * changes[key] / abs(b[key]) if b[key] != 0 else None
            checks[key] = dict(
                absolute_change=changes[key],
                relative_percent=pct,
                status="pass" if pct is not None and pct <= 5.0 else "outside 5 percent",
            )
    if "peak_rotation_deg" in changes:
        val = changes["peak_rotation_deg"]
        checks["peak_rotation_deg"] = dict(
            absolute_change=val, status="pass" if val <= 0.5 else "outside 0.5 degrees"
        )
    return dict(first=a, second=b, absolute_changes=changes, criteria=checks)


def checks(row, variant, case):
    if not (
        np.isfinite(row["force_balance_N"])
        and row["force_balance_N"] < 0.003
        and row["moment_balance_Nmm"] < 0.3
        and row["free_residual_inf"] < 3.01e-5
    ):
        raise ValueError(
            f"Reaction closure or free equilibrium residual at {case}, {variant}, {row['fraction']}"
        )
    if row["minimum_oriented_area_ratio"] <= 0.0:
        raise ValueError(f"Local director/area inversion at {case}, {variant}, {row['fraction']}")
    expected = 0 if variant == "bare" else 8
    if len(row["lands"]) != expected:
        raise ValueError("Incomplete mount reactions")
    if variant == "point" and max(np.linalg.norm(x["land_moment_Nmm"]) for x in row["lands"]) > 0.001:
        raise ValueError("Free land rotation transmits a spurious moment")
    if case.startswith("bend"):
        angle = row["fraction"] * KAPPA * LENGTH
        if (
            abs(angle - row["bend_angle_rad"]) > 1.0e-8
            or np.linalg.norm(row["distal_force_N"]) > 0.003
            or row["orthogonal_moment_Nmm"] > 0.001
        ):
            raise ValueError("Pure bending end conditions differ from the demand")
    if "surface_extremes" in row:
        extreme = row["surface_extremes"]
        mag = max(abs(extreme[k]["strain"]) for k in ("principal_tensile", "principal_compressive"))
        if abs(row["max_abs_surface_strain"] - mag) > 1.0e-7:
            raise ValueError("Surface strain extrema do not match")


def joint_ranking(complete):
    """Separate the convergence of a paired design difference from the absolute stiffnesses."""
    ranking = {}
    for case in ("bend0", "bend67.5"):
        if any((v, case) not in complete for v in VARIANTS):
            continue
        areas = sorted(set.intersection(*(set(complete[v, case]) for v in VARIANTS)), reverse=True)
        rows = []
        for area in areas:
            endpoints = {v: complete[v, case][area]["samples"][-1] for v in VARIANTS}
            values = {}
            for field in ("applied_couple_Nmm", "tangent_EI_Nmm2", "tangent_GJ_Nmm2"):
                values[field] = {v: endpoints[v][field] for v in VARIANTS}
                val = values[field]
                val["bond_minus_point"] = val["bond"] - val["point"]
                val["bond_minus_point_percent_of_point"] = 100.0 * val["bond_minus_point"] / val["point"]
            rows.append(dict(area_mm2=area, metrics=values))
        check = {}
        if len(rows) >= 2:
            for name in rows[-1]["metrics"]:
                first, second = (r["metrics"][name] for r in rows[-2:])
                low_bond = min(first["bond"], second["bond"])
                high_point = max(first["point"], second["point"])
                check[name] = dict(
                    change_in_paired_difference=abs(
                        first["bond_minus_point"] - second["bond_minus_point"]
                    ),
                    finer_paired_difference=second["bond_minus_point"],
                    lowest_bond_minus_highest_point=low_bond - high_point,
                )
        ranking[case] = dict(full_bend_by_mesh=rows, last_two_common_meshes=check)
    return ranking


def figures(complete, out_dir):
    plt.rcParams.update({"font.size": 9, "svg.fonttype": "none", "svg.hashsalt": "m5-shell-nov18"})
    common = set.intersection(
        *(set(a for a, d in complete[v, "bend67.5"].items() if len(d["samples"]) == 5) for v in VARIANTS)
    )
    if not common:
        raise ValueError("No common five-point bending sweep")
    area = min(common)
    fig, axes = plt.subplots(2, 2, sharex=True, figsize=(9.4, 6.7), layout="constrained")
    panels = [
        (axes[0, 0], "applied_couple_Nmm", 1.0, "Holding couple (N·mm)"),
        (axes[0, 1], "tangent_EI_Nmm2", 1.0e-3, "Tangent bending stiffness (kN·mm²)"),
        (axes[1, 0], "peak_land_force_N", 1.0, "Peak force at one mounting land (N)"),
        (axes[1, 1], "peak_socket_inplane_mm", 1.0, "Peak in-plane strut travel (mm)"),
    ]
    for v in VARIANTS:
        rows = complete[v, "bend67.5"][area]["samples"]
        x = [np.degrees(z["bend_angle_rad"]) for z in rows]
        values = [measures(row) for row in rows]
        for ax, key, scale, _ in panels:
            if key not in values[0]:
                continue
            ax.plot(
                x,
                [z[key] * scale for z in values],
                marker="o",
                lw=1.8,
                markersize=4,
                label=LABELS[v],
                color=COLORS[v],
            )
    for ax, _, _, ylabel in panels:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dce2e5", lw=0.6)
        ax.set_ylabel(ylabel)
        ax.set_xticks([0, 24, 48, 72, 96])
    for ax in axes[1]:
        ax.set_xlabel("End-disk bend angle (degrees)")
    axes[0, 0].legend(frameon=False)
    fig.suptitle(f"M5 pure bend about 67.5°  |  maximum triangle area {area:g} mm²", fontsize=12)
    with StringIO() as svg:
        fig.savefig(svg, format="svg", metadata={"Date": None, "Creator": "ASRC M5 shell study"})
        lines = (line.rstrip() for line in svg.getvalue().splitlines())
        (out_dir / "moment_curvature.svg").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=HERE / "results")
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    results_dir = args.results_dir.resolve()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    loads = dict(
        frame="M5 proximal CAD axes, origin at the straight module centre. Proximal disk at z = -48 mm.",
        records={},
    )
    for record, state in archive_loads().items():
        loads["records"][str(record)] = dict(
            M5_axes_in_source_base=state["source_frame"],
            distal_displacement_mm=state["displacement_mm"],
            distal_frame=state["rotation"],
            station_audits=state["checks"],
            stations=state["stations_detail"],
        )
    save(out_dir / "load_cases.json", loads)
    files = sorted(results_dir.glob("*/*.json"))
    if not files:
        raise FileNotFoundError("No solved cases")
    complete, failures, inventory = {}, [], []
    bounds = {"force_balance_N": 0.0, "moment_balance_Nmm": 0.0, "free_residual_inf": 0.0}
    min_ratio = 1.0
    audited_states = 0
    audited_cases = 0
    audited_min_ratio = 1.0
    for path in files:
        d = json.loads(path.read_text())
        key = d["variant"], d["case"]
        area = d["mesh"]["max_triangle_area_mm2"]
        inventory.append(
            dict(
                file=(Path(results_dir.name) / path.relative_to(results_dir)).as_posix(),
                completed=d["completed"],
                last_sample=d["samples"][-1]["fraction"] if d["samples"] else None,
            )
        )
        if not d["completed"]:
            failures.append(
                dict(
                    file=inventory[-1]["file"],
                    reason=d.get("failure", "Continuation stopped"),
                    steps=d["steps"][-2:],
                )
            )
            continue
        if key not in EXPECTED or area in complete.setdefault(key, {}):
            raise ValueError(f"Unexpected case or duplicate completed mesh {key}, {area}")
        complete[key][area] = d
        if "accepted_state_orientation_audit" in d:
            audit = d["accepted_state_orientation_audit"]
            expected_states = 1 + sum(step["accepted"] for step in d["steps"])
            if audit["states"] != expected_states or not 0.0 < audit["minimum_ratio"] <= 1.0:
                raise ValueError(f"Inconsistent saved-state orientation audit for {key}, {area}")
            audited_cases += 1
            audited_states += audit["states"]
            audited_min_ratio = min(audited_min_ratio, audit["minimum_ratio"])
        if d["samples"][0]["fraction"] != 0.0 or d["samples"][-1]["fraction"] != 1.0:
            raise ValueError("Missing unloaded or full-load equilibrium")
        rows = d["samples"] + ([d["split_last_step"]["endpoint"]] if "split_last_step" in d else [])
        for row in rows:
            checks(row, *key)
            min_ratio = min(min_ratio, row["minimum_oriented_area_ratio"])
            for k in bounds:
                bounds[k] = max(bounds[k], row[k])
        if not key[1].startswith("bend"):
            from scipy.spatial.transform import Rotation

            target = np.array(d["inputs"]["target"])
            row = d["samples"][-1]
            angle = Rotation.from_matrix(row["tip_rotation"]).as_quat()
            if np.max(abs(np.r_[row["tip_displacement_mm"], angle[:3] / angle[3]] - target)) > 1.0e-8:
                raise ValueError("Published loaded endpoint differs from its saved pose")
    missing = sorted(EXPECTED - set(complete))
    raw = json.loads(REFERENCE.read_text())
    linear = raw["runs"][-1]
    factor = E / raw["parameters"]["E"]
    summary = []
    for (v, c), group in sorted(complete.items()):
        areas = sorted(group, reverse=True)
        item = dict(
            variant=v,
            case=c,
            completed_areas_mm2=areas,
            final_by_area={str(a): measures(group[a]["samples"][-1]) for a in areas},
            mesh_comparisons=[],
            step_comparisons=[],
            twist_probes=[],
        )
        for a, b in zip(areas, areas[1:]):
            common = {z["fraction"]: z for z in group[a]["samples"]}
            pairs = {
                str(z["fraction"]): difference(common[z["fraction"]], z)
                for z in group[b]["samples"]
                if z["fraction"] in common
            }
            item["mesh_comparisons"].append(dict(coarse_area=a, fine_area=b, at_fraction=pairs))
        if item["mesh_comparisons"]:
            final_pair = item["mesh_comparisons"][-1]
            criteria = final_pair["at_fraction"]["1.0"]["criteria"]
            outside = [name for name, value in criteria.items() if value["status"].startswith("outside")]
            item["endpoint_mesh_check"] = dict(
                coarse_area_mm2=final_pair["coarse_area"],
                fine_area_mm2=final_pair["fine_area"],
                outside_threshold=outside,
                passed=not outside,
            )
        for a in areas:
            d = group[a]
            if "split_last_step" in d:
                item["step_comparisons"].append(
                    dict(area=a, endpoints=difference(d["samples"][-1], d["split_last_step"]["endpoint"]))
                )
            if "finite_twist" in d:
                val = d["finite_twist"]["central_GJ_Nmm2"]
                analytic = d["samples"][-1]["tangent_GJ_Nmm2"]
                item["twist_probes"].append(
                    dict(
                        area=a,
                        tangent_GJ_Nmm2=analytic,
                        central_GJ_Nmm2=val,
                        difference_percent=100.0 * abs(analytic - val) / abs(val),
                    )
                )
        if c.startswith("bend"):
            matching = next(
                x
                for x in linear["cases"]
                if x["variant"] == LINEAR_NAMES[v] and x["bending_axis_deg"] == float(c[4:])
            )
            EI = matching["EI_Nmm2"] * factor
            GJ = linear["global_stiffness"][LINEAR_NAMES[v]]["GJ_Nmm2"] * factor
            ref = dict(EI_Nmm2=EI, GJ_Nmm2=GJ, source_area_mm2=linear["mesh"]["max_triangle_area_mm2"])
            item["unloaded_comparison"] = dict(reference=ref, by_area={})
            for a in areas:
                row = group[a]["samples"][0]
                item["unloaded_comparison"]["by_area"][str(a)] = dict(
                    EI_difference_percent=100.0 * (row["tangent_EI_Nmm2"] / EI - 1.0),
                    GJ_difference_percent=100.0 * (row["tangent_GJ_Nmm2"] / GJ - 1.0),
                )
        summary.append(item)
    inputs = [
        Path(baseline.BODY).resolve(),
        ARCHIVE,
        ARCHIVE.with_name("equilibria.json"),
        HOLES,
        STATIONS_CSV,
        ARCHIVE.with_name("mass_model.json"),
        REFERENCE,
        *(
            LANES / name
            for name in (
                "rib_joint_model.py",
                "rib_joint_3d.py",
                "state_archives.py",
                "lanes.py",
                "bellmouth_model.py",
                "end_bellmouth_kernel.py",
            )
        ),
        LANES / "../../../cad/lanes_u4m2/end_bellmouth_v1/design.json",
    ]
    reference_revision = "4e1992e56460559967e102809668701e3d6942f9"
    hashes = {
        p.resolve().relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs
    }
    try:
        matches = all(
            hashlib.sha256(
                subprocess.check_output(
                    ["git", "show", f"{reference_revision}:{name}"],
                    cwd=ROOT,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                )
            ).hexdigest()
            == digest
            for name, digest in hashes.items()
        )
    except (OSError, subprocess.SubprocessError):
        matches = None
    versions = {
        n: version(n)
        for n in (
            "numpy",
            "scipy",
            "shapely",
            "trimesh",
            "triangle",
            "numba",
            "matplotlib",
            "cvxopt",
            "rtree",
            "networkx",
        )
    }
    endpoint_checks = [case["endpoint_mesh_check"] for case in summary if "endpoint_mesh_check" in case]
    result = dict(
        reference_revision=reference_revision,
        source_input_revision=reference_revision if matches else None,
        input_files_match_reference_revision=matches,
        nominal_payload_kg=0.5,
        axial_length_mm=LENGTH,
        maximum_pure_curvature_rad_per_mm=KAPPA,
        youngs_modulus_MPa=E,
        poissons_ratio=NU,
        input_hashes_sha256=hashes,
        python=platform.python_version(),
        packages=versions,
        inventory=inventory,
        completed_simulation_case_count=len(complete),
        expected_case_count=len(EXPECTED),
        endpoint_mesh_checks=dict(
            tested_families=len(endpoint_checks),
            passed_families=sum(check["passed"] for check in endpoint_checks),
            relative_tolerance_percent=5.0,
            seat_rotation_tolerance_deg=0.5,
            near_zero_force_N=0.1,
            near_zero_moment_Nmm=1.0,
        ),
        cases_without_a_full_endpoint=missing,
        incomplete_runs=failures,
        equilibrium_maxima=bounds,
        minimum_signed_area_ratio=min_ratio,
        independent_checkpoint_orientation_audit=dict(
            cases=audited_cases,
            states_including_unloaded=audited_states,
            minimum_signed_area_ratio=audited_min_ratio if audited_cases else None,
        ),
        paired_full_bend_ranking=joint_ranking(complete),
        cases=summary,
    )
    save(out_dir / "summary.json", result)
    if not missing:
        figures(complete, out_dir)
    print(
        f"{len(complete)}/{len(EXPECTED)} case families completed. {len(failures)} incomplete runs listed."
    )
    print("Largest reaction closure errors", bounds)


if __name__ == "__main__":
    main()
