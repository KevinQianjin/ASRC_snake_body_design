"""Consistency checks of the 25 Nov evening mission envelope; writes results/validation.json."""
import json, re
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"; PREV = HERE.parent / "evening_20261124/results"
checks = []


def check(name, ok, **info):
    checks.append(dict(name=name, passed=bool(ok), **info)); print("PASS" if ok else "FAIL", name, info)


S = np.load(RES / "rod_steps.npz")
check("rod_steps covers all 3,405 states, finite", S["end_rotvec"].shape == (3405, 3) and np.isfinite(S["end_rotvec"]).all()
      and np.isfinite(S["station_wrench"]).all())
q5a = json.loads((PREV / "bond_q5/body_bond.json").read_text())
for s, r in q5a["rod_rotations"].items():
    d = np.abs(np.degrees(S["end_rotvec"][int(s)]) - r["end_rotvec_deg"]).max()
    dl = max(np.abs(np.degrees(S["local_rotvec"][int(s), i]) - r["local_rotvec_deg"][k]).max() for i, k in enumerate(("-12", "12")))
    check(f"rod rotations at step {s} reproduce the 24 Nov archive", max(d, dl) < 1e-9, max_diff_deg=float(max(d, dl)))

MAP = dict(peak_axial="peak", mean_axial="mean")
for tag, folder in (("q5", RES), ("q3", RES / "q3")):
    if not (folder / "mission_envelope.json").exists():
        check(f"{tag} mission results present", False); continue
    arch = json.loads((PREV / f"bond_{tag}/body_bond.json").read_text())
    worst = 0.0
    for c in arch["cases"]:
        f = folder / f"mission_G{int(c['G_MPa'])}_c{int(round(c['crown_mm'] * 100)):02d}.npz"
        if not f.exists(): continue
        d = np.load(f)
        for k, v in c["total_local"].items():
            for ci, comp in enumerate(("normal", "axial", "cross")):
                for q, src in (("peak", "peak_abs_MPa"), ("mean", "mean_abs_MPa")):
                    a_, b_ = d[f"{k}__{q}"][c["step"], ci], v[src][comp]
                    worst = max(worst, abs(a_ - b_) / max(abs(b_), 1e-9))
            for q, src in (("slip", "max_slip_mm"), ("rel_rot_deg", "guide_minus_land_rot_deg"),
                           ("sock_in", "socket_nonrigid_in_land_mm"), ("sock_end", "socket_nonrigid_at_ends_mm")):
                a_, b_ = d[f"{k}__{q}"][c["step"]], v[src]
                worst = max(worst, abs(a_ - b_) / max(abs(b_), 1e-9))
    check(f"{tag} superposition reproduces the archived direct solves (steps 1,709/1,885, all lands, all metrics)",
          worst < 1e-5, max_relative_difference=worst)
    doc = json.loads((folder / "mission_envelope.json").read_text())
    check(f"{tag} solve residuals < 1e-9", all(c["solve_residual"] < 1e-9 for c in doc["cases"]),
          residuals=[c["solve_residual"] for c in doc["cases"]])
    rng = doc["phase_step_ranges"]
    check(f"{tag} phase coverage: straighten -> entry -> right out/return -> left out/return -> pitch -> exit, 3,405 states",
          rng["straighten"][0] == 0 and rng["exit"][1] == 3404 and doc["n_steps"] == 3405, ranges=rng)

P = json.loads((RES / "mission_probe.json").read_text())
A = json.loads((PREV / "solid_arm_probe.json").read_text())
worst = 0.0
for r in A["rows"]:
    m = [p for p in P["rows"] if p["step"] == r["step"] and p["station_mm"] == r["station_mm"] and p["crown_mm"] == r["crown_mm"]]
    if m:
        worst = max(worst, abs(m[0]["min_gap_tilted_mm"] - r["min_gap_tilted_mm"]), abs(m[0]["gap_no_tilt_mm"] - r["gap_no_tilt_mm"]))
check("targeted probe reproduces the archived 24 Nov solid-arm gaps at steps 1,709/1,885", worst < 1e-6, max_abs_diff_mm=worst)
sw = RES / "probe_sweep.json"
if sw.exists():
    W = json.loads(sw.read_text())
    check("probe sweep complete and finite", len(W["rows"]) == W["n_jobs"] and all(np.isfinite(r["min_gap_tilted_mm"]) for r in W["rows"]),
          rows=len(W["rows"]), jobs=W["n_jobs"])
    worst = 0.0
    for r in P["rows"]:
        if r["G_MPa"] != 500: continue
        m = [x for x in W["rows"] if x["step"] == r["step"] and x["station_mm"] == r["station_mm"] and x["crown_mm"] == r["crown_mm"]]
        if m: worst = max(worst, abs(m[0]["min_gap_tilted_mm"] - r["min_gap_tilted_mm"]))
    check("probe sweep (saved unit fields) reproduces the targeted probe", worst < 1e-6, max_abs_diff_mm=worst)
else:
    check("probe sweep present", False)

se = RES / "strain_envelope.json"
if se.exists():
    D = json.loads(se.read_text()); A2 = json.loads((PREV / "strain_check.json").read_text())["cases"]["end_moment_plus_wrench"]
    d = abs(D["at_1709"]["peak"] - A2["peak_abs_principal_strain"]); d2 = abs(D["at_1709"]["land_band_peak"] - A2["peak_in_land_bands"])
    check("strain envelope reproduces the archived 24 Nov step-1,709 peak and land-band strain", max(d, d2) < 1e-9,
          max_abs_diff=max(d, d2))
else:
    check("strain envelope present", False)

for md in [HERE / "README.md", HERE / "HANDOFF.md", HERE.parents[3] / "reports/daily/Evening_Report_2026_11_25.md", HERE.parents[3] / "README.md"]:
    if not md.exists():
        check(f"{md.name} exists", False); continue
    bad = [l for l in re.findall(r"\]\(([^)#\s]+)", md.read_text()) if not l.startswith("http") and not (md.parent / l.split("?")[0]).exists()]
    check(f"relative links resolve in {md.relative_to(HERE.parents[3])}", not bad, broken=bad)

(RES / "validation.json").write_text(json.dumps(dict(checks=checks, all_passed=all(c["passed"] for c in checks)), indent=1))
print("all passed", all(c["passed"] for c in checks))
