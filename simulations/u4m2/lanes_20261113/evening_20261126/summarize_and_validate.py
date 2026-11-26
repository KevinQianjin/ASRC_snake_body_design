"""Summarize, plot, and validate the 26 November 2026 M6 backbone-strain and stride-1 tilt results."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PREV25 = HERE.parent / "evening_20261125/results"


def main():
    b = json.loads((RES / "backbone_strain.json").read_text())
    t = json.loads((RES / "stride1_tilt_sweep.json").read_text())

    print("=== LAND TRACTION COMPARISON (step 1869, G=500, crowned 0.06) ===")
    for lk, v in b["q5_step_comparisons"]["1869"]["land_traction_by_land"].items():
        print(
            f"  {lk:10s} | ax_pk: {v['bare_peak_axial_MPa']:5.2f} -> {v['bb_peak_axial_MPa']:5.2f} "
            f"({v['rel_diff_peak_axial']*100:5.1f}%) | mean: {v['bare_mean_axial_MPa']:4.2f} -> "
            f"{v['bb_mean_axial_MPa']:4.2f} ({v['rel_diff_mean_axial']*100:5.1f}%) | "
            f"norm: {v['bare_peak_normal_MPa']:5.2f} -> {v['bb_peak_normal_MPa']:5.2f} "
            f"({v['rel_diff_peak_normal']*100:5.1f}%)"
        )

    print("\n=== BACKBONE HUB CLEARANCE (step 1869) ===")
    for rk, rv in b["q5_step_comparisons"]["1869"]["backbone_hub_clearance"]["rings"].items():
        print(f"  {rk}: z={rv['z_mm']:+6.2f} mm, rel_lat={rv['relative_lateral_mm']:.3f} mm "
              f"(bb={[round(x,2) for x in rv['bb_xy_mm']]}, ring={[round(x,2) for x in rv['ring_xy_mm']]})")

    print("\n=== MOMENT SPLIT (steps 1709 & 1869) ===")
    for s in ("1709", "1869"):
        sk = b["q5_step_comparisons"][s]["moment_split_kinematic"]
        sl = b["q5_step_comparisons"][s]["moment_split_load_controlled"]
        print(f"  Step {s} kin: M_body={sk['M_body_norm_Nmm']:.1f}, M_bb={sk['M_backbone_norm_Nmm']:.1f}, "
              f"M_tot={sk['M_total_norm_Nmm']:.1f} N mm ({sk['body_share']*100:.1f}% / {sk['backbone_share']*100:.1f}%)")
        print(f"  Step {s} lc : M_body={sl['M_body_norm_Nmm']:.1f}, M_bb={sl['M_backbone_norm_Nmm']:.1f}, "
              f"M_tot={sl['M_total_norm_Nmm']:.1f} N mm ({sl['body_share']*100:.1f}% / {sl['backbone_share']*100:.1f}%)")

    print("\n=== FINEST MESH (q2.5/a0.25) STRAIN ENVELOPE BY PHASE ===")
    for ph, pv in b["finest_mesh_strain_envelope_with_backbone"]["by_phase"].items():
        print(f"  {ph:18s}: {pv['max']*100:.3f}% @ step {pv['step']}")

    # --- Generate 3-panel summary figure ---
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), dpi=160)

    # Panel 1: Mesh convergence at step 1869
    ax = axes[0]
    q5_s = b["q5_step_comparisons"]["1869"]["kinematic_with_bb_q5"]
    q3_s = b["local_mesh_refinement"][0]["steps"]["1869"]["strain"]
    q25_s = b["local_mesh_refinement"][1]["steps"]["1869"]["strain"]
    labels = ["q5\n(130k tets)", "q3\n(179k tets)", "q2.5/a0.25\n(246k tets)"]
    x = np.arange(3)
    peaks = [q5_s["peak_abs_principal_strain"] * 100,
             q3_s["peak_abs_principal_strain"] * 100,
             q25_s["peak_abs_principal_strain"] * 100]
    g05 = [q5_s["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100,
           q3_s["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100,
           q25_s["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100]
    g10 = [q5_s["finite_gauge_at_peak"]["r_1.0mm"]["tensor_avg_principal_strain"] * 100,
           q3_s["finite_gauge_at_peak"]["r_1.0mm"]["tensor_avg_principal_strain"] * 100,
           q25_s["finite_gauge_at_peak"]["r_1.0mm"]["tensor_avg_principal_strain"] * 100]
    ax.plot(x, peaks, "o-", lw=2, color="#c0392b", label="Element peak")
    ax.plot(x, g05, "s-", lw=2, color="#e67e22", label="0.5 mm gauge avg")
    ax.plot(x, g10, "^-", lw=2, color="#2980b9", label="1.0 mm gauge avg")
    ax.axhspan(15 / 15.3, 18 / 15.3, color="#27ae60", alpha=0.18, label="PA12 fatigue limit (15-18 MPa)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Principal strain (%)")
    ax.set_title("Hub/arm strain convergence (step 1,869)")
    ax.set_ylim(0, 4.8)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7.5, loc="center right")

    # Panel 2: Full mission strain envelope
    ax = axes[1]
    pk_bare = np.load(PREV25 / "strain_envelope.npz")["peak"] * 100
    pk_q5bb = np.load(RES / "strain_envelope_q5_bb.npz")["peak"] * 100
    pk_ref = np.load(RES / "strain_envelope_refined_bb.npz")["peak"] * 100
    steps = np.arange(len(pk_ref))
    ax.plot(steps, pk_bare, lw=1.0, alpha=0.75, color="#7f8c8d", label="25 Nov q5 bare (max 3.81%)")
    ax.plot(steps, pk_q5bb, lw=1.0, alpha=0.85, color="#2980b9", label="26 Nov q5 + NiTi (max 3.48%)")
    ax.plot(steps, pk_ref, lw=1.1, alpha=0.9, color="#c0392b", label="26 Nov q2.5 + NiTi (max 4.21%)")
    ax.axhline(3.0, ls="--", lw=0.9, color="#c0392b", alpha=0.5)
    ax.axhline(2.0, ls=":", lw=0.9, color="#e67e22", alpha=0.6)
    ax.set_xlabel("Mission state")
    ax.set_ylabel("Peak |principal strain| (%)")
    ax.set_title("Full-mission hub strain (3,405 states)")
    ax.set_ylim(0, 4.6)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7.5, loc="upper right")

    # Panel 3: Stride-1 vs Stride-5 tilt clearance
    ax = axes[2]
    cats = ["Uncr.\n-12 mm", "Uncr.\n+12 mm", "Crown.\n-12 mm", "Crown.\n+12 mm"]
    s5 = [r["stride5_min_tilted_mm"] for r in t["summary"]]
    s1 = [r["stride1_min_tilted_mm"] for r in t["summary"]]
    x3 = np.arange(4)
    w = 0.34
    ax.bar(x3 - w / 2, s5, w, color="#95a5a6", label="25 Nov stride-5")
    ax.bar(x3 + w / 2, s1, w, color="#27ae60", label="26 Nov stride-1 (±10)")
    ax.axhline(0.025, ls="--", lw=1.0, color="#c0392b", label="0.025 mm probe offset")
    ax.set_xticks(x3)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Min tilted gap at ±0.2° (mm)")
    ax.set_title("Priority 2: stride-1 tilt closeout")
    ax.set_ylim(0, 0.095)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=7.5, loc="lower right")

    fig.tight_layout()
    fig.savefig(RES / "evening_20261126_summary.png", dpi=160)
    plt.close(fig)

    # --- Validation checks ---
    stiff = b["stiffness_summary"]
    ei_add_err = abs(stiff["with_bb_EIxx_crop_Nmm2"] - (stiff["bare_bonded_EIxx_crop_Nmm2"] + stiff["backbone_EI_Nmm2"])) / stiff["with_bb_EIxx_crop_Nmm2"]
    q3_to_q25_1709 = abs(b["local_mesh_refinement"][1]["steps"]["1709"]["strain"]["peak_abs_principal_strain"] -
                         b["local_mesh_refinement"][0]["steps"]["1709"]["strain"]["peak_abs_principal_strain"]) / b["local_mesh_refinement"][0]["steps"]["1709"]["strain"]["peak_abs_principal_strain"]
    q3_to_q25_1869 = abs(b["local_mesh_refinement"][1]["steps"]["1869"]["strain"]["peak_abs_principal_strain"] -
                         b["local_mesh_refinement"][0]["steps"]["1869"]["strain"]["peak_abs_principal_strain"]) / b["local_mesh_refinement"][0]["steps"]["1869"]["strain"]["peak_abs_principal_strain"]
    max_resid = max(
        b["q5_step_comparisons"]["1709"]["load_controlled_with_bb_q5"]["solve_residual"],
        b["q5_step_comparisons"]["1869"]["load_controlled_with_bb_q5"]["solve_residual"],
        b["local_mesh_refinement"][0]["solve_residual"],
        b["local_mesh_refinement"][1]["solve_residual"],
    )

    checks = {
        "cad_hub_bore_measured_8p40mm": abs(b["cad_bore_check"]["hub_ring_bore_diameter_mm"] - 8.40) < 0.02,
        "backbone_EI_parallel_addition_lt_1pct": ei_add_err < 0.01,
        "all_pardiso_residuals_le_1e-10": max_resid <= 1e-10,
        "mesh_q3_to_q2p5_peak_change_lt_5pct": (q3_to_q25_1709 < 0.05) and (q3_to_q25_1869 < 0.05),
        "stride1_max_drop_le_0p001mm": bool(t["all_drops_le_0p001_mm"]),
        "stride1_zero_contacts": all(r["contacts_tilted"] == 0 for r in t["summary"]),
        "stride1_zero_below_0p025mm": all(r["below_0p025_mm"] == 0 for r in t["summary"]),
        "summary_figure_exists": (RES / "evening_20261126_summary.png").exists(),
    }
    val = dict(
        all_passed=all(checks.values()),
        checks=checks,
        metrics=dict(
            ei_parallel_rel_err=ei_add_err,
            max_solve_residual=max_resid,
            q3_to_q2p5_rel_change_1709=q3_to_q25_1709,
            q3_to_q2p5_rel_change_1869=q3_to_q25_1869,
            stride1_max_drop_mm=t["max_drop_vs_stride5_mm"],
        ),
    )
    (RES / "validation.json").write_text(json.dumps(val, indent=1, default=float))
    print("\n=== VALIDATION ===")
    print(json.dumps(val, indent=1, default=float))
    assert val["all_passed"], "Some validation checks failed!"


if __name__ == "__main__":
    main()
