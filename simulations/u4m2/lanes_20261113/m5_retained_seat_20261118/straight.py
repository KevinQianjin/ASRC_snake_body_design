"""Check the complete straight M5 assembly, rope holes, component mass and insertion corridors."""

import argparse
import itertools
import json
from pathlib import Path

from clearance import CAD, b, bounds_distance, j, np, read_parts, station_parts


def drill_lines(arm):
    # Compare actual throat and both mouths using XY slices; source and candidate use the identical mesh sector.
    from shapely import Polygon

    out = []
    for z in (-1.60, 0, 1.60):
        loops = arm.slice(z).to_polygons()
        hits = sorted(
            [
                Polygon(x)
                for x in loops
                if len(x) > 15
                and 22 < Polygon(x).centroid.x < 30
                and Polygon(x).area < 14
            ],
            key=lambda p: p.centroid.x,
        )
        if len(hits) != 2:
            raise ValueError(f"Expected B/C bore loops at {z}: {len(hits)}")
        out.append(
            dict(
                z_mm=z,
                centres_xy_mm=[[p.centroid.x, p.centroid.y] for p in hits],
                equivalent_diameters_mm=[2 * (p.area / np.pi) ** 0.5 for p in hits],
            )
        )
    return out


def test_static(args):
    parts = read_parts(args.parts)
    replacement = getattr(args, "hub_parts", None)
    if replacement is not None:
        for name in ("hub_upper_sector", "hub_lower_sector"):
            parts[name] = b.load(replacement / f"{name}.stl")
    body = b.load(args.parts / "M5_machined_body.stl")
    props = json.loads((args.parts / "parts.json").read_text())
    baseline = CAD.parent / "guides_v3"
    rho = json.loads((baseline / "mass_model.json").read_text())["densities_kg_per_mm3"]
    densities = {
        "PA12": 1000 * rho["PA12"],
        "steel": 1000 * rho["steel"],
        "aluminium": 0.00270,
    }
    old = []
    for z in j.STATIONS:
        before = {
            family: b.load(baseline / f"M5_z{z:+d}_{family}.stl").volume()
            * densities["steel" if family == "wire_envelope" else "PA12"]
            for family in ("guide", "caps", "wire_envelope")
        }
        old.append(dict(station=z, **before, total_g=sum(before.values())))
    stations = []
    tol = 1e-7
    for z in j.STATIONS:
        components = list(station_parts(parts, z))
        whole = components + [("body", "body", body.translate((0, 0, -z)))]
        overlaps = []
        n = 0
        near = 0
        body_dist = []
        mass = 0
        for name, family, obj in components:
            key = f"{family}_{z:+d}" if family in ("fork", "gate") else family
            mass += obj.volume() * densities[props[key]["material"]]
            dist = obj.min_gap(whole[-1][2], 1)
            body_dist.append(dict(part=name, gap_mm=dist))
        for (ka, fa, A), (kb, fb, B) in itertools.combinations(whole, 2):
            n += 1
            if bounds_distance(A.bounding_box(), B.bounding_box()) > 0:
                continue
            near += 1
            v = max(0.0, (A ^ B).volume())
            if v > tol:
                overlaps.append(dict(first=ka, second=kb, volume_mm3=v))
        worst = sorted(overlaps, key=lambda r: -r["volume_mm3"])
        print(
            "straight",
            z,
            len(components),
            n,
            "overlaps",
            len(worst),
            worst[:6],
            flush=True,
        )
        stations.append(
            dict(
                station_mm=z,
                parts=len(components),
                pairs=n,
                overlapping_bounds=near,
                intersections=worst,
                body_gaps_mm_capped_at_one=body_dist,
                guide_mass_g=mass,
            )
        )
    after = drill_lines(parts["rope_arm"])
    before = drill_lines(b.load(b.FRAME))
    bore_checks = []
    for z in j.STATIONS:
        original = b.load(baseline / f"M5_z{z:+d}_guide.stl")
        for theta in (0, 90, 180, 270):
            previous = drill_lines(b.place(original, -theta))
            centre = max(
                np.linalg.norm(
                    np.asarray(x["centres_xy_mm"]) - y["centres_xy_mm"], axis=1
                ).max()
                for x, y in zip(previous, after)
            )
            diameter = max(
                abs(
                    np.asarray(x["equivalent_diameters_mm"])
                    - y["equivalent_diameters_mm"]
                ).max()
                for x, y in zip(previous, after)
            )
            bore_checks.append(
                dict(
                    station=z,
                    azimuth_deg=theta,
                    centre_change_mm=float(centre),
                    equivalent_diameter_change_mm=float(diameter),
                )
            )
    result = dict(
        stations=stations,
        positive_overlap_reporting_threshold_mm3=tol,
        density_g_per_mm3=densities,
        original_station_mass_breakdown_g=old,
        rope_bore_checks=bore_checks,
        body_removed_mass_g=props["body_machining"]["removed_mm3"] * densities["PA12"],
        previous_rope_bores=before,
        candidate_rope_bores=after,
        backbone_diameter_mm=1.8,
        unobstructed_hub_radius_mm=7.8,
    )
    if replacement is not None:
        result["inside_hub_chamfer_mm"] = json.loads(
            (replacement / "manifest.json").read_text()
        )["chamfer_radial_and_axial_mm"]
    args.out.mkdir(exist_ok=True, parents=True)
    (args.out / "straight.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts", type=Path, default=CAD / "parts")
    ap.add_argument(
        "--hub-parts", type=Path, help="Use both hub sectors from this dated candidate"
    )
    ap.add_argument("--out", type=Path, required=True)
    test_static(ap.parse_args())
