"""Reduce completed paired CAD/contact checks without turning an incomplete study into a pass."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from assembly import sequence
from clearance import CAD, CASES, j


def read(path):
    return json.loads(path.read_text())


def contacts(base, name):
    out = {}
    for f in sorted((base / name).glob("*.json")):
        d = read(f)
        for s in d["sites"]:
            key = (d["case"], s["station_mm"], s["rib_deg"])
            if key in out:
                raise ValueError(f"Duplicate {key}")
            if "error" in s or not s.get("converged"):
                raise ValueError(f"Unsolved contact {name}:{key}")
            out[key] = s
    return out


def extremum(table, k, minimise=False):
    choose = min if minimise else max
    key = choose(table, key=lambda ix: table[ix][k])
    return {"case": key[0], "station": key[1], "rib_deg": key[2], k: table[key][k]}


def compare(crs, fine):
    rows = []
    for key in fine:
        a, b = crs[key], fine[key]
        row = dict(case=key[0], station=key[1], rib_deg=key[2])
        for field, name in [
            ("peak_tensile_principal_strain", "strain"),
            ("peak_nodal_pressure_MPa", "pressure"),
        ]:
            row[name + "_change_pct_of_finer"] = (
                100 * abs(a[field] - b[field]) / max(1e-12, abs(b[field]))
            )
        rows.append(row)
    return dict(
        paired_sites=len(rows),
        both_within_five_pct=sum(
            max(x["strain_change_pct_of_finer"], x["pressure_change_pct_of_finer"]) < 5
            for x in rows
        ),
        largest_strain_change_pct=max(r["strain_change_pct_of_finer"] for r in rows),
        largest_pressure_change_pct=max(
            r["pressure_change_pct_of_finer"] for r in rows
        ),
        sites=rows,
    )


def bore_sizes(maximum_tilt_deg):
    tilt = np.radians(maximum_tilt_deg)
    y = np.linspace(0, j.HALF_THICKNESS, 3001)
    pin_envelope = j.PIN / np.cos(tilt) + y * np.tan(tilt)
    rows = []
    for radius in (j.CROWN_RADIUS, 2.0):
        # At the opening the axial face relief and the bore profile intersect.
        opening = brentq(
            lambda r: j.hole_radius(j.face_height(r), crown_radius=radius) - r,
            j.PIN,
            j.WEB_WIDTH / 2,
        )
        rows.append(
            dict(
                crown_radius_mm=radius,
                minimum_zero_load_radial_gap_at_tilt_mm=float(
                    min(j.hole_radius(y, crown_radius=radius) - pin_envelope)
                ),
                remaining_side_ligament_at_opening_mm=float(j.WEB_WIDTH / 2 - opening),
            )
        )
    return dict(
        maximum_tilt_deg=maximum_tilt_deg,
        unrelieved_extra_diameter_mm=float(2 * (pin_envelope[-1] - j.PIN)),
        crowns=rows,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True)
    a = ap.parse_args()
    p = a.results
    nominal = [
        read(p / f)
        for f in (
            "clearance_0p055_edge0p2.json",
            "clearance_0p025_edge0p2.json",
            "clearance_0p025_edge0p1.json",
        )
    ]
    digest = {
        x.name: hashlib.sha256(x.read_bytes()).hexdigest()
        for x in sorted((CAD / "parts").glob("*.stl"))
    }
    if any(n["part_sha256"] != digest for n in nominal):
        raise ValueError("Clearance results use a different CAD revision")
    locs = {(c, z) for c in CASES for z in j.STATIONS}
    sets = []
    for n in nominal:
        s = {(r["case"], r["station"]): r for r in n["stations"]}
        if set(s) != locs:
            raise ValueError("Missing shell/CAD endpoint")
        sets.append(s)
    coarse, fine, high = sets
    A = contacts(p, "contact_middle")
    B = contacts(p, "contact_fine")
    C = contacts(p, "contact_finer")
    all_sites = {
        (c, z, t)
        for c in CASES
        for z in j.STATIONS
        for t in (67.5, 157.5, 247.5, 337.5)
    }
    if set(A) != all_sites or set(B) != all_sites:
        raise ValueError("Incomplete contact matrix")
    expected = {(c, 12, t) for c in CASES for t in (67.5, 157.5)}
    if set(C) != expected:
        raise ValueError("Incomplete local refinement")
    st = read(p / "straight.json")
    old = st["original_station_mass_breakdown_g"]
    got = np.array([r["guide_mass_g"] for r in st["stations"]])
    was = np.array([r["total_g"] for r in old])
    paths = [read(p / f"assembly_{z:+d}.json") for z in j.STATIONS]
    for station, journal in zip(j.STATIONS, paths):
        expected_parts = [(station, part.label) for part in sequence(station)]
        actual_parts = [
            (part["station"], part["component"]) for part in journal["parts"]
        ]
        if actual_parts != expected_parts or not journal["extended_fork_envelope"]:
            raise ValueError(
                f"Incomplete installation sequence or different fork envelope at {station} mm"
            )
    stages = [
        s
        for data in paths
        for q in data["parts"]
        for s in q["stages"]
        if s.get("samples", 0)
    ]
    tr = [s for s in stages if s["method"] == "distance-bounded translation"]
    he = [s for s in stages if s["method"] == "sampled helix"]
    tools = read(p / "tool_access.json")["rows"]
    lateral = read(p / "side_drive.json")["rows"]
    side_drive = []
    for design in ("wide", "slim", "low"):
        for station in j.STATIONS:
            rows = [
                v for v in lateral if v["driver"] == design and v["station"] == station
            ]
            if len(rows) != 8 or {v["screw"] for v in rows} != {
                f"lap_screw_{i}" for i in range(8)
            }:
                raise ValueError("Incomplete side-drive sweep")
            clear = [v["minimum_gap_mm"] for v in rows if v["full_sweep_clear"]]
            side_drive.append(
                dict(
                    driver=design,
                    station=station,
                    verified=len(clear),
                    minimum_verified_gap_mm=min(clear, default=None),
                )
            )
    glob = read(p / "remaining_body.json")
    globfine = read(p / "remaining_body_fine.json")
    corr = read(p / "corrected_edge0p15.json")
    if {(q["case"], q["station"]) for q in corr["stations"]} != locs:
        raise ValueError("Incomplete local CAD transfer")
    globmap = {(v["case"], v["station"]): v for v in glob["rows"]}
    fineglob = {(v["case"], v["station"]): v for v in globfine["rows"]}
    best_global = {**globmap, **fineglob}
    corrected = {(v["case"], v["station"]): v for v in corr["stations"]}
    env = read(
        Path(__file__).resolve().parent.parent
        / "evening_20261118/envelope/envelope_pin_r0p30_0p025.json"
    )
    k = "land 0.30 mm, clearance 0.20 mm, slope 0.25"
    per_case = []
    for c in CASES:
        sites = {key: v for key, v in B.items() if key[0] == c}

        def cv(name):
            return max(v[name] for v in sites.values())

        else_gap = min(
            v["closest_lower_bound"][1] for key, v in best_global.items() if key[0] == c
        )
        per_case.append(
            dict(
                case=c,
                stage1_ideal_wall_margin_mm=env["cases"][c][-1]["bowtie"][k][
                    "min_clearance_mm"
                ],
                nominal_local_gap_mm=min(
                    high[c, z]["unintended"]["clearance_mm"] for z in j.STATIONS
                ),
                corrected_local_gap_mm=min(
                    corrected[c, z]["unintended"]["gap_mm"] for z in j.STATIONS
                ),
                other_body_gap_or_lower_bound_mm=else_gap,
                local_peak_tensile_principal_strain=cv("peak_tensile_principal_strain"),
                local_peak_nodal_pressure_MPa=cv("peak_nodal_pressure_MPa"),
                maximum_pivot_translation_mm=cv("translation_mm"),
                pin_nominal_bending_stress_MPa=cv("pin_nominal_bending_stress_MPa"),
                rigid_fit_bore_shift_mm=max(
                    corrected[c, z]["rigid_fit"]["maximum_bore_shift_mm"]
                    for z in j.STATIONS
                ),
            )
        )
    changes = dict(
        shell_only_gap_mm=max(
            abs(
                coarse[k]["unintended"]["clearance_mm"]
                - fine[k]["unintended"]["clearance_mm"]
            )
            for k in locs
        ),
        surface_only_gap_mm=max(
            abs(
                high[k]["unintended"]["clearance_mm"]
                - fine[k]["unintended"]["clearance_mm"]
            )
            for k in locs
        ),
        independent_distance_agreement_mm=max(
            abs(v[f]["clearance_mm"] - v[f]["independent_manifold_gap_mm"])
            for v in high.values()
            for f in ("unintended", "bearing")
        ),
        other_body_refinement_mm=max(
            abs(globmap[k]["closest_lower_bound"][1] - v["closest_lower_bound"][1])
            for k, v in fineglob.items()
        ),
    )
    maxv = {
        name: extremum(B, name)
        for name in (
            "translation_mm",
            "peak_tensile_principal_strain",
            "peak_nodal_pressure_MPa",
            "p95_volume_tensile_principal_strain",
            "pin_nominal_bending_stress_MPa",
            "force_residual_N",
            "max_elastic_deflection_mm",
        )
    }
    maxv["worst_saved_hold_strain"] = extremum(
        {k: v for k, v in B.items() if k[0].isdigit()}, "peak_tensile_principal_strain"
    )
    geometries = [q for v in corr["stations"] for q in v["nearby_pairs"]]
    comparison = compare(A, B)
    refine = compare(B, C)
    out = dict(
        source_revision="1c101887e4c6c84e66a660d2d2460594a741fd54",
        payload_g=500,
        per_case=per_case,
        bore_sizes=bore_sizes(max(v["tilt_deg"] for v in B.values())),
        mass=dict(
            previous_stations_g=was.tolist(),
            candidate_stations_g=got.tolist(),
            removed_web_mass_g=st["body_removed_mass_g"],
            net_change_g=float((got - was).sum() - st["body_removed_mass_g"]),
        ),
        straight=dict(
            component_pair_checks=sum(r["pairs"] for r in st["stations"]),
            overlaps=sum(len(r["intersections"]) for r in st["stations"]),
            bore_centre_change_mm=max(
                x["centre_change_mm"] for x in st["rope_bore_checks"]
            ),
            bore_diameter_change_mm=max(
                x["equivalent_diameter_change_mm"] for x in st["rope_bore_checks"]
            ),
        ),
        motion=dict(
            component_placements=sum(len(v["parts"]) for v in paths),
            linear_segments=len(tr),
            helical_segments=len(he),
            samples=sum(v["samples"] for v in stages),
            failed=[
                (r["station"], r["component"])
                for v in paths
                for r in v["parts"]
                if not r["passed_samples"]
            ],
            unresolved_linear_segments=sum(
                r["unresolved_interval_max_surface_travel_mm"] > 0 for r in tr
            ),
            unresolved_linear_interval_max_mm=max(
                r["unresolved_interval_max_surface_travel_mm"] for r in tr
            ),
            shortest_shank_space_mm=min(r["unobstructed_length_mm"] for r in tools),
            shaft_access_rows=len(tools),
            side_drive=side_drive,
        ),
        clearance_refinement=changes,
        previous_tip_comparison=globfine["previous_tip_comparison"],
        local_contact_extremes=maxv,
        force_balance_residual_N=max(b["force_residual_N"] for b in B.values()),
        largest_contact_moment_Nmm=max(
            np.linalg.norm(r["contact_moment_about_pivot_spn_Nmm"]) for r in B.values()
        ),
        compressive_thrust_sites={
            side: sum(
                r["contact_components"][side]["normal_force_sum_N"] > 0.001
                for r in B.values()
            )
            for side in ("negative_thrust", "positive_thrust")
        },
        middle_to_fine_contact=comparison,
        fine_to_finer_selected_contact=refine,
        correction=dict(
            max_material_projection_error_mm=max(
                x["max_projection_error_mm"] for x in corr["transfer_quality"]
            ),
            max_rigid_fit_residual_mm=max(
                q["rigid_fit"]["maximum_incompatibility_mm"] for q in corr["stations"]
            ),
            max_rigid_fit_bore_shift_mm=max(
                q["rigid_fit"]["maximum_bore_shift_mm"] for q in corr["stations"]
            ),
            max_intended_metal_overlap_mm3=max(
                q["intended"]["intersection_mm3"] for q in corr["stations"]
            ),
            unintended_overlap_pairs=sum(
                q["intersection_mm3"] > 1e-7
                for q in geometries
                if q["family"] not in ("shoulder_pin", "threaded_cap")
            ),
        ),
    )
    out["manufacturing_status"] = (
        "Open pending contact refinement, material and tolerance measurements, tool access and hardware validation."
    )
    (p / "summary.json").write_text(json.dumps(out, indent=2) + "\n")
    with (p / "case_summary.csv").open("w") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(per_case[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(per_case)
    print(
        json.dumps(
            {
                k: v
                for k, v in out.items()
                if k
                in ("mass", "straight", "motion", "clearance_refinement", "correction")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
