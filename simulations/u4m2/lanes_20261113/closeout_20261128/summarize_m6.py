"""Apply the convergence and candidate checks to the completed M6 solver records."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


OUT = Path(__file__).resolve().parent / "results"
LEVELS = ("global", "local_0.28", "local_0.18")
VARIANTS = ("native_control", "radius_2p0", "depth_0p42")
GAUGE_LIMIT = 0.012
REFINEMENT_LIMIT = 0.05


def load(name):
    return json.loads((OUT / ("crown_" + name + ".json")).read_text())


def metric_vector(row):
    return np.array([value for _, radii in sorted(row["gauges"].items())
                     for _, data in sorted(radii.items())
                     for value in data["three_states_abs_principal"]])


def max_gauge(row, mission=False, native_peaks=True):
    values = [
        value
        for site, gauge in row["gauges"].items()
        if native_peaks or not site.startswith("at_element_peak_")
        for value in ([gauge["0.5"]["mission_max"]] if mission else gauge["0.5"]["three_states_abs_principal"])
    ]
    return float(max(values))


def main():
    levels = list(map(load, LEVELS))
    geometry = json.loads((OUT / "crown_cad" / "geometry.json").read_text())
    changes = [
        float(np.max(abs(metric_vector(b) / metric_vector(a) - 1)))
        for a, b in zip(levels, levels[1:])
    ]
    passes = max(changes) < REFINEMENT_LIMIT
    control = load(VARIANTS[0])
    screening = {}
    for variant in VARIANTS[1:]:
        result = load(variant)
        limit = max_gauge(result)
        accepted = (
            passes and geometry["variants"][variant]["valid"] and limit <= GAUGE_LIMIT
            and result["linear_rod_clearance"]["min_mm"] >= 0.25
        )
        screening[variant] = dict(
            maximum_0p5mm_fixed_critical_strain=max_gauge(result, native_peaks=False),
            maximum_0p5mm_critical_strain_including_displaced_hotspots=limit,
            maximum_0p5mm_mission_projection=max_gauge(result, mission=True),
            EI_change_percent=(100 * (np.array(result["combined_EI_Nmm2"])
                                      / np.array(control["combined_EI_Nmm2"]) - 1)).tolist(),
            added_PA12_g=geometry["variants"][variant]["PA12_added_g"],
            linear_rod_gap_mm=result["linear_rod_clearance"]["min_mm"],
            numerical_triage_pass=accepted,
            requires_refined_candidate_and_motion_check=True,
        )

    report = dict(
        convergence=dict(meshes=LEVELS, max_relative_changes=changes,
                         threshold=REFINEMENT_LIMIT, pass_gate=passes,
                         fixed_gauge_sites=len(levels[-1]["gauges"]),
                         selected_steps=levels[-1]["selected_states"],
                         finest_fixed_crown_max=max_gauge(levels[-1]),
                         finest_mission_projection=max_gauge(levels[-1], mission=True)),
        native_control=dict(critical_gauge_max=max_gauge(control),
                            critical_fixed_gauge_max=max_gauge(control, native_peaks=False),
                            mission_max_gauge=max_gauge(control, mission=True),
                            EI_Nmm2=control["combined_EI_Nmm2"],
                            linear_rod_gap_mm=control["linear_rod_clearance"]["min_mm"]),
        candidate_gauge_screen_limit=GAUGE_LIMIT, candidates=screening,
    )
    (OUT / "M6_decision.json").write_text(json.dumps(report, indent=2) + "\n")

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.8, 4.4), layout="constrained")
    for name, label, color in (("ring0_arch", "Proximal crown", "#126b73"),
                               ("ring0_opposed_arch", "Opposite proximal crown", "#d87940"),
                               ("ring3_arch", "Distal crown", "#6a5d9a"),
                               ("ring3_opposed_arch", "Opposite distal crown", "#739047")):
        left.plot(
            range(3), [100 * d["gauges"][name]["0.5"]["three_states_abs_principal"][1] for d in levels],
            marker="o", lw=2, label=label, color=color,
        )
    left.set_xticks(range(3), ["Global", "Local 0.28", "Local 0.18"])
    left.set(ylabel="0.5 mm gauge strain (%)", title="Fixed locations at solver step 1,869")
    left.grid(axis="y", alpha=0.24)
    left.legend(frameon=False, fontsize=8)
    ordered = [control, *[load(name) for name in VARIANTS[1:]]]
    values = [100 * max_gauge(r) for r in ordered]
    bars = right.bar(["Control", "R2.0", "+0.42 mm"], values,
                     color=["#6b7d89", "#126b73", "#d87940"], width=0.61)
    right.bar_label(bars, fmt="%.2f%%", padding=3)
    right.axhline(GAUGE_LIMIT * 100, color="#a23c44", ls="--", label="1.2% screening target")
    right.set_ylim(0, max(values) * 1.22)
    right.set(ylabel="Maximum 0.5 mm gauge strain (%)", title="Matched native-CAD screens")
    right.legend(loc="lower left", frameon=False, fontsize=8)
    right.grid(axis="y", alpha=0.24)
    for axes in (left, right):
        axes.spines[["top", "right"]].set_visible(False)
    fig.suptitle("M6 arch crown strain under archived 500 g mission loads", fontsize=13, fontweight="bold")
    fig.savefig(OUT / "M6_crown_comparison.png", dpi=160)
    plt.close(fig)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
