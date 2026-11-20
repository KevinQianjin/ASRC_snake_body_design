"""Map hypothetical measured tensile capacities to first sampled crossings on each screened route."""

from pathlib import Path
import argparse
import numpy as np
from study_context import RESULTS, NAMES, motion_rows, read, read_csv, save, write_table
from free_space import PATHS
from pitch_reference import angle_between
from pose_map import axis

TRIAL_PULL_N = (10, 15, 20, 25, 30, 40, 60, 80, 100, 125, 150)
TRIAL_WEB_STRAIN = (0.02, 0.04, 0.06, 0.08, 0.10)
NEUTRAL = axis(0, 20)


def event(r, y, p):
    return dict(
        yaw_deg=y,
        pitch_deg=p,
        stage=r["stage"],
        rope=max(NAMES, key=lambda n: float(r[n + "_N"])),
        demand_N=max(float(r[n + "_N"]) for n in NAMES),
    )


def path_prefix(archive, phase):
    ids = [i for i, r in enumerate(archive) if r["phase"] == phase]
    neutral = max(
        i
        for i in range(ids[0])
        if float(archive[i]["target_yaw_deg"]) == 0
        and abs(float(archive[i]["target_elevation_deg"]) - 20) < 1e-6
    )
    return [dict(stage=archive[i]["phase"], **archive[i]) for i in [neutral, *ids]]


def run(root):
    archive = motion_rows()
    angles = root / "angles"
    geom = root / "geometry"
    boundaries = []
    lookup = []
    for name, (_, _, phase, _) in PATHS.items():
        ideal = read(angles / (name + ".json"))
        g = read(geom / (name + ".json"))["paths"][name]
        end = g["last_contiguous_screened_deg"]
        seed = ideal["seed_deg"]
        raw = read_csv(angles / (name + ".csv.gz"))
        accept = [
            r
            for r in raw
            if r["pass_ideal"] == "True"
            and r["leg"] != "return"
            and end is not None
            and abs(float(r["command_deg"]) - seed) <= abs(end - seed) + 1e-8
        ]
        probes = geom / (name + "_probes.csv.gz")
        if probes.is_file():
            accept.extend(
                r
                for r in read_csv(probes)
                if r["out_pass"] == "True"
                and end is not None
                and abs(float(r["command_deg"]) - seed) <= abs(end - seed) + 1e-8
            )
        accept = sorted(accept, key=lambda r: abs(float(r["command_deg"]) - seed))
        pre = path_prefix(archive, phase)
        route = [
            event(r, float(r["target_yaw_deg"]), float(r["target_elevation_deg"]))
            for r in pre
        ]
        if name == "antipode":
            connector = [
                r
                for r in read_csv(angles / "right.csv.gz")
                if r["pass_ideal"] == "True"
                and r["leg"] == "out"
                and float(r["yaw_deg"]) <= 180
            ]
            route.extend(
                event(
                    dict(stage="right connector", **r),
                    float(r["yaw_deg"]),
                    float(r["pitch_deg"]),
                )
                for r in connector
            )
        route.extend(
            event(
                dict(stage="extension", **r), float(r["yaw_deg"]), float(r["pitch_deg"])
            )
            for r in accept
        )
        for limit in TRIAL_PULL_N:
            i = next((i for i, r in enumerate(route) if r["demand_N"] >= limit), None)
            a = route[i - 1] if i is not None and i > 0 else {}
            b = route[i] if i is not None else {}
            lookup.append(
                dict(
                    path=name,
                    assumed_installed_rupture_or_pullout_N=limit,
                    status="already exceeded at path start"
                    if i == 0
                    else "crossed"
                    if i is not None
                    else "not reached on samples",
                    preceding_yaw_deg=a.get("yaw_deg"),
                    preceding_pitch_deg=a.get("pitch_deg"),
                    preceding_peak_N=a.get("demand_N"),
                    first_yaw_deg=b.get("yaw_deg"),
                    first_pitch_deg=b.get("pitch_deg"),
                    crossing_stage=b.get("stage"),
                    rope=b.get("rope"),
                    first_demand_N=b.get("demand_N"),
                    path_peak_N=max(r["demand_N"] for r in route),
                )
            )
        best = (
            max(
                accept,
                key=lambda r: angle_between(
                    NEUTRAL, np.array([float(r["head_" + k]) for k in "xyz"])
                ),
            )
            if accept
            else None
        )
        bounds = dict(
            path=name,
            source_step=ideal["source_step"],
            seed_deg=seed,
            rod_last_deg=ideal["last_pass_deg"],
            rod_stop_deg=ideal["first_rejected_deg"],
            rod_reason=ideal["limiting_reason"],
            screened_last_deg=end,
            screened_stop_deg=g["first_failed_CAD_deg"]
            if g["first_failed_CAD_deg"] is not None
            else ideal["first_rejected_deg"],
            reason=g["first_CAD_component"] or ideal["limiting_reason"],
            prefix_return=g["prefix_return_checked"] and ideal["return_to_seed"],
            largest_sampled_base_axis_separation_deg=None,
            at_yaw_deg=None,
            at_pitch_deg=None,
            peak_tension_screened_path_N=max(r["demand_N"] for r in route),
        )
        if best:
            bounds.update(
                largest_sampled_base_axis_separation_deg=angle_between(
                    NEUTRAL, np.array([float(best["head_" + k]) for k in "xyz"])
                ),
                at_yaw_deg=float(best["yaw_deg"]),
                at_pitch_deg=float(best["pitch_deg"]),
            )
        boundaries.append(bounds)
    write_table(root / "strength" / "pull_capacity_lookup.csv.gz", lookup)
    p = read(root / "strength" / "pin_area_0.1_fine.json")
    web = []
    for limit in TRIAL_WEB_STRAIN:
        i = next(
            (
                j
                for j, r in enumerate(p["rows"])
                if r["shell_peak_tensile"]["strain"] >= limit
            ),
            None,
        )
        before = p["rows"][i - 1] if i is not None and i > 0 else None
        after = p["rows"][i] if i is not None else None
        web.append(
            dict(
                hypothetical_principal_fracture_strain=limit,
                preceding_yaw_deg=before["yaw_deg"] if before else None,
                first_yaw_deg=after["yaw_deg"] if after else None,
                preceding_strain=before["shell_peak_tensile"]["strain"]
                if before
                else None,
                first_strain=after["shell_peak_tensile"]["strain"] if after else None,
                first_rib_deg=after["shell_peak_tensile"]["rib_deg"] if after else None,
                status="crossed" if after else "not reached on sampled branch",
            )
        )
    save(
        root / "strength" / "limits.json",
        dict(
            paths=boundaries,
            trial_web_left_out=web,
            actual_rupture_angle_deg=None,
            status="The angle map combines nominal functional and sampled geometric checks. Hypothetical local tensile criteria require independently measured installed capacities.",
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
