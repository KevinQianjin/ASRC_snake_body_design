"""Transfer local contact displacements back to the machined CAD and check shared-guide compatibility."""

import argparse
import json
from pathlib import Path

import fcl
from scipy.spatial.transform import Rotation
from clearance import (
    CASES,
    CAD,
    b,
    bounds_distance,
    collider,
    j,
    map_vertices,
    md,
    np,
    prepared_webs,
    read_parts,
    station_parts,
)
from contact import LEVELS, SIGNS


def local_transfer(x, mesh, level, length, crown, compare_parameterisation=False):
    _, nr, ny = LEVELS[level]
    q = mesh["q"]
    v = mesh["x"]
    na = len(v) // ((nr + 1) * (ny + 1))
    grid = v.reshape(na, nr + 1, ny + 1, 3)
    angles = np.mod(np.arctan2(grid[:, 0, 0, 1], grid[:, 0, 0, 0]), 2 * np.pi)
    angles = np.r_[angles, 2 * np.pi]
    pt = x[np.abs(x[:, 0]) <= length + 1e-6]
    angle = np.mod(np.arctan2(pt[:, 1], pt[:, 0]), 2 * np.pi)
    r = np.linalg.norm(pt[:, :2], axis=1)
    ia = np.clip(np.searchsorted(angles, angle, side="right") - 1, 0, na - 1)
    p = (angle - angles[ia]) / (angles[ia + 1] - angles[ia])
    xmax = np.minimum(
        length / np.maximum(1e-9, abs(np.cos(angle))),
        0.75 / np.maximum(1e-9, abs(np.sin(angle))),
    )
    waist = j.hole_radius(pt[:, 2], crown_radius=crown)
    radial = nr * np.clip((r - waist) / (xmax - waist), 0, 1) ** (1 / 1.30)
    height = ny / 2 * (1 + np.clip(pt[:, 2] / j.face_height(r), -1, 1))
    ir = np.clip(radial.astype(int), 0, nr - 1)
    ih = np.clip(height.astype(int), 0, ny - 1)
    # The analytic parameterisation seeds an inverse trilinear lookup in the actual HEX8 mesh.
    uvw = 2 * np.c_[radial - ir, p, height - ih] - 1
    param_elem = q[(ia * nr + ir) * ny + ih]
    param_N = np.prod((1 + uvw[:, None, :] * SIGNS) / 2, axis=2)
    for _ in range(10):
        elem = q[(ia * nr + ir) * ny + ih]
        nodes = v[elem]
        factor = (1 + uvw[:, None, :] * SIGNS) / 2
        N = np.prod(factor, axis=2)
        diff = pt - np.einsum("ij,ijk->ik", N, nodes)
        der = np.stack(
            [
                SIGNS[:, k] / 2 * factor[:, :, (k + 1) % 3] * factor[:, :, (k + 2) % 3]
                for k in range(3)
            ],
            axis=2,
        )
        jac = np.einsum("eik,eij->ejk", der, nodes)
        delta = np.linalg.solve(jac, diff[:, :, None])[:, :, 0]
        uvw += delta
        di = (uvw > 1.00001).astype(int) - (uvw < -1.00001).astype(int)
        ri = np.clip(ir + di[:, 0], 0, nr - 1)
        ti = np.clip(ih + di[:, 2], 0, ny - 1)
        uvw[:, 0] -= 2 * (ri - ir)
        uvw[:, 1] -= 2 * di[:, 1]
        uvw[:, 2] -= 2 * (ti - ih)
        change = np.any(ri != ir) or np.any(ti != ih) or np.any(di[:, 1] != 0)
        ir, ia, ih = ri, (ia + di[:, 1]) % na, ti
        if not change and abs(delta).max() < 1e-8:
            break
    elem = q[(ia * nr + ir) * ny + ih]
    uvw = np.clip(uvw, -1, 1)
    N = np.prod((1 + uvw[:, None, :] * SIGNS) / 2, axis=2)
    error = np.linalg.norm(np.einsum("ij,ijk->ik", N, v[elem]) - pt, axis=1)
    basic = (np.abs(x[:, 0]) <= length + 1e-6, elem, N, error)
    return (*basic, param_elem, param_N) if compare_parameterisation else basic


