"""Reduce synchronized transverse optical observations at the two metal end faces and coupon pivot."""

import argparse
from itertools import product
import json
from pathlib import Path

import numpy as np

from inputs import BENCH, HERE
from bench_inputs import load_targets, program
from score_bench import COUPON, assess_coupon, number, read_csv, vector

FIELDS = (
    "specimen",
    "print_lot",
    "calibration_id",
    "fixture_id",
    "trace_id",
    "frame_id",
    "direction",
    "phase",
    "elapsed_s",
    "coupon_datum_s_mm",
    "coupon_datum_p_mm",
    "head_datum_s_mm",
    "head_datum_p_mm",
    "head_face_n_mm",
    "cap_datum_s_mm",
    "cap_datum_p_mm",
    "cap_face_n_mm",
    "coupon_sp_bound_mm",
    "head_sp_bound_mm",
    "cap_sp_bound_mm",
    "axial_coordinate_bound_mm",
)


def observe(r):
    coupon = vector(r, FIELDS[9:11])
    head = vector(r, FIELDS[11:13])
    cap = vector(r, FIELDS[14:16])
    upper = number(r, "head_face_n_mm")
    lower = number(r, "cap_face_n_mm")
    u = number(r, "axial_coordinate_bound_mm", positive=True)
    if min(upper, -lower) <= 2 * u:
        raise ValueError(
            "Witness face intervals must bracket the pivot plane including axial uncertainty"
        )
    mix = -lower / (upper - lower)
    chord = (1 - mix) * cap + mix * head
    # Perturb both end planes and the registered zero plane within the stated absolute bound.
    weights = [
        (z - lo) / (hi - lo)
        for z, lo, hi in product(
            (-u, u), (lower - u, lower + u), (upper - u, upper + u)
        )
    ]
    uh = number(r, "head_sp_bound_mm", positive=True)
    uc = number(r, "cap_sp_bound_mm", positive=True)
    raw_bound = number(r, "coupon_sp_bound_mm", positive=True)
    chord_bound = max(
        (1 - w) * uc + w * uh + abs(w - mix) * np.linalg.norm(head - cap)
        for w in weights
    )
    return dict(
        raw=coupon,
        chord=chord,
        relative=coupon - chord,
        raw_bound=raw_bound,
        chord_bound=chord_bound,
        relative_bound=raw_bound + chord_bound,
        head_weight=mix,
        chord_slope_sp=(head - cap) / (upper - lower),
    )


def difference(a, b):
    out = {}
    for key in ("raw", "chord", "relative"):
        delta = b[key] - a[key]
        bound = float(a[key + "_bound"] + b[key + "_bound"])
        val = float(np.linalg.norm(delta))
        out[key] = dict(
            delta_sp_mm=delta.tolist(),
            magnitude_mm=val,
            worst_case_bound_mm=bound,
            resolved=bool(val > bound),
        )
    return out


def assess(witness, coupon):
    cmdrows = [r for r in program(load_targets()) if r["target"] == "P3"]
    phases = {(r["direction"], r["phase"]): r["order"] for r in cmdrows}
    paired = [r for r in coupon if r["target"] == "P3"]
    checks = assess_coupon(paired, {"peak_pairs": []})
    bench = {(r["specimen"], r["direction"], r["phase"]): r for r in paired}
    quality = {
        (s["specimen"], c["direction"]): c
        for s in checks["specimens"]
        for c in s["cycles"]
        if c["target"] == "P3"
    }
    if not witness and not paired:
        return dict(
            status="awaiting_measurements",
            witness_rows=0,
            matched_coupon_rows=0,
            specimens=[],
        )
    groups = {}
    settings = {}
    frames = set()
    last = {}
    matched = set()
    for r in witness:
        sid = r["specimen"]
        dr, ph = r["direction"], r["phase"]
        ids = tuple(r[k] for k in FIELDS[:6])
        if not all(ids) or (dr, ph) not in phases:
            raise ValueError("Missing registration or unknown P3 direction or phase")
        setup = ids[1:4]
        if settings.setdefault(sid, setup) != setup:
            raise ValueError(
                "Mixed print lot, calibration or fixture within a specimen series"
            )
        obs = groups.setdefault(sid, {})
        frame = (sid, r["trace_id"], r["frame_id"])
        if frame in frames or (dr, ph) in obs:
            raise ValueError("Duplicate witness frame or phase")
        frames.add(frame)
        time = number(r, "elapsed_s", nonnegative=True)
        order = phases[dr, ph]
        prev = last.get((sid, dr))
        if prev and (time <= prev[0] or order <= prev[1]):
            raise ValueError("Non-increasing phase or clock within the signed cycle")
        last[sid, dr] = (time, order)
        b = bench.get((sid, dr, ph))
        if b:
            if (b["print_lot"], b["calibration_id"]) != setup[:2] or abs(
                time - number(b, "elapsed_s")
            ) > 1e-6:
                raise ValueError(
                    "Witness and force/pose rows must share identifiers and the same hardware trigger time"
                )
            matched.add((sid, dr, ph))
        obs[dr, ph] = observe(r)
    result = []
    for sid in sorted(set(groups) | {r["specimen"] for r in paired}):
        obs = groups.get(sid, {})
        missing = [list(k) for k in phases if k not in obs]
        unpaired = [list(k) for k in phases if (sid, *k) not in matched]
        faults = []
        cycles = {}
        for dr in ("source", "reverse"):
            control = quality.get((sid, dr), {})
            for field in (
                "force_or_orientation_outside_declared_uncertainty",
                "visible_damage_phases",
            ):
                faults.extend(
                    [
                        dict(direction=dr, phase=p, issue=field)
                        for p in control.get(field, [])
                    ]
                )
            if (dr, "pre_ref") in obs and (dr, "post_ref") in obs:
                diff = difference(obs[dr, "pre_ref"], obs[dr, "post_ref"])
                cycles[dr] = diff
                if diff["relative"]["resolved"]:
                    faults.append(
                        dict(
                            direction=dr,
                            issue="resolved matched-reference transverse shift",
                        )
                    )
        peaks = None
        if ("source", "peak") in obs and ("reverse", "peak") in obs:
            peaks = difference(obs["source", "peak"], obs["reverse", "peak"])
        result.append(
            dict(
                specimen=sid,
                missing_witness_phases=missing,
                missing_matched_force_pose=unpaired,
                paired_peak_reversal=peaks,
                matched_positive_1N_reference_shifts=cycles,
                review_items=faults,
                complete_synchronized_P3=not (missing or unpaired),
            )
        )
    status = (
        "review_required"
        if any(s["review_items"] or not s["complete_synchronized_P3"] for s in result)
        else "synchronized_P3_observed"
    )
    return dict(
        status=status,
        witness_rows=len(witness),
        matched_coupon_rows=len(matched),
        specimens=result,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--witness", type=Path, default=HERE / "witness_measurements.csv")
    p.add_argument("--coupon", type=Path, default=BENCH / "coupon_measurements.csv")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = assess(read_csv(a.witness, FIELDS), read_csv(a.coupon, COUPON))
    a.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(report["status"])
