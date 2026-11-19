"""Pinned rotating seat on the M5 +/-12 mm outer webs: effect of the pin hole.

Test 2, stage 1 of docs/500g_validation_plan.md. The 18 November rotating-seat
model ("point" variant) ties a 0.5 mm oblique rigid band of each mounting web to
an ideal spherical pivot. A physical seat that carries the along-web land force
in both directions needs a bidirectional stop; the candidate here is a pin
through the web along the rib normal. This script reuses the archived shell
solver unchanged and only replaces the land patch by a circular hole of radius
--hole-radius at the same land centre. The hole edge is a rigid ring (perfectly
fitting rigid pin) tied to the same ideal pivot with all three rotations free.
Unmounted ribs receive the same hole with a free rigid insert, as the archived
model gave them a free rigid band.

What this does not model: pin clearance, pin bending, contact/friction at the
hole edge, the bow-tie cavity walls, retention of the pin itself, material
non-linearity or strength. Units: N, mm.
"""

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from shapely.geometry import LineString, Point
from shapely import set_precision, union_all
import triangle

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "m5_large_rotation_20261118"
sys.path.insert(0, str(SRC))

import shell  # noqa: E402
import study  # noqa: E402

HOLE = dict(radius=None, centre_r=None, segments=64)


def rib_mesh_with_holes(area, profile):
    """Archived rib_mesh with the +/-0.25 mm land cut lines replaced by pin holes."""
    from shapely.geometry import Polygon

    line = profile.intersection(LineString([(15.0, 12.0), (24.0, 12.0)]))
    HOLE["centre_r"] = 0.5 * (line.bounds[0] + line.bounds[2])
    holes = [
        Point(HOLE["centre_r"], s).buffer(HOLE["radius"], quad_segs=HOLE["segments"] // 4)
        for s in shell.STATIONS
    ]
    profile = set_precision(profile.difference(union_all(holes)), 0.002)
    cuts = list(profile.interiors) + [profile.exterior]
    lines = [(15.0, s + a, 24.0, s + a) for s in shell.STATIONS for a in (-1.62, 1.62)]
    lines += [(0.0, z, 35.0, z) for z in (-45.0, 45.0)]
    for lo, hi in shell.RING_WINDOWS:
        lines += [(0.0, lo, 8.6, lo), (0.0, hi, 8.6, hi), (8.6, lo, 8.6, hi)]
    for z1, z2 in [(-48.0, -30.0), (30.0, 48.0)]:
        lines += [(3.3, z1, 3.3, z2)]
    for x0, z0, x1, z1 in lines:
        cuts.append(LineString([(x0, z0), (x1, z1)]).intersection(profile))
    graph = union_all(cuts, grid_size=0.002)
    vertices, segments, ids = [], set(), {}
    for g in graph.geoms:
        if g.geom_type not in ("LineString", "LinearRing"):
            continue
        link = []
        for point in g.coords:
            key = tuple(np.round(point, 7))
            if key not in ids:
                ids[key] = len(vertices)
                vertices.append(key)
            link.append(ids[key])
        segments.update(tuple(sorted((a, b))) for a, b in zip(link, link[1:]) if a != b)
    geometry = dict(vertices=np.array(vertices), segments=np.array(sorted(segments)))
    geometry["holes"] = np.array([Polygon(r).representative_point().coords[0] for r in profile.interiors])
    mesh = triangle.triangulate(geometry, f"pq26a{area}")
    return mesh["vertices"], mesh["triangles"]


_original_tags = shell.master_tags


def master_tags_with_holes(x):
    tags = _original_tags(x)
    r, z = x.T
    for s in shell.STATIONS:
        tags[tags == f"G{s:+}"] = ""
        on_edge = np.hypot(r - HOLE["centre_r"], z - s) <= HOLE["radius"] + 0.004
        tags[on_edge] = f"G{s:+}"
    return tags


def install(radius):
    HOLE["radius"] = radius
    shell.rib_mesh = rib_mesh_with_holes
    shell.master_tags = master_tags_with_holes


def local_strain(mesh, strains, centre_r, radius):
    """Peak face principal strain in triangles whose centre lies within `radius` of a land centre,
    on the mounted ribs only (rib index odd)."""
    thickness = np.tile(mesh.thick, 8)
    centres = np.tile(mesh.centres, (8, 1))
    rib = np.repeat(np.arange(8), len(mesh.t))
    best = dict(strain=0.0)
    for s in shell.STATIONS:
        near = (np.hypot(centres[:, 0] - centre_r, centres[:, 1] - s) <= radius) & (rib % 2 == 1)
        for side in (-1.0, 1.0):
            e = strains[near, :3] + side * 0.5 * thickness[near, None] * strains[near, 3:6]
            mean = 0.5 * (e[:, 0] + e[:, 1])
            delta = 0.5 * np.hypot(e[:, 0] - e[:, 1], e[:, 2])
            for v in (mean + delta, mean - delta):
                k = int(np.argmax(abs(v)))
                if abs(v[k]) > abs(best["strain"]):
                    idx = np.flatnonzero(near)[k]
                    best = dict(
                        strain=float(v[k]),
                        station_mm=s,
                        rib_deg=float(mesh.theta[rib[idx]]),
                        r_z_mm=[float(a) for a in centres[idx]],
                        distance_from_land_centre_mm=float(
                            np.hypot(centres[idx, 0] - centre_r, centres[idx, 1] - s)
                        ),
                        face=side,
                    )
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", type=float, required=True)
    ap.add_argument("--hole-radius", type=float, help="omit to evaluate the archived band-patch model")
    ap.add_argument("--cases", nargs="+", default=["bend67.5", "bend0", "146", "141", "47", "64"])
    ap.add_argument("--step", type=float, default=0.0625)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--seed", type=Path, help="checkpoint folder of a coarser run of the same geometry")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--local-radius", type=float, default=2.0)
    ap.add_argument("--post-only", action="store_true", help="only evaluate saved states in --cache")
    a = ap.parse_args()
    if a.hole_radius is not None:
        install(a.hole_radius)
    a.out.mkdir(parents=True, exist_ok=True)
    mesh = shell.Mesh(a.area)
    centre_r = mesh.land_centres[12]
    print(mesh.info, flush=True)
    model = shell.Model(mesh, "point")
    data = study.archive_loads() if any(not c.startswith("bend") for c in a.cases) else {}
    summary = dict(
        hole_radius_mm=a.hole_radius,
        seed=None if a.seed is None else a.seed.name,
        land_centre_r_mm=centre_r,
        mesh=mesh.info,
        local_radius_mm=a.local_radius,
        cases={},
    )
    for case in a.cases:
        out = a.out / f"point_{case}.json"
        if not a.post_only:
            if out.exists():
                raise FileExistsError(out)
            t = time.monotonic()
            res = study.run_case(model, data, case, a.step, out, a.cache, a.seed)
            print(case, "completed", res["completed"], f"{time.monotonic() - t:.1f}s", flush=True)
        cp = study.Checkpoints(model, case, None, a.cache)
        q, _ = cp.load(1.0)
        if not case.startswith("bend"):
            model.external = data[int(case)]["loads"]
        _, _, _, (x, f, strains) = model.assemble(q, 0.0 if case.startswith("bend") else 1.0, hessian=False)
        res = json.loads(out.read_text()) if out.exists() else None
        last = res["samples"][-1] if res else {}
        summary["cases"][case] = dict(
            completed=bool(res and res["completed"]),
            local_peak_strain=local_strain(mesh, strains, centre_r, a.local_radius),
            near_pivot_peak_strain=local_strain(mesh, strains, centre_r, 0.6),
            global_peak_abs_strain=last.get("max_abs_surface_strain"),
            applied_couple_Nmm=last.get("applied_couple_Nmm"),
            tangent_EI_Nmm2=last.get("tangent_EI_Nmm2"),
            max_land_force_N=max((float(np.linalg.norm(L["force_N"])) for L in last.get("lands", [])), default=None),
            max_relative_rotation_deg=max((L["relative_rotation_deg"] for L in last.get("lands", [])), default=None),
            minimum_oriented_area_ratio=last.get("minimum_oriented_area_ratio"),
            distal_force_N=last.get("distal_force_N"),
            distal_moment_Nmm=last.get("distal_moment_Nmm"),
        )
        print(case, json.dumps(summary["cases"][case]["local_peak_strain"]), flush=True)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
