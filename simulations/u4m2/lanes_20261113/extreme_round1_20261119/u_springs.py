"""End-driven curved NiTi strip screen using the four extant CAD blades and the U-disk poses."""

import argparse
from pathlib import Path

from numba import njit
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from shapely.geometry import Polygon
import trimesh

from study_inputs import CAD, SOURCE, load_motion, read_csv, save, write_csv

# Principal beam directors: thickness, width and tangent. CAD z is the module axis.
CAD_TO_ROD = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
E_MPA = 40000.0
NU = 0.33
END_Z = 44.9999  # free side of the abrupt changes into the shaped tabs at z = +/-45 mm


def section(mesh, z):
    cut = mesh.section(plane_normal=[0, 0, 1], plane_origin=[0, 0, z])
    polygons = [Polygon(loop[:, :2]) for loop in cut.discrete]
    if len(polygons) != 1 or not polygons[0].is_valid:
        raise ValueError("Expected one closed blade section")
    poly = polygons[0]
    return (
        [poly.centroid.x, poly.centroid.y, z],
        poly.area,
        poly.bounds[3] - poly.bounds[1],
    )


def blade_profile(mesh, spacing):
    zs = np.linspace(-END_Z, END_Z, int(np.ceil(2 * END_Z / spacing)) + 1)
    # Include the short CAD crown segments. Neighbouring float32 STL vertices can describe one plane.
    features = np.unique(np.round(mesh.vertices[:, 2], 5))
    z = np.unique(np.r_[zs, features[abs(features) < END_Z]])
    z = z[np.r_[True, np.diff(z) > 1e-6]]
    p = np.array([section(mesh, v)[0] for v in z])
    d = np.diff(p, axis=0)
    ds = np.linalg.norm(d, axis=1)
    tangent = d / ds[:, None]
    dims = np.array([section(mesh, v)[1:] for v in (z[1:] + z[:-1]) / 2])
    width = dims[:, 1]
    area = dims[:, 0] * tangent[:, 2]
    thick = area / width
    if np.max(abs(tangent[:, 1])) > 1e-5 or np.any(thick >= width):
        raise ValueError("Expected the broad CAD blade direction along y")
    y = np.tile([0.0, 1.0, 0.0], (len(tangent), 1))
    x = np.cross(y, tangent)
    # Saint-Venant rectangular torsion constant, with thickness as the smaller side.
    aspect = thick / width
    J = width * thick**3 * (1 / 3 - 0.21 * aspect * (1 - aspect**4 / 12))
    stiffness = np.c_[
        E_MPA * thick * width**3 / 12,
        E_MPA * width * thick**3 / 12,
        E_MPA * J / (2 * (1 + NU)),
    ]
    basis = np.stack([x, y, tangent], axis=2)
    compliance = (basis / stiffness[:, None, :]) @ basis.transpose(0, 2, 1)
    return p, ds, tangent, E_MPA * area, compliance, basis, stiffness, width, thick


@njit(cache=True)
def derivative(state, n, m0, tangent, ea, compliance):
    pos = state[:3]
    orient = state[3:].reshape((3, 3))
    axis = orient @ tangent
    moment = m0 - np.cross(pos, n)
    omega = orient @ (compliance @ (orient.T @ moment))
    result = np.empty(12)
    result[:3] = axis * (1 + np.dot(n, axis) / ea)
    # Q' = skew(omega) Q transports the deviation from the stress-free CAD directors.
    for j in range(3):
        result[3 + j] = omega[1] * orient[2, j] - omega[2] * orient[1, j]
        result[6 + j] = omega[2] * orient[0, j] - omega[0] * orient[2, j]
        result[9 + j] = omega[0] * orient[1, j] - omega[1] * orient[0, j]
    return result


