"""Score measured coupon and cage observations. Blank templates never count as hardware evidence."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import brentq

from bench_inputs import HERE, load_targets, program
from clearance import j

COUPON = (
    "specimen",
    "print_lot",
    "calibration_id",
    "target",
    "direction",
    "phase",
    "elapsed_s",
    "pin_on_web_s_N",
    "pin_on_web_p_N",
    "pin_on_web_n_N",
    "qx",
    "qy",
    "qz",
    "qw",
    "coupon_s_mm",
    "coupon_p_mm",
    "coupon_n_mm",
    "force_vector_uncertainty_N",
    "pose_uncertainty_deg",
    "position_vector_uncertainty_mm",
    "visible_damage",
)
CAGE = (
    "cage_id",
    "print_lot",
    "calibration_id",
    "trial_id",
    "station_mm",
    "observation",
    "feature",
    "value",
    "uncertainty",
    "requirement",
    "upper_requirement",
    "criterion_id",
)
CAGE_RULES = {
    "bent_gap_mm": (
        "lower",
        {"rib7_hub0", "nearest_local_fork_or_gate", "bend0_closest_pair"},
    ),
    "lap_torque_Nmm": ("range", {f"lap_{k}" for k in range(8)}),
    "cap_install_torque_Nmm": ("range", {f"seat_{k}" for k in range(4)}),
    "cap_engagement_mm": ("lower", {f"seat_{k}" for k in range(4)}),
    "cap_retention_N": ("lower", {f"seat_{k}" for k in range(4)}),
    "both_pin_ends_accessible": ("boolean", {f"seat_{k}" for k in range(4)}),
    "guide_mass_g": ("observe", {"assembled_station"}),
    "bore_position_error_mm": (
        "upper",
        {f"{lane}_{angle}" for lane in "BC" for angle in (0, 90, 180, 270)},
    ),
}


def read_csv(path, fields):
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(fields):
            raise ValueError(f"Use the published columns and units in {path.name}")
        rows = list(reader)
    for i, r in enumerate(rows, 2):
        if None in r or any(v is None for v in r.values()):
            raise ValueError(f"{path.name}, row {i}: wrong number of columns")
        for key in r:
            r[key] = r[key].strip()
    return rows


def number(r, key, *, positive=False, nonnegative=False):
    v = float(r[key])
    if not np.isfinite(v) or (positive and v <= 0) or (nonnegative and v < 0):
        raise ValueError(f"Invalid {key}: {r[key]!r}")
    return v


def vector(r, keys):
    return np.array([number(r, k) for k in keys])


def assess_coupon(rows, predictions):
    if not rows:
        return dict(status="awaiting_measurements", rows=0, specimens=[])
    cmds = program(load_targets())
    programs = {(c["target"], c["direction"], c["phase"]): c for c in cmds}
    groups = defaultdict(list)
    seen = set()
    configuration = defaultdict(set)
    for r in rows:
        key = tuple(r[k] for k in ("target", "direction", "phase"))
        sid = r["specimen"]
        if (
            not all(r[k] for k in ("specimen", "print_lot", "calibration_id"))
            or key not in programs
        ):
            raise ValueError("Missing specimen identification or unknown command")
        if (sid, key) in seen:
            raise ValueError(f"Duplicate measurement {sid}, {key}")
        seen.add((sid, key))
        cmd = programs[key]
        configuration[sid].add((r["print_lot"], r["calibration_id"]))
        F = vector(r, COUPON[7:10])
        q = vector(r, COUPON[10:14])
        t = vector(r, COUPON[14:17])
        if abs(np.linalg.norm(q) - 1) > 0.001:
            raise ValueError(f"Invalid measured unit quaternion at {sid}, {key}")
        if r["visible_damage"] not in ("yes", "no"):
            raise ValueError("visible_damage must be yes or no")
        error = np.linalg.norm(
            F - vector(cmd, ("pin_on_web_s_N", "pin_on_web_p_N", "pin_on_web_n_N"))
        )
        wanted = Rotation.from_quat([cmd[f"coupon_to_pin_q{k}"] for k in "xyzw"])
        angle = np.degrees((wanted.inv() * Rotation.from_quat(q)).magnitude())
        groups[(sid, *key[:2])].append(
            dict(
                phase=key[2],
                order=cmd["order"],
                time=number(r, "elapsed_s", nonnegative=True),
                t=t,
                fu=number(r, "force_vector_uncertainty_N", positive=True),
                au=number(r, "pose_uncertainty_deg", positive=True),
                tu=number(r, "position_vector_uncertainty_mm", positive=True),
                force_error_N=float(error),
                angle_error_deg=float(angle),
                damage=r["visible_damage"] == "yes",
            )
        )
    if any(len(c) != 1 for c in configuration.values()):
        raise ValueError(
            "Use a single declared print lot and calibration setup for each specimen or register a new series ID"
        )
    results = []
    flags = set()
    for sid in sorted(configuration):
        cycles = []
        peak = {}
        incomplete = False
        for target in ("P1", "P2", "P3"):
            for direction in ("source", "reverse"):
                obs = groups.get((sid, target, direction), [])
                if any(
                    a["order"] >= b["order"] or a["time"] >= b["time"]
                    for a, b in zip(obs, obs[1:])
                ):
                    raise ValueError(
                        f"Non-increasing phase order or elapsed time in {sid} {target} {direction}"
                    )
                by = {a["phase"]: a for a in obs}
                missing = [
                    k[2]
                    for k in programs
                    if k[:2] == (target, direction) and k[2] not in by
                ]
                incomplete |= bool(missing)
                outside = [
                    a["phase"]
                    for a in obs
                    if a["force_error_N"] > a["fu"] or a["angle_error_deg"] > a["au"]
                ]
                damage = [a["phase"] for a in obs if a["damage"]]
                out = dict(
                    target=target,
                    direction=direction,
                    missing_phases=missing,
                    force_or_orientation_outside_declared_uncertainty=outside,
                    visible_damage_phases=damage,
                )
                if "pre_ref" in by and "post_ref" in by:
                    pre, post = by["pre_ref"], by["post_ref"]
                    res = float(np.linalg.norm(post["t"] - pre["t"]))
                    bound = pre["tu"] + post["tu"]
                    out.update(
                        matched_reference_shift_mm=res,
                        combined_position_bound_mm=bound,
                        resolved_reference_shift=bool(res > bound),
                    )
                    if res > bound:
                        flags.add("reference shift exceeds declared uncertainty")
                if "peak" in by:
                    peak[target, direction] = by["peak"]
                if outside:
                    flags.add("load or pose discrepancy")
                if damage:
                    flags.add("visible damage")
                cycles.append(out)
        pairs = []
        for r in predictions["peak_pairs"]:
            target = r["target"]
            if (target, "source") in peak and (target, "reverse") in peak:
                a, bp = (peak[target, d] for d in ("source", "reverse"))
                travel = float(np.linalg.norm(a["t"] - bp["t"]))
                pred = r["loaded_reversal_travel_mm"]
                pairs.append(
                    dict(
                        target=target,
                        measured_reversal_mm=travel,
                        predicted_reversal_mm=pred,
                        measured_minus_model_mm=travel - pred,
                        combined_position_bound_mm=a["tu"] + bp["tu"],
                    )
                )
        if incomplete:
            flags.add("incomplete program")
        results.append(dict(specimen=sid, cycles=cycles, reversal_pairs=pairs))
    return dict(
        status="review_required" if flags else "measured_program_complete",
        rows=len(rows),
        flags=sorted(flags),
        specimens=results,
    )


def assess_cage(rows):
    if not rows:
        return dict(status="awaiting_measurements", rows=0, trials=[])
    seen = set()
    groups = defaultdict(dict)
    quality = defaultdict(set)
    for r in rows:
        group = tuple(r[k] for k in ("cage_id", "trial_id"))
        if not all((*group, r["print_lot"], r["calibration_id"])):
            raise ValueError("Cage identifiers and calibration are required")
        quality[group].add((r["print_lot"], r["calibration_id"]))
        z = number(r, "station_mm")
        kind = r["observation"]
        feat = r["feature"]
        if (
            z not in (-12, 12)
            or kind not in CAGE_RULES
            or feat not in CAGE_RULES[kind][1]
        ):
            raise ValueError("Unknown station, observation or feature")
        key = (int(z), kind, feat)
        if (group, key) in seen:
            raise ValueError(f"Duplicate cage feature {group}, {key}")
        seen.add((group, key))
        mode = CAGE_RULES[kind][0]
        v = number(r, "value", nonnegative=kind != "bent_gap_mm")
        # Gaps may be reported signed, and must exceed zero plus any declared additional allowance.
        u = number(
            r, "uncertainty", nonnegative=mode == "boolean", positive=mode != "boolean"
        )
        limit = None
        upper = None
        status = "recorded"
        if mode != "range" and r["upper_requirement"]:
            raise ValueError("Unexpected upper specification in this row")
        if mode == "boolean":
            if v not in (0, 1) or u != 0 or r["requirement"]:
                raise ValueError(
                    "Record direct access as 0 or 1, uncertainty 0, with no numeric requirement"
                )
            status = "meets_criterion" if v == 1 else "flagged"
        elif mode == "range":
            if (
                not r["requirement"]
                or not r["upper_requirement"]
                or not r["criterion_id"]
            ):
                status = "awaiting_predeclared_criterion"
            else:
                limit = number(r, "requirement", positive=True)
                upper = number(r, "upper_requirement", positive=True)
                if upper <= limit:
                    raise ValueError("Invalid torque interval")
                status = (
                    "meets_criterion"
                    if v - u >= limit and v + u <= upper
                    else "flagged"
                )
        elif mode in ("lower", "upper"):
            if not r["requirement"] or not r["criterion_id"]:
                status = "awaiting_predeclared_criterion"
            else:
                limit = number(
                    r,
                    "requirement",
                    nonnegative=kind == "bent_gap_mm",
                    positive=kind != "bent_gap_mm",
                )
                meets = (
                    v - u > limit
                    if kind == "bent_gap_mm"
                    else (v - u >= limit if mode == "lower" else v + u <= limit)
                )
                status = "meets_criterion" if meets else "flagged"
        elif r["requirement"]:
            raise ValueError(
                "Mass is an observation; put a release criterion in its independent specification"
            )
        groups[group][key] = dict(
            station_mm=z,
            observation=kind,
            feature=feat,
            value=v,
            uncertainty=u,
            requirement=limit,
            upper_requirement=upper,
            criterion_id=r["criterion_id"],
            status=status,
        )
    if any(len(v) != 1 for v in quality.values()):
        raise ValueError("Mixed specimen or calibration metadata in a cage trial")
    expected = {
        (z, n, f)
        for z in (-12, 12)
        for n, (_, feats) in CAGE_RULES.items()
        for f in feats
    }
    summary = []
    for (sid, trial), obs in sorted(groups.items()):
        missing = sorted(expected - obs.keys())
        ready = not missing and all(
            r["status"] in ("meets_criterion", "recorded") for r in obs.values()
        )
        summary.append(
            dict(
                cage_id=sid,
                trial_id=trial,
                complete_within_declared_criteria=ready,
                missing=missing,
                observations=list(obs.values()),
            )
        )
    return dict(
        status="measured_program_complete"
        if all(r["complete_within_declared_criteria"] for r in summary)
        else "review_required",
        rows=len(rows),
        trials=summary,
    )


METRO = (
    "specimen",
    "print_lot",
    "build_orientation_id",
    "calibration_id",
    "feature",
    "measured_mm",
    "uncertainty_mm",
    "lower_limit_mm",
    "upper_limit_mm",
    "criterion_id",
)
DIMENSIONS = {
    "free_gauge_length": 5.4,
    "web_width": 1.5,
    "web_thickness": 3.0,
    "shaft_diameter": 0.60,
    "bore_waist_diameter": 0.64,
    "crown_radius": 1.0,
    "minimum_side_ligament": j.WEB_WIDTH / 2
    - brentq(lambda r: j.hole_radius(j.face_height(r)) - r, j.PIN, j.WEB_WIDTH / 2),
    "web_thrust_sphere_radius": 1.50,
    "metal_thrust_sphere_radius": 1.52,
}


def assess_metrology(rows):
    if not rows:
        return dict(status="awaiting_measurements", rows=0, specimens=[])
    groups = defaultdict(dict)
    setups = defaultdict(set)
    for r in rows:
        sid = r["specimen"]
        feat = r["feature"]
        if (
            not all(r[k] for k in METRO[:4])
            or feat not in DIMENSIONS
            or feat in groups[sid]
        ):
            raise ValueError(
                "Missing identifier, duplicate or unknown dimensional observation"
            )
        setups[sid].add(tuple(r[k] for k in METRO[1:4]))
        v = number(r, "measured_mm", positive=True)
        u = number(r, "uncertainty_mm", positive=True)
        if bool(r["lower_limit_mm"]) != bool(r["upper_limit_mm"]):
            raise ValueError("Declare both dimensional limits")
        low = high = None
        status = "awaiting_predeclared_criterion"
        if r["lower_limit_mm"]:
            low = number(r, "lower_limit_mm", nonnegative=True)
            high = number(r, "upper_limit_mm", positive=True)
            if high <= low or not r["criterion_id"]:
                raise ValueError(
                    "A valid dimensional specification and ID are required"
                )
            status = "meets_criterion" if v - u >= low and v + u <= high else "flagged"
        groups[sid][feat] = dict(
            nominal_mm=float(DIMENSIONS[feat]),
            measured_mm=v,
            uncertainty_mm=u,
            deviation_mm=v - DIMENSIONS[feat],
            lower_limit_mm=low,
            upper_limit_mm=high,
            status=status,
        )
    if any(len(v) != 1 for v in setups.values()):
        raise ValueError("Mixed setup metadata within one dimensional record")
    out = []
    good = True
    for sid, values in sorted(groups.items()):
        missing = sorted(set(DIMENSIONS) - values.keys())
        good &= not missing and all(
            v["status"] == "meets_criterion" for v in values.values()
        )
        out.append(dict(specimen=sid, missing=missing, features=values))
    return dict(
        status="measured_program_complete" if good else "review_required",
        rows=len(rows),
        specimens=out,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coupon", type=Path, required=True)
    parser.add_argument("--cage", type=Path, required=True)
    parser.add_argument("--metrology", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=HERE / "results/coupon_fine.json")
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    d = dict(
        metrology=assess_metrology(read_csv(a.metrology, METRO)),
        coupon=assess_coupon(
            read_csv(a.coupon, COUPON), json.loads(a.model.read_text())
        ),
        cage=assess_cage(read_csv(a.cage, CAGE)),
        interpretation="Scores refer to the supplied specimens and predeclared uncertainties. Calibrated stiffness, pull-through loss, fatigue life and prototype release require separate evidence.",
    )
    a.out.write_text(json.dumps(d, indent=2) + "\n")
    print(*(d[k]["status"] for k in ("metrology", "coupon", "cage")))


if __name__ == "__main__":
    main()
