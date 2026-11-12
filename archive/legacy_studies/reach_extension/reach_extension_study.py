"""Compare the existing 31-module design with longer, rear-stiffened layouts.

This is a planar screening study using the project's original CRAFT module
data and rear-backbone beam solver. It compares self-weight alone and a 500 g
tip payload. It does not include tendons, entry geometry, contact, or 3D
maneuvering. The 32 mm capsule envelope and 205 MPa 304 reference-yield screen
match the existing studies.

Run with the project's NumPy/SciPy/Matplotlib environment:
    python reach_extension_study.py
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'simulations' / 'shared' / 'legacy_models'))
import snake_model_rear_backbone as R

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "results"
TOTALS = (31, 34, 36, 38)
FRONT_COUNTS = (2, 3, 4, 5, 6, 8, 11)
BACKBONE_DIAMETERS_MM = (4.2, 5.0, 6.0, 7.0, 8.0)
TIP_PAYLOADS_KG = (0.0, 0.5)
ENVELOPE_MM = (1600.0, 830.0, 300.0)  # X reach, Z width, Y height
BODY_DIAMETER_MM = 32.0


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def add_envelope(solution: dict, rows: list[dict], inspection=ENVELOPE_MM) -> list[dict]:
    length, phi = solution["length"], solution["phi"]
    x = np.cumsum(length * np.cos(phi), axis=1) * 1000
    y = np.cumsum(length * np.sin(phi), axis=1) * 1000
    xmin = np.minimum(0, x.min(axis=1))
    xmax = np.maximum(0, x.max(axis=1))
    ymin = np.minimum(0, y.min(axis=1))
    ymax = np.maximum(0, y.max(axis=1))
    for i, row in enumerate(rows):
        row["capsule_horizontal_span_mm"] = float(xmax[i] - xmin[i] + BODY_DIAMETER_MM)
        row["capsule_vertical_span_mm"] = float(ymax[i] - ymin[i] + BODY_DIAMETER_MM)
        row["capsule_width_mm"] = BODY_DIAMETER_MM
        row["passes_empty_box_envelope_screen"] = bool(
            row["capsule_horizontal_span_mm"] <= inspection[0]
            and row["capsule_width_mm"] <= inspection[1]
            and row["capsule_vertical_span_mm"] <= inspection[2]
        )
        row["passes_combined_screen"] = bool(
            row["converged"] and row["passes_reference_yield_screen"]
            and row["passes_empty_box_envelope_screen"]
        )
        row["passes_reach_target_screen"] = bool(
            row["converged"] and row["tip_x_mm"] >= inspection[0]
            and row["capsule_vertical_span_mm"] <= inspection[2]
            and row["capsule_width_mm"] <= inspection[1]
            and row["passes_reference_yield_screen"]
        )
    return rows


def solve_counts_with_tip_payload(counts, config: dict, material: dict, payload_kg: float):
    """Same chain equilibrium as solve_cells, with a point load at the tip.

    A tip payload contributes g*m*length[i] to every cell's gravity moment
    coefficient. This follows the existing energy/gradient convention exactly.
    """
    body = R.build_cells(counts, config, material)
    length, mass, k = body["length"], body["mass"], body["k"]
    gravity = float(config["gravity_m_s2"])
    solver = config["solver"]
    steps = int(solver["gravity_steps"])
    max_iterations = int(solver["max_iterations"])
    tolerance = float(solver["moment_tolerance_nm"])
    a_full = gravity * length * (
        np.cumsum(mass[:, ::-1], axis=1)[:, ::-1] - .5 * mass + payload_kg)
    phi = np.zeros_like(length)
    elastic_diag = k.copy()
    elastic_diag[:, :-1] += k[:, 1:]
    off = -k[:, 1:]
    iterations = np.zeros(len(phi), dtype=int)
    for factor in np.linspace(1 / steps, 1, steps):
        a = a_full * factor
        for _ in range(max_iterations):
            grad = R.S.elastic_gradient(phi, k) + a * np.cos(phi)
            active = np.max(np.abs(grad), axis=1) > tolerance
            if not active.any():
                break
            ids = np.flatnonzero(active)
            p, ka, aa, gg = phi[ids], k[ids], a[ids], grad[ids]
            diag = elastic_diag[ids] - aa * np.sin(p)
            step = R.S.tridiagonal_solve(diag, off[ids], gg)
            bound = np.full_like(step, np.inf)
            np.divide(p + np.pi / 2, step, out=bound, where=step > 1e-16)
            upper = np.full_like(step, np.inf)
            np.divide(-p, -step, out=upper, where=step < -1e-16)
            alpha = np.minimum(1., .99 * np.min(np.minimum(bound, upper), axis=1))
            old_energy = R.S.energy(p, ka, aa)
            decrease = np.sum(gg * step, axis=1)
            for _ in range(40):
                candidate = p - alpha[:, None] * step
                trial_energy = R.S.energy(candidate, ka, aa)
                accepted = trial_energy <= old_energy - 1e-4 * alpha * decrease + 1e-14
                if accepted.all():
                    break
                alpha[~accepted] *= .5
            phi[ids] = candidate
            iterations[ids] += 1
    residual = np.max(np.abs(R.S.elastic_gradient(phi, k) + a_full * np.cos(phi)), axis=1)
    angles = np.diff(phi, prepend=np.zeros((len(phi), 1)), axis=1)
    converged = (np.isfinite(phi).all(axis=1) & (residual <= tolerance)
                 & (phi.min(axis=1) >= -np.pi / 2 - 1e-12)
                 & (phi.max(axis=1) <= 1e-12) & (angles.max(axis=1) <= 1e-9))
    solution = dict(phi=phi,
                    tip_drop_mm=-np.sum(length * np.sin(phi), axis=1) * 1000,
                    tip_x_mm=np.sum(length * np.cos(phi), axis=1) * 1000,
                    converged=converged, moment_residual_nm=residual,
                    iterations=iterations)
    solution.update(body)
    solution["tip_payload_kg"] = payload_kg
    return solution


def configuration_groups(config: dict):
    """Yield count batches with fixed total length and fixed flexible front."""
    for total in TOTALS:
        for front in FRONT_COUNTS:
            rear = total - front
            if rear < 2:
                continue
            cfg = json.loads(json.dumps(config))
            cfg["front"]["modules"] = front
            cfg["focus_total_modules"] = total
            counts = list(R.count_combinations(rear, front))
            yield total, front, cfg, counts


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["total_modules"], row["front_modules"], row["backbone_diameter_mm"], row["tip_payload_g"])].append(row)
    out = []
    for (total, front, diameter, payload_g), items in sorted(groups.items()):
        valid = [r for r in items if r["converged"]]
        elastic = [r for r in valid if r["passes_reference_yield_screen"]]
        cross_section = [r for r in elastic if r["capsule_vertical_span_mm"] <= ENVELOPE_MM[2]
                         and r["capsule_width_mm"] <= ENVELOPE_MM[1]]
        combined = [r for r in elastic if r["passes_empty_box_envelope_screen"]]
        best = max(valid, key=lambda r: r["tip_x_mm"], default=None)
        best_elastic = max(elastic, key=lambda r: r["tip_x_mm"], default=None)
        best_combined = max(combined, key=lambda r: r["tip_x_mm"], default=None)
        record = dict(total_modules=total, reference_length_mm=total * 48,
                      flexible_front_modules=front, rear_modules=total-front,
                      backbone_diameter_mm=diameter, tip_payload_g=payload_g, combinations=len(items),
                      converged=len(valid), yield_screen_passes=len(elastic),
                      yield_and_cross_section_passes=len(cross_section),
                      combined_screen_passes=len(combined),
                      reach_target_screen_passes=sum(r["passes_reach_target_screen"] for r in items))
        target_candidates = [r for r in items if r["passes_reach_target_screen"]]
        if target_candidates:
            best_target = min(target_candidates, key=lambda r: r["total_system_mass_g"])
            record["lightest_target_configuration"] = best_target["combination"]
            record["lightest_target_mass_g"] = best_target["total_system_mass_g"]
            record["lightest_target_tip_x_mm"] = best_target["tip_x_mm"]
            record["lightest_target_drop_mm"] = best_target["tip_drop_mm"]
        else:
            record["lightest_target_configuration"] = None
            record["lightest_target_mass_g"] = None
            record["lightest_target_tip_x_mm"] = None
            record["lightest_target_drop_mm"] = None
        for prefix, candidate in (("max_reach_any", best), ("max_reach_yield_screened", best_elastic),
                                  ("max_reach_yield_and_cross_section", max(cross_section, key=lambda r: r["tip_x_mm"], default=None)),
                                  ("max_reach_combined_screened", best_combined)):
            if candidate:
                record[f"{prefix}_mm"] = candidate["tip_x_mm"]
                record[f"{prefix}_drop_mm"] = candidate["tip_drop_mm"]
                record[f"{prefix}_stress_mpa"] = candidate["max_core_stress_mpa"]
                record[f"{prefix}_configuration"] = candidate["combination"]
            else:
                record[f"{prefix}_mm"] = None
                record[f"{prefix}_drop_mm"] = None
                record[f"{prefix}_stress_mpa"] = None
                record[f"{prefix}_configuration"] = None
        out.append(record)
    return out


def mark_longitudinal_extension(rows: list[dict]) -> None:
    """Add a controlled comparison that preserves the reference front stack."""
    for row in rows:
        h, u, d, low = (row["n_high"], row["n_uni"], row["n_directional"], row["n_low"])
        row["reference_front_stack"] = d == 8 and low == 3
        row["reference_rear_split"] = row["reference_front_stack"] and h == 8
        row["extended_reference_stack"] = row["reference_rear_split"]


def make_plots(rows: list[dict], summaries: list[dict], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {4.2: "#2878b5", 5.0: "#e28e2c", 6.0: "#3a9d68", 7.0: "#9867b2", 8.0: "#d65f5f"}
    fronts = {2: "o", 3: "v", 4: "s", 5: "P", 6: "^", 8: "D", 11: "X"}
    base = next((r for r in rows if r["total_modules"] == 31 and r["backbone_diameter_mm"] == 4.2
                 and r["combination"] == "H8-U12-D8-L3"), None)

    # Reach and sag versus total nominal length. The root may remain outside
    # the tank, so use the yield and Y/Z cross-section screens here; retain the
    # whole-body box screen separately in the CSV for fully-inside comparisons.
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
    for diameter in BACKBONE_DIAMETERS_MM:
        grouped = [s for s in summaries if s["backbone_diameter_mm"] == diameter and s["tip_payload_g"] == 0]
        by_total = defaultdict(list)
        for s in grouped:
            by_total[s["total_modules"]].append(s)
        xs, ys, drops, drop_y = [], [], [], []
        for total in TOTALS:
            candidates = [s for s in by_total[total] if s["max_reach_yield_and_cross_section_mm"] is not None]
            if candidates:
                chosen = max(candidates, key=lambda s: s["max_reach_yield_and_cross_section_mm"])
                xs.append(total * 48); ys.append(chosen["max_reach_yield_and_cross_section_mm"])
                drops.append(total * 48); drop_y.append(chosen["max_reach_yield_and_cross_section_drop_mm"])
        if xs:
            axes[0].plot(xs, ys, marker="o", color=colors[diameter],
                         label=f"{diameter:g} mm core · yield + cross-section pass")
            axes[1].plot(drops, drop_y, marker="o", color=colors[diameter],
                         label=f"{diameter:g} mm core · yield + cross-section pass")
    if base:
        axes[0].scatter([base["total_length_mm"]], [base["tip_x_mm"]], s=100, marker="*", color="#b3212d",
                        edgecolor="white", zorder=5, label="Previous D build H8/U12/D8/L3")
        axes[1].scatter([base["total_length_mm"]], [base["tip_drop_mm"]], s=100, marker="*", color="#b3212d",
                        edgecolor="white", zorder=5, label="Previous D build H8/U12/D8/L3")
    axes[0].axhline(1600, color="#555", ls=":", label="1,600 mm reach target")
    axes[0].set(xlabel="Nominal body length (mm)", ylabel="Horizontal tip reach X (mm)",
                title="Reach under self-weight")
    axes[1].axhline(268, color="#7a3333", ls=":", label="300 mm clearance minus 32 mm body")
    axes[1].set(xlabel="Nominal body length (mm)", ylabel="Tip drop (mm)", title="Sag versus 300 mm height limit")
    for ax in axes:
        ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.suptitle("Longer body + stiff rear + flexible front: gravity-only screening")
    fig.savefig(output / "reach_vs_length.png", dpi=180)
    plt.close(fig)

    # All simulated designs, with the target box's maximum centerline drop.
    fig, ax = plt.subplots(figsize=(10.5, 6.4), constrained_layout=True)
    for diameter in BACKBONE_DIAMETERS_MM:
        for front in (2, 4, 6, 11):
            subset = [r for r in rows if r["backbone_diameter_mm"] == diameter
                      and r["front_modules"] == front and r["converged"] and r["tip_payload_g"] == 0]
            if not subset:
                continue
            ax.scatter([r["tip_x_mm"] for r in subset], [r["tip_drop_mm"] for r in subset],
                       s=13, alpha=.22, color=colors[diameter], marker=fronts[front],
                       label=f"{diameter:g} mm core, {front} front" )
    ax.axhline(268, color="#7a3333", ls="--", label="300 mm tank height (centerline limit 268 mm)")
    ax.axvline(1600, color="#333", ls=":", label="1,600 mm length")
    if base:
        ax.scatter(base["tip_x_mm"], base["tip_drop_mm"], s=160, marker="*", color="#b3212d",
                   edgecolor="white", zorder=6, label="Previous D build")
    ax.set(xlabel="Horizontal tip reach X (mm)", ylabel="Tip drop (mm)",
           title="Reach–sag trade-off across module layouts")
    ax.grid(alpha=.25)
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    fig.savefig(output / "reach_sag_tradeoff.png", dpi=180)
    plt.close(fig)

    # A compact design table plot for the fixed H8/D8/L3 stack while adding rear
    # unidirectional modules, plus the best combined-screen design at each N.
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5), constrained_layout=True)
    for diameter in BACKBONE_DIAMETERS_MM:
        controlled = []
        for total in TOTALS:
            u = total - 19
            target_name = f"H8-U{u}-D8-L3"
            found = next((r for r in rows if r["total_modules"] == total and r["backbone_diameter_mm"] == diameter
                          and r["tip_payload_g"] == 0 and r["combination"] == target_name), None)
            if found:
                controlled.append(found)
        if controlled:
            xx = [r["total_length_mm"] for r in controlled]
            axes[0].plot(xx, [r["tip_x_mm"] for r in controlled], marker="s", color=colors[diameter],
                         label=f"H8/U(N−19)/D8/L3 · {diameter:g} mm")
            axes[1].plot(xx, [r["max_core_stress_mpa"] for r in controlled], marker="s", color=colors[diameter],
                         label=f"H8/U(N−19)/D8/L3 · {diameter:g} mm")
    axes[0].axhline(1600, color="#555", ls=":", label="1,600 mm length")
    axes[1].axhline(205, color="#7a3333", ls="--", label="304 reference yield 205 MPa")
    axes[0].set(xlabel="Nominal body length (mm)", ylabel="Horizontal reach X (mm)",
                title="Keep reference flexible front, add stiff rear modules")
    axes[1].set(xlabel="Nominal body length (mm)", ylabel="Peak 304 core stress (MPa)",
                title="Stress cost of longer core")
    for ax in axes:
        ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.savefig(output / "reference_stack_extension.png", dpi=180)
    plt.close(fig)

    # Head-load penalty for candidate designs, paired against the same
    # 0 g configurations. This graph makes the screening status visible.
    by_case = {(r["total_modules"], r["combination"], r["backbone_diameter_mm"], r["tip_payload_g"]): r
               for r in rows}
    candidates = []
    for r in rows:
        if r["tip_payload_g"] != 0:
            continue
        counterpart = by_case.get((r["total_modules"], r["combination"],
                                   r["backbone_diameter_mm"], 500))
        if counterpart:
            candidates.append((r, counterpart))
    selected = []
    for total in TOTALS:
        pairs = [pair for pair in candidates if pair[0]["total_modules"] == total
                 and pair[0]["passes_reference_yield_screen"]
                 and pair[0]["capsule_vertical_span_mm"] <= 300]
        if pairs:
            selected.append(max(pairs, key=lambda pair: pair[0]["tip_x_mm"]))
    fig, ax = plt.subplots(figsize=(10.5, 5.5), constrained_layout=True)
    for no_load, loaded in selected:
        label = f"N={no_load['total_modules']}, {no_load['combination']}, {no_load['backbone_diameter_mm']:g} mm core"
        ax.plot([no_load["tip_x_mm"], loaded["tip_x_mm"]],
                [no_load["tip_drop_mm"], loaded["tip_drop_mm"]], color="#7b8794", lw=1.3)
        ax.scatter(no_load["tip_x_mm"], no_load["tip_drop_mm"], marker="o", s=60,
                   color="#2d8a55", label=label + " · 0 g")
        ax.scatter(loaded["tip_x_mm"], loaded["tip_drop_mm"], marker="X", s=75,
                   color="#b83b3b", label=label + " · 500 g")
    ax.axhline(268, color="#7a3333", ls="--", label="300 mm clearance (centerline drop ≤268 mm)")
    ax.axvline(1600, color="#333", ls=":", label="1,600 mm reach target")
    ax.set(xlabel="Horizontal tip reach X (mm)", ylabel="Tip drop (mm)",
           title="Effect of a 500 g tip payload on the best gravity-screened layouts")
    ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.savefig(output / "payload_effect_on_candidates.png", dpi=180)
    plt.close(fig)

    # Direct target feasibility at 0 g and 500 g. This target screen assumes
    # the root can remain outside the tank, so it constrains tip X and the
    # tank cross-section rather than requiring the whole body to fit in X.
    fig, ax = plt.subplots(figsize=(9.5, 5.2), constrained_layout=True)
    payload_color = {0: "#247a48", 500: "#bd3d3d"}
    offsets = {0: -.14, 500: .14}
    for payload_g in (0, 500):
        counts_by_n = [sum(r["passes_reach_target_screen"] for r in rows
                           if r["total_modules"] == n and r["tip_payload_g"] == payload_g) for n in TOTALS]
        ax.bar(np.arange(len(TOTALS)) + offsets[payload_g], counts_by_n, width=.26,
               color=payload_color[payload_g], label=f"{payload_g} g tip payload")
    ax.set_xticks(np.arange(len(TOTALS)), [f"{n} modules\n{48*n} mm" for n in TOTALS])
    ax.set(ylabel="Layouts reaching 1,600 mm and passing height/yield screens",
           title="How many tested layouts meet the reach target?")
    ax.grid(axis="y", alpha=.25); ax.legend()
    fig.savefig(output / "reach_target_screen_counts.png", dpi=180)
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "rear_backbone_config.json")
    parser.add_argument("--catalog", type=Path, default=HERE / "rope_materials.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)

    base_config, _, catalog = R.read_inputs(args.config, args.catalog)
    material = next(m for m in catalog["materials"] if m["id"] == "ss304_annealed")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for diameter in BACKBONE_DIAMETERS_MM:
        for payload_kg in TIP_PAYLOADS_KG:
            for total, front, cfg, counts in configuration_groups(base_config):
                cfg["backbone"]["diameter_mm"] = diameter
                sol = solve_counts_with_tip_payload(counts, cfg, material, payload_kg)
                batch = add_envelope(sol, R.case_rows(sol, cfg))
                for row in batch:
                    row["backbone_diameter_mm"] = diameter
                    row["tip_payload_g"] = payload_kg * 1000
                    row["total_system_mass_g"] = row["total_mass_g"] + payload_kg * 1000
                    row["envelope_length_mm"] = ENVELOPE_MM[0]
                    row["envelope_width_mm"] = ENVELOPE_MM[1]
                    row["envelope_height_mm"] = ENVELOPE_MM[2]
                    row["tendons_included"] = False
                all_rows.extend(batch)
                print(f"N={total}, front={front}, core={diameter:g} mm, payload={payload_kg*1000:g} g: "
                      f"{sum(r['converged'] for r in batch)}/{len(batch)} converged; "
                      f"combined screen pass={sum(r['passes_combined_screen'] for r in batch)}", flush=True)

    mark_longitudinal_extension(all_rows)
    grouped = summarize(all_rows)
    write_csv(args.output_dir / "all_configurations.csv", all_rows)
    write_csv(args.output_dir / "summary_by_length_front_core.csv", grouped)
    write_csv(args.output_dir / "target_feasible_candidates.csv",
              [r for r in all_rows if r["passes_reach_target_screen"]])

    key_rows = [r for r in all_rows if r["reference_rear_split"] or r["combination"] == "H8-U12-D8-L3"]
    write_csv(args.output_dir / "reference_stack_candidates.csv", key_rows)
    summary = {
        "study": "longer body + rear backbone + flexible front module sweep",
        "scope": "planar gravity equilibrium; compares 0 g and 500 g tip payload; no tendons, entry/collision or 3D maneuvering",
        "envelope_mm": {"length_x": ENVELOPE_MM[0], "width_z": ENVELOPE_MM[1], "height_y": ENVELOPE_MM[2]},
        "module_length_assumption_mm": 48.0,
        "body_diameter_mm": BODY_DIAMETER_MM,
        "minimum_modules_for_1600mm_straight_path": int(np.ceil(ENVELOPE_MM[0] / 48.0)),
        "minimum_reference_length_mm_for_1600mm_straight_path": int(np.ceil(ENVELOPE_MM[0] / 48.0)) * 48,
        "total_module_counts": list(TOTALS),
        "flexible_front_counts": list(FRONT_COUNTS),
        "backbone_diameters_mm": list(BACKBONE_DIAMETERS_MM),
        "tip_payloads_g": [int(m * 1000) for m in TIP_PAYLOADS_KG],
        "configurations": len(all_rows),
        "combined_screen_passes": sum(r["passes_combined_screen"] for r in all_rows),
        "reach_target_screen_passes_by_payload_g": {str(int(p * 1000)): sum(
            r["passes_reach_target_screen"] for r in all_rows if r["tip_payload_g"] == p * 1000)
            for p in TIP_PAYLOADS_KG},
        "whole_body_box_screen_passes_by_payload_g": {str(int(p * 1000)): sum(
            r["passes_combined_screen"] for r in all_rows if r["tip_payload_g"] == p * 1000)
            for p in TIP_PAYLOADS_KG},
        "warning": "This is a passive gravity screen. Tendon actuation, actual entry position, contact and 3D path are not modeled; material properties are reference values, not hardware measurements.",
    }
    (args.output_dir / "study_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not args.no_plots:
        make_plots(all_rows, grouped, args.output_dir)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
