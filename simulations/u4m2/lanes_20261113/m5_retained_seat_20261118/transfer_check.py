"""Measure CAD-to-submodel registration error separately from the displacement interpolated there."""

import argparse
import json
from pathlib import Path

from clearance import CASES, CAD, b, j, np, prepared_webs
from corrected import local_transfer


def shell_footprint(body, cache):
    mesh = np.load(cache / "mesh_0p025.npz")
    rows = []
    for station in j.STATIONS:
        for _, angle, corners, weights, _, _, _, _, outside in prepared_webs(
            body, station, 0.1, mesh
        ):
            triangles = mesh["x"][corners]
            targets = np.einsum("ij,ijk->ik", weights, triangles)
            # Affine weights locate the source point even outside the closest triangle.
            edges = np.roll(triangles, -1, axis=1) - triangles
            delta = targets[:, None, :] - triangles
            fraction = np.clip((delta * edges).sum(2) / (edges * edges).sum(2), 0, 1)
            distance = np.linalg.norm(delta - fraction[:, :, None] * edges, axis=2).min(
                axis=1
            )
            distance[weights.min(axis=1) >= 0] = 0
            rows.append(
                dict(
                    station=station,
                    rib_deg=float(angle),
                    vertices=len(targets),
                    flagged_by_triangle_finder=outside,
                    above_one_micrometre=int((distance > 0.001).sum()),
                    above_ten_micrometres=int((distance > 0.01).sum()),
                    maximum_distance_to_shell_triangle_mm=float(distance.max()),
                    p99_distance_mm=float(np.quantile(distance, 0.99)),
                    worst_reference_r_z_mm=targets[distance.argmax()].tolist(),
                )
            )
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fields", type=Path, required=True)
    ap.add_argument("--feature-fields", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    body = b.load(CAD / "parts/M5_machined_body.stl")
    patch = dict(np.load(a.fields / "patch_mesh.npz"))
    feature = dict(np.load(a.feature_fields / "patch_mesh.npz"))
    refs = []
    rows = []
    for z in j.STATIONS:
        # The geometry and units match the CAD transfer. Use the 67.5 degree manufactured web at each station.
        obj = body.translate((0, 0, -z)).rotate((0, 0, -67.5)) ^ b.box(
            (12, -1.501, -4.85), (26, 1.501, 4.85)
        )
        v = (
            obj.simplify(0.0005)
            .refine_to_length(0.15)
            .to_mesh64()
            .vert_properties[:, :3]
        )
        x = (v - [j.R_PIVOT, 0, 0]) @ j.web_axes(z)
        sel, elem, N, error, pel, pN = local_transfer(x, patch, "fine", 2.7, 1.0, True)
        _, fe, fN, ferr = local_transfer(x, feature, "fine", 2.7, 1.0)
        r = np.linalg.norm(x[sel, :2], axis=1)
        bearing = r <= 0.73
        worst = x[sel][error.argmax()]
        refs.append(
            dict(
                station=z,
                points=int(sel.sum()),
                max_reference_distance_mm=float(error.max()),
                p99_reference_distance_mm=float(np.quantile(error, 0.99)),
                max_inside_radius_0p73_mm=float(error[bearing].max()),
                worst_location_spn_mm=worst.tolist(),
                feature_fitted_max_reference_distance_mm=float(ferr.max()),
                feature_fitted_max_inside_radius_0p73_mm=float(ferr[bearing].max()),
            )
        )
        for case in CASES:
            for angle in (67.5, 157.5, 247.5, 337.5):
                fn = f"{case}_{z}_{angle:g}.npz"
                f = np.load(a.fields / fn)
                u = f["u"]
                du = np.einsum("ij,ijk->ik", N, u[elem])
                alt = np.einsum("ij,ijk->ik", pN, u[pel])
                dist = np.linalg.norm(du - alt, axis=1)
                row = dict(
                    case=case,
                    station=z,
                    rib_deg=angle,
                    max_interpolated_displacement_difference_mm=float(dist.max()),
                    max_inside_radius_0p73_displacement_difference_mm=float(
                        dist[bearing].max()
                    ),
                )
                if (a.feature_fields / fn).exists():
                    g = np.load(a.feature_fields / fn)
                    trial = (
                        np.einsum("ij,ijk->ik", fN, g["u"][fe]) @ g["R"].T
                        + g["translation"]
                    )
                    actual = du @ f["R"].T + f["translation"]
                    row["feature_fitted_total_correction_difference_mm"] = float(
                        np.linalg.norm(trial - actual, axis=1).max()
                    )
                rows.append(row)
    a.out.mkdir(exist_ok=True, parents=True)
    (a.out / "transfer_sensitivity.json").write_text(
        json.dumps(
            dict(
                representative_web_azimuth_deg=67.5,
                reference=refs,
                loads=rows,
                global_shell_footprint=shell_footprint(body, a.cache),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