def rigid_fit(angles, translations):
    r = np.asarray(
        [
            [j.R_PIVOT * np.cos(np.radians(a)), j.R_PIVOT * np.sin(np.radians(a)), 0.0]
            for a in angles
        ]
    )
    # Positive translations are movements of the web relative to a stationary guide.
    H = np.vstack([np.c_[np.eye(3), np.cross(np.eye(3), pos).T] for pos in r])
    u = np.linalg.lstsq(H, -np.asarray(translations).ravel(), rcond=None)[0]
    miss = (H @ u).reshape(-1, 3) + translations
    bores = np.array(
        [
            [rad * np.cos(a), rad * np.sin(a), 0]
            for rad in (24, 28)
            for a in np.arange(4) * np.pi / 2
        ]
    )
    motions = u[:3] + np.cross(u[3:], bores)
    return dict(
        translation_xyz_mm=u[:3].tolist(),
        rotation_xyz_rad=u[3:].tolist(),
        maximum_incompatibility_mm=float(np.linalg.norm(miss, axis=1).max()),
        rms_incompatibility_mm=float(np.sqrt(np.mean(np.sum(miss**2, axis=1)))),
        maximum_bore_shift_mm=float(np.linalg.norm(motions, axis=1).max()),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--fields", type=Path, required=True)
    ap.add_argument("--edge", type=float, default=0.15)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    shell = np.load(a.cache / "mesh_0p025.npz")
    patch = dict(np.load(a.fields / "patch_mesh.npz"))
    level = str(patch["level"])
    length = float(patch["length"])
    crown = float(patch["crown"])
    parts = read_parts(CAD / "parts")
    body = b.load(CAD / "parts/M5_machined_body.stl")
    rows = []
    quality = []
    for z in j.STATIONS:
        builds = prepared_webs(body, z, a.edge, shell)
        case_data = {
            case: dict(candidates=[], translations=[], angles=[]) for case in CASES
        }
        hw = list(station_parts(parts, z))
        static = [fcl.CollisionObject(collider(obj)) for _, _, obj in hw]
        for web in builds:
            i, angle = web[:2]
            a0 = np.radians(angle)
            W = Rotation.from_euler("z", angle, degrees=True).as_matrix() @ j.web_axes(
                z
            )
            centre = [j.R_PIVOT * np.cos(a0), j.R_PIVOT * np.sin(a0), z]
            mounted = any(
                abs((angle - ang + 180) % 360 - 180) < 1e-3 for ang in j.ANGLES
            )
            if mounted:
                sel, elem, N, error = local_transfer(
                    (web[7] - centre) @ W, patch, level, length, crown
                )
                quality.append(
                    dict(
                        station=z,
                        rib_deg=float(angle),
                        points=len(error),
                        max_projection_error_mm=float(error.max()),
                        p99_projection_error_mm=float(np.quantile(error, 0.99)),
                    )
                )
            for case, state in case_data.items():
                with np.load(a.cache / f"{case}_0p025.npz") as pose:
                    world = map_vertices(pose["fields"], pose, z, web)
                if mounted:
                    with np.load(a.fields / f"{case}_{z}_{angle:g}.npz") as pc:
                        u = np.zeros_like(world)
                        u[sel] = np.einsum("ij,ijk->ik", N, pc["u"][elem])
                        world += (u @ pc["R"].T + pc["translation"]) @ W.T
                        state["translations"].append((W @ pc["translation"]).tolist())
                        state["angles"].append(float(angle))
                solid = md.Manifold(
                    md.Mesh64(
                        np.array(world, order="C", copy=True),
                        np.array(web[5], dtype=np.uint64, order="C", copy=True),
                    )
                )
                if solid.status() != md.Error.NoError or solid.volume() <= 0:
                    raise ValueError("Invalid corrected surface")
                query = fcl.CollisionObject(collider(solid))
                for (label, fam, part), obs in zip(hw, static):
                    if bounds_distance(solid.bounding_box(), part.bounding_box()) > 0.6:
                        continue
                    result = fcl.DistanceResult()
                    gap = max(
                        0.0,
                        fcl.distance(
                            query,
                            obs,
                            fcl.DistanceRequest(enable_nearest_points=True),
                            result,
                        ),
                    )
                    if gap > 0.6:
                        continue
                    vol = max(0.0, (solid ^ part).volume()) if gap < 1e-7 else 0.0
                    loc = (
                        np.mean(result.nearest_points, axis=0).tolist()
                        if gap > 1e-7
                        else None
                    )
                    state["candidates"].append(
                        dict(
                            rib_deg=float(angle),
                            part=label,
                            family=fam,
                            gap_mm=gap,
                            intersection_mm3=vol,
                            location_xyz_mm=loc,
                        )
                    )
        for case, state in case_data.items():
            rr = state["candidates"]
            support = lambda r: r["family"] in ("shoulder_pin", "threaded_cap")
            key = lambda q: (q["gap_mm"], -q["intersection_mm3"])
            rows.append(
                dict(
                    case=case,
                    station=z,
                    rigid_fit=rigid_fit(state["angles"], state["translations"]),
                    unintended=min((r for r in rr if not support(r)), key=key),
                    intended=min((r for r in rr if support(r)), key=key),
                    nearby_pairs=rr,
                )
            )
            print(
                case,
                z,
                rows[-1]["unintended"],
                rows[-1]["intended"]["intersection_mm3"],
                flush=True,
            )
    a.out.mkdir(exist_ok=True, parents=True)
    name = "corrected_edge" + str(a.edge).replace(".", "p") + ".json"
    (a.out / name).write_text(
        json.dumps(
            dict(surface_edge_mm=a.edge, transfer_quality=quality, stations=rows),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
