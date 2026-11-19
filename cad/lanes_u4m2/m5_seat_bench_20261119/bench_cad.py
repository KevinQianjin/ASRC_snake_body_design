"""Generate the M5 single-web coupon and the two independent fixture carriages (mm)."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
RETAINED = HERE.parent / "retained_seat_20261118"
sys.path.insert(0, str(RETAINED))
import build as b
import joint as j

FREE_HALF = 2.7
AZIMUTH = 67.5
STATION = 12


def to_bench(obj, azimuth=AZIMUTH, station=STATION):
    turn = Rotation.from_euler("z", azimuth, degrees=True).as_matrix()
    basis = turn @ j.web_axes(station)
    origin = turn @ np.array([j.R_PIVOT, 0.0, station])
    return obj.transform(np.column_stack((basis.T, -basis.T @ origin)))


def on_pin_frame(obj):
    # The part library stores the pin at the 0-degree pivot in station coordinates.
    basis = j.web_axes(STATION)
    return obj.transform(np.column_stack((basis.T, -basis.T @ [j.R_PIVOT, 0, 0])))


def hole(radius, start, end, x, y):
    return b.cyl(radius, start, end).translate((x, y, 0))


def coupon(body):
    web = to_bench(body)
    window = b.box((-FREE_HALF - 0.20, -0.95, -1.52), (FREE_HALF + 0.20, 0.95, 1.52))
    gauge = web ^ window
    tab = (
        b.md.CrossSection(
            [
                [
                    (FREE_HALF, -0.746),
                    (3.52, -1.60),
                    (4.35, -2.35),
                    (9.35, -2.35),
                    (9.35, 2.35),
                    (4.35, 2.35),
                    (3.52, 1.60),
                    (FREE_HALF, 0.746),
                ]
            ]
        )
        .extrude(3.0)
        .translate((0, 0, -1.5))
    )
    tab -= hole(1.04, -2, 2, 6.7, 0)
    specimen = gauge + tab + tab.mirror((1, 0, 0))
    free = b.box((-FREE_HALF, -1.85, -1.7), (FREE_HALF, 1.85, 1.7))
    central = specimen ^ free
    actual = web ^ free
    return specimen, dict(
        source_free_gauge_mm3=actual.volume(),
        added_free_gauge_mm3=max(0.0, (central - actual).volume()),
        lost_free_gauge_mm3=max(0.0, (actual - central).volume()),
    )


def carrier_parts(corner_relief=True):
    floor = b.box((FREE_HALF, -5.9, -5.5), (10.7, 5.9, -1.5))
    floor -= hole(1.01, -4.75, -1.49, 6.7, 0)
    lid = b.box((FREE_HALF, -5.7, 1.5), (10.7, 5.7, 4.0))
    # Relieve the inside corner on the pin-carriage side without cutting the tab footprint.
    corner = (
        b.md.CrossSection([[(2.65, -6.0), (4.25, -6.0), (2.65, -1.90)]])
        .extrude(11)
        .translate((0, 0, -6))
    )
    if corner_relief:
        floor -= corner
        lid -= corner
    for y in (-4.05, 4.05):
        bore = hole(1.10, -6, 5, 6.7, y)
        floor -= bore
        lid -= bore
    tie = b.box((-10.7, 5.5, -5.5), (10.7, 12.0, -1.5))
    for x in (-6.7, 6.7):
        tie -= hole(1.60, -6, 0, x, 8.9)
    base = floor + floor.mirror((1, 0, 0)) + tie
    return base, lid


def pin_carriage(pilot_radius=0.75):
    # The positive-n face seats the head; the negative-n face seats the production cap.
    positive = b.box((-1.40, -7.95, 2.12), (1.40, 1.35, j.CHEEK))
    negative = b.box((-1.40, -7.95, -j.GATE_TOP), (1.40, 1.35, -2.12))
    hole_tool = b.cyl(pilot_radius, -6, 6)
    stem = b.box((-1.40, -9.0, -j.GATE_TOP), (1.40, -6.90, j.CHEEK))
    flange = b.box((-6.60, -17.50, -3.2), (6.60, -8.25, 3.2))
    for x in (-3.7, 3.7):
        flange -= hole(1.60, -4, 4, x, -13.0)
    return ((positive + negative) - hole_tool) + stem + flange


def build(directory):
    directory.mkdir(exist_ok=True, parents=True)
    source = RETAINED / "parts/M5_machined_body.stl"
    obj, inspection = coupon(b.load(source))
    base, lid = carrier_parts()
    objects = {
        "web_coupon": obj,
        "coupon_carrier": base,
        "tab_cover": lid,
        "pin_carriage": pin_carriage(),
    }
    meta = {
        k: b.export(v.simplify(1e-6), directory / f"{k}.stl")
        for k, v in objects.items()
    }
    exported = b.load(directory / "web_coupon.stl")
    actual_body = b.load(source)
    original = to_bench(actual_body)
    free = b.box((-FREE_HALF, -1.85, -1.7), (FREE_HALF, 1.85, 1.7))
    original = original ^ free
    delivered = exported ^ free
    inspection["stl_free_gauge_symmetric_difference_mm3"] = max(
        0.0, (original - delivered).volume()
    ) + max(0.0, (delivered - original).volume())
    rotation_checks = {}
    for az in (67.5, 157.5, 247.5, 337.5):
        comparison = to_bench(actual_body, az) ^ free
        rotation_checks[str(az)] = max(0.0, (comparison - delivered).volume()) + max(
            0.0, (delivered - comparison).volume()
        )
    inspection["registered_gauge_difference_by_source_rib_mm3"] = rotation_checks
    if max(rotation_checks.values()) > 1e-4:
        raise ValueError("Exported gauge differs from the actual M5 web")
    data = dict(
        source="retained_seat_20261118/parts/M5_machined_body.stl",
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        coordinate_order=[
            "along web (s)",
            "across web in its plane (p)",
            "normal to web (n)",
        ],
        source_station_mm=STATION,
        source_rib_deg=AZIMUTH,
        free_length_mm=2 * FREE_HALF,
        clamp_dowels_mm=[2, 6],
        tab_pin_bore_diameter_mm=2.08,
        clamp_fasteners="4 x M2 through screws and nuts",
        stage_mounting_through_holes_mm=3.2,
        inspection=inspection,
        parts=meta,
    )
    (directory / "manifest.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data["inspection"]), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    build(ap.parse_args().out)
