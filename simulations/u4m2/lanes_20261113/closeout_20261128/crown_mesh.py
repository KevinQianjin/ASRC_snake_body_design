"""Refine the actual M6 sleeve model at the two arch crowns on a bounded-memory host."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import resource
import sys
import time

from cvxopt import cholmod, matrix, spmatrix
import numpy as np
import pymetis
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.stats import qmc
import tetgen
import trimesh

HERE = Path(__file__).resolve().parent
EVENING = HERE.parent / "evening_20261127"
sys.path.insert(0, str(EVENING))
import hub_variant_fe as archived
from bore_contact import linear_offsets
from strain_check import element_strain

BS, BB, BF = archived.BS, archived.FS.BB, archived.BF
F = BB.F
STEPS = (1709, 1869, 1884)
GAUGES = (0.5, 1.0)
INPUTS = archived.EV25 / "results/rod_steps.npz"


def crown_centers():
    levels = json.loads((EVENING / "results/fe_baseline_q2p5.json").read_text())["levels"]
    case = levels[0]["steps"]["1869"]
    sites = {}
    for ring in ("ring0", "ring3"):
        center = np.asarray(case[f"arch_crown_{ring}"]["peak_location_mm"])
        sites[ring + "_arch"] = center
        sites[ring + "_opposed_arch"] = center * [-1, -1, 1]
    return sites


def refine_surface(lattice, edge):
    """Split shared edges in the crown windows while preserving the faceted surface."""
    centers = cKDTree(np.asarray(list(crown_centers().values())))
    mesh = lattice
    for _ in range(12):
        midpoints = mesh.vertices[mesh.edges_unique].mean(axis=1)
        selected = (centers.query(midpoints)[0] <= 1.70) & (mesh.edges_unique_length > edge)
        if not selected.any():
            assert mesh.is_volume and mesh.body_count == 1
            assert abs(mesh.volume - lattice.volume) < 1e-5
            return mesh
        indices = np.full(len(selected), -1, dtype=int)
        indices[selected] = len(mesh.vertices) + np.arange(selected.sum())
        split_faces = []
        for face, mid in zip(mesh.faces, indices[mesh.faces_unique_edges]):
            count = np.count_nonzero(mid >= 0)
            if count == 0:
                split_faces.append(face)
            elif count == 1:
                k = int(np.argmax(mid >= 0))
                a, b, c = np.roll(face, -k)
                m = mid[k]
                split_faces.extend(((a, m, c), (m, b, c)))
            elif count == 2:
                # Rotate the absent midpoint to the final edge, CA.
                k = (int(np.argmax(mid < 0)) + 1) % 3
                a, b, c = np.roll(face, -k)
                m, n = mid[k], mid[(k + 1) % 3]
                split_faces.extend(((a, m, c), (m, n, c), (m, b, n)))
            else:
                a, b, c = face
                m, n, p = mid
                split_faces.extend(((a, m, p), (m, b, n), (p, n, c), (m, n, p)))
        mesh = trimesh.Trimesh(vertices=np.vstack([mesh.vertices, midpoints[selected]]),
                               faces=split_faces, process=False)
    raise RuntimeError("Local shared-edge refinement did not reach the target")


def mesh_lattice(lattice, quality, max_volume, edge):
    surface = lattice if edge is None else refine_surface(lattice, edge)
    print("TetGen input faces", len(surface.faces), flush=True)
    for tolerance in ("", "T1e-9", "T1e-6"):
        mesher = tetgen.TetGen(np.asarray(surface.vertices, float), np.asarray(surface.faces, np.int32))
        switches = f"pq{quality}a{max_volume}{tolerance}Q"
        try:
            nodes, tets = mesher.tetrahedralize(switches=switches)[:2]
            return np.asarray(nodes, float), np.asarray(tets, np.int64)
        except RuntimeError:
            continue
    raise RuntimeError("TetGen could not mesh the cropped lattice")


def build_body(lattice, information, quality, max_volume, edge, max_tets):
    def bounded_mesh(solid, q, a):
        nodes, tets = mesh_lattice(solid, q, a, edge)
        if len(tets) > max_tets:
            raise MemoryError(f"{len(tets):,} tets exceed the bounded solve size of {max_tets:,}")
        return nodes, tets

    old_mesh, old_lattice = BS.tet_mesh, BS.lattice
    BS.tet_mesh = bounded_mesh
    BS.lattice = lambda: (lattice, information)
    try:
        body = BB.Body(quality, max_volume, 0.08)
    finally:
        BS.tet_mesh, BS.lattice = old_mesh, old_lattice
    assert len(body.clamped) > 0 and len(body.d1) > 0, "Both FE cut-face masters must exist"
    del body.K
    return body


def modal_solve(body):
    bare = body.system(500.0, 0.06)
    del body.Kr
    stiffness = BF.add_k(body, bare, BF.sleeve_backbone_stiffness_d1()[0])
    del bare
    prescribed = body.c1 + np.arange(3, 6)
    free = np.setdiff1d(np.arange(len(stiffness.indptr) - 1), prescribed)
    block = stiffness[free][:, free].tocsr()
    rhs = np.zeros((len(free), 15))
    rhs[:, :3] = -stiffness[free][:, prescribed].toarray()
    rhs[-12:, 3:] = np.eye(12)
    diagonal_scale = 1 / np.sqrt(block.diagonal())
    graph = block[::3, ::3].tocsr()
    graph.setdiag(0)
    graph.eliminate_zeros()
    ordering = pymetis.nested_dissection(
        pymetis.CSRAdjacency(graph.indptr, graph.indices)
    )[0]
    permutation = (3 * np.asarray(ordering)[:, None] + np.arange(3)).ravel()
    permutation = permutation[permutation < block.shape[0]]
    del graph
    print("Ordered reduced DOFs", len(free), flush=True)
    lower = sparse.tril(block, format="coo")
    lower.data *= diagonal_scale[lower.row] * diagonal_scale[lower.col]
    factor_matrix = spmatrix(lower.data, lower.row.astype(np.int64), lower.col.astype(np.int64),
                             size=block.shape)
    del lower
    factor = cholmod.symbolic(factor_matrix, p=matrix(permutation.astype(np.int64)), uplo="L")
    cholmod.numeric(factor_matrix, factor)
    print("Factored", flush=True)
    del factor_matrix
    work = matrix(rhs * diagonal_scale[:, None])
    cholmod.solve(factor, work)
    solution = np.array(work) * diagonal_scale[:, None]
    del factor, work
    residual = np.max(np.abs(block @ solution - rhs)) / np.abs(rhs).max()
    assert residual < 1e-7, residual
    modes = np.zeros((stiffness.shape[0], 15))
    modes[free] = solution
    modes[prescribed, :3] = np.eye(3)
    response = (stiffness[prescribed] @ modes[:, :3])
    ei = (BS.Z_HI - BS.Z_LO) / np.diag(np.linalg.inv(response))
    print("Relative residual", residual, "EI", ei[:2], flush=True)
    return modes, float(residual), ei[:2]


def gauge_points(length=12):
    u = qmc.Sobol(3, scramble=True, seed=319).random_base2(length)
    z = 2 * u[:, 1] - 1
    angle = 2 * np.pi * u[:, 2]
    transverse = np.sqrt(1 - z * z)
    return u[:, 0, None] ** (1 / 3) * np.column_stack(
        [transverse * np.cos(angle), transverse * np.sin(angle), z]
    )


def gauges(body, modes, centers):
    """Integrate affine P2 strains over the material portion of fixed-radius gauges."""
    data = {}
    offsets = gauge_points()
    nodal = (body.T @ modes[:body.n]).reshape(-1, 3, 15)
    Xv = body.X[body.conn[:, :4]]
    centroid = Xv.mean(1)
    grads, vol = F.bary_grad(Xv)
    for name, site in centers.items():
        # A tetrahedron that can enter the 1 mm gauge must overlap its bounding box.
        zone = np.flatnonzero(np.all((Xv.min(1) <= site + 1) & (Xv.max(1) >= site - 1), axis=1))
        local_tree = cKDTree(centroid[zone])
        metrics = {}
        for radius in GAUGES:
            found = np.zeros(len(offsets), dtype=bool)
            strain = np.zeros((len(offsets), 3, 3, 15))
            points = site + radius * offsets
            for start in range(0, len(points), 128):
                sl = slice(start, start + 128)
                p = points[sl]
                nearest = zone[local_tree.query(p, k=min(96, len(zone)))[1].reshape(len(p), -1)]
                u = np.einsum("pqki,pqi->pqk", grads[nearest, 1:], p[:, None] - Xv[nearest, 0])
                bary = np.concatenate([1 - u.sum(axis=2, keepdims=True), u], axis=2)
                score = bary.min(2)
                best = np.argmax(score, axis=1)
                ix = np.arange(len(p))
                valid = score[ix, best] >= -1e-9
                if not valid.any():
                    continue
                tet = nearest[ix, best][valid]
                _, shape_grad = F.shape(bary[ix, best][valid])
                gradient = np.einsum("pak,pkj->paj", shape_grad, grads[tet])
                H = np.einsum("paiq,paj->pijq", nodal[body.conn[tet]], gradient)
                strain[sl][valid] = (H + H.transpose(0, 2, 1, 3)) * 0.5
                found[sl] = valid
            assert found.sum() > 512, (name, radius, found.sum())
            count = len(points) // 2
            metrics[str(radius)] = dict(
                modes=strain[found].mean(0), half_modes=strain[:count][found[:count]].mean(0),
                material_fraction=float(found.mean()),
                local_tets=len(zone), min_tet_volume_mm3=float(vol[zone].min()),
                median_tet_edge_equivalent_mm=float(np.median((6 * np.sqrt(2) * vol[zone]) ** (1 / 3))),
            )
        data[name] = metrics
    return data


def reduce_metrics(metrics, loads):
    report = {}
    for site, by_radius in metrics.items():
        report[site] = {}
        for radius, data in by_radius.items():
            field = np.einsum("ijm,sm->sij", data["modes"], loads)
            principal = np.linalg.eigvalsh(field)
            magnitude = np.abs(principal).max(1)
            half = np.abs(np.linalg.eigvalsh(np.einsum("ijm,sm->sij", data["half_modes"], loads[list(STEPS)]))).max(1)
            report[site][radius] = {
                key: value for key, value in data.items() if not key.endswith("modes")
            } | {
                "three_states_abs_principal": magnitude[list(STEPS)].tolist(),
                "mission_max": float(magnitude.max()), "mission_max_state": int(magnitude.argmax()),
                "integration_relative_change": (np.abs(half / magnitude[list(STEPS)] - 1)).tolist(),
            }
    return report


def peak_regions(body, modal, loads):
    positions = body.X[body.conn[:, :4]].mean(1)
    radial = np.hypot(*positions[:, :2].T)
    axial = np.abs(positions[:, 2])
    regions = {
        "whole_lattice": np.ones(len(axial), dtype=bool),
        "crown_neighborhood": (axial > 19.97) & (axial < 24) & (radial > 7) & (radial < 13),
        "inner_rings": (axial > 3) & (axial < 7) & (radial > 6) & (radial < 13),
    }
    output, extra = {}, {}
    for step in STEPS:
        displacement = (body.T @ (modal[:body.n] @ loads[step])).reshape(-1, 3)
        strain, _ = element_strain(body.X, body.conn, displacement)
        magnitude = np.abs(np.linalg.eigvalsh(strain)).max(1)
        output[str(step)] = {}
        for name, mask in regions.items():
            index = int(np.argmax(np.where(mask, magnitude, -1)))
            output[str(step)][name] = dict(point_mm=positions[index].tolist(), strain=float(magnitude[index]))
            if step == 1869:
                extra["at_element_peak_" + name] = positions[index]
    return output, extra


def run(args):
    lattice, info = BS.lattice()
    if args.lattice:
        imported = trimesh.load_mesh(args.lattice)
        nodes = imported.vertices.copy()
        for cut in (BS.Z_LO, BS.Z_HI):
            nodes[abs(nodes[:, 2] - cut) < 1e-4, 2] = cut
        lattice = trimesh.Trimesh(vertices=nodes, faces=imported.faces, process=False)
        assert lattice.is_volume and lattice.body_count == 1
    if args.mesh_only:
        v, t = mesh_lattice(lattice, args.quality, args.volume, args.edge)
        print(len(v), len(t), flush=True)
        return
    start = time.monotonic()
    body = build_body(lattice, info, args.quality, args.volume, args.edge, args.max_tets)
    print("Built mesh", body.mesh, flush=True)
    U, residual, ei = modal_solve(body)
    with np.load(INPUTS) as samples:
        loads = np.c_[samples["end_rotvec"], samples["station_wrench"][:, 0], samples["station_wrench"][:, 1]]
    sites = crown_centers()
    peaks, extra = peak_regions(body, U, loads)
    if args.lattice:
        sites.update(extra)
    metrics = reduce_metrics(gauges(body, U, sites), loads)
    rings = np.einsum("rcm,sm->src", BF.ring_pose_maps(body, U), loads)
    end = loads @ U[body.c1:body.c1 + 6].T
    gap = 3.30 - linear_offsets(rings, end, BS.RING_Z, "cad")
    critical = np.unravel_index(np.argmin(gap), gap.shape)
    clearance = dict(min_mm=float(gap[critical]), step=int(critical[0]), ring=int(critical[1]),
                     selected_steps_gap_mm=gap[list(STEPS)].min(1).tolist())
    result = dict(
        source_revision="d9347e87ab3612342962125580187523a0b42fd5",
        input_hashes={path.name: sha256(path.read_bytes()).hexdigest()
                      for path in (BS.BODY, INPUTS, *( [args.lattice] if args.lattice else []))},
        versions={package: version(package) for package in ("numpy", "scipy", "tetgen", "cvxopt", "pymetis")},
        mesh=body.mesh, requested_local_edge_mm=args.edge, combined_EI_Nmm2=ei.tolist(),
        lattice_volume_mm3=lattice.volume, selected_states=list(STEPS), projected_states=len(loads),
        gauge_centers_mm={n: p.tolist() for n, p in sites.items()}, gauges=metrics, relative_residual=residual,
        element_center_peak_regions=peaks, linear_rod_clearance=clearance,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        elapsed_s=time.monotonic() - start,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(args.out, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--lattice", type=Path)
    parser.add_argument("--quality", type=float, default=5.0)
    parser.add_argument("--volume", type=float, default=0.4)
    parser.add_argument("--edge", type=float)
    parser.add_argument("--max-tets", type=int, default=208000)
    parser.add_argument("--mesh-only", action="store_true")
    run(parser.parse_args())
