"""Share the axial resultant between four curved CAD blades, finite tab restraint and the U cage."""

import argparse
from pathlib import Path
import numpy as np
import trimesh
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from common import CAD, R1, OUT, load_motion, read, save
from u_springs import blade_profile, disk_motion, solve_blade

EVENTS = (("U1", 1510), ("U1", 2819), ("U3", 1498))
DELTA = (-1.3, -0.8, -0.45, -0.25, -0.12, 0.0, 0.12, 0.3, 0.65, 1.2)


def cage_upper(mesh, spacing):
    # Kinematic upper bound for the straight elastic cage: trial u_z(z), u_x=u_y=0.
    # Use the constrained modulus in the strain energy, not the uniaxial modulus.
    z0, z1 = mesh.bounds[:, 2]
    count = int(np.ceil((z1 - z0) / spacing))
    h = (z1 - z0) / count
    values = []
    for z in z0 + (np.arange(count) + 0.5) * h:
        cut = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        area = sum(poly.area for poly in cut.to_2D()[0].polygons_full)
        if area <= 0:
            raise ValueError("Empty axial cage section")
        values.append(area)
    nu = 0.4
    E = 1530.0
    M = E * (1 - nu) / ((1 + nu) * (1 - 2 * nu))
    return dict(
        spacing_mm=h,
        minimum_area_mm2=min(values),
        maximum_area_mm2=max(values),
        estimated_kinematic_upper_N_mm=M / np.sum(h / np.array(values)),
    )


