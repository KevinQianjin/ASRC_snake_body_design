"""Checks for the 24 November 2026 evening study; writes results/validation.json.

Reads only this folder's results/ (and the archived comparators). Pass/fail thresholds are the
handoff's acceptance criteria where one exists.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
DB_EI = 44117.8  # data/materials/module_stiffness.sqlite3, middle_stiffness_pa12 (N mm^2)
BACKBONE_EI = 64729.79 - DB_EI  # rod M-cell EI (5.39415 N m/rad x 12 mm) minus the PA12 body


def load(p):
    return json.loads((RES / p).read_text())


def main():
    checks = []
    def add(name, value, ok, note=""):
        checks.append(dict(check=name, value=value, passed=bool(ok), note=note))

    meshes = []
    for tag in ("conv_q10", "conv_q5", "conv_q3", "conv_q2"):
        f = RES / tag / "body_stiffness.json"
        if f.exists():
            for m in json.loads(f.read_text())["meshes"]:
                v = {x["variant"]: x for x in m["variants"]}
                meshes.append((tag, m, v))
                c = m["checks"]
                add(f"{tag}: rigid-body modes give zero force", c["rigid_mode_force_rel"], c["rigid_mode_force_rel"] < 1e-10)
                add(f"{tag}: uniform-strain energy exact", c["uniform_strain_energy_rel_err"], c["uniform_strain_energy_rel_err"] < 1e-10)
                add(f"{tag}: mesh volume = CAD lattice volume", c["volume_rel_err"], c["volume_rel_err"] < 1e-5)
    fine = meshes[-1]
    prev = meshes[-2]
    ei_f = fine[2]["solid_rings"]["EI_mean_Nmm2"]; ei_p = prev[2]["solid_rings"]["EI_mean_Nmm2"]
    add("EI mesh convergence (last two levels, solid rings)", abs(ei_f - ei_p) / ei_f, abs(ei_f - ei_p) / ei_f < 0.02,
        f"{prev[0]} {ei_p:.0f} -> {fine[0]} {ei_f:.0f} N mm^2")
    for var in ("solid_rings", "rigid_rings", "rigid_rings_lands"):
        if var in fine[2]:
            r = fine[2][var]["EI_over_plate"]
            add(f"EI within 30% of plate bare body ({var}, {fine[0]})", r, abs(r - 1) <= 0.30, "handoff acceptance")
    r = ei_f / DB_EI
    add("EI vs user database PA12 body EI 44,118 N mm^2 (solid rings)", r, abs(r - 1) <= 0.15)
    r_rod = ei_f / 64729.79
    add("EI vs rod M-cell EI 64,730 N mm^2 (includes Ø1.8 mm NiTi backbone)", r_rod, True,
        f"not a pass/fail: rod = PA12 body {DB_EI:.0f} + backbone {BACKBONE_EI:.0f} N mm^2 (backbone_20261108, niti18_E40)")

    bonds = {}
    for tag in ("bond_q5", "bond_q3", "bond_q2"):
        f = RES / tag / "body_bond.json"
        if f.exists():
            bonds[tag] = json.loads(f.read_text())
    for tag, d in bonds.items():
        add(f"{tag}: max linear-solve residual", max(c["residual"] for c in d["cases"]), max(c["residual"] for c in d["cases"]) < 1e-8)
        cl = max(max(c["wrench_force_closure_N"].values()) for c in d["cases"])
        add(f"{tag}: station wrench force closure (N)", cl, cl < 1e-6)
    tags = list(bonds)
    if len(tags) >= 2:
        a, b = bonds[tags[-2]], bonds[tags[-1]]
        worst_mean, worst_peak = 0.0, 0.0
        for ca, cb in zip(a["cases"], b["cases"]):
            for k in ca["total_local"]:
                ma, mb = ca["total_local"][k]["mean_abs_MPa"]["axial"], cb["total_local"][k]["mean_abs_MPa"]["axial"]
                pa, pb = ca["total_local"][k]["peak_abs_MPa"]["axial"], cb["total_local"][k]["peak_abs_MPa"]["axial"]
                worst_mean = max(worst_mean, abs(ma - mb) / mb); worst_peak = max(worst_peak, abs(pa - pb) / pb)
        add(f"area-mean axial shear convergence {tags[-2]} -> {tags[-1]}", worst_mean, worst_mean < 0.05)
        add(f"peak axial shear convergence {tags[-2]} -> {tags[-1]} (edge peak; reported, not converged to <5%)", worst_peak, worst_peak < 0.15)
    if (RES / "solid_arm_probe.json").exists():
        p = load("solid_arm_probe.json")
        rb = json.loads((HERE.parent / "evening_20261123/results/rigid_arm_probe.json").read_text())
        und = {(r["station_mm"], r["crown_mm"]): r["min_gap_tilted_mm"] for r in rb["rows"]}
        for r in p["rows"]:
            add(f"solid-arm min gap at 0.2 deg tilt, step {r['step']}, z {r['station_mm']:+d}, crown {r['crown_mm']} (mm)",
                r["min_gap_tilted_mm"], r["min_gap_tilted_mm"] > 0.025,
                f"undeformed bracket {und[(r['station_mm'], r['crown_mm'])]:.4f}; 0.025 mm probe offset")
    if (RES / "strain_check.json").exists():
        s = load("strain_check.json")["cases"]["end_moment_plus_wrench"]
        add("peak body principal strain (linear small-strain validity)", s["peak_abs_principal_strain"], s["peak_abs_principal_strain"] < 0.02,
            "FAIL means the linear model is outside its validity in the hub/arm region; land bands peak "
            f"{s['peak_in_land_bands']:.4f}; max linearised rotation {s['max_linearised_rotation_rad']:.2f} rad")
    (RES / "validation.json").write_text(json.dumps(dict(checks=checks, all_passed=all(c["passed"] for c in checks)), indent=1, default=float))
    for c in checks:
        print("PASS" if c["passed"] else "FAIL", c["check"], c["value"], c["note"])


if __name__ == "__main__":
    main()
