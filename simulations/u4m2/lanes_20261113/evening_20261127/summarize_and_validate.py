"""Summarise the evening 27 Nov 2026 hub-variant study and write results/validation.json + summary figure."""
import json, gzip
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = Path(__file__).resolve().parent; R = HERE / "results"
ARCH = HERE.parent / "hub_fillet_20261127/results/sleeve_hub_strain.json"
STEPS = ("1709", "1869", "1884")
SITES = ("global_max", "ring0_hotspot", "ring1_hotspot", "ring2_hotspot", "ring3_hotspot",
         "slot_root_ring0", "arch_crown_ring0", "slot_root_ring3", "arch_crown_ring3")


def load(n):
    p = R / n
    return json.loads(p.read_text()) if p.exists() else None


def hs(st, key):
    h = st[key]
    return dict(peak=h["peak_abs_principal_strain"], g05=h["finite_gauge_at_peak"]["r_0.5mm"]["tensor_avg_principal_strain"],
                g10=h["finite_gauge_at_peak"]["r_1.0mm"]["tensor_avg_principal_strain"], loc=h["peak_location_mm"],
                edge=h.get("peak_tet_mean_edge_mm"))


def main():
    br = load("brep_variants.json")
    runs = {k: load(f"fe_{k}.json") for k in ("baseline_q3", "baseline_q2p5", "slot_fill_q3", "slot_fill_q3_a025", "slot_fill_q2p5_a040")}
    runs = {k: v for k, v in runs.items() if v is not None}
    table = {}
    for k, d in runs.items():
        if d is None:
            continue
        L = d["levels"][0]
        table[k] = dict(tets=L["mesh"]["tets"], residual=L["solve_residual"], EI=L.get("equivalent_EI_over_85p8mm_Nmm2"),
                        added_volume_mm3=d["geometry"]["added_volume_mm3"], added_mass_g=d["geometry"]["added_mass_g"],
                        steps={s: {h: hs(L["steps"][s], h) for h in SITES if h in L["steps"][s]} for s in STEPS})
    arch = json.loads(ARCH.read_text())
    arch_q3 = {s: dict(ring0=arch["levels"][1]["steps"][s]["ring0_hotspot"]["peak_abs_principal_strain"],
                       ring1=arch["levels"][1]["steps"][s]["ring1_hotspot"]["peak_abs_principal_strain"]) for s in ("1709", "1869")}
    conv = {}
    for v, fine in (("baseline", "baseline_q2p5"), ("slot_fill", "slot_fill_q2p5_a040")):
        a, b = table.get(f"{v}_q3"), table.get(fine)
        if a and b:
            conv[v] = dict(fine_level=fine, steps={s: {h: dict(q3=a["steps"][s][h]["peak"], fine=b["steps"][s][h]["peak"],
                                   change=(b["steps"][s][h]["peak"] / a["steps"][s][h]["peak"] - 1),
                                   g05_q3=a["steps"][s][h]["g05"], g05_fine=b["steps"][s][h]["g05"])
                           for h in ("slot_root_ring0", "arch_crown_ring0", "ring1_hotspot", "arch_crown_ring3")} for s in STEPS})
    summary = dict(brep=br, fe=table, archived_q3_hub_fillet_20261127=arch_q3, convergence_q3_to_q2p5=conv)
    (R / "summary.json").write_text(json.dumps(summary, indent=1, default=float))

    b0 = table["baseline_q3"]["steps"]["1869"]
    checks = {
        "frame_check_step_vs_fe_stl_max_dev_lt_0p005mm": br["frame_check"]["max_dev_mm"] < 0.005,
        "brep_fillet_R0p14_valid_single_solid": br["variants"]["fillet_R0p14"].get("valid") is True and br["variants"]["fillet_R0p14"]["n_solids"] == 1,
        "brep_fillet_R_ge_0p25_rejected_visible": br["variants"]["fillet_R0p25"].get("valid") is False and all(br["variants"][k]["build"] != "ok" for k in ("fillet_R0p30", "fillet_R0p50", "fillet_R0p80")),
        "brep_slot_fill_valid_single_solid": br["variants"]["slot_fill"]["valid"] and br["variants"]["slot_fill"]["n_solids"] == 1,
        "fe_slot_fill_watertight_single_body_bore": all(runs[k]["geometry"]["is_watertight"] and runs[k]["geometry"]["body_count"] == 1 and runs[k]["geometry"]["bore_preserved_8p40mm"] for k in runs if runs[k] and "slot" in k),
        "fe_residuals_lt_1e-9": all(t["residual"] < 1e-9 for t in table.values()),
        "baseline_q3_reproduces_archive_within_3pct": all(abs(table["baseline_q3"]["steps"][s][h + "_hotspot"]["peak"] / arch_q3[s][h] - 1) < 0.03 for s in ("1709", "1869") for h in ("ring0", "ring1")),
        "baseline_q3_ring0_at_slot_root_corner": abs(b0["ring0_hotspot"]["loc"][2] + 18.0) < 0.1,
    }
    if conv:
        checks["baseline_q3_to_q2p5_element_peaks_change_lt_5pct"] = all(abs(conv["baseline"]["steps"][s][h]["change"]) < 0.05 for s in STEPS for h in ("slot_root_ring0", "arch_crown_ring0", "ring1_hotspot", "arch_crown_ring3"))
        checks["baseline_arch_crown_ring0_g05_change_lt_5pct (FAIL kept visible: gauge not converged)"] = all(abs(conv["baseline"]["steps"][s]["arch_crown_ring0"]["g05_fine"] / conv["baseline"]["steps"][s]["arch_crown_ring0"]["g05_q3"] - 1) < 0.05 for s in STEPS)
        checks["slot_fill_arch_crown_ring0_element_peak_change_lt_5pct (FAIL kept visible)"] = all(abs(conv["slot_fill"]["steps"][s]["arch_crown_ring0"]["change"]) < 0.05 for s in STEPS)
        checks["baseline_arch_crown_ring0_is_max_0p5mm_gauge_site"] = all(table["baseline_q2p5"]["steps"][s]["arch_crown_ring0"]["g05"] > max(table["baseline_q2p5"]["steps"][s][h]["g05"] for h in ("ring0_hotspot", "ring1_hotspot", "ring2_hotspot")) for s in STEPS)
    sf = table.get("slot_fill_q3")
    if sf:
        checks["slot_fill_removes_slot_root_corner_peak_gt_25pct_q3"] = all(sf["steps"][s]["slot_root_ring0"]["peak"] < 0.75 * table["baseline_q3"]["steps"][s]["slot_root_ring0"]["peak"] for s in STEPS)
        checks["slot_fill_rejected_arch_crown_g05_increases_q3"] = all(sf["steps"][s]["arch_crown_ring0"]["g05"] > table["baseline_q3"]["steps"][s]["arch_crown_ring0"]["g05"] for s in STEPS)
    vis = [k for k in checks if "FAIL kept visible" in k]
    (R / "validation.json").write_text(json.dumps(dict(checks=checks, all_pass=all(checks.values()),
        required_pass=all(v for k, v in checks.items() if k not in vis), informational_convergence_checks=vis), indent=1))
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)

    # figure
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    labels = [k for k in ("baseline_q3", "baseline_q2p5", "slot_fill_q3", "slot_fill_q2p5_a040") if k in table]
    x = np.arange(len(labels)); w = 0.2
    w = 0.2
    for i, (h, nm) in enumerate([("slot_root_ring0", "slot root (ring_0 end)"), ("arch_crown_ring0", "arch crown (ring_0 end)"), ("ring1_hotspot", "ring_1"), ("arch_crown_ring3", "arch crown (ring_3 end)")]):
        ax[0].bar(x + (i - 1.5) * w, [100 * table[l]["steps"]["1869"][h]["peak"] for l in labels], w, label=f"{nm} element peak")
        ax[1].bar(x + (i - 1.5) * w, [100 * table[l]["steps"]["1869"][h]["g05"] for l in labels], w, label=f"{nm} 0.5 mm gauge")
    ax[1].axhspan(0.98, 1.18, color="0.85", label="PA12 endurance band (~0.98-1.18%)")
    for a, t in zip(ax, ("Peak principal strain, step 1,869 (%)", "0.5 mm finite-gauge strain, step 1,869 (%)")):
        a.set_xticks(x); a.set_xticklabels(labels, rotation=15); a.set_title(t, fontsize=10); a.legend(fontsize=8)
    fig.suptitle("M6 hub pocket: baseline (0.30 mm rib/socket slot) vs native B-Rep slot fill - evening 27 Nov 2026", fontsize=10)
    fig.tight_layout(); fig.savefig(R / "evening_20261127_summary.png", dpi=110)


if __name__ == "__main__":
    main()
