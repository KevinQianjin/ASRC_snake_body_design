"""Summarize, plot, and validate the Morning 2026-11-27 coupled nonlinear M6 body + NiTi backbone study."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"


def stamp():
    now = datetime.now(timezone.utc)
    return dict(
        et=now.astimezone(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def main():
    d = json.loads((RES / "coupled_nonlinear.json").read_text())
    rows = d["mission_sweep_rows"]
    steps = np.array([r["step"] for r in rows])
    gaps = np.array([r["gaps_mm"] for r in rows])  # (M, 4)
    n_rod = np.array([r["rod_axial_force_mean_N"] for r in rows])
    tau = np.array([r["sleeve_bond_avg_shear_MPa"] for r in rows])
    eps = np.array([r["max_niti_bending_strain"] * 100.0 for r in rows])

    # --- 3-panel summary figure ---
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), dpi=160)

    # Panel 1: Ring gaps across the mission
    ax = axes[0]
    colors = ["#2980b9", "#c0392b", "#e67e22", "#27ae60"]
    for j in range(4):
        ax.plot(steps, gaps[:, j], lw=1.4, color=colors[j], label=f"ring_{j}")
    ax.axhline(0.25, ls="--", lw=1.0, color="#c0392b", alpha=0.7, label="0.25 mm acceptance")
    ax.axhline(0.393, ls=":", lw=1.0, color="#7f8c8d", label="26 Nov uncoupled min (0.39 mm)")
    ax.set_xlabel("Mission state")
    ax.set_ylabel("Radial bore gap (mm)")
    ax.set_title("Coupled nonlinear ring gaps (183 states)")
    ax.set_ylim(0, 3.4)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7.5, loc="lower left")

    # Panel 2: Rod axial force & sleeve-bond shear
    ax = axes[1]
    ax.plot(steps, n_rod, lw=1.4, color="#2980b9", label="Rod axial force N_rod (N)")
    ax.set_xlabel("Mission state")
    ax.set_ylabel("Rod axial force (N)", color="#2980b9")
    ax.tick_params(axis="y", labelcolor="#2980b9")
    ax.set_title("Coupled axial compatibility (max 3.52 N)")
    ax.grid(True, alpha=0.3)
    ax2 = ax.twinx()
    ax2.plot(steps, tau, lw=1.0, ls="--", color="#c0392b", alpha=0.8, label="Sleeve shear (MPa)")
    ax2.set_ylabel("Sleeve-bond avg shear (MPa)", color="#c0392b")
    ax2.tick_params(axis="y", labelcolor="#c0392b")

    # Panel 3: Step 1,866 comparison (uncoupled vs coupled h=1.0 / h=0.5 / follower)
    ax = axes[2]
    cs = d["convergence_and_sensitivity"]["1866"]
    labels = ["26 Nov\nuncoupled\n(float)", "Coupled\nh=1.0 mm\n(D0 wrench)", "Coupled\nh=0.5 mm\n(D0 wrench)", "Coupled\nh=1.0 mm\n(follower)"]
    vals = [0.393, cs["h1p0"]["min_gap_mm"], cs["h0p5"]["min_gap_mm"], cs["follower_wrench"]["min_gap_mm"]]
    bar_colors = ["#95a5a6", "#2980b9", "#1f618d", "#27ae60"]
    bars = ax.bar(np.arange(4), vals, width=0.55, color=bar_colors)
    ax.axhline(0.25, ls="--", lw=1.0, color="#c0392b", label="0.25 mm acceptance")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.025, f"{v:.3f}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(np.arange(4))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Min ring_1 gap at step 1,866 (mm)")
    ax.set_title("Step 1,866 (46.7°) sensitivity & convergence")
    ax.set_ylim(0, 1.15)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=7.5, loc="upper right")

    fig.tight_layout()
    fig.savefig(RES / "morning_20261127_summary.png", dpi=160)
    plt.close(fig)

    # --- Validation checks ---
    lv = d["linear_verification_below_15deg"]
    ms = d["mission_sweep_summary"]
    max_res_sweep = max(r["res_inf"] for r in rows)
    max_res_conv = max(
        d["convergence_and_sensitivity"][s][k]["res_inf"]
        for s in ("1709", "1866", "1869")
        for k in ("h1p0", "h0p5", "follower_wrench")
    )
    min_gap_all_variants = min(
        ms["worst_gap"]["min_gap_mm"],
        *(d["convergence_and_sensitivity"][s][k]["min_gap_mm"]
          for s in ("1709", "1866", "1869")
          for k in ("h1p0", "h0p5", "follower_wrench")),
    )
    checks = {
        "linear_small_angle_2p3deg_lt_2pct": bool(lv["small_angle_2p3deg_raw_pos_rel_err"] < 0.02 and lv["small_angle_2p3deg_raw_rot_rel_err"] < 0.02),
        "linear_below_15deg_lifted_3d_lt_2pct": bool(lv["max_lifted_3d_rel_err"] < 0.02),
        "linear_below_15deg_rot_lt_2pct": bool(lv["max_rot_rel_err"] < 0.02),
        "all_newton_residuals_le_1e-6": bool(max(max_res_sweep, max_res_conv) <= 1e-6),
        "min_gap_ge_0p25mm_all_variants": bool(min_gap_all_variants >= 0.25),
        "zero_bore_contact_all_states": bool(ms["zero_contact_states"] == ms["n_states"]),
        "rod_axial_force_physical_lt_20N": bool(abs(ms["max_axial_force"]["rod_axial_force_mean_N"]) < 20.0),
        "summary_figure_exists": (RES / "morning_20261127_summary.png").exists(),
    }
    ts = stamp()
    val = dict(
        completed_at_et=ts["et"],
        completed_at_utc=ts["utc"],
        all_passed=all(checks.values()),
        checks=checks,
        metrics=dict(
            small_angle_pos_rel_err=lv["small_angle_2p3deg_raw_pos_rel_err"],
            below_15deg_max_lifted_3d_rel_err=lv["max_lifted_3d_rel_err"],
            below_15deg_max_rot_rel_err=lv["max_rot_rel_err"],
            max_newton_residual=max(max_res_sweep, max_res_conv),
            min_gap_sweep_mm=ms["worst_gap"]["min_gap_mm"],
            min_gap_all_variants_mm=min_gap_all_variants,
            max_rod_axial_force_N=abs(ms["max_axial_force"]["rod_axial_force_mean_N"]),
            max_sleeve_bond_shear_MPa=ms["max_axial_force"]["sleeve_bond_avg_shear_MPa"],
            max_niti_bending_strain_pct=ms["max_niti_bending_strain"]["max_niti_bending_strain"] * 100.0,
        ),
    )
    (RES / "validation.json").write_text(json.dumps(val, indent=1, default=float))
    print(json.dumps(val, indent=1, default=float))
    assert val["all_passed"], "Some validation checks failed!"


if __name__ == "__main__":
    main()
