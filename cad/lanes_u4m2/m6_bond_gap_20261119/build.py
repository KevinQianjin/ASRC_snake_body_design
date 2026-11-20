"""Export the M6 outer-station (z = +/-12 mm) guide candidate with a 0.25 mm land bond gap.

Runs the unchanged V3 builder (`../guides_v3/build.py`) with `--bond-gap 0.25` into a
temporary folder and keeps only the M6 +/-12 mm guide, caps and lockwire envelope.
All other stations keep their current parts: M5 +/-12 mm uses the retained rotating
seat, and every +/-24 mm station keeps V3 (the V3 builder would otherwise also widen
the +/-24 mm inner-web sockets). Engineering candidate; not released for manufacture.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
V3 = HERE.parent / "guides_v3"
BOND_GAP = 0.25
TAGS = ("M6_z-12", "M6_z+12")
PARTS = ("guide", "caps", "wire_envelope")


def rope_bores(mesh, z):
    """Rope-bore holes (radius > 20 mm) in a section at local z."""
    planar, _ = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1]).to_2D(to_2D=np.eye(4))
    holes = []
    for poly in planar.polygons_full:
        for ring in poly.interiors:
            h = Polygon(ring)
            c = h.centroid
            if h.area < 10 and np.hypot(c.x, c.y) > 20:
                holes.append((round(np.hypot(c.x, c.y), 4), round(np.degrees(np.arctan2(c.y, c.x)), 3), round(h.area, 4)))
    return sorted(holes)


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(V3 / "build.py"), "--out", tmp, "--bond-gap", str(BOND_GAP)], check=True)
        tmp = Path(tmp)
        full = json.loads((tmp / "geometry_check.json").read_text())
        report = dict(
            status="M6 outer-socket bond-gap candidate; not released for manufacture",
            bond_gap_mm=BOND_GAP, v3_bond_gap_mm=0.15,
            builder=f"guides_v3/build.py --bond-gap {BOND_GAP}",
            builder_sha256=hashlib.sha256((V3 / "build.py").read_bytes()).hexdigest(),
            unchanged=dict(land_axial_mm=full["design"]["socket_land_axial_mm"],
                           flare_slope=full["design"]["socket_flare_slope"],
                           socket_wall_mm=full["design"]["socket_wall_mm"],
                           lane_radii_mm=full["design"]["lane_radii_mm"],
                           rope_bore_mm=full["design"]["rope_bore_mm"]),
            parts={}, rope_bore_sections={}, mass_delta_g={})
        for tag in TAGS:
            report["parts"][tag] = full["parts"][tag]
            if not full["parts"][tag]["pass_geometry"]:
                raise RuntimeError(f"{tag} fails the straight assembly check")
            for p in PARTS:
                shutil.copyfile(tmp / f"{tag}_{p}.stl", out / f"{tag}_{p}.stl")
            new = {p: trimesh.load_mesh(out / f"{tag}_{p}.stl") for p in PARTS}
            old = {p: trimesh.load_mesh(V3 / f"{tag}_{p}.stl") for p in PARTS}
            zs = np.linspace(-1.6, 1.6, 17)
            same = [rope_bores(old["guide"], z) == rope_bores(new["guide"], z) for z in zs]
            report["rope_bore_sections"][tag] = dict(sections=len(zs), identical=int(sum(same)))
            if not all(same):
                raise RuntimeError(f"{tag}: rope bores changed")
            rho = dict(guide=0.93e-3, caps=0.93e-3, wire_envelope=7.9e-3)  # g/mm^3, as mass_model.json
            report["mass_delta_g"][tag] = {p: (new[p].volume - old[p].volume) * rho[p] for p in PARTS}
            report["parts"][tag]["sha256"] = {p: hashlib.sha256((out / f"{tag}_{p}.stl").read_bytes()).hexdigest() for p in PARTS}
    (out / "geometry_check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["mass_delta_g"], indent=1), report["rope_bore_sections"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=HERE)
    main(p.parse_args().out)
