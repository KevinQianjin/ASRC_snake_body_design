"""Checks for the 22 November 2026 evening bond study; writes results/validation.json."""

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RES = HERE / "results"
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119/results/m6_guides/m6_support.json"
CROWN = ROOT / "cad/lanes_u4m2/m6_crowned_land_20261120"
checks = {}


def check(name, ok, detail=""):
    checks[name] = dict(ok=bool(ok), detail=detail)


rows = json.loads((RES / "bond_cases.json").read_text())["rows"]
arc = {(c["step"], c["station_mm"], c["G_MPa"]): c
       for c in json.loads(ROUND2.read_text())["cases"] if c["gap_mm"] == 0.25}
diff = max(max(abs(arc[k]["relative_motion_mm"] - r["witness_relative_motion_mm"]),
               abs(arc[k]["normal_closure_at_candidate_witness_mm"] - r["witness_normal_closure_mm"]),
               max(abs(a - b) for a, b in zip(arc[k]["guide_increment_mm_rad"], r["guide_increment_mm_rad"])))
           for r in rows if r["nh"] == 2 and r["crown_mm"] == 0 and r["mismatch"] == "rod"
           for k in [(r["step"], r["station_mm"], r["G_MPa"])])
check("round2_reproduced_nh2_uncrowned_rod", diff < 1e-10, f"max abs difference {diff:.2e}")
check("case_coverage", len(rows) == 3 * 2 * 3 * 2 * 2 * 3,
      f"{len(rows)} rows = 3 steps x 2 stations x nh(2,4,8) x crown(0,0.06) x G(500,1500) x mismatch(rod,midplane,rigidland)")
check("land_wrench_closure", max(r["land_wrench_closure_residual"] for r in rows) < 2e-5,
      f"max {max(r['land_wrench_closure_residual'] for r in rows):.2e}")
crowned = [r for r in rows if r["crown_mm"] == 0.06]
check("crowned_mean_layer", all(abs(r["mean_layer_mm"] - (0.25 + 0.06 / 3)) < 3e-3 for r in crowned if r["nh"] >= 4),
      "area-mean layer 0.27 mm = 0.25 + 0.06/3 for nh >= 4")

for st in (-12, 12):
    p = json.loads((RES / f"bond_tilt_probe_z{st}.json").read_text())["rows"]
    ideal = [r for r in p if r["case"] == "ideal position"]
    ref = {(-12, 0.0, 1709): 0.00070, (-12, 0.06, 1709): 0.02829,
           (12, 0.0, 1709): 0.01719, (12, 0.06, 1709): 0.04400}
    d = [abs(r["min_gap_tilted_mm"] - ref[(st, r["crown_mm"], r["step"])])
         for r in ideal if (st, r["crown_mm"], r["step"]) in ref]
    check(f"probe_z{st:+d}_ideal_matches_21nov_tilt", d and max(d) < 1e-4,
          f"{len(d)} reference points, max diff {max(d) if d else None}")
    check(f"probe_z{st:+d}_coverage", len(p) == 2 * 3 * 7, f"{len(p)} rows (2 variants x 3 steps x (ideal + 3 models x 2 G))")

rl = json.loads((RES / "rigidland/bond_duty_nh2-8.json").read_text())["runs"]
check("duty_rigidland_complete", len(rl) == 8 and all(r["steps"] == 3405 for r in rl), f"{len(rl)} runs")
for f in (RES / "bond_duty_nh2-8.json",):
    if f.exists():
        runs = json.loads(f.read_text())["runs"]
        check("duty_complete", all(r["steps"] == 3405 for r in runs) and len(runs) == 16, f"{len(runs)} runs")
        base = [r for r in runs if r["nh"] == 2 and r["crown_mm"] == 0 and r["G_MPa"] == 500 and r["mismatch"] == "rod"][0]
        check("duty_round2_axial_peak", abs(base["envelope"]["axial_shear"]["max"] - 63.95869548325363) < 1e-6,
              f"{base['envelope']['axial_shear']['max']:.6f} vs archived 63.958695")
    else:
        check("duty_complete", False, "missing")

ref = json.loads((HERE.parent / "evening_20261120/results/validation.json").read_text())["parts"]
bad = [f.name for f in sorted(CROWN.glob("*.stl"))
       if hashlib.sha256(f.read_bytes()).hexdigest() != ref[f.stem]["sha256"]]
check("crowned_cad_unchanged_since_20nov", not bad and len(list(CROWN.glob("*.stl"))) == 6,
      f"unmatched: {bad}")

broken = []
docs = [HERE / "README.md", HERE / "HANDOFF.md", ROOT / "reports/daily/Evening_Report_2026_11_22.md", ROOT / "README.md"]
for doc in docs:
    for link in re.findall(r"\]\(([^)#?]+)(?:[#?][^)]*)?\)", doc.read_text()):
        if link.startswith("http"):
            continue
        if not (doc.parent / link).resolve().exists():
            broken.append(f"{doc.relative_to(ROOT)} -> {link}")
check("relative_links", not broken, f"{len(broken)} broken: {broken[:10]}")

ok = all(c["ok"] for c in checks.values())
(RES / "validation.json").write_text(json.dumps(dict(all_ok=ok, checks=checks), indent=1))
for k, v in checks.items():
    print("PASS" if v["ok"] else "FAIL", k, v["detail"])
sys.exit(0 if ok else 1)
