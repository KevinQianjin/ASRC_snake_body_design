"""Validation record for the 21 November evening M6 full-mission certification."""

import hashlib
import json
import re
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RES = HERE / "results"
CAD20 = ROOT / "cad/lanes_u4m2/m6_crowned_land_20261120"
VAL20 = HERE.parent / "evening_20261120/results/validation.json"
DOCS = [
    HERE / "README.md",
    HERE / "HANDOFF.md",
    ROOT / "README.md",
    ROOT / "reports/daily/Evening_Report_2026_11_21.md",
]


def links(md):
    bad = []
    if not md.exists():
        return ["<missing document>"]
    for target in re.findall(r"\]\(([^)\s]+)\)", md.read_text()):
        if target.startswith(("http", "#", "mailto:")):
            continue
        path = target.split("#")[0].split("?")[0]
        if path and not (md.parent / path).exists():
            bad.append(target)
    return bad


def main():
    s = json.loads((RES / "summary.json").read_text())
    nom, tilt = s["nominal"], s["tilt_0p2deg"]
    ref = json.loads(VAL20.read_text())["parts"]
    sha = {}
    for f in sorted(CAD20.glob("*.stl")):
        sha[f.stem] = hashlib.sha256(f.read_bytes()).hexdigest() == ref[f.stem]["sha256"]
    checks = dict(
        crowned_cad_unchanged_since_20nov=all(sha.values()) and len(sha) == 6,
        g025_reproduces_round2_exactly=all(v["g025_reproduces_round2_max_abs_mm"] == 0 for v in nom.values()),
        crown060_matches_20nov_screen=all(v["crown060_matches_20nov_screen_max_abs_mm"] < 1e-6 for v in nom.values()),
        nominal_full_mission_3405_steps_11_phases=all(v["steps"] == 3405 and v["phases"] == 11 for v in nom.values()),
        nominal_no_contact=all(v["crown060_contacts"] == 0 for v in nom.values()),
        crown_never_reduces_gap=all(min(v["per_part_gain_min_mm"].values()) >= 0 for v in nom.values()),
        tilt_crown060_complete=all(tilt["crown060"][k]["complete"] and tilt["crown060"][k]["steps_covered"] == 3405
                                   for k in ("-12", "12")),
        tilt_crown060_no_contact=all(tilt["crown060"][k]["contacts_at_tilt"] == 0 for k in ("-12", "12")),
        relative_links={str(d.relative_to(ROOT)): links(d) for d in DOCS},
    )
    ok = all(v if isinstance(v, bool) else not any(v.values()) for v in checks.values())
    versions = {"python": sys.version.split()[0]}
    for pkg in ("numpy", "scipy", "trimesh", "python-fcl", "pandas", "matplotlib", "numba", "clarabel"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    out = dict(all_pass=ok, checks=checks, cad_sha256_match=sha, versions=versions)
    (RES / "validation.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
