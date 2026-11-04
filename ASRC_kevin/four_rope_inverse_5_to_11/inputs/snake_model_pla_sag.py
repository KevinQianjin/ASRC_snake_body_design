"""Self-weight sag using original CRAFT paper data; no ropes/core/payload.

Directly reads craft_data.py's original EI and PC + PLA material consumption.
No material conversion, geometric rescaling or property overrides are applied.
The paper structure uses PC flexures and PLA disks/rings. The 48 mm module
length remains the explicitly labelled assumption already in craft_data.py.
Planar, geometrically nonlinear, inextensible Euler-Bernoulli approximation.
The continuum is discretized into straight cells with centre tangent angles.
Half-cell compliance at the clamp and summed half-cell compliances at interior
hinges impose a clamped continuum tangent and account for EI discontinuities.

For absolute cell angles phi, l=cell lengths and k=hinge stiffnesses:
  U = sum(k[i]*(phi[i]-phi[i-1])**2)/2 + sum(a[i]*sin(phi[i]))
  phi[-1] = 0; a[i] = g*l[i]*(mass downstream + mass[i]/2).
The exact gradient and tridiagonal Hessian are used in damped Newton solves.
Gravity continuation follows the downward branch (-pi/2 <= phi <= 0). Its
Hessian is positive definite: elastic SPD + nonnegative gravity diagonal.
All counts have the fixed order high -> unidirectional -> directional -> low.
Units: SI internally, CSV lengths mm and masses g. See README_pla_sag.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
import numpy as np
from scipy.linalg import solve_banded

import craft_data as D

HERE = Path(__file__).resolve().parent
KINDS = ("high", "unidirectional", "directional", "low")
COLORS = ("#426b9a", "#c69b35", "#c57542", "#82884b")


def read_config(path=HERE / "pla_sag_config.json"):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def positive(value, name, allow_zero=False):
    value = float(value)
    if not np.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return value


def integer(value, name, minimum=1):
    if isinstance(value, bool) or int(value) != value or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def properties(config):
    """Original table values, with only g/kg and mm/m unit conversions."""
    if config.get("data_mode") != "paper_original":
        raise ValueError("data_mode must be paper_original; material conversion is disabled")
    if "material" in config or config.get("property_overrides"):
        raise ValueError("material conversion settings and property overrides are not supported")
    if config.get("extras_g_per_module", 0) != 0:
        raise ValueError("paper_original mode uses paper material mass only")
    diameter = positive(config["module_diameter_mm"], "diameter")
    length_mm = positive(config["module_length_mm"], "module length")
    if not np.isclose(diameter, D.MODULE_DIAMETER_MM, rtol=0, atol=1e-9):
        raise ValueError("paper_original mode does not rescale the module diameter")
    if not np.isclose(length_mm, D.MODULE_LENGTH_M * 1000, rtol=0, atol=1e-9):
        raise ValueError("paper_original mode uses the module length recorded in craft_data.py")
    result = []
    for key in KINDS:
        axis = config["axes"][key]
        if axis not in ("x", "-x", "y", "-y"):
            raise ValueError(f"invalid axis {axis}")
        m = D.MODULES[key]
        # On the downward branch all curvature is negative; -x reverses X.
        field = {"x": "EI_negx", "-x": "EI_x", "y": "EI_y", "-y": "EI_y"}[axis]
        result.append(dict(kind=key, axis=axis, EI_source_field=field,
                           EI_down_nm2=positive(m[field], f"{key} EI"),
                           mass_g=positive(m["pc_g"] + m["pla_g"], f"{key} mass"),
                           pc_mass_g=m["pc_g"], pla_mass_g=m["pla_g"],
                           EI_x_nm2=m["EI_x"], EI_negx_nm2=m["EI_negx"], EI_y_nm2=m["EI_y"],
                           EA_n=m["EA"], torsional_stiffness_nm_rad=m["GJ"],
                           length_mm=D.MODULE_LENGTH_M * 1000,
                           length_is_assumption=True, material_conversion_applied=False))
    return result


def combinations(total, min_each=1):
    """Every ordered count tuple once; zero counts may be enabled explicitly."""
    total = integer(total, "total", 1)
    minimum = integer(min_each, "min_each", 0)
    for h in range(minimum, total - 3 * minimum + 1):
        for u in range(minimum, total - h - 2 * minimum + 1):
            for d in range(minimum, total - h - u - minimum + 1):
                yield h, u, d, total - h - u - d


def cell_arrays(counts, props, cells_per_module):
    counts = np.asarray(counts)
    if counts.ndim == 1:
        counts = counts[None, :]
    if (counts.ndim != 2 or counts.shape[1] != 4 or not np.isfinite(counts).all()
            or (counts < 0).any() or (counts != counts.astype(int)).any()):
        raise ValueError("counts must contain four nonnegative integers")
    totals = counts.sum(axis=1).astype(int)
    if not len(totals) or totals[0] == 0 or (totals != totals[0]).any():
        raise ValueError("a batch needs the same positive total for every row")
    sub = integer(cells_per_module, "cells_per_module")
    module = np.arange(totals[0])[None, :]
    kind = (module >= counts.cumsum(axis=1)[:, 0, None]).astype(int)
    kind += module >= counts.cumsum(axis=1)[:, 1, None]
    kind += module >= counts.cumsum(axis=1)[:, 2, None]
    kind = np.repeat(kind, sub, axis=1)
    ei = np.array([p["EI_down_nm2"] for p in props])[kind]
    mass = np.array([p["mass_g"] / 1000 for p in props])[kind] / sub
    length = np.array([p["length_mm"] / 1000 for p in props])[kind] / sub
    compliance = length / (2 * ei)
    hinge_compliance = compliance.copy()
    hinge_compliance[:, 1:] += compliance[:, :-1]
    return length, mass, 1 / hinge_compliance


def elastic_gradient(phi, k):
    rotation = np.diff(phi, prepend=np.zeros((len(phi), 1)), axis=1)
    tau = k * rotation
    out = tau.copy()
    out[:, :-1] -= tau[:, 1:]
    return out


def energy(phi, k, a):
    delta = np.diff(phi, prepend=np.zeros((len(phi), 1)), axis=1)
    return .5 * np.sum(k * delta**2, axis=1) + np.sum(a * np.sin(phi), axis=1)


def tridiagonal_solve(diag, off, rhs):
    """Batched Thomas elimination; positive pivots certify SPD on this branch."""
    diag = np.array(diag, order="F", copy=True)
    rhs = np.array(rhs, order="F", copy=True)
    off = np.asarray(off, order="F")
    for i in range(1, diag.shape[1]):
        factor = off[:, i - 1] / diag[:, i - 1]
        diag[:, i] -= factor * off[:, i - 1]
        rhs[:, i] -= factor * rhs[:, i - 1]
    if (diag <= 0).any() or not np.isfinite(diag).all():
        raise RuntimeError("equilibrium Hessian is not positive definite")
    out = np.empty_like(rhs, order="F")
    out[:, -1] = rhs[:, -1] / diag[:, -1]
    for i in range(diag.shape[1] - 2, -1, -1):
        out[:, i] = (rhs[:, i] - off[:, i] * out[:, i + 1]) / diag[:, i]
    return out


def solve_cells(length, mass, k, *, gravity=9.81, steps=8, max_iterations=80,
                tolerance=1e-10):
    """Solve independent equal-size chains together, returning per-case status."""
    g = positive(gravity, "gravity", True)
    steps = integer(steps, "steps")
    max_iterations = integer(max_iterations, "max_iterations")
    tolerance = positive(tolerance, "tolerance")
    phi = np.zeros_like(length)
    a_full = g * length * (np.cumsum(mass[:, ::-1], axis=1)[:, ::-1] - .5 * mass)
    elastic_diag = k.copy()
    elastic_diag[:, :-1] += k[:, 1:]
    off = -k[:, 1:]
    iterations = np.zeros(len(phi), dtype=int)
    for factor in np.linspace(1 / steps, 1, steps):
        a = a_full * factor
        for _ in range(max_iterations):
            grad = elastic_gradient(phi, k) + a * np.cos(phi)
            active = np.max(np.abs(grad), axis=1) > tolerance
            if not active.any():
                break
            ids = np.flatnonzero(active)
            p, ka, aa, gg = phi[ids], k[ids], a[ids], grad[ids]
            diag = elastic_diag[ids] - aa * np.sin(p)
            step = tridiagonal_solve(diag, off[ids], gg)
            # Stay on the physical downward branch. A zero boundary derivative
            # is allowed within roundoff when taking the first Newton step.
            bound = np.full_like(step, np.inf)
            np.divide(p + np.pi / 2, step, out=bound, where=step > 1e-16)
            upper = np.full_like(step, np.inf)
            np.divide(-p, -step, out=upper, where=step < -1e-16)
            alpha = np.minimum(1., .99 * np.min(np.minimum(bound, upper), axis=1))
            old_energy = energy(p, ka, aa)
            decrease = np.sum(gg * step, axis=1)
            for _ in range(40):
                candidate = p - alpha[:, None] * step
                trial_energy = energy(candidate, ka, aa)
                accepted = trial_energy <= old_energy - 1e-4 * alpha * decrease + 1e-14
                if accepted.all():
                    break
                alpha[~accepted] *= .5
            phi[ids] = candidate
            iterations[ids] += 1
        # Each case continues independently; failed cases stay explicitly marked.
    residual = np.max(np.abs(elastic_gradient(phi, k) + a_full * np.cos(phi)), axis=1)
    angles = np.diff(phi, prepend=np.zeros((len(phi), 1)), axis=1)
    converged = (np.isfinite(phi).all(axis=1) & (residual <= tolerance)
                 & (phi.min(axis=1) >= -np.pi / 2 - 1e-12)
                 & (phi.max(axis=1) <= 1e-12) & (angles.max(axis=1) <= 1e-9))
    return dict(phi=phi, tip_drop_mm=-np.sum(length * np.sin(phi), axis=1) * 1000,
                tip_x_mm=np.sum(length * np.cos(phi), axis=1) * 1000,
                moment_residual_nm=residual, converged=converged, iterations=iterations)


def solve_counts(counts, config, *, cells=None, steps=None):
    props = properties(config)
    solver = config["solver"]
    length, mass, k = cell_arrays(counts, props, solver["cells_per_module"] if cells is None else cells)
    out = solve_cells(length, mass, k, gravity=config["gravity_m_s2"],
                      steps=solver["gravity_steps"] if steps is None else steps,
                      max_iterations=solver["max_iterations"],
                      tolerance=solver["moment_tolerance_nm"])
    out.update(length=length, mass=mass, k=k)
    return out


def row_for(counts, i, result, config):
    h, u, d, low = map(int, counts)
    sub = config["solver"]["cells_per_module"]
    phi = result["phi"][i]
    # Integrate a linear interpolation of boundary moment over each cell.
    torque = result["k"][i] * np.diff(phi, prepend=0.)
    ei = np.repeat([p["EI_down_nm2"] for p, n in zip(properties(config), counts)
                    for _ in range(int(n))], sub)
    right_torque = np.append(torque[1:], 0.)
    integrated = (.5 * (torque + right_torque) / ei * result["length"][i]).reshape(-1, sub).sum(axis=1)
    max_angle = float(np.degrees(np.max(np.abs(integrated))))
    return dict(combination=f"H{h}-U{u}-D{d}-L{low}", n_high=h, n_uni=u, n_directional=d,
                n_low=low, total_modules=h + u + d + low,
                total_length_mm=float(result["length"][i].sum() * 1000),
                total_mass_g=float(result["mass"][i].sum() * 1000),
                tip_drop_mm=float(result["tip_drop_mm"][i]),
                tip_x_mm=float(result["tip_x_mm"][i]),
                drop_fraction=float(result["tip_drop_mm"][i] / (result["length"][i].sum() * 1000)),
                max_module_rotation_deg=max_angle,
                large_rotation_flag=max_angle > 30,
                moment_residual_nm=float(result["moment_residual_nm"][i]),
                converged=bool(result["converged"][i]), iterations=int(result["iterations"][i]),
                cells_per_module=sub, data_mode="paper_original", material_conversion_applied=False)


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=plain), encoding="utf-8")


def counts_from_row(row):
    return tuple(row[k] for k in ("n_high", "n_uni", "n_directional", "n_low"))


def validation(config, representatives):
    """Independent physical/numerical checks, with quantitative pass criteria."""
    rng = np.random.default_rng(912)
    n = 25
    off = rng.uniform(-.4, -.1, (3, n - 1))
    diag = np.full((3, n), 2.)
    rhs = rng.normal(size=(3, n))
    batch = tridiagonal_solve(diag, off, rhs)
    references = []
    for i in range(3):
        band = np.zeros((3, n)); band[1] = diag[i]
        band[0, 1:] = off[i]; band[2, :-1] = off[i]
        references.append(solve_banded((1, 1), band, rhs[i]))
    linear_error = float(np.max(np.abs(batch - references)))

    # Uniform cantilever, infinitesimal self weight: q L^4/(8 EI).
    n, span, ei, total_mass, gravity = 160, .48, .028, .01, 1e-4
    length = np.full((1, n), span / n); mass = np.full((1, n), total_mass / n)
    k = np.full((1, n), ei / (span / n)); k[:, 0] *= 2
    uniform = solve_cells(length, mass, k, gravity=gravity, tolerance=1e-13)
    analytic = total_mass / span * gravity * span**4 / (8 * ei) * 1000
    uniform_error = float(abs(uniform["tip_drop_mm"][0] / analytic - 1))
    zero = solve_cells(length, mass, k, gravity=0)
    # Independent energy finite-difference derivative at a nonuniform angle.
    p = np.linspace(-.15, -.55, n)[None, :]
    a = 9.81 * length * (np.cumsum(mass[:, ::-1], axis=1)[:, ::-1] - .5 * mass)
    grad = elastic_gradient(p, k) + a * np.cos(p)
    numerical = []
    for j in (0, 1, n // 2, n - 1):
        dx = np.zeros_like(p); dx[:, j] = 1e-6
        numerical.append(abs(float((energy(p + dx, k, a) - energy(p - dx, k, a))[0] / 2e-6 - grad[0, j])))

    mesh_checks, shape_results = [], []
    for label, counts in representatives:
        sub = config["solver"]["cells_per_module"]
        base = solve_counts(counts, config)
        fine = solve_counts(counts, config, cells=sub * 2)
        finer = solve_counts(counts, config, cells=sub * 4)
        stepped = solve_counts(counts, config, steps=config["solver"]["gravity_steps"] * 2)
        drops = [float(r["tip_drop_mm"][0]) for r in (base, fine, finer)]
        mesh_checks.append(dict(label=label, counts=counts, cells_per_module=[sub, sub * 2, sub * 4],
                                tip_drop_mm=drops, mesh_difference_mm=abs(drops[1] - drops[0]),
                                next_mesh_difference_mm=abs(drops[2] - drops[1]),
                                doubled_steps_difference_mm=abs(float(stepped["tip_drop_mm"][0]) - drops[0]),
                                converged=all(bool(r["converged"][0]) for r in (base, fine, finer, stepped))))
        phi, ll = base["phi"][0], base["length"][0]
        xy = np.vstack((np.zeros(2), np.cumsum(np.column_stack((ll * np.cos(phi), ll * np.sin(phi))), axis=0)))
        shape_results.append(dict(label=label, counts=counts, tip_drop_mm=drops[0], points_mm=xy * 1000))
    passed = (linear_error < 1e-12 and uniform_error < 1e-4 and max(numerical) < 1e-7
              and float(zero["tip_drop_mm"][0]) == 0
              and all(m["converged"] and m["mesh_difference_mm"] < 1.
                      and m["doubled_steps_difference_mm"] < 1e-4 for m in mesh_checks))
    return dict(passed=passed, tridiagonal_vs_scipy_max_error=linear_error,
                small_load_uniform=dict(computed_mm=float(uniform["tip_drop_mm"][0]),
                                        analytical_mm=analytic, relative_error=uniform_error),
                energy_gradient_max_error_nm=max(numerical), zero_gravity_drop_mm=float(zero["tip_drop_mm"][0]),
                representative_refinements=mesh_checks), shape_results


def make_plots(rows, summary_rows, shapes, config, output):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "asrc_pla_matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.ticker import MaxNLocator
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "axes.labelcolor": "#26364a",
                         "text.color": "#26364a", "axes.edgecolor": "#83909d",
                         "savefig.facecolor": "white"})
    note = "Original paper EI and PC+PLA masses | 48 mm/module assumed | self weight only | no ropes / backbone / payload"
    valid = [r for r in rows if r["converged"]]
    if not valid:
        return
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), layout="constrained")
    x = np.array([r["total_modules"] for r in valid])
    y = np.array([r["tip_drop_mm"] for r in valid])
    axes[0].scatter(x, y, s=3, alpha=.11, c=COLORS[0], linewidths=0, rasterized=True)
    n = [r["total_modules"] for r in summary_rows]
    axes[0].plot(n, [r["minimum_drop_mm"] for r in summary_rows], color="#26364a", label="Minimum at each total", lw=2)
    axes[0].plot(n, [r["maximum_drop_mm"] for r in summary_rows], color=COLORS[2], label="Maximum at each total", lw=2, ls="--")
    axes[0].set(title="All ordered count combinations", xlabel="Total modules (each module = 48 mm)" if config["module_length_mm"] == 48 else "Total modules",
                ylabel="Head drop below clamp (mm)", ylim=(0, None))
    axes[0].legend(frameon=False)
    axes[1].scatter(x, [r["drop_fraction"] * 100 for r in valid], s=3, alpha=.11,
                    c=COLORS[0], linewidths=0, rasterized=True)
    axes[1].set(title="Drop relative to nominal length", xlabel="Total modules", ylabel="Head drop / length (%)", ylim=(0, 100))
    for ax in axes:
        ticks = sorted(set(np.linspace(min(n), max(n), min(8, len(n)), dtype=int)))
        ax.set_xticks(ticks); ax.grid(axis="y", alpha=.15)
    fig.suptitle("Self-weight sag versus composition", fontsize=17)
    fig.supxlabel(note, fontsize=9)
    fig.savefig(output / "sag_vs_total.png", dpi=180)
    plt.close(fig)

    focus = config["scan"]["focus_total"]
    fixed = [r for r in rows if r["total_modules"] == focus]
    if any(r["converged"] for r in fixed):
        levels = sorted({r["n_low"] for r in fixed})
        lower = min(min(r["n_high"], r["n_uni"]) for r in fixed) - .5
        upper = max(max(r["n_high"], r["n_uni"]) for r in fixed) + .5
        columns, rows_count = 4, math.ceil(len(levels) / 4)
        fig, axes = plt.subplots(rows_count, columns, figsize=(16, 3.65 * rows_count),
                                 squeeze=False, layout="constrained")
        norm = Normalize(min(r["tip_drop_mm"] for r in fixed if r["converged"]),
                         max(r["tip_drop_mm"] for r in fixed if r["converged"]))
        image = None
        for ax, low in zip(axes.flat, levels):
            grid = np.full((focus + 1, focus + 1), np.nan)
            for r in fixed:
                if r["n_low"] == low and r["converged"]:
                    grid[r["n_uni"], r["n_high"]] = r["tip_drop_mm"]
            image = ax.imshow(grid, origin="lower", extent=(-.5, focus + .5, -.5, focus + .5),
                              cmap="cividis", norm=norm, interpolation="nearest", aspect="equal")
            ax.set(title=f"low = {low}", xlabel="high count", ylabel="uni-d count",
                   xlim=(lower, upper), ylim=(lower, upper))
            ax.xaxis.set_major_locator(MaxNLocator(5, integer=True)); ax.yaxis.set_major_locator(MaxNLocator(5, integer=True))
            if low == config["reference_counts"][3] and sum(config["reference_counts"]) == focus:
                ax.plot(*config["reference_counts"][:2], marker="*", ms=14, color="#e99a42", mec="#26364a")
        for ax in list(axes.flat)[len(levels):]:
            ax.set_visible(False)
        if image is not None:
            fig.colorbar(image, ax=list(axes.flat), shrink=.8, label="Head drop (mm); one common scale")
        fig.suptitle(f"Composition and head drop | {focus} modules, {focus * config['module_length_mm']:.0f} mm\n"
                     "directional count = total - high - uni-d - low; blank = infeasible / failed; star = reference",
                     fontsize=15)
        fig.supxlabel(note, fontsize=9)
        fig.savefig(output / f"composition_heatmaps_N{focus}.png", dpi=150)
        # Compact, clearly disclosed slices for an easily readable chat preview.
        best = min((r for r in fixed if r["converged"]), key=lambda r: r["tip_drop_mm"])
        chosen = sorted({levels[0], levels[len(levels) // 3], best["n_low"],
                         config["reference_counts"][3]} & set(levels))
        plt.close(fig)
        columns = min(2, len(chosen))
        fig, axes = plt.subplots(math.ceil(len(chosen) / columns), columns, squeeze=False,
                                 figsize=(10, 4.5 * math.ceil(len(chosen) / columns)), layout="constrained")
        for ax, low in zip(axes.flat, chosen):
            grid = np.full((focus + 1, focus + 1), np.nan)
            for r in fixed:
                if r["n_low"] == low and r["converged"]:
                    grid[r["n_uni"], r["n_high"]] = r["tip_drop_mm"]
            image = ax.imshow(grid, origin="lower", cmap="cividis", norm=norm, interpolation="nearest")
            ax.set(title=f"low = {low}", xlabel="high count", ylabel="uni-d count", xlim=(lower, upper), ylim=(lower, upper))
            ax.xaxis.set_major_locator(MaxNLocator(6, integer=True)); ax.yaxis.set_major_locator(MaxNLocator(6, integer=True))
            if low == config["reference_counts"][3] and sum(config["reference_counts"]) == focus:
                ax.plot(*config["reference_counts"][:2], marker="*", ms=12, color="#e99a42", mec="#26364a")
            if low == best["n_low"]:
                ax.plot(best["n_high"], best["n_uni"], marker="o", ms=10, mfc="none", mec="#e99a42", mew=2)
                ax.text(best["n_high"] + .8, best["n_uni"] + .5,
                        f"Minimum {best['tip_drop_mm']:.1f} mm", fontsize=10)
        for ax in list(axes.flat)[len(chosen):]:
            ax.set_visible(False)
        fig.colorbar(image, ax=list(axes.flat), shrink=.75, label="Head drop (mm)")
        fig.suptitle(f"Selected composition slices | N = {focus}\ndirectional = N - high - uni-d - low", fontsize=15)
        fig.supxlabel("Selected slices; full set in composition_heatmaps_N*.png. Star = reference; ring = minimum.\n" + note, fontsize=9)
        fig.savefig(output / f"composition_preview_N{focus}.png", dpi=170)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 10), layout="constrained")
    for j, shape in enumerate(shapes):
        xy = np.asarray(shape["points_mm"])
        counts = "/".join(map(str, shape["counts"]))
        ax.plot(xy[:, 0], xy[:, 1], color=COLORS[j % 4], lw=2.3,
                ls=("-", "--", "-.", ":")[j % 4],
                label=f"{shape['label']}: {counts}; drop {shape['tip_drop_mm']:.1f} mm")
        ax.plot(*xy[-1], "o", color=COLORS[j % 4], ms=5)
    ax.axhline(0, color="#83909d", lw=.8)
    ax.plot(0, 0, marker="s", color="#26364a", ms=7)
    ax.set(xlabel="Horizontal distance from clamp (mm)", ylabel="Height relative to clamp (mm)",
           title="Representative deformed centre lines\nCounts: high / uni-d / directional / low")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(frameon=False, fontsize=10, loc="upper left", bbox_to_anchor=(0, -.08))
    ax.grid(alpha=.15)
    fig.supxlabel("Original paper EI and PC+PLA masses | 48 mm/module assumed\nSelf weight only; no ropes, backbone or payload", fontsize=10)
    fig.savefig(output / "representative_shapes.png", dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=HERE / "pla_sag_config.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--total-min", type=int)
    parser.add_argument("--total-max", type=int)
    parser.add_argument("--total", type=int, help="scan just one total")
    parser.add_argument("--min-each", type=int, help="default 1; use 0 to permit absent types")
    parser.add_argument("--cells-per-module", type=int)
    parser.add_argument("--counts", nargs=4, type=int, metavar=("HIGH", "UNI", "DIR", "LOW"))
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    config = read_config(args.config)
    scan = config["scan"]
    if args.total is not None:
        scan.update(total_min=args.total, total_max=args.total, focus_total=args.total)
    for arg in ("total_min", "total_max", "min_each"):
        if getattr(args, arg) is not None:
            scan[arg] = getattr(args, arg)
    if args.cells_per_module is not None:
        config["solver"]["cells_per_module"] = args.cells_per_module
    integer(scan["total_min"], "total_min"); integer(scan["total_max"], "total_max")
    integer(scan["min_each"], "min_each", 0)
    if scan["total_max"] < scan["total_min"]:
        raise ValueError("total_max must be >= total_min")
    if not scan["total_min"] <= scan["focus_total"] <= scan["total_max"]:
        scan["focus_total"] = scan["total_max"]
    if args.counts is not None:
        cell_arrays(args.counts, properties(config), config["solver"]["cells_per_module"])
        scan.update(total_min=sum(args.counts), total_max=sum(args.counts), focus_total=sum(args.counts))
    output = args.output_dir or HERE / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    originals = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (HERE / "snake_model.py", HERE / "craft_data.py", HERE / "snake_model_ropes.py")}
    started = time.monotonic()
    props = properties(config)
    write_csv(output / "module_properties.csv", props)
    print("Original paper EI and PC+PLA masses | no material conversion | no ropes / central backbone / payload", flush=True)
    print("Geometry note: 48 mm/module is the existing craft_data.py assumption.", flush=True)
    for p in props:
        print(f"  {p['kind']:16s} {p['axis']:2s} EI={p['EI_down_nm2']:.7f} Nm2; mass={p['mass_g']:.4f} g", flush=True)
    all_rows, summary_rows = [], []
    for total in range(scan["total_min"], scan["total_max"] + 1):
        counts = [tuple(args.counts)] if args.counts is not None else list(combinations(total, scan["min_each"]))
        if not counts:
            continue
        result = solve_counts(counts, config)
        rows = [row_for(c, i, result, config) for i, c in enumerate(counts)]
        all_rows.extend(rows)
        good = [r for r in rows if r["converged"]]
        if good:
            best, worst = min(good, key=lambda r: r["tip_drop_mm"]), max(good, key=lambda r: r["tip_drop_mm"])
            summary_rows.append(dict(total_modules=total, total_length_mm=best["total_length_mm"],
                                     combinations=len(rows), converged=len(good), minimum_drop_mm=best["tip_drop_mm"],
                                     maximum_drop_mm=worst["tip_drop_mm"], best_combination=best["combination"],
                                     worst_combination=worst["combination"]))
        print(f"N={total:2d}: {len(good):5d}/{len(rows):5d} converged; "
              + (f"drop {min(r['tip_drop_mm'] for r in good):.2f}..{max(r['tip_drop_mm'] for r in good):.2f} mm" if good else "FAILED"), flush=True)
    if not all_rows:
        raise ValueError("no combinations in selected range")
    write_csv(output / "combinations.csv", all_rows)
    write_csv(output / "summary_by_total.csv", summary_rows)
    fixed = sorted([r for r in all_rows if r["total_modules"] == scan["focus_total"] and r["converged"]],
                   key=lambda r: r["tip_drop_mm"])
    write_csv(output / f"ranking_N{scan['focus_total']}.csv", fixed)
    representatives = []
    if fixed:
        representatives.extend([(f"N{scan['focus_total']} minimum", counts_from_row(fixed[0])),
                                (f"N{scan['focus_total']} maximum", counts_from_row(fixed[-1]))])
    representatives.append(("Reference", tuple(config["reference_counts"])))
    checks, shapes = validation(config, representatives)
    unchanged = all(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest for name, digest in originals.items())
    checks["original_files_unchanged"] = unchanged
    checks["all_combinations_converged"] = all(r["converged"] for r in all_rows)
    checks["paper_properties_exact"] = all(
        p["EI_down_nm2"] == D.MODULES[p["kind"]][p["EI_source_field"]]
        and p["mass_g"] == D.MODULES[p["kind"]]["pc_g"] + D.MODULES[p["kind"]]["pla_g"]
        and not p["material_conversion_applied"] for p in props)
    checks["passed"] &= unchanged and checks["all_combinations_converged"] and checks["paper_properties_exact"]
    write_json(output / "validation.json", checks)
    write_json(output / "representative_shapes.json", shapes)
    summary = dict(config=config, original_sha256=originals,
                   implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), module_properties=props,
                   combination_count=len(all_rows), failed_combinations=sum(not r["converged"] for r in all_rows),
                   focus_minimum=fixed[0] if fixed else None, focus_maximum=fixed[-1] if fixed else None,
                   reference={k: v for k, v in next(s for s in shapes if s["label"] == "Reference").items()
                              if k != "points_mm"},
                   elapsed_seconds=time.monotonic() - started, validation_passed=checks["passed"],
                   model_scope="Original paper EI and PC+PLA material masses, no rescaling or overrides. Planar, inextensible, large-rotation bending; no shear, twist, contact, creep, damage or head accessories. Module length is the existing 48 mm assumption in craft_data.py.")
    write_json(output / "run_summary.json", summary)
    if not args.no_plots:
        make_plots(all_rows, summary_rows, shapes, config, output)
    print(f"Saved {len(all_rows)} combinations to {output}; validation={checks['passed']}", flush=True)
    if not checks["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