@njit(cache=True)
def integrate_from(state, wrench, ds, tangent, ea, compliance):
    n, m0 = wrench[:3], wrench[3:]
    history = np.empty((len(ds) + 1, 12))
    history[0] = state
    for i in range(len(ds)):
        h = ds[i]
        k1 = derivative(state, n, m0, tangent[i], ea[i], compliance[i])
        k2 = derivative(state + h / 2 * k1, n, m0, tangent[i], ea[i], compliance[i])
        k3 = derivative(state + h / 2 * k2, n, m0, tangent[i], ea[i], compliance[i])
        k4 = derivative(state + h * k3, n, m0, tangent[i], ea[i], compliance[i])
        state = state + (h / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
        history[i + 1] = state
    return history


def disk_motion(rod, z, module):
    det = rod.evaluate(z, detail=True)[2]
    i = module * rod.sub
    j = i + rod.sub
    base = det["frames"][i] @ CAD_TO_ROD
    R = base.T @ det["frames"][j] @ CAD_TO_ROD
    d = 1000 * base.T @ (det["points"][j] - det["points"][i]) - [0, 0, 96]
    return R, d


def solve_blade(profile, R, d):
    p, ds, tangent, ea, compliance, basis, stiffness, width, thick = profile
    chord = p[-1] - p[0]
    tip = chord + d + (R - np.eye(3)) @ (p[-1] - [0, 0, 48.0])
    length = ds.sum()
    rv = Rotation.from_matrix(R).as_rotvec()
    # Multiple shooting bounds the sensitivity of long slender spans under axial tension.
    cuts = np.linspace(0, len(ds), 5, dtype=int)
    coords = np.zeros(6 + 6 * (len(cuts) - 2))
    older = coords.copy()
    length_scale = length / (len(cuts) - 1)
    cases = []

    def shoot(unknown, wanted, end_rotation, get_field=False):
        internal = unknown[6:].reshape(-1, 6)
        centres = np.vstack(
            [np.zeros(3), p[cuts[1:-1]] - p[0] + internal[:, :3], wanted]
        )
        frames = np.concatenate(
            [
                np.eye(3)[None, :, :],
                Rotation.from_rotvec(internal[:, 3:]).as_matrix(),
                end_rotation[None, :, :],
            ],
            axis=0,
        )
        matches, fields = [], []
        for b, (lo, hi) in enumerate(zip(cuts[:-1], cuts[1:])):
            start = np.r_[centres[b], frames[b].ravel()]
            arc = integrate_from(
                start,
                unknown[:6],
                ds[lo:hi],
                tangent[lo:hi],
                ea[lo:hi],
                compliance[lo:hi],
            )
            last = arc[-1]
            angle = Rotation.from_matrix(
                last[3:].reshape(3, 3) @ frames[b + 1].T
            ).as_rotvec()
            matches.append(np.r_[last[:3] - centres[b + 1], length_scale * angle])
            if get_field:
                fields.append(arc if b == 0 else arc[1:])
        return np.vstack(fields) if get_field else np.concatenate(matches)

    fraction, increment, previous_increment = 0.0, 0.125, 0.125
    rejected = []
    while fraction < 1.0:
        increment = min(increment, 1.0 - fraction)
        trial = fraction + increment
        wanted = chord + trial * (tip - chord)
        end_rotation = Rotation.from_rotvec(trial * rv).as_matrix()
        predictor = coords + (coords - older) * increment / previous_increment
        sol = least_squares(
            shoot,
            predictor,
            args=(wanted, end_rotation),
            method="lm",
            x_scale="jac",
            max_nfev=250,
            xtol=1e-10,
            ftol=1e-10,
            gtol=1e-10,
        )
        error = float(np.linalg.norm(sol.fun))
        if not np.isfinite(error) or error > 2e-5:
            rejected.append(
                dict(fraction=trial, residual_mm=error if np.isfinite(error) else None)
            )
            increment *= 0.5
            if increment < 1 / 256:
                return dict(
                    converged=False,
                    last_accepted_fraction=fraction,
                    endpoint_residual_mm=cases,
                    rejected_continuation=rejected,
                )
            continue
        cases.append(error)
        fraction, previous_increment = trial, increment
        increment = min(0.125, 2 * increment)
        older, coords = coords, sol.x
    wrench = coords[:6]
    history = shoot(coords, tip, R, True)
    max_orth = max(
        np.linalg.norm(f.reshape(3, 3).T @ f.reshape(3, 3) - np.eye(3))
        for f in history[:, 3:]
    )
    if max_orth > 1e-5:
        raise ValueError("Strip director drift exceeds tolerance")
    fields = []
    # Recover outer-fibre longitudinal strain on each side of each CAD segment at its ends.
    for i in range(len(ds)):
        for k in (i, i + 1):
            pos = history[k, :3]
            local = history[k, 3:].reshape(3, 3) @ basis[i]
            moment = local.T @ (wrench[3:] - np.cross(pos, wrench[:3]))
            kap = moment / stiffness[i]
            axial = np.dot(wrench[:3], local[:, 2]) / ea[i]
            excursion = (abs(kap[0]) * width[i] + abs(kap[1]) * thick[i]) / 2
            fields.append((axial - excursion, axial + excursion, p[k, 2]))
    field = np.array(fields)
    a, b = field[:, 0].argmin(), field[:, 1].argmax()
    return dict(
        converged=True,
        endpoint_residual_mm=cases,
        rejected_continuation=rejected,
        orthogonality_error=max_orth,
        rest_material_length_mm=length,
        imposed_chord_mm=np.linalg.norm(tip),
        geometric_extension_lower_bound=max(0.0, np.linalg.norm(tip) / length - 1),
        force_in_proximal_CAD_N=wrench[:3],
        proximal_internal_moment_Nmm=wrench[3:],
        distal_internal_moment_Nmm=wrench[3:] - np.cross(history[-1, :3], wrench[:3]),
        peak_tension_strain=field[b, 1],
        peak_tension_z_mm=field[b, 2],
        peak_compression_strain=field[a, 0],
        peak_compression_z_mm=field[a, 2],
    )


def run(out, spacings):
    rod, states, _ = load_motion()
    rows = read_csv(SOURCE / "rope_tensions_every_step.csv.gz")
    cells = (states / rod.scale).reshape(len(states), 6, rod.sub, 4)[:, :4]
    denom = 1000 * rod.l * (1 + cells[:, :, :, 3])
    cases = []
    for module in range(4):
        for axis, label in ((1, "stiff"), (2, "compliant")):
            kappa = cells[:, module, :, axis] / denom[:, module]
            i, j = np.unravel_index(np.abs(kappa).argmax(), kappa.shape)
            cases.append(
                dict(
                    module=f"U{module + 1}",
                    direction=label,
                    step=int(i),
                    cell=int(j + 1),
                    signed_curvature_rad_per_current_mm=kappa[i, j],
                    phase=rows[i]["phase"],
                )
            )
    write_csv(out / "u_axis_ranking.csv", cases)
    stiff = max(cases[::2], key=lambda v: abs(v["signed_curvature_rad_per_current_mm"]))
    easy = max(cases[1::2], key=lambda v: abs(v["signed_curvature_rad_per_current_mm"]))
    same = next(
        v
        for v in cases
        if v["direction"] == "compliant" and v["module"] == stiff["module"]
    )
    targets = {(v["module"], v["step"]): v for v in [stiff, same, easy]}
    mesh = trimesh.load_mesh(CAD / "guides_v2/U_leaf_springs.stl")
    parts = sorted(mesh.split(), key=lambda m: tuple(np.sign(m.centroid[:2])))
    if len(parts) != 4:
        raise ValueError("Expected two opposing spring pairs")
    results = []
    for spacing in spacings:
        for part in parts:
            p = blade_profile(part, spacing)
            for (name, step), v in targets.items():
                R, d = disk_motion(rod, states[step], int(name[1]) - 1)
                answer = solve_blade(p, R, d)
                results.append(
                    dict(
                        **v,
                        gauge_spacing_mm=spacing,
                        blade_x_sign=int(np.sign(part.centroid[0])),
                        blade_y_sign=int(np.sign(part.centroid[1])),
                        disk_translation_mm=d,
                        disk_rotation_deg=Rotation.from_matrix(R).as_rotvec(
                            degrees=True
                        ),
                        **answer,
                    )
                )
                print(
                    spacing,
                    name,
                    step,
                    results[-1]["blade_x_sign"],
                    results[-1]["blade_y_sign"],
                    answer["converged"],
                    answer.get("peak_tension_strain"),
                    flush=True,
                )
            save(
                out / "u_blades.json",
                dict(trial_E_MPa=E_MPA, trial_nu=NU, end_z_mm=END_Z, solutions=results),
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--spacing", type=float, nargs="+", default=[2.0, 1.0, 0.5])
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out, a.spacing)
