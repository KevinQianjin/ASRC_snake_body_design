"""Consistency checks for the 19 November evening M6 socket study. Writes results/validation.json."""

import hashlib
import json
import re
import sys
from importlib.metadata import version
from pathlib import Path

import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT / "cad/lanes_u4m2/m6_bond_gap_20261119"
R1 = HERE.parent / "extreme_round1_20261119/results/m6_clearance.json"
checks = {}


def check(name, ok, detail=None):
    checks[name] = dict(passed=bool(ok), detail=detail)


geo = json.loads((CAND / "geometry_check.json").read_text())
for tag, part in geo["parts"].items():
    for p, sha in part["sha256"].items():
        f = CAND / f"{tag}_{p}.stl"
        m = trimesh.load_mesh(f)
        n = 1 if p == "guide" else 4
        check(f"{tag}_{p}_hash_watertight_components",
              hashlib.sha256(f.read_bytes()).hexdigest() == sha and m.is_watertight and len(m.split()) == n,
              dict(components=len(m.split()), volume_mm3=m.volume))
    check(f"{tag}_straight_overlap_zero", part["body_overlap_mm3"] < 1e-6, part["body_overlap_mm3"])
    rb = geo["rope_bore_sections"][tag]
    check(f"{tag}_rope_bores_unchanged", rb["identical"] == rb["sections"], rb)

r1 = json.loads(R1.read_text())
r1_fine = [r for r in r1["resolution"] if r["axial_mesh_span_mm"] == 0.125][0]["nominal_gaps_mm"]["guide"]
fine = json.loads((HERE / "results/fine_governing_minus12.json").read_text())["rows"]
v3 = [r for r in fine if r["variant"] == "V3" and r["step"] == 1710][0]["guide_gap_mm"]
check("v3_step1710_fine_reproduces_round1", abs(v3 - r1_fine) < 1e-9, dict(this_run=v3, round1=r1_fine))
r1_straight = r1["straight_gaps_mm"]["guide"]
scr = json.loads((HERE / "results/screen/top_minus.json").read_text())
st = [r for r in scr["straight"] if r["variant"] == "v3"][0]["guide_gap_mm"]
check("v3_straight_reproduces_round1", abs(st - r1_straight) < 1e-9, dict(this_run=st, round1=r1_straight))

cand_fine = {f: [r for r in json.loads((HERE / f"results/fine_governing_{f}.json").read_text())["rows"]
                 if r["variant"] == "bond_gap_0p25"] for f in ("minus12", "plus12")}
check("candidate_fine_no_contact", all(not r[f"{p}_contact"] for v in cand_fine.values() for r in v
                                       for p in ("guide", "caps", "wire_envelope")),
      {k: min(r["guide_gap_mm"] for r in v) for k, v in cand_fine.items()})
summ = json.loads((HERE / "results/coverage_summary.json").read_text())
check("coverage_all_eleven_phases", len(summ["phases"]) == 11, summ["phases"])
check("coverage_candidate_no_contact", all(summ[s]["variants"]["g025"]["contacts"] == 0 for s in ("z-12", "z+12")))

broken = []
for doc in [HERE / "README.md", HERE / "HANDOFF.md", CAND / "README.md",
            ROOT / "reports/daily/Evening_Report_2026_11_19.md", ROOT / "README.md"]:
    for link in re.findall(r"\]\(([^)#\s]+)", doc.read_text()):
        target = (doc.parent / link).resolve()
        if target == (HERE / "results/validation.json").resolve():
            continue  # this script's own output
        if not link.startswith("http") and not target.exists():
            broken.append(f"{doc.relative_to(ROOT)} -> {link}")
check("relative_links_resolve", not broken, broken)

out = dict(
    checks=checks, all_passed=all(c["passed"] for c in checks.values()),
    python=sys.version.split()[0],
    versions={p: version(p) for p in ("numpy", "scipy", "trimesh", "python-fcl", "manifold3d", "shapely", "matplotlib", "clarabel")},
)
(HERE / "results/validation.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: v["passed"] for k, v in checks.items()}, indent=1), out["all_passed"])
sys.exit(0 if out["all_passed"] else 1)
