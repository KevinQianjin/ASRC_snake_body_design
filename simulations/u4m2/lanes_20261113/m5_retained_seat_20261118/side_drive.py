"""Check swept space for a side-entry hub driver from first thread engagement to seating."""

import argparse
import itertools
import json
from pathlib import Path

import fcl
import manifold3d as md
import numpy as np

from assembly import ZERO, rz, sequence
from clearance import CAD, b, bounds_distance, collider, j, read_parts

# Each tuple gives housing diameter, total height above the screw head, and shaft diameter.
DRIVERS = {
    "wide": (2.50, 1.55, 1.10),
    "slim": (1.70, 1.55, 0.90),
    "low": (2.50, 1.15, 0.80),
}
SCREW_TOP = 1.88
THREAD_TRAVEL = 1.60
SIDE_REACH = 55.0


def sweeps(diameter, height, shaft_diameter):
    # Circumscription encloses the true round tool between polygon vertices.
    factor = 1 / np.cos(np.pi / 48)
    shaft_radius = shaft_diameter / 2
    z = height - shaft_radius
    pieces = [
        b.cyl(0.45 * factor, 0.002, 0.48, 48),
        b.cyl(diameter * factor / 2, 0.35, height, 48),
        b.cyl(shaft_radius * factor, 0, SIDE_REACH, 48)
        .rotate((0, 90, 0))
        .translate((0, 0, z)),
    ]
    out = []
    for phase, start_height, travel in [
        ("side entry", THREAD_TRAVEL, (SIDE_REACH, 0, 0)),
        ("tightening stroke", 0, (0, 0, THREAD_TRAVEL)),
    ]:
        # The convex hull of a convex primitive and its translation is its exact swept volume.
        hull = md.Manifold.batch_boolean(
            [md.Manifold.batch_hull([x, x.translate(travel)]) for x in pieces],
            md.OpType.Add,
        )
        out.append((phase, hull.translate((0, 0, start_height))))
    return out


def inspect_screw(part, hardware, probes):
    position = part.centre + [0, 0, SCREW_TOP]
    tested = []
    for delta in range(-180, 180, 5):
        angle = part.angle + delta
        rot = rz(angle)
        checks = []
        for phase, shape, query, corners in probes:
            query.setRotation(rot)
            query.setTranslation(position)
            world = corners @ rot.T + position
            bounds = np.r_[world.min(axis=0), world.max(axis=0)]
            gap = float("inf")
            closest = None
            for name, solid, body, box in hardware:
                if bounds_distance(bounds, box) >= gap:
                    continue
                distance = fcl.distance(
                    query, body, fcl.DistanceRequest(), fcl.DistanceResult()
                )
                if distance < gap:
                    gap, closest = max(0.0, float(distance)), name
                if gap <= 0:
                    break
            checks.append((phase, gap, closest))
        tested.append((min(v[1] for v in checks), delta, checks))
    ordered = sorted(tested, key=lambda x: (-x[0], abs(x[1]), x[1]))
    target = next((row for row in ordered if row[0] > 1e-6), None)
    # With no positive gap, report a representative radial direction and its actual material intersections.
    options = (
        [row for row in ordered if row[0] > 1e-6]
        if target
        else [next(row for row in tested if row[1] == 0)]
    )
    for best, delta, checks in options:
        rot = rz(part.angle + delta)
        verified = []
        for (phase, shape, _, _), (_, dist, close) in zip(probes, checks):
            placed = shape.transform(np.column_stack((rot, position)))
            intersections = []
            for name, solid, _, box in hardware:
                if bounds_distance(placed.bounding_box(), box) > 0:
                    continue
                volume = max(0.0, (placed ^ solid).volume())
                if volume > 1e-7:
                    intersections.append(dict(obstacle=name, intersection_mm3=volume))
            verified.append(
                dict(
                    phase=phase,
                    surface_gap_mm=dist,
                    closest=close,
                    intersections=intersections,
                )
            )
        clear = best > 1e-6 and all(not r["intersections"] for r in verified)
        if clear or not target:
            break
    return dict(
        screw=part.label,
        positive_surface_directions=sum(row[0] > 1e-6 for row in tested),
        selected_offset_deg=delta,
        selected_azimuth_deg=(part.angle + delta) % 360,
        full_sweep_clear=clear,
        minimum_gap_mm=best,
        selected_sweeps=verified,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    parts = read_parts(CAD / "parts")
    hardware = []

    def install(label, solid):
        hardware.append(
            (label, solid, fcl.CollisionObject(collider(solid)), solid.bounding_box())
        )

    install("M5 body", b.load(CAD / "parts/M5_machined_body.stl"))
    tools = {}
    for name, dims in DRIVERS.items():
        meshes = []
        for phase, hull in sweeps(*dims):
            box = np.array(hull.bounding_box()).reshape(2, 3)
            corners = np.array(list(itertools.product(*box.T)))
            meshes.append((phase, hull, fcl.CollisionObject(collider(hull)), corners))
        tools[name] = meshes
    rows = []
    for station in j.STATIONS:
        for part in sequence(station):
            if part.family == "lap_screw":
                for name, probes in tools.items():
                    row = inspect_screw(part, hardware, probes)
                    rows.append(dict(station=station, driver=name, **row))
                    print(
                        station,
                        part.label,
                        name,
                        row["full_sweep_clear"],
                        f"{row['minimum_gap_mm']:.5f}",
                        flush=True,
                    )
            rot, tr = part.pose(ZERO)
            install(
                f"{part.label}@{station}",
                parts[part.name].transform(np.column_stack((rot, tr))),
            )
    args.out.mkdir(exist_ok=True, parents=True)
    result = dict(
        screw_face_z_in_station_mm=SCREW_TOP,
        engagement_to_seating_mm=THREAD_TRAVEL,
        side_shank_length_mm=SIDE_REACH,
        side_entry_travel_mm=SIDE_REACH,
        shaft_tip_radius_mm=0.45,
        tip_face_offset_mm=0.002,
        yaw_step_deg=5,
        directions_per_screw_and_driver=72,
        driver_dimensions_mm={
            k: dict(
                housing_diameter=a, height_over_screw_head=b_, side_shank_diameter=c
            )
            for k, (a, b_, c) in DRIVERS.items()
        },
        scope="Axisymmetric tool exterior and fixed housing attitude. The internal drive, blade/slot engagement, hand, fixture, strength and torque are untested.",
        rows=rows,
    )
    (args.out / "side_drive.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
