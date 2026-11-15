"""Conforming axial refinement before nonlinear beam mapping of a CAD surface.

STL triangles are planar only in the undeformed configuration. Mapping just their
original corners replaces curved material surfaces by chords. Split shared edges
before mapping; selecting by axial span is sufficient because map_cad is affine
in the transverse coordinates at fixed axial position. This controls a geometric
discretisation, not the rod equilibrium mesh or a physical contact solution.
"""
import numpy as np
import trimesh


def refine_axial(mesh, max_span_mm, max_rounds=20):
    """Return a conforming triangle mesh with every edge's |delta z| bounded.

    Shared edges get exactly one midpoint. All adjacent faces are retriangulated
    using the same midpoint, including faces with only one or two marked edges.
    Unmarked edges and their neighbours remain conforming. No face is projected
    or moved, so the original flat CAD surface and volume are preserved.
    """
    if not np.isfinite(max_span_mm) or max_span_mm <= 0:
        raise ValueError('max_span_mm must be finite and positive')
    vertices = np.asarray(mesh.vertices, dtype=float).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    for _ in range(max_rounds):
        oriented = faces[:, [[0, 1], [1, 2], [2, 0]]]
        edges, inverse = np.unique(np.sort(oriented.reshape(-1, 2), axis=1),
                                   axis=0, return_inverse=True)
        split = abs(vertices[edges[:, 0], 2] - vertices[edges[:, 1], 2]) > max_span_mm * (1 + 1e-12)
        if not split.any():
            return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        midpoint_ids = np.full(len(edges), -1, dtype=np.int64)
        midpoint_ids[split] = np.arange(len(vertices), len(vertices) + split.sum())
        vertices = np.vstack([vertices, vertices[edges[split]].mean(axis=1)])
        mids = midpoint_ids[inverse].reshape(-1, 3)
        mask = (mids >= 0) @ np.array([1, 2, 4])
        parts = [faces[mask == 0]]
        # Rotate each local face so the same templates cover all 1/2-edge cases.
        for rotation, single, double in [(0, 1, 3), (1, 2, 6), (2, 4, 5)]:
            for code, count in [(single, 1), (double, 2)]:
                chosen = mask == code
                if not chosen.any():
                    continue
                f = np.roll(faces[chosen], -rotation, axis=1)
                m = np.roll(mids[chosen], -rotation, axis=1)
                a, b, c = f.T
                u, v, _ = m.T
                if count == 1:
                    parts.extend([np.c_[a, u, c], np.c_[u, b, c]])
                else:
                    parts.extend([np.c_[u, b, v], np.c_[a, u, c], np.c_[u, v, c]])
        chosen = mask == 7
        if chosen.any():
            a, b, c = faces[chosen].T
            u, v, w = mids[chosen].T
            parts.extend([np.c_[a, u, w], np.c_[u, b, v], np.c_[w, v, c], np.c_[u, v, w]])
        faces = np.vstack(parts)
    raise RuntimeError('axial refinement did not reach the requested span')


def axial_span(mesh):
    return float(np.ptp(mesh.vertices[mesh.faces, 2], axis=1).max())
