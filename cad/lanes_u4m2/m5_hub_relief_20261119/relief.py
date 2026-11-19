"""Candidate edge breaks on the inside rim of the retained hub. Dimensions in mm."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "retained_seat_20261118"
sys.path.insert(0, str(SOURCE))
import build as b
import joint as j

FAMILIES = ("hub_upper_sector", "hub_lower_sector")
SIZES = (0.0, 0.15, 0.30, 0.45)


def sectors(size):
    src = {name: b.load(SOURCE / f"parts/{name}.stl") for name in FAMILIES}
    if not 0 <= size <= 0.45:
        raise ValueError("This study covers 0 to 0.45 mm")
    if size == 0:
        return src
    half = j.PLATE_HALF
    rad = 7.80
    tool = b.axial_profile(
        [-1.72, -half, -half + size, half - size, half, 1.72],
        [rad + size, rad + size, rad, rad, rad + size, rad + size],
    )
    return {name: o - tool for name, o in src.items()}


def build(size, out):
    original = sectors(0)
    parts = sectors(size)
    out.mkdir(exist_ok=True, parents=True)
    observations = {}
    for name, part in parts.items():
        before = original[name]
        q = b.export(part.simplify(1e-6), out / f"{name}.stl")
        after = b.load(out / f"{name}.stl")
        added = max(0.0, (after - before).volume())
        removed = before - after
        if added > 1e-4:
            raise ValueError("Export protrudes outside original sector")
        # The authoritative sockets run to +/-0.595. All 16 upper/lower fork and arm holdings remain unchanged in this slab.
        core = b.box((-15, -15, -0.596), (15, 15, 0.596))
        core_loss = (removed ^ core).volume()
        if abs(core_loss) > 1e-4:
            raise ValueError("Socket bearing slab has changed")
        # Use analytic lower bounds for screw clearance; validate against the fresh cut surface, not boolean float specks.
        # Entire cut stays within radius 7.8+size, including each sector's lap edges.
        bounds = {
            "lap": 9.6 - 0.421 - (7.8 + size),
            "arm": j.HUB_FASTENER_X - 0.54 - (7.8 + size),
            "fork": float(np.hypot(j.HUB_FASTENER_X, j.FORK_Y) - 0.54 - (7.8 + size)),
        }
        observations[name] = q | dict(
            source_sha256=hashlib.sha256(
                (SOURCE / f"parts/{name}.stl").read_bytes()
            ).hexdigest(),
            outside_source_mm3=added,
            removed_mm3=before.volume() - after.volume(),
            socket_core_volume_loss_mm3=max(0.0, core_loss),
            lower_bounds_to_thread_envelopes_mm=bounds,
        )
    data = dict(
        chamfer_radial_and_axial_mm=size,
        base_inner_radius_mm=7.80,
        remaining_unrelieved_axial_height_mm=3.2 - 2 * size,
        distance_axial_from_chamfer_start_to_socket_face_mm=1.6 - size - 0.595,
        parts=observations,
        manufacturing_status="Geometric option only. Strength, manufacturing tolerance and resulting module equilibrium require validation.",
    )
    (out / "manifest.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=float, choices=SIZES[1:], required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(build(a.size, a.out))