def run(out):
    rod, states, _ = load_motion()
    blades = sorted(
        trimesh.load_mesh(CAD / "guides_v2/U_leaf_springs.stl").split(),
        key=lambda m: tuple(np.sign(m.centroid[:2])),
    )
    cage = trimesh.load_mesh(CAD / "guides_v2/U_lane_pass.stl")
    geometry = [cage_upper(cage, h) for h in (1.0, 0.5)]
    cap = geometry[-1]["estimated_kinematic_upper_N_mm"]
    archive = read(R1 / "u_blades.json")["solutions"]
    profiles = [blade_profile(b, 1.0) for b in blades]
    fields = []
    results = []
    for name, step in EVENTS:
        module = int(name[1:]) - 1
        R, d = disk_motion(rod, states[step], module)
        n = R[:, 2]
        cells = (states[step] / rod.scale).reshape(-1, 4)[
            8 * module : 8 * (module + 1), 3
        ]
        target = rod.planar.EA[8 * module + 7] * cells[-1]
        prestrain_extension = 12 * sum(cells)
        curves = []
        for k, (b, prof) in enumerate(zip(blades, profiles)):
            x, y = np.sign(b.centroid[:2]).astype(int)
            original = next(
                a
                for a in archive
                if (
                    a["module"],
                    a["step"],
                    a["blade_x_sign"],
                    a["blade_y_sign"],
                    a["gauge_spacing_mm"],
                )
                == (name, step, x, y, 1.0)
            )
            data = []
            start = solve_blade(prof, R, d, return_seed=True)
            np.testing.assert_allclose(
                start["force_in_proximal_CAD_N"],
                original["force_in_proximal_CAD_N"],
                atol=0.001,
            )
            seeds = {0.0: start["shooting_seed"]}
            for delta in sorted(DELTA, key=abs):
                nearest = min(seeds, key=lambda s: abs(delta - s))
                try:
                    a = (
                        start
                        if delta == 0
                        else solve_blade(
                            prof,
                            R,
                            d + n * delta,
                            warm=seeds[nearest],
                            return_seed=True,
                        )
                    )
                except (ValueError, np.linalg.LinAlgError) as exc:
                    a = dict(converged=False, reason=str(exc))
                if a["converged"]:
                    seeds[delta] = a["shooting_seed"]
                row = dict(
                    module=name,
                    step=step,
                    blade=k,
                    x_sign=x,
                    y_sign=y,
                    effective_end_shift_mm=delta,
                    converged=a["converged"],
                )
                if a["converged"]:
                    row.update(
                        axial_force_N=np.dot(a["force_in_proximal_CAD_N"], n),
                        tension_strain=a["peak_tension_strain"],
                        compression_strain=a["peak_compression_strain"],
                        force_norm_N=np.linalg.norm(a["force_in_proximal_CAD_N"]),
                        peak_solution_residual_mm=max(a["endpoint_residual_mm"]),
                    )
                    data.append(row)
                if not a["converged"]:
                    row["reason"] = a.get("reason", "continuation did not complete")
                fields.append(row)
            data.sort(key=lambda row: row["effective_end_shift_mm"])
            if len(data) < 4 or np.any(np.diff([v["axial_force_N"] for v in data]) < 0):
                raise RuntimeError("Blade response lacks a continuous ascending branch")
            curves.append(
                (
                    np.array([v["effective_end_shift_mm"] for v in data]),
                    {
                        k: PchipInterpolator(
                            [v["effective_end_shift_mm"] for v in data],
                            [v[k] for v in data],
                            extrapolate=False,
                        )
                        for k in (
                            "axial_force_N",
                            "tension_strain",
                            "compression_strain",
                            "force_norm_N",
                        )
                    },
                )
            )
            print(name, step, k, "curve complete", flush=True)
            save(out / "u_blade_curves.json", fields)
        for ktab in (50.0, 250.0, 1000.0, 10000.0):
            for cage_factor in (0.01, 0.10, 1.0):
                kcage = cap * cage_factor

                def displacements(disk):
                    values = []
                    for grid, prop in curves:

                        def defect(s):
                            return s + 2 * prop["axial_force_N"](s) / ktab - disk

                        values.append(brentq(defect, grid[0], grid[-1]))
                    return values

                limits = np.array(
                    [
                        [
                            s + 2 * curve["axial_force_N"](s) / ktab
                            for s in (grid[0], grid[-1])
                        ]
                        for grid, curve in curves
                    ]
                )
                lower = limits[:, 0].max() + 1e-9
                upper = limits[:, 1].min() - 1e-9

                def equilibrium(disk):
                    slips = displacements(disk)
                    return (
                        kcage * (prestrain_extension + disk)
                        + sum(
                            curve["axial_force_N"](s)
                            for s, (_, curve) in zip(slips, curves)
                        )
                        - target
                    )

                row = dict(
                    module=name,
                    step=step,
                    per_tab_stiffness_N_mm=ktab,
                    cage_fraction=cage_factor,
                    cage_stiffness_N_mm=kcage,
                    target_axial_N=target,
                )
                if lower >= upper or equilibrium(lower) * equilibrium(upper) > 0:
                    row["status"] = "outside solved blade response"
                else:
                    disk = brentq(equilibrium, lower, upper)
                    shifts = displacements(disk)
                    forces = np.array(
                        [c["axial_force_N"](s) for s, (_, c) in zip(shifts, curves)]
                    )
                    row.update(
                        status="balanced",
                        disk_axial_correction_mm=disk,
                        cage_axial_N=kcage * (prestrain_extension + disk),
                        blade_axial_N=forces,
                        tab_slip_mm=forces / ktab,
                        blade_effective_shift_mm=shifts,
                        axial_residual_N=equilibrium(disk),
                        blades=[
                            {k: float(v(s)) for k, v in c.items()}
                            for s, (_, c) in zip(shifts, curves)
                        ],
                    )
                results.append(row)
        save(out / "u_assembly.json", dict(cage_sections=geometry, cases=results))
    # Independent off-knot solves for the governing U1 setting verify interpolation at its four load splits.
    case = next(
        r
        for r in results
        if r["step"] == 1510
        and r["per_tab_stiffness_N_mm"] == 250
        and r["cage_fraction"] == 0.1
    )
    if case["status"] == "balanced":
        R, d = disk_motion(rod, states[1510], 0)
        checks = []
        for s, p, estimate in zip(
            case["blade_effective_shift_mm"], profiles, case["blades"]
        ):
            a = solve_blade(p, R, d + R[:, 2] * s)
            checks.append(
                dict(
                    converged=a["converged"],
                    force_error_N=float(
                        np.dot(a["force_in_proximal_CAD_N"], R[:, 2])
                        - estimate["axial_force_N"]
                    ),
                    tensile_strain_error=a["peak_tension_strain"]
                    - estimate["tension_strain"],
                )
            )
        save(out / "u_interpolation_check.json", checks)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out)
