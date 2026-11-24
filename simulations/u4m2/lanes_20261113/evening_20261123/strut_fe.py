"""Local quadratic-tetrahedron solid model of the M6 struts that carry the bonded guide lands.

Handoff item 2 of the 22 November 2026 evening run. Each bonded land of the crowned M6
candidate sits on one straight inclined PA12 strut of the actual CAD
(``end_bellmouth_v1/M6_lane_anchorC.stl``). Between its two nodes the strut is an isolated
8 mm^2 bar (z = -16.75 ... -6.5 mm at the z = -12 mm station, mirrored at +12 mm).

The strut is cropped from the CAD with two capped planes, meshed with TetGen and solved
as a linear-elastic P2 (10-node) tetrahedral continuum (PA12, E = 1,530 MPa, nu = 0.4, the
repository value). The two cut faces follow the homogenised rod map (the same
``to_station`` map that the Round 2 and 22 November bond models used); all CAD surfaces
are traction-free. The guide is NOT coupled ("free web"), so the strut strain is not
reduced by the bond. The displacement field at the bond points is a linear operator H of
the cut-face displacements; H is precomputed once per strut and mesh.

Outputs go only under this run's ``results/`` folder.
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl
import tetgen
import trimesh
from scipy.spatial import cKDTree

E_PA12, NU_PA12 = 1530.0, 0.4

QA, QB = 0.5854101966249685, 0.1381966011250105
QP = np.full((4, 4), QB) + np.eye(4) * (QA - QB)  # 4-point barycentric rule, weights 1/4
EDGES = ((0, 1), (1, 2), (0, 2), (0, 3), (1, 3), (2, 3))


def crop_strut(module, angle_deg, z_lo, z_hi):
    """Watertight crop of the single strut at ``angle_deg`` between two capped z planes."""
    c = trimesh.intersections.slice_mesh_plane(module, [0, 0, 1], [0, 0, z_lo], cap=True)
    c = trimesh.intersections.slice_mesh_plane(c, [0, 0, -1], [0, 0, z_hi], cap=True)
    want = np.array([np.cos(np.radians(angle_deg)), np.sin(np.radians(angle_deg))])
    parts = c.split(only_watertight=False)
    best = max(parts, key=lambda p: p.centroid[:2] @ want / np.linalg.norm(p.centroid[:2]))
    if not best.is_watertight or best.body_count != 1:
        raise ValueError("strut crop is not a single watertight body")
    return best


def mesh(strut, h):
    tg = tetgen.TetGen(np.asarray(strut.vertices, float), np.asarray(strut.faces, np.int32))
    vmax = h ** 3 / (6 * np.sqrt(2))  # volume of a regular tetrahedron of edge h
    nodes, tets = tg.tetrahedralize(switches=f"pq1.5/10a{vmax:.6f}Q")[:2]
    return np.asarray(nodes, float), np.asarray(tets, np.int64)


def p2(nodes, tets):
    """Add edge mid-nodes: returns (X, conn10) with VTK-like order v0..v3, e01,e12,e02,e03,e13,e23."""
    e = np.sort(np.concatenate([tets[:, list(ab)] for ab in EDGES]), axis=1)
    uniq, inv = np.unique(e, axis=0, return_inverse=True)
    mid = 0.5 * (nodes[uniq[:, 0]] + nodes[uniq[:, 1]])
    X = np.vstack([nodes, mid])
    conn = np.hstack([tets, len(nodes) + inv.reshape(6, -1).T])
    return X, conn


def shape(L):
    """P2 shape functions and barycentric derivatives at barycentric points L (n,4)."""
    N = np.empty((len(L), 10))
    dN = np.zeros((len(L), 10, 4))
    for i in range(4):
        N[:, i] = L[:, i] * (2 * L[:, i] - 1)
        dN[:, i, i] = 4 * L[:, i] - 1
    for k, (a, b) in enumerate(EDGES):
        N[:, 4 + k] = 4 * L[:, a] * L[:, b]
        dN[:, 4 + k, a] = 4 * L[:, b]
        dN[:, 4 + k, b] = 4 * L[:, a]
    return N, dN


def bary_grad(Xv):
    """Gradients of barycentric coordinates (ne,4,3) and volumes for vertex coords (ne,4,3)."""
    J = (Xv[:, 1:] - Xv[:, :1]).transpose(0, 2, 1)  # columns x1-x0, x2-x0, x3-x0
    vol = np.linalg.det(J) / 6
    Jinv = np.linalg.inv(J)  # rows = grad L1..L3
    g = np.concatenate([-Jinv.sum(1, keepdims=True), Jinv], axis=1)
    return g, vol


def stiffness(X, conn, E=E_PA12, nu=NU_PA12):
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    C = np.zeros((6, 6))
    C[:3, :3] = lam
    C[np.arange(3), np.arange(3)] += 2 * mu
    C[np.arange(3, 6), np.arange(3, 6)] = mu
    g, vol = bary_grad(X[conn[:, :4]])
    if (vol <= 0).any():
        raise ValueError("inverted tetrahedra")
    ne = len(conn)
    Ke = np.zeros((ne, 30, 30))
    _, dNq = shape(QP)
    for q in range(4):
        G = np.einsum("nk,ekx->enx", dNq[q], g)  # (ne,10,3)
        B = np.zeros((ne, 6, 30))
        for a in range(10):
            gx, gy, gz = G[:, a, 0], G[:, a, 1], G[:, a, 2]
            c = 3 * a
            B[:, 0, c], B[:, 1, c + 1], B[:, 2, c + 2] = gx, gy, gz
            B[:, 3, c + 1], B[:, 3, c + 2] = gz, gy
            B[:, 4, c], B[:, 4, c + 2] = gz, gx
            B[:, 5, c], B[:, 5, c + 1] = gy, gx
        Ke += np.einsum("eij,jk,ekl->eil", B.transpose(0, 2, 1), C, B) * (vol / 4)[:, None, None]
    dof = (3 * conn[:, :, None] + np.arange(3)).reshape(ne, 30)
    rows = np.repeat(dof, 30, axis=1).ravel()
    cols = np.tile(dof, (1, 30)).ravel()
    K = sp.csc_matrix((Ke.ravel(), (rows, cols)), shape=(3 * len(X),) * 2)
    return K, float(vol.sum())


def locate(X, conn, pts, k_near=64):
    """Interpolation matrix (3m x 3n) of the P2 field at points (nearest containing tet)."""
    Xv = X[conn[:, :4]]
    tree = cKDTree(Xv.mean(1))
    rows, cols, vals, worst = [], [], [], 0.0
    for i, p in enumerate(pts):
        _, cand = tree.query(p, k=min(k_near, len(conn)))
        J = (Xv[cand, 1:] - Xv[cand, :1]).transpose(0, 2, 1)
        l123 = np.linalg.solve(J, (p - Xv[cand, 0])[..., None])[..., 0]
        L = np.column_stack([1 - l123.sum(1), l123])
        k = int(np.argmax(L.min(1)))
        worst = min(worst, float(L[k].min()))
        N, _ = shape(L[k:k + 1])
        for a, node in enumerate(conn[cand[k]]):
            for d in range(3):
                rows.append(3 * i + d)
                cols.append(3 * node + d)
                vals.append(N[0, a])
    M = sp.csr_matrix((vals, (rows, cols)), shape=(3 * len(pts), 3 * len(X)))
    return M, worst


class Strut:
    """One cropped, meshed strut with a precomputed bond-point operator."""

    def __init__(self, module, angle_deg, z_lo, z_hi, h, points):
        self.angle, self.z = angle_deg, (z_lo, z_hi)
        self.solid = crop_strut(module, angle_deg, z_lo, z_hi)
        v, t = mesh(self.solid, h)
        X, conn = p2(v, t)
        self.X, self.conn = X, conn
        K, self.volume = stiffness(X, conn)
        tol = 1e-6
        fixed_node = (np.abs(X[:, 2] - z_lo) < tol) | (np.abs(X[:, 2] - z_hi) < tol)
        self.bnodes = np.flatnonzero(fixed_node)
        bd = (3 * self.bnodes[:, None] + np.arange(3)).ravel()
        fd = np.setdiff1d(np.arange(3 * len(X)), bd)
        self.bd, self.fd = bd, fd
        M, self.locate_min_bary = locate(X, conn, points)
        # u_f = -Kff^-1 Kfb u_b ; pad displacement = M_f u_f + M_b u_b = H u_b.
        lu = spl.splu(K[fd][:, fd].tocsc())
        Mf = M[:, fd].toarray()
        Y = lu.solve(Mf.T.copy(), trans="T")  # Kff^-T Mf^T (Kff symmetric)
        self.H = M[:, bd].toarray() - (K[fd][:, bd].T @ Y).T
        self.n_tets, self.n_nodes = len(conn), len(X)
        self.max_dofs = 3 * len(X)
        self._lu, self._K = lu, K

    def boundary_points(self):
        return self.X[self.bnodes]

    def full_field(self, ub):
        u = np.zeros(3 * len(self.X))
        u[self.bd] = ub
        u[self.fd] = -self._lu.solve(self._K[self.fd][:, self.bd] @ ub)
        return u.reshape(-1, 3)
