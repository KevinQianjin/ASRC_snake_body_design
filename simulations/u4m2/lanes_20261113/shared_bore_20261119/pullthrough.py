"""Compare paired steady-sliding load-cell records with the geometric wrap at a specified shared bore."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

COLUMNS = (
    "specimen",
    "rope_lot",
    "calibration_id",
    "hold",
    "ray",
    "cycle",
    "direction",
    "elapsed_s",
    "speed_mm_s",
    "steady_sliding",
    "M5_tension_N",
    "M6_tension_N",
    "M5_uncertainty_N",
    "M6_uncertainty_N",
    "wear",
)
WRAP_COLUMNS = ("measured_wrap_deg", "wrap_uncertainty_deg")
DIRECTIONS = ("pull_M5", "pull_M6")


def wrap_record(row, reference_rad):
    """Select the observed wrap if both its angle and uncertainty are available."""
    angle, uncertainty = (row.get(k, "").strip() for k in WRAP_COLUMNS)
    if not angle and not uncertainty:
        return dict(
            wrap_source="simulated",
            wrap_rad=reference_rad,
            wrap_bounds_rad=[reference_rad, reference_rad],
        )
    if not angle or not uncertainty:
        raise ValueError("Supply both the measured absolute wrap and its uncertainty")
    theta, bound = np.radians([float(angle), float(uncertainty)])
    if not np.isfinite([theta, bound]).all() or theta < 0 or bound <= 0:
        raise ValueError("Measured wrap must be nonnegative with positive uncertainty")
    return dict(
        wrap_source="measured",
        wrap_rad=theta,
        wrap_bounds_rad=[max(0.0, theta - bound), theta + bound],
    )


def score(rows, records):
    if not rows:
        return dict(status="awaiting_measurements", samples=0, observations=[])
    lookup = {(r["hold"], r["ray"]): r for r in records}
    groups = {}
    seen = set()
    setup = {}
    for r in rows:
        tags = [
            r[k].strip()
            for k in ("specimen", "rope_lot", "calibration_id", "cycle", "direction")
        ]
        if not all(tags) or tags[-1] not in DIRECTIONS:
            raise ValueError("Missing ID or unknown pull direction")
        sid, lot, cal, cycle, d = tags
        key = (int(r["hold"]), r["ray"])
        if key not in lookup:
            raise ValueError(f"No simulated geometry reference for hold and ray {key}")
        if r["steady_sliding"] not in ("yes", "no") or r["wear"] not in ("yes", "no"):
            raise ValueError("steady_sliding and wear use yes or no")
        t, v, a, b, ua, ub = map(
            float,
            [
                r[k]
                for k in (
                    "elapsed_s",
                    "speed_mm_s",
                    "M5_tension_N",
                    "M6_tension_N",
                    "M5_uncertainty_N",
                    "M6_uncertainty_N",
                )
            ],
        )
        if (
            not np.isfinite([t, v, a, b, ua, ub]).all()
            or t < 0
            or min(a, b, ua, ub) <= 0
            or a <= ua
            or b <= ub
        ):
            raise ValueError(
                "Positive tensions above their reported uncertainty and valid time are required"
            )
        if r["steady_sliding"] == "yes" and (v <= 0 if d == "pull_M6" else v >= 0):
            raise ValueError("Signed speed and declared pulling end disagree")
        group = (sid, *key, cycle, d)
        if (group, t) in seen:
            raise ValueError("Duplicate timestamp in one direction and cycle")
        seen.add((group, t))
        setup.setdefault(sid, set()).add((lot, cal))
        obs = groups.setdefault(group, [])
        if obs and obs[-1]["elapsed_s"] >= t:
            raise ValueError("Timestamps must increase within each trace")
        hi, lo, uh, ul = (b, a, ub, ua) if d == "pull_M6" else (a, b, ua, ub)
        datum = dict(
            elapsed_s=t,
            speed_mm_s=v,
            steady_sliding=r["steady_sliding"],
            wear=r["wear"],
            high_minus_low_N=hi - lo,
            **wrap_record(r, lookup[key]["absolute_wrap_rad"]),
        )
        if r["steady_sliding"] == "yes":
            datum.update(
                tension_ratio=hi / lo,
                ratio_bounds=[(hi - uh) / (lo + ul), (hi + uh) / (lo - ul)],
                tension_order_resolved=bool(hi - uh > lo + ul),
                high_tension_inconsistent=bool(hi + uh < lo - ul),
            )
            angular_bounds = datum["wrap_bounds_rad"]
            if angular_bounds[0] > 1e-5:
                # A reversed tension order can give negative logs. Bound all four corners.
                corners = np.divide.outer(np.log(datum["ratio_bounds"]), angular_bounds)
                datum.update(
                    effective_mu=float(np.log(hi / lo) / datum["wrap_rad"]),
                    effective_mu_bounds=[float(corners.min()), float(corners.max())],
                )
        obs.append(datum)
    if any(len(config) != 1 for config in setup.values()):
        raise ValueError("Inconsistent lot or calibration ID within one specimen")
    out = []
    incomplete = False
    flags = set()
    for sid, hold, ray, cy in sorted({g[:4] for g in groups}):
        present = {
            d: groups[sid, hold, ray, cy, d]
            for d in DIRECTIONS
            if (sid, hold, ray, cy, d) in groups
        }
        if any(
            not any(r["steady_sliding"] == "yes" for r in present.get(d, []))
            for d in DIRECTIONS
        ):
            incomplete = True
        for obs in present.values():
            if any(
                r["steady_sliding"] == "yes" and r["wrap_bounds_rad"][0] <= 1e-5
                for r in obs
            ):
                flags.add("wrap too small or uncertain to estimate friction")
            if any(r["wear"] == "yes" for r in obs):
                flags.add("wear observed")
            if any(r.get("high_tension_inconsistent", False) for r in obs):
                flags.add("tension order contradicts pull direction beyond uncertainty")
            if any(r.get("tension_order_resolved") is False for r in obs):
                flags.add(
                    "tension difference unresolved within measurement uncertainty"
                )
        out.append(
            dict(
                specimen=sid,
                hold=hold,
                ray=ray,
                cycle=cy,
                wrap_rad_reference=lookup[hold, ray]["absolute_wrap_rad"],
                directions=present,
            )
        )
    return dict(
        status="review_required"
        if flags or incomplete
        else "paired_sliding_data_recorded",
        samples=len(rows),
        missing_steady_direction=incomplete,
        flags=sorted(flags),
        observations=out,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--geometry", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    with a.input.open(newline="") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames not in (list(COLUMNS), list(COLUMNS + WRAP_COLUMNS)):
            raise ValueError("Use the supplied columns and units")
        rows = list(rd)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError("Invalid column count")
    d = score(rows, json.loads(a.geometry.read_text())["records"])
    a.out.write_text(json.dumps(d, indent=2) + "\n")
    print(d["status"])
