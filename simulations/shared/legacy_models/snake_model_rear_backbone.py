"""Rear-only SS304 backbone with an 11-module (528 mm) flexible front.

Module EI and masses are read directly from craft_data.py via the original-data
solver. Fixed order: high -> uni-d (rear) -> directional -> low (front).
The solid round core follows the rear module centreline, clamped at each disk.
Its EI=E*pi*d**4/64 and mass=rho*pi*d**2*length/4 are added only at the rear.
An elastic solution is screened against the catalogue's reference yield stress;
above-yield shapes are not accepted as elastic designs. No plastic shape or
strength of printed module flexures is inferred. No ropes or tip payload.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np

import snake_model_pla_sag as S

HERE = Path(__file__).resolve().parent
DEG_PER_NMM = 180 / np.pi / 1000


def read_inputs(config_path=HERE / "rear_backbone_config.json", catalog_path=(HERE.parents[2] / 'data' / 'materials' / 'rope_materials.json')):
    config = S.read_config(config_path)
    catalog = S.read_config(catalog_path)
    material = next((m for m in catalog["materials"] if m["id"] == config["backbone"]["material"]), None)
    if material is None or material.get("role") != "backbone":
        raise ValueError("unknown backbone material")
    if config["backbone"]["attachment"] != "clamped_each_module":
        raise ValueError("rear backbone must follow the module centreline")
    if config["front"]["types"] != ["directional", "low"] or config["rear"]["types"] != ["high", "unidirectional"]:
        raise ValueError("required order is high -> uni -> directional -> low")
    S.integer(config["front"]["modules"], "front modules", 2)
    S.properties(config)
    return config, material, catalog


def backbone_properties(material, diameter_mm):
    d = S.positive(diameter_mm, "backbone diameter") / 1000
    e = S.positive(material["young_modulus_pa"], "backbone E")
    rho = S.positive(material["density_kg_m3"], "backbone density")
    sy = S.positive(material["yield_strength_pa"], "reference yield stress")
    area, inertia = np.pi * d**2 / 4, np.pi * d**4 / 64
    return dict(material_id=material["id"], diameter_mm=diameter_mm,
                young_modulus_pa=e, density_kg_m3=rho, reference_yield_pa=sy,
                area_m2=area, inertia_m4=inertia, EI_nm2=e * inertia,
                linear_mass_kg_m=rho * area, first_yield_moment_nm=sy * inertia / (d / 2),
                catalogue_calibrated=material.get("calibrated", False))


def count_combinations(rear_modules, front_modules=11):
    for high in range(1, rear_modules):
        for directional in range(1, front_modules):
            yield high, rear_modules - high, directional, front_modules - directional


def build_cells(counts, config, material, *, cells=None):
    counts = np.atleast_2d(np.asarray(counts))
    props = S.properties(config)
    sub = config["solver"]["cells_per_module"] if cells is None else cells
    length, module_mass, _ = S.cell_arrays(counts, props, sub)
    if not np.all(counts[:, 2:].sum(axis=1) == config["front"]["modules"]):
        raise ValueError("directional + low must equal the fixed front module count")
    rear_n = counts[:, :2].sum(axis=1)
    if (rear_n < 2).any() or (rear_n != rear_n[0]).any() or (counts < 1).any():
        raise ValueError("equal rear count and at least one of each module type are required")
    module = np.arange(int(counts[0].sum()))[None, :]
    kind = sum((module >= counts.cumsum(axis=1)[:, j, None]).astype(int) for j in range(3))
    kind = np.repeat(kind, sub, axis=1)
    ei_module = np.array([p["EI_down_nm2"] for p in props])[kind]
    rear_cells = int(rear_n[0] * sub)
    core_mask = np.arange(length.shape[1])[None, :] < rear_cells
    core = backbone_properties(material, config["backbone"]["diameter_mm"]) if material else None
    ei = ei_module + (core_mask * core["EI_nm2"] if core else 0.)
    core_mass = core_mask * length * core["linear_mass_kg_m"] if core else np.zeros_like(length)
    half_compliance = length / (2 * ei)
    compliance = half_compliance.copy()
    compliance[:, 1:] += half_compliance[:, :-1]
    return dict(length=length, module_mass=module_mass, core_mass=core_mass,
                mass=module_mass + core_mass, EI_module=ei_module, EI_effective=ei,
                half_compliance=half_compliance, k=1 / compliance,
                rear_cells=rear_cells, core=core, counts=counts, cells_per_module=sub)


def solve_counts(counts, config, material, *, cells=None, steps=None):
    body = build_cells(counts, config, material, cells=cells)
    solver = config["solver"]
    solution = S.solve_cells(body["length"], body["mass"], body["k"],
                             gravity=config["gravity_m_s2"],
                             steps=solver["gravity_steps"] if steps is None else steps,
                             max_iterations=solver["max_iterations"],
                             tolerance=solver["moment_tolerance_nm"])
    solution.update(body)
    return solution


def response_metrics(solution, config):
    """Infinitesimal tip-moment flexibility around the self-weight equilibrium.

    Absolute cell angles are centre tangents. Interface tangent is interpolated
    by the two half-cell compliances. Tip tangent response includes the final
    half-cell compliance, condensed from the physical free-end segment.
    """
    phi, length, mass, k = (solution[x] for x in ("phi", "length", "mass", "k"))
    b = solution["rear_cells"]
    half = solution["half_compliance"]
    left_weight = half[:, b - 1] / (half[:, b - 1] + half[:, b])
    boundary_angle = phi[:, b - 1] + left_weight * (phi[:, b] - phi[:, b - 1])
    a = config["gravity_m_s2"] * length * (np.cumsum(mass[:, ::-1], axis=1)[:, ::-1] - .5 * mass)
    diagonal = k.copy()
    diagonal[:, :-1] += k[:, 1:]
    diagonal -= a * np.sin(phi)
    rhs = np.zeros_like(phi)
    rhs[:, -1] = 1.
    response = S.tridiagonal_solve(diagonal, -k[:, 1:], rhs)
    boundary_response = response[:, b - 1] + left_weight * (response[:, b] - response[:, b - 1])
    front_response = response[:, -1] + half[:, -1] - boundary_response
    front_zero_gravity = np.sum(length[:, b:] / solution["EI_module"][:, b:], axis=1)
    rear_zero_gravity = np.sum(length[:, :b] / solution["EI_effective"][:, :b], axis=1)
    torque = k * np.diff(phi, prepend=np.zeros((len(phi), 1)), axis=1)
    if solution["core"]:
        core = solution["core"]
        # The rear curvature on each boundary is M_total / EI_effective.
        left_curvature = np.abs(torque[:, :b]) / solution["EI_effective"][:, :b]
        right_curvature = np.abs(torque[:, 1:b + 1]) / solution["EI_effective"][:, :b]
        max_curvature = np.maximum(left_curvature, right_curvature).max(axis=1)
        stress = core["young_modulus_pa"] * core["diameter_mm"] / 2000 * max_curvature
        yield_ratio = stress / core["reference_yield_pa"]
    else:
        stress, yield_ratio = np.zeros(len(phi)), np.zeros(len(phi))
    rear_drop = -np.sum(length[:, :b] * np.sin(phi[:, :b]), axis=1) * 1000
    return dict(front_compliance_gravity_deg_per_nmm=front_response * DEG_PER_NMM,
                rear_compliance_gravity_deg_per_nmm=boundary_response * DEG_PER_NMM,
                front_compliance_zero_g_deg_per_nmm=front_zero_gravity * DEG_PER_NMM,
                rear_compliance_zero_g_deg_per_nmm=rear_zero_gravity * DEG_PER_NMM,
                rear_interface_angle_deg=np.degrees(boundary_angle), rear_drop_mm=rear_drop,
                front_relative_angle_deg=np.degrees(phi[:, -1] - boundary_angle),
                root_reaction_moment_nm=np.abs(torque[:, 0]),
                max_core_stress_mpa=stress / 1e6, core_reference_yield_ratio=yield_ratio)


def case_rows(solution, config):
    metrics = response_metrics(solution, config)
    rows = []
    for i, c in enumerate(solution["counts"]):
        h, u, d, low = map(int, c)
        length = solution["length"][i]
        row = dict(combination=f"H{h}-U{u}-D{d}-L{low}", n_high=h, n_uni=u,
                   n_directional=d, n_low=low, rear_modules=h + u, front_modules=d + low,
                   total_modules=int(c.sum()), rear_length_mm=float(length[:solution['rear_cells']].sum() * 1000),
                   front_length_mm=float(length[solution['rear_cells']:].sum() * 1000),
                   total_length_mm=float(length.sum() * 1000),
                   module_mass_g=float(solution["module_mass"][i].sum() * 1000),
                   backbone_mass_g=float(solution["core_mass"][i].sum() * 1000),
                   total_mass_g=float(solution["mass"][i].sum() * 1000),
                   tip_drop_mm=float(solution["tip_drop_mm"][i]), tip_x_mm=float(solution["tip_x_mm"][i]),
                   converged=bool(solution["converged"][i]),
                   residual_nm=float(solution["moment_residual_nm"][i]),
                   module_data_mode="paper_original", cells_per_module=solution["cells_per_module"])
        row.update({key: float(value[i]) for key, value in metrics.items()})
        row["passes_reference_yield_screen"] = row["core_reference_yield_ratio"] <= 1.
        rows.append(row)
    return rows


def pareto_rows(rows):
    """Maximise reach and gravity-loaded front compliance within elastic cases."""
    candidates = [r for r in rows if r["converged"] and r["passes_reference_yield_screen"]]
    result = []
    for row in candidates:
        x, y = row["tip_x_mm"], row["front_compliance_gravity_deg_per_nmm"]
        dominated = any(other["tip_x_mm"] >= x and other["front_compliance_gravity_deg_per_nmm"] >= y
                        and (other["tip_x_mm"] > x + 1e-7 or other["front_compliance_gravity_deg_per_nmm"] > y + 1e-10)
                        for other in candidates)
        if not dominated:
            result.append(row)
    return sorted(result, key=lambda r: r["tip_x_mm"])


def shape(solution, i=0):
    phi, length = solution["phi"][i], solution["length"][i]
    points = np.vstack((np.zeros(2), np.cumsum(np.c_[length * np.cos(phi), length * np.sin(phi)], axis=0)))
    return dict(points_mm=points * 1000, rear_cells=solution["rear_cells"],
                counts=solution["counts"][i], row=None)


def verify(config, material, rows):
    c = config["reference_counts"]
    base = solve_counts(c, config, material)
    fine = solve_counts(c, config, material, cells=config["solver"]["cells_per_module"] * 2)
    finer = solve_counts(c, config, material, cells=config["solver"]["cells_per_module"] * 4)
    stepped = solve_counts(c, config, material, steps=config["solver"]["gravity_steps"] * 2)
    r0, r1, r2 = [case_rows(r, config)[0] for r in (base, fine, finer)]
    baseline = solve_counts(c, config, None)
    ref = S.solve_counts(c, config)
    zero_config = copy.deepcopy(config)
    zero_config["gravity_m_s2"] = 0.
    zero = solve_counts(c, zero_config, material)
    zr = case_rows(zero, zero_config)[0]
    expected_front = sum(n * p["length_mm"] / 1000 / p["EI_down_nm2"]
                         for n, p in zip(c[2:], S.properties(config)[2:])) * DEG_PER_NMM
    no_core_error = float(np.max(np.abs(baseline["phi"] - ref["phi"])))
    zero_error = abs(zr["front_compliance_gravity_deg_per_nmm"] - expected_front)
    mesh_delta = abs(r0["tip_drop_mm"] - r1["tip_drop_mm"])
    step_delta = float(abs(base["tip_drop_mm"][0] - stepped["tip_drop_mm"][0]))
    checks = dict(all_cases_converged=all(r["converged"] for r in rows),
                  front_count_is_fixed=all(r["front_modules"] == config["front"]["modules"] for r in rows),
                  all_front_lengths_mm=sorted({round(r["front_length_mm"], 9) for r in rows}),
                  zero_backbone_reproduces_original_solver_max_angle_error_rad=no_core_error,
                  zero_gravity_drop_mm=float(zero["tip_drop_mm"][0]),
                  zero_gravity_front_compliance_error_deg_per_nmm=zero_error,
                  refinement_cells=[r["cells_per_module"] for r in (r0, r1, r2)],
                  refinement_drops_mm=[r["tip_drop_mm"] for r in (r0, r1, r2)],
                  base_to_fine_drop_difference_mm=mesh_delta,
                  next_refinement_drop_difference_mm=abs(r1["tip_drop_mm"] - r2["tip_drop_mm"]),
                  doubled_gravity_steps_drop_difference_mm=step_delta,
                  refinement_front_compliance_deg_per_nmm=[r["front_compliance_gravity_deg_per_nmm"] for r in (r0, r1, r2)])
    checks["passed"] = bool(checks["all_cases_converged"] and checks["front_count_is_fixed"]
                            and no_core_error < 1e-10 and zero_error < 1e-6
                            and mesh_delta < 1. and step_delta < 1e-4)
    return checks, base, baseline


def make_plots(rows, fixed, frontier, config, output, selected_shapes):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "asrc_pla_matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.ticker import MaxNLocator
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "text.color": "#26364a", "axes.labelcolor": "#26364a"})
    note = "Original module EI/masses | SS304 core: 4.2 mm, rear only | front: 11 modules = 528 mm assumed"
    norm = Normalize(1, config["front"]["modules"] - 1)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), layout="constrained")
    for ax, field, ylabel in zip(axes, ("tip_drop_mm", "tip_x_mm"), ("Head drop (mm)", "Horizontal reach (mm)")):
        sc = ax.scatter([r["rear_length_mm"] for r in rows], [r[field] for r in rows],
                        c=[r["n_low"] for r in rows], cmap="cividis", norm=norm, s=11, alpha=.6)
        ax.set(xlabel="Rear length with backbone (mm)", ylabel=ylabel)
        ax.grid(axis="y", alpha=.15)
    fig.colorbar(sc, ax=list(axes), label="low count in the 11-module front", shrink=.8)
    fig.suptitle("Rear backbone and fixed flexible front", fontsize=17, fontweight="bold")
    fig.supxlabel(note, fontsize=9)
    fig.savefig(output / "rear_length_vs_shape.png", dpi=180)
    plt.close(fig)

    if fixed:
        fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout="constrained")
        grid = np.full((config["front"]["modules"] - 1, fixed[0]["rear_modules"] - 1), np.nan)
        for r in fixed:
            grid[r["n_low"] - 1, r["n_high"] - 1] = r["tip_drop_mm"]
        image = axes[0].imshow(grid, origin="lower", aspect="auto", cmap="cividis",
                              extent=(.5, grid.shape[1] + .5, .5, grid.shape[0] + .5))
        axes[0].set(xlabel="high count in rear (uni-d = rear count - high)", ylabel="low count in front (directional = 11 - low)",
                    title=f"Head drop at N={config['focus_total_modules']}")
        axes[0].xaxis.set_major_locator(MaxNLocator(integer=True))
        fig.colorbar(image, ax=axes[0], label="Head drop (mm)", shrink=.8)
        axes[1].scatter([r["tip_x_mm"] for r in fixed], [r["front_compliance_gravity_deg_per_nmm"] for r in fixed],
                        color="#426b9a", s=24, alpha=.6)
        axes[1].plot([r["tip_x_mm"] for r in frontier], [r["front_compliance_gravity_deg_per_nmm"] for r in frontier],
                     color="#c57542", lw=2., marker="o", ms=4, label="Pareto candidates within reference yield")
        axes[1].set(xlabel="Horizontal reach (mm)", ylabel="Front relative rotation / tip moment (deg per N mm)",
                    title="Reach and front flexibility under self weight")
        axes[1].grid(alpha=.15); axes[1].legend(frameon=False, fontsize=9)
        fig.suptitle("Fixed front length: composition and flexibility", fontsize=16, fontweight="bold")
        fig.supxlabel(note + "\nFlexibility is an infinitesimal tip-moment response around the loaded shape.", fontsize=9)
        fig.savefig(output / "composition_and_flexibility.png", dpi=180)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 9), layout="constrained")
    for item in selected_shapes:
        xy, b = np.asarray(item["points_mm"]), item["rear_cells"]
        if item["label"] == "Same modules, no backbone":
            ax.plot(xy[:, 0], xy[:, 1], color="#83909d", ls="--", lw=2, label=item["label"])
        else:
            ax.plot(xy[:b+1, 0], xy[:b+1, 1], color="#426b9a", lw=3, label="Rear: modules + SS304 backbone")
            ax.plot(xy[b:, 0], xy[b:, 1], color="#c57542", lw=3, label="Front: modules only, 528 mm")
            ax.plot(*xy[b], "s", color="#26364a", ms=6, label="Backbone termination at module disk")
            ax.plot(*xy[-1], "o", color="#c57542", ms=5)
    ax.plot(0, 0, "s", color="#26364a", ms=7)
    ax.axhline(0, color="#83909d", lw=.8)
    ax.set(xlabel="Horizontal distance from clamp (mm)", ylabel="Height relative to clamp (mm)",
           title="Reference H8 / U12 / D8 / L3\nRear backbone and no-backbone comparison")
    ax.set_aspect("equal", adjustable="box"); ax.grid(alpha=.15)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -.09))
    fig.supxlabel("SS304 4.2 mm in rear only | flexible front: 11 modules (528 mm)\nOriginal module data | equal physical scale | self weight only", fontsize=9)
    fig.savefig(output / "reference_shape_comparison.png", dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "rear_backbone_config.json")
    parser.add_argument("--catalog", type=Path, default=(HERE.parents[2] / 'data' / 'materials' / 'rope_materials.json'))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    config, material, catalog = read_inputs(args.config, args.catalog)
    output = args.output_dir or HERE / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    input_paths = [Path(__file__), HERE / "craft_data.py", HERE / "snake_model_pla_sag.py", args.config, args.catalog]
    hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    S.write_csv(output / "module_properties.csv", S.properties(config))
    core = backbone_properties(material, config["backbone"]["diameter_mm"])
    S.write_json(output / "backbone_properties.json", dict(properties=core, material=material, sources=catalog["sources"]))
    rows = []
    for rear in range(config["rear"]["modules_min"], config["rear"]["modules_max"] + 1):
        counts = list(count_combinations(rear, config["front"]["modules"]))
        result = solve_counts(counts, config, material)
        current = case_rows(result, config)
        rows.extend(current)
        print(f"Rear={rear:2d}, front=11: {sum(r['converged'] for r in current)}/{len(current)} converged; "
              f"max reference yield ratio={max(r['core_reference_yield_ratio'] for r in current):.3f}", flush=True)
    fixed = [r for r in rows if r["total_modules"] == config["focus_total_modules"]]
    frontier = pareto_rows(fixed)
    S.write_csv(output / "combinations.csv", rows)
    S.write_csv(output / f"fixed_N{config['focus_total_modules']}.csv", fixed)
    S.write_csv(output / f"pareto_N{config['focus_total_modules']}.csv", frontier)
    checks, reference, baseline = verify(config, material, rows)
    checks["inputs_unchanged"] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
    checks["passed"] &= checks["inputs_unchanged"]
    S.write_json(output / "validation.json", checks)
    selected_shapes = [dict(shape(reference), label="With rear backbone"),
                       dict(shape(baseline), label="Same modules, no backbone")]
    S.write_json(output / "reference_shapes.json", selected_shapes)
    summary = dict(config=config, backbone=core, combinations=len(rows), fixed_total_combinations=len(fixed),
                   elastic_screen_failures=sum(not r["passes_reference_yield_screen"] for r in rows),
                   reference=case_rows(reference, config)[0], baseline=case_rows(baseline, config)[0],
                   max_reach_fixed=max(fixed, key=lambda r: r["tip_x_mm"]) if fixed else None,
                   pareto_candidates=len(frontier), input_sha256=hashes,
                   validation_passed=checks["passed"],
                   scope="Planar inextensible elastic screening; no plastic shape, shear, torsion, slip, ropes or tip payload. Module length 48 mm assumed; metal catalogue is a reference, not a measured wire.")
    S.write_json(output / "run_summary.json", summary)
    if not args.no_plots:
        make_plots(rows, fixed, frontier, config, output, selected_shapes)
    print(json.dumps({"reference":summary["reference"],"validation_passed":checks["passed"]}, indent=2), flush=True)
    return 0 if checks["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
