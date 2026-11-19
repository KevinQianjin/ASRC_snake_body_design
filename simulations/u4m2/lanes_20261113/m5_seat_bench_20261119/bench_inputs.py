"""Archived paired targets in the stationary pin frame. All lengths are in mm and forces in N."""

import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
LANES = HERE.parent
ROOT = HERE.parents[3]
PREVIOUS = LANES / "m5_retained_seat_20261118"
CAD = ROOT / "cad/lanes_u4m2/m5_seat_bench_20261119"
sys.path.insert(0, str(PREVIOUS))
sys.path.insert(0, str(CAD))
from contact import relative_rotation

TARGET_SITES = {
    "P1": ("bend67.5", 12, 157.5),
    "P2": ("bend67.5", 12, 67.5),
    "P3": ("146", 12, 67.5),
}
COMPONENTS = (
    "force_along_web_N",
    "force_perpendicular_inplane_N",
    "force_tangential_N",
)
REF_FORCE = 1.0


def write_csv(path, rows, fields=None):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=fields or list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def load_targets():
    source = json.loads(
        (LANES / "evening_20261118/envelope/envelope_pin_r0p30_0p025.json").read_text()
    )["cases"]
    targets = {}
    for name, (case, z, theta) in TARGET_SITES.items():
        land = next(
            v
            for v in source[case][-1]["lands"]
            if v["station_mm"] == z and v["rib_deg"] == theta
        )
        force = np.array([land[k] for k in COMPONENTS])
        R = relative_rotation(land)
        targets[name] = (land, force, R)
    return targets


def program(targets):
    commands = []
    for target, (_, force, R) in targets.items():
        reference = REF_FORCE / np.linalg.norm(force)
        quat = Rotation.from_matrix(R).as_quat()
        for name, sign in [("source", 1), ("reverse", -1)]:
            seq = [
                ("pre_ref", reference),
                ("zero_in", 0.0),
                ("load25", 0.25 * sign),
                ("load50", 0.50 * sign),
                ("load75", 0.75 * sign),
                ("peak", sign),
                ("unload75", 0.75 * sign),
                ("unload50", 0.50 * sign),
                ("unload25", 0.25 * sign),
                ("zero_out", 0.0),
                ("post_ref", reference),
            ]
            for order, (phase, factor) in enumerate(seq):
                row = dict(
                    target=target,
                    direction=name,
                    order=order,
                    phase=phase,
                    load_multiplier=float(factor),
                )
                row.update(
                    {
                        f"pin_on_web_{ax}_N": float(f * factor)
                        for ax, f in zip("spn", force)
                    }
                )
                row.update(
                    {f"coupon_to_pin_q{k}": float(v) for k, v in zip("xyzw", quat)}
                )
                commands.append(row)
    return commands
