"""Evening 2026-11-26: summary figure and automated checks for bore_fe.py + bore_contact.py."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "results"
MORN = HERE.parent / "morning_20261126/results/backbone_strain.json"
sys.path.insert(0, str(HERE.parent / "evening_20261125")); sys.path.insert(0, str(HERE.parent / "evening_20261124"))


def main():
    import mission_envelope as ME
    fe = json.load(open(R / "bore_fe.json"))
    bc = json.load(open(R / "bore_contact.json"))
    mo = json.load(open(MORN))
    cv = json.load(open(R / "convergence.json"))
    rows = np.load(R / "bore_contact_rows.npz")
    C = bc["parameters"]["radial_clearance_mm"]
    n = len(rows["lin_cad"]); phase = ME.phase_of(n)

    # ---- figure
    fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    st = np.arange(n)
    ax[0].plot(st, rows["lin_morning"].max(1), color="#b0b0b0", lw=1, label="L0 morning model (clamp at z=-44.9/+40.9, L=85.8 mm)")
    ax[0].plot(st, rows["lin_cad"].max(1), color="#1f5fa8", lw=1.2, label="L1 linear, CAD sleeves (z=±33, L=66 mm)")
    nl_off = C - rows["gap"]
    ax[0].plot(rows["step"], nl_off.max(1), ".", ms=3, color="#d2691e", label="L2 nonlinear elastica (h=1 mm), arc-length lift")
    ax[0].axhline(C, color="k", ls="--", lw=1, label="radial clearance 3.30 mm (Ø8.40 bore, Ø1.80 rod)")
    ax[0].set_ylabel("max backbone offset\nfrom ring-bore axis (mm)"); ax[0].legend(fontsize=7, loc="upper left")
    for j, c in enumerate(["#1b9e77", "#d95f02", "#7570b3", "#e7298a"]):
        ax[1].plot(rows["step"], nl_off[:, j], ".", ms=2.5, color=c, label=f"ring_{j}")
    ax[1].axhline(C, color="k", ls="--", lw=1)
    ax[1].set_ylabel("L2 offset per ring (mm)"); ax[1].legend(fontsize=7, ncol=4)
    ax[2].plot(rows["step"], 100 * rows["strain"], ".", ms=3, color="#444")
    ax[2].set_ylabel("L2 NiTi max bending\nstrain (%)"); ax[2].set_xlabel("mission state")
    for a in ax:
        for k in np.flatnonzero(np.diff(phase)) + 0.5:
            a.axvline(k, color="#ddd", lw=0.6, zorder=0)
    fig.suptitle("Evening 2026-11-26 — M6 NiTi backbone vs hub-ring bore clearance over the 3,405-state mission (q5 FE, G=500 MPa, crown 0.06 mm)", fontsize=9)
    fig.tight_layout(); fig.savefig(R / "evening_20261126_summary.png", dpi=130)

    # ---- checks
    nl = bc["L2_nonlinear_cad"]; l0 = bc["L0_linear_morning"]; l1 = bc["L1_linear_cad"]
    ext = fe["cad_bore"]["sleeve_z_extent_mm"]
    low = rows["rot"] < 15.0
    lin_at = rows["lin_cad"][rows["step"]]
    agree = float(np.abs(nl_off[low] - lin_at[low]).max())
    m1869 = mo["q5_step_comparisons"]["1869"]["backbone_hub_clearance"]["max_relative_lateral_mm"]
    ms = fe["solves"]["morning_L85p8"]["steps"]
    phases_cov = sorted(set(phase[rows["step"]].tolist()))
    checks = [
        ("CAD sleeve bore Ø1.85 mm spans |z| = 33..48 mm (15 mm support per end)",
         abs(fe["cad_bore"]["sleeve_bore_radius_mm"] - 0.925) < 0.01 and abs(ext[0][1] + 33.0) <= 0.1 and abs(ext[1][0] - 33.0) <= 0.1,
         dict(radius=fe["cad_bore"]["sleeve_bore_radius_mm"], extent=ext)),
        ("Only the Ø8.40 ring bores lie within r < 5.5 mm in the free span",
         abs(fe["cad_bore"]["free_span_min_radius_mm"] - 4.2) < 0.02, fe["cad_bore"]["free_span_min_radius_mm"]),
        ("Morning backbone model reproduced (offset 1,869 and moment shares)",
         abs(l0["step_1869"][0] - m1869) < 0.01 and abs(ms["1869"]["backbone_moment_share"] - 0.235) < 0.002
         and abs(ms["1709"]["backbone_moment_share"] - 0.248) < 0.002, dict(L0=l0["step_1869"][0], morning=m1869)),
        ("PARDISO relative residuals < 1e-9", max(fe["solves"][k]["residual"] for k in ("morning_L85p8", "cad_sleeve_L66")) < 1e-9,
         [fe["solves"][k]["residual"] for k in ("morning_L85p8", "cad_sleeve_L66")]),
        ("Elastica reproduces exact circular arcs at production settings (radius error < 0.15 mm)",
         max(v["max_radius_error_mm"] for v in bc["L2_verification_circular_arc"].values()) < 0.15,
         bc["L2_verification_circular_arc"]),
        ("Production h=1.0 mm min gap within 0.02 mm of (and not above) the converged h=0.25 mm value",
         all(-0.02 <= cv[k]["production_minus_converged_min_gap_mm"] <= 0.0 for k in cv),
         {k: cv[k]["production_minus_converged_min_gap_mm"] for k in cv}),
        ("Rod discretisation converged: h=0.5 -> 0.25 mm changes every ring gap < 0.01 mm",
         all(cv[k]["h0p5_vs_h0p25_max_gap_change_mm"] < 0.01 for k in cv),
         {k: cv[k]["h0p5_vs_h0p25_max_gap_change_mm"] for k in cv}),
        ("L2 agrees with L1 below 15 deg end rotation (< 0.05 mm)", agree < 0.05, agree),
        ("L2 coverage spans all 11 mission phases", len(phases_cov) == 11, phases_cov),
        ("Rotation lift reproduces D1 rotation (< 0.01 deg)", nl["max_D1_rotation_lift_error_deg"] < 0.01,
         nl["max_D1_rotation_lift_error_deg"]),
        ("Summary figure written", (R / "evening_20261126_summary.png").stat().st_size > 10000, None),
    ]
    out = dict(checks=[dict(name=a, passed=bool(b), value=c) for a, b, c in checks],
               all_passed=all(bool(b) for _, b, _ in checks),
               headline=dict(L0_max_offset_mm=l0["max_offset_mm"], L0_states_exceeding=l0["states_exceeding_clearance"],
                             L1_max_offset_mm=l1["max_offset_mm"], L1_min_gap_mm=l1["min_gap_mm"],
                             L2_min_gap_mm=nl["min_gap_mm"], L2_min_gap_step=nl["min_gap_step"],
                             L2_states_in_contact=nl["states_in_contact"], L2_states=nl["states_evaluated"],
                             L2_max_bending_strain=nl["max_backbone_bending_strain"]))
    json.dump(out, open(R / "validation.json", "w"), indent=1, default=float)
    for c in out["checks"]:
        print("PASS" if c["passed"] else "FAIL", c["name"], c["value"] if not isinstance(c["value"], dict) else "")
    print(json.dumps(out["headline"], indent=1))


if __name__ == "__main__":
    main()
