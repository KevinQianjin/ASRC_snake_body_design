"""Explain the low-count sag trend without changing the original-paper model.

Fix N=31, H=1, D=1 and replace U with L: U=29-L. Compare original masses
against an explicitly artificial equal-mass control, at normal and very small
gravity. The independent multipoint continuum BVP verifies two equal-mass
cases. Diagnostic files are separate from the original-paper sweep results.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np
from scipy.integrate import solve_bvp

import snake_model_pla_sag as S

SUBDIVISIONS = 32
EQUAL_MODULE_MASS_KG = .0039
SMALL_GRAVITY_SCALE = 1e-5


def continuum_equal_mass(counts, props, discrete):
    """Four smooth domains with continuity of tangent, moment and position.

    In each domain: theta'=M/EI, M'=downstream_weight*cos(theta),
    x'=cos(theta), y'=sin(theta). The physical coordinate of each domain is
    mapped onto t in [0,1]. Root theta/x/y fixed; free-tip moment zero.
    This BVP does not impose the discrete solver's angle bounds.
    """
    counts = np.asarray(counts)
    length = counts * props[0]["length_mm"] / 1000
    rigidity = np.array([p["EI_down_nm2"] for p in props])
    mass = counts * EQUAL_MODULE_MASS_KG
    downstream = np.cumsum(mass[::-1])[::-1] - mass

    def ode(t, values):
        a = values.reshape(4, 4, -1)
        weight = 9.81 * (downstream[:, None] + mass[:, None] * (1 - t[None, :]))
        derivative = np.empty_like(a)
        derivative[:, 0] = length[:, None] * a[:, 1] / rigidity[:, None]
        derivative[:, 1] = length[:, None] * weight * np.cos(a[:, 0])
        derivative[:, 2] = length[:, None] * np.cos(a[:, 0])
        derivative[:, 3] = length[:, None] * np.sin(a[:, 0])
        return derivative.reshape(16, -1)

    def boundary(left, right):
        a, b = left.reshape(4, 4), right.reshape(4, 4)
        return np.r_[a[0, 0], a[0, 2], a[0, 3], b[-1, 1], (b[:-1] - a[1:]).ravel()]

    phi, ll, stiffness = discrete["phi"], discrete["length"], discrete["k"]
    points = np.vstack((np.zeros(2), np.cumsum(np.c_[ll * np.cos(phi), ll * np.sin(phi)], axis=0)))
    centres = np.cumsum(ll) - ll / 2
    nodes = np.r_[0, np.cumsum(ll)]
    torque = stiffness * np.diff(phi, prepend=0.)
    t = np.linspace(0, 1, 100)
    start = np.r_[0, np.cumsum(length)[:-1]]
    guess = np.zeros((4, 4, len(t)))
    for j in range(4):
        s = start[j] + length[j] * t
        guess[j, 0] = np.interp(s, centres, phi, left=0.)
        guess[j, 1] = np.interp(s, nodes, np.r_[torque, 0.])
        guess[j, 2] = np.interp(s, nodes, points[:, 0])
        guess[j, 3] = np.interp(s, nodes, points[:, 1])
    solution = solve_bvp(ode, boundary, t, guess.reshape(16, -1), tol=1e-8, max_nodes=3000)
    if not solution.success:
        raise RuntimeError(solution.message)
    return dict(counts=counts.tolist(), converged=solution.success,
                drop_mm=float(-solution.y[-1, -1] * 1000),
                tip_x_mm=float(solution.y[-2, -1] * 1000),
                maximum_residual=float(solution.rms_residuals.max()))


def make_plot(rows, output):
    os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "asrc_pla_matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "text.color": "#26364a", "axes.labelcolor": "#26364a"})
    x = [r["n_low"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), layout="constrained")
    for ax, suffix in zip(axes, ("normal", "small")):
        ax.plot(x, [r[f"original_mass_{suffix}_drop_mm"] for r in rows],
                color="#426b9a", lw=2.2, label="Original paper masses")
        ax.plot(x, [r[f"equal_mass_{suffix}_drop_mm"] for r in rows],
                color="#c57542", lw=2.2, ls="--", label="Control: every module = 3.9 g")
        ax.set(xlabel="low count (uni-d count = 29 - low)", ylabel="Head drop (mm)",
               xticks=[1, 5, 10, 15, 20, 24, 28], xlim=(1, 28))
        ax.grid(axis="y", alpha=.18)
        ax.legend(frameon=False, fontsize=10, loc="best")
    axes[0].set_title("Normal gravity: large deformation\nExpanded vertical scale", fontsize=13)
    axes[0].set_ylim(1345, 1400)
    for low, offset in ((1, (12, 15)), (24, (-115, 18)), (28, (-115, 0))):
        row = rows[low - 1]
        y = row["original_mass_normal_drop_mm"]
        axes[0].plot(low, y, "o", color="#426b9a", ms=5)
        axes[0].annotate(f"low={low}: {y:.1f} mm", (low, y), xytext=offset,
                         textcoords="offset points", fontsize=10)
    axes[1].set_title("Gravity reduced to 1/100,000\nDiagnostic for the small-deformation regime", fontsize=13)
    axes[1].set_ylim(0, 1.65)
    fig.suptitle("Why more low modules can give less head drop", fontsize=17, fontweight="bold")
    fig.supxlabel("31 modules, 1488 mm assumed | high=1, directional=1 | original EI in every case\n"
                  "Equal masses and reduced gravity are diagnostic controls; original sweep inputs are unchanged.", fontsize=10)
    fig.savefig(output / "low_count_diagnostic.png", dpi=180)
    plt.close(fig)


def main():
    config = S.read_config()
    props = S.properties(config)
    low = np.arange(1, 29)
    counts = np.c_[np.ones(28, int), 29 - low, np.ones(28, int), low]
    ll, original_mass, stiffness = S.cell_arrays(counts, props, SUBDIVISIONS)
    equal_mass = np.full_like(original_mass, EQUAL_MODULE_MASS_KG / SUBDIVISIONS)
    results = {}
    for name, mass in (("original_mass", original_mass), ("equal_mass", equal_mass)):
        for suffix, gravity_scale in (("normal", 1.), ("small", SMALL_GRAVITY_SCALE)):
            result = S.solve_cells(ll, mass, stiffness, gravity=9.81 * gravity_scale, tolerance=1e-12)
            if not result["converged"].all():
                raise RuntimeError(f"Diagnostic did not converge: {name} {suffix}")
            results[f"{name}_{suffix}"] = result
    rows = []
    for i, c in enumerate(counts):
        row = dict(n_high=int(c[0]), n_uni=int(c[1]), n_directional=int(c[2]), n_low=int(c[3]),
                   original_total_mass_g=float(original_mass[i].sum() * 1000),
                   equal_control_total_mass_g=float(equal_mass[i].sum() * 1000))
        for name, result in results.items():
            row[f"{name}_drop_mm"] = float(result["tip_drop_mm"][i])
            row[f"{name}_tip_x_mm"] = float(result["tip_x_mm"][i])
        rows.append(row)

    verified = []
    for i in (0, 23):
        phi = results["equal_mass_normal"]["phi"][i]
        discrete = dict(phi=phi, length=ll[i], k=stiffness[i])
        bvp = continuum_equal_mass(counts[i], props, discrete)
        bvp["discrete_drop_mm"] = rows[i]["equal_mass_normal_drop_mm"]
        bvp["absolute_difference_mm"] = abs(bvp["drop_mm"] - bvp["discrete_drop_mm"])
        points = np.vstack((np.zeros(2), np.cumsum(np.c_[ll[i] * np.cos(phi), ll[i] * np.sin(phi)], axis=0)))
        xmid = .5 * (points[:-1, 0] + points[1:, 0])
        bvp["root_gravity_moment_nm"] = float(9.81 * equal_mass[i] @ xmid)
        bvp["angle_at_end_of_first_module_deg"] = float(np.degrees(np.interp(
            .048, np.cumsum(ll[i]) - ll[i] / 2, phi)))
        verified.append(bvp)
    passed = (all(v["absolute_difference_mm"] < .01 for v in verified)
              and np.all(np.diff(results["equal_mass_small"]["tip_drop_mm"]) > 0))
    if not passed:
        raise RuntimeError("Independent diagnostic checks failed")
    output = S.HERE / config["output_directory"]
    S.write_csv(output / "low_count_diagnostic.csv", rows)
    S.write_json(output / "low_count_diagnostic.json", dict(
        fixed_counts="N=31, high=1, directional=1, uni=29-low", cells_per_module=SUBDIVISIONS,
        equal_mass_control_g_per_module=EQUAL_MODULE_MASS_KG * 1000,
        small_gravity_scale=SMALL_GRAVITY_SCALE, original_paper_EI_used=True,
        original_model_inputs_modified=False, independent_BVP_checks=verified,
        passed=bool(passed), rows=rows))
    make_plot(rows, output)
    for i in (0, 23, 27):
        row = rows[i]
        print(f"low={row['n_low']:2d}, uni={row['n_uni']:2d}: original-mass drop "
              f"{row['original_mass_normal_drop_mm']:.3f} mm; equal-mass drop "
              f"{row['equal_mass_normal_drop_mm']:.3f} mm", flush=True)
    print(f"Independent BVP checks passed; diagnostic saved in {output}", flush=True)


if __name__ == "__main__":
    main()
