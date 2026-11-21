"""Validation record for the 20 Nov 2026 evening crowned-land study.

Checks: (1) zero crown rebuilds the committed 0.25 mm candidate exactly (vertex match);
(2) the committed crowned parts are closed, single-component (guide) / four-component
(caps, wire) volumes with zero straight overlap and unchanged rope bores; (3) every
screened step was checked for every variant with no contact; (4) relative Markdown links
in the new/updated documents resolve. Writes results/validation.json.
"""

import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAD = ROOT / "cad/lanes_u4m2"
NEW, REF = CAD / "m6_crowned_land_20261120", CAD / "m6_bond_gap_20261119"
TAGS, PARTS = ("M6_z-12", "M6_z+12"), ("guide", "caps", "wire_envelope")
DOCS = [HERE / "README.md", HERE / "HANDOFF.md", NEW / "README.md", ROOT / "README.md",
        ROOT / "reports/daily/Evening_Report_2026_11_20.md"]


def same_mesh(a, b):
    return (len(a.faces) == len(b.faces) and abs(a.volume - b.volume) < 1e-9
            and cKDTree(b.vertices).query(a.vertices)[0].max() < 1e-9)


def links(doc):
    bad = []
    for target in re.findall(r"\]\(([^)#?]+)(?:[#?][^)]*)?\)", doc.read_text()):
        if "://" in target or target.startswith("mailto:"):
            continue
        if not (doc.parent / target).exists():
            bad.append(target)
    return bad


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(CAD / "guides_v3/build.py"), "--out", tmp, "--bond-gap", "0.25"],
                       check=True, capture_output=True)
        checks["zero_crown_reproduces_0p25_candidate"] = all(
            same_mesh(trimesh.load_mesh(Path(tmp) / f"{t}_{p}.stl"), trimesh.load_mesh(REF / f"{t}_{p}.stl"))
            for t in TAGS for p in PARTS)
    geo = json.loads((NEW / "geometry_check.json").read_text())
    parts = {}
    for t in TAGS:
        for p in PARTS:
            m = trimesh.load_mesh(NEW / f"{t}_{p}.stl")
            parts[f"{t}_{p}"] = dict(watertight=bool(m.is_watertight), components=len(m.split(only_watertight=False)),
                                     volume_mm3=float(m.volume),
                                     sha256=hashlib.sha256((NEW / f"{t}_{p}.stl").read_bytes()).hexdigest())
    checks["parts_closed"] = all(v["watertight"] for v in parts.values())
    checks["component_counts"] = all(v["components"] == (1 if k.endswith("guide") else 4) for k, v in parts.items())
    checks["straight_overlap_zero"] = all(geo["parts"][t]["body_overlap_mm3"] < 1e-6 for t in TAGS)
    checks["rope_bores_identical"] = all(v["identical"] == v["sections"] for v in geo["rope_bore_sections"].values())
    summary = json.loads((HERE / "results/summary.json").read_text())
    checks["screen_no_contact"] = all(v["contacts"] == 0 for s in summary["screen"].values() for v in s.values())
    checks["screen_complete_787_430"] = (summary["screen"]["z-12"]["g025"]["steps"] == 787
                                         and summary["screen"]["z+12"]["g025"]["steps"] == 430)
    checks["crown_never_reduces_gap"] = all(v["min_gain_vs_g025_mm"] >= -1e-9 for s in summary["screen"].values()
                                            for v in s.values())
    checks["relative_links"] = {str(d.relative_to(ROOT)): links(d) for d in DOCS if d.exists()}
    ok = all(v for k, v in checks.items() if k != "relative_links") and not any(checks["relative_links"].values())
    versions = {"python": platform.python_version(),
                **{m: metadata.version(m) for m in ("numpy", "scipy", "trimesh", "python-fcl", "manifold3d",
                                                    "shapely", "matplotlib", "numba", "vtk")}}
    out = dict(all_pass=ok, checks=checks, parts=parts, versions=versions,
               source_revision=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                              text=True).stdout.strip())
    (HERE / "results/validation.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(checks, indent=1), "\nALL PASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
