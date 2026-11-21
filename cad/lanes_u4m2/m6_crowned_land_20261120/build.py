"""Export the M6 outer-station (z = +/-12 mm) guide candidate with a crowned 0.25 mm bond land.

Evening 20 Nov 2026. Runs the V3 builder (`../guides_v3/build.py`) with
`--bond-gap 0.25 --crown CROWN` into a temporary folder. The crown adds
CROWN*(z/0.25 mm)^2 to the land gap so the gap stays 0.25 mm at mid-land and reaches
0.25+CROWN mm at each land edge; the 1.5 flare continues from there. It and keeps only the M6 +/-12 mm guide, caps and lockwire envelope.
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
CROWN = 0.06  # mm, selected candidate (see README)
REFERENCE = HERE.parent / "m6_bond_gap_20261119"  # uncrowned 0.25 mm candidate
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


def main(out, crown=CROWN):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(V3 / "build.py"), "--out", tmp, "--bond-gap", str(BOND_GAP), "--crown", str(crown)], check=True)
        tmp = Path(tmp)
        full = json.loads((tmp / "geometry_check.json").read_text())
        report = dict(
            status="M6 outer-socket crowned-land candidate; not released for manufacture",
            bond_gap_mm=BOND_GAP, land_crown_mm=crown, land_edge_gap_mm=BOND_GAP + crown,
            mean_land_gap_mm=BOND_GAP + crown / 3, reference="../m6_bond_gap_20261119 (uncrowned 0.25 mm)",
            builder=f"guides_v3/build.py --bond-gap {BOND_GAP} --crown {crown}",
            guides_v2_builder_sha256=hashlib.sha256((HERE.parent / "guides_v2/build.py").read_bytes()).hexdigest(),
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
            report["parts"][tag]["export_checks"] = full["parts"][tag]["export_checks"]
            for p in PARTS:
                shutil.copyfile(tmp / f"{tag}_{p}.stl", out / f"{tag}_{p}.stl")
            new = {p: trimesh.load_mesh(out / f"{tag}_{p}.stl") for p in PARTS}
            old = {p: trimesh.load_mesh(REFERENCE / f"{tag}_{p}.stl") for p in PARTS}
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
    p.add_argument("--crown", type=float, default=CROWN)
    a = p.parse_args()
    main(a.out, a.crown)
