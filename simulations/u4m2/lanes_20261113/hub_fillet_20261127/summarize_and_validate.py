"""Summarize, plot, and validate the 27 Nov 2026 sleeve-attached hub-strain convergence and fillet study."""
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
    s1 = json.loads((RES / "sleeve_hub_strain.json").read_text())
    s2 = json.loads((RES / "fillet_study.json").read_text())

    # --- 3-panel summary figure ---
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6), dpi=160)

    # Panel 1: Mesh convergence at step 1,869 (ring_0 vs ring_1, element peak & 0.5 mm gauge)
    ax = axes[0]
    x = np.arange(3)
    labels = ["q5\n(130k tets)", "q3\n(179k tets)", "q2.5/a0.25\n(246k tets)"]
    r0_pk = [lv["steps"]["1869"]["ring0_hotspot"]["peak_abs_principal_strain"] * 100 for lv in s1["levels"]]
    r1_pk = [lv["steps"]["1869"]["ring1_hotspot"]["peak_abs_principal_strain"] * 100 for lv in s1["levels"]]
    r0_g05 = [lv["steps"]["1869"]["ring0_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100 for lv in s1["levels"]]
    r1_g05 = [lv["steps"]["1869"]["ring1_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100 for lv in s1["levels"]]

    ax.plot(x, r0_pk, "o-", lw=2, color="#c0392b", label="ring_0 peak (r=8.5, z=-18.0)")
    ax.plot(x, r1_pk, "s-", lw=2, color="#2980b9", label="ring_1 peak (r=12.0, z=-5.2)")
    ax.plot(x, r0_g05, "o--", lw=1.6, color="#e74c3c", alpha=0.8, label="ring_0 0.5 mm gauge")
    ax.plot(x, r1_g05, "s--", lw=1.6, color="#3498db", alpha=0.8, label="ring_1 0.5 mm gauge")
    ax.axhspan(15 / 15.3, 18 / 15.3, color="#27ae60", alpha=0.18, label="PA12 fatigue (15-18 MPa)")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Principal strain (%)")
    ax.set_title("CAD sleeve (L=66 mm): mesh convergence (1,869)")
    ax.set_ylim(0, 4.4); ax.grid(True, alpha=0.3); ax.legend(fontsize=7.2, loc="center right")

    # Panel 2: Full 3,405-state mission envelope (q2.5/a0.25 with CAD sleeve)
    ax = axes[1]
    pk = np.load(RES / "strain_envelope_sleeve_q2p5.npz")["peak"] * 100
    ax.plot(np.arange(len(pk)), pk, lw=1.1, color="#c0392b", label="q2.5 + CAD sleeve (max 3.89%)")
    ax.axhline(3.0, ls="--", lw=0.9, color="#c0392b", alpha=0.5)
    ax.axhline(2.0, ls=":", lw=0.9, color="#e67e22", alpha=0.6)
    ax.axhspan(15 / 15.3, 18 / 15.3, color="#27ae60", alpha=0.18, label="PA12 fatigue band")
    ax.set_xlabel("Mission state")
    ax.set_ylabel("Peak |principal strain| (%)")
    ax.set_title("Full-mission envelope (602 > 3%, 1,063 > 2%)")
    ax.set_ylim(0, 4.4); ax.grid(True, alpha=0.3); ax.legend(fontsize=7.5, loc="upper right")

    # Panel 3: Stage 2 STL-boolean collar trials vs baseline (q3, step 1,869, 0.5 mm gauge)
    ax = axes[2]
    b_r0_g = s1["levels"][1]["steps"]["1869"]["ring0_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100
    b_r1_g = s1["levels"][1]["steps"]["1869"]["ring1_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100
    c0_r0_g = s2["candidates"][0]["levels"][0]["steps"]["1869"]["ring0_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100
    c0_r1_g = s2["candidates"][0]["levels"][0]["steps"]["1869"]["ring1_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100
    c1_r0_g = s2["candidates"][1]["levels"][0]["steps"]["1869"]["ring0_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100
    c1_r1_g = s2["candidates"][1]["levels"][0]["steps"]["1869"]["ring1_hotspot"]["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"] * 100

    x3 = np.arange(3); w = 0.34
    ax.bar(x3 - w / 2, [b_r0_g, c0_r0_g, c1_r0_g], w, color="#c0392b", label="ring_0 (0.5 mm gauge)")
    ax.bar(x3 + w / 2, [b_r1_g, c0_r1_g, c1_r1_g], w, color="#2980b9", label="ring_1 (0.5 mm gauge)")
    ax.axhspan(15 / 15.3, 18 / 15.3, color="#27ae60", alpha=0.18, label="PA12 fatigue band")
    ax.set_xticks(x3); ax.set_xticklabels(["Baseline\nCAD", "STL collar\nR=0.8 (rej.)", "STL collar+\narm R=1.0 (rej.)"], fontsize=8)
    ax.set_ylabel("0.5 mm gauge principal strain (%)")
    ax.set_title("Stage 2 STL-boolean collar trials (q3, 1,869)")
    ax.set_ylim(0, 1.8); ax.grid(True, axis="y", alpha=0.3); ax.legend(fontsize=7.2, loc="upper right")

    fig.tight_layout()
    fig.savefig(RES / "hub_fillet_20261127_summary.png", dpi=160)
    plt.close(fig)

    # --- Validation checks ---
    conv = s1["convergence_q3_to_q2p5"]
    max_res_s1 = max(lv["solve_residual"] for lv in s1["levels"])
    max_res_s2 = max(lv["solve_residual"] for c in s2["candidates"] for lv in c["levels"])
    checks = {
        "stage1_ring0_conv_lt_5pct_1709_1869": bool(conv["1709"]["ring0_hotspot"]["passes_5pct"] and conv["1869"]["ring0_hotspot"]["passes_5pct"]),
        "stage1_ring1_conv_lt_5pct_1709_1869": bool(conv["1709"]["ring1_hotspot"]["passes_5pct"] and conv["1869"]["ring1_hotspot"]["passes_5pct"]),
        "stage1_all_residuals_le_1e-10": bool(max_res_s1 <= 1e-10),
        "stage2_all_cad_watertight_single_body": bool(all(c["geometry"]["is_watertight"] and c["geometry"]["body_count"] == 1 for c in s2["candidates"])),
        "stage2_all_cad_bore_preserved_8p40mm": bool(all(c["geometry"]["bore_preserved_8p40mm"] for c in s2["candidates"])),
        "stage2_all_residuals_le_1e-10": bool(max_res_s2 <= 1e-10),
        "summary_figure_exists": (RES / "hub_fillet_20261127_summary.png").exists(),
    }
    ts = stamp()
    val = dict(
        completed_at_et=ts["et"],
        completed_at_utc=ts["utc"],
        all_passed=all(checks.values()),
        checks=checks,
        metrics=dict(
            ring0_q3_to_q2p5_1869=conv["1869"]["ring0_hotspot"]["rel_change"],
            ring1_q3_to_q2p5_1869=conv["1869"]["ring1_hotspot"]["rel_change"],
            finest_mission_max_pct=s1["finest_mesh_envelope"]["mission_max"]["peak"] * 100.0,
            finest_steps_above_3pct=s1["finest_mesh_envelope"]["steps_above_3pct"],
            finest_steps_above_2pct=s1["finest_mesh_envelope"]["steps_above_2pct"],
            max_solve_residual_s1=max_res_s1,
            max_solve_residual_s2=max_res_s2,
        ),
    )
    (RES / "validation.json").write_text(json.dumps(val, indent=1, default=float))
    print(json.dumps(val, indent=1, default=float))
    assert val["all_passed"], "Validation failed!"


if __name__ == "__main__":
    main()
