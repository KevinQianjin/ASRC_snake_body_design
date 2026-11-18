"""Finite-rotation triangular shell on the eight CAD rib mid-surfaces (N, mm).

The membrane metric, director curvature and Mindlin transverse shear are
objective. Their tangent at the flat reference is the archived CST/Mindlin
formulation. Material elasticity is linear in these shell strains.
"""

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
from numba import njit
from scipy import sparse
from scipy.sparse.linalg import splu
from shapely.geometry import LineString
from shapely import set_precision, union_all
import triangle
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rib_joint_model as baseline

E = 1530.0
NU = 0.4
RING_WINDOWS = [(-20.0, -16.95), (-6.5, -3.45), (3.45, 6.5), (16.95, 20.0)]
STATIONS = (-12, 12)
AXES = np.eye(3)


def skew(v):
    x, y, z = v
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


SPINS = np.array([skew(axis) for axis in AXES])


def rotation(p):
    """Gibbs rotation and its exact first and second derivatives."""
    den = 1.0 + p @ p
    R = ((1.0 - p @ p) * AXES + 2.0 * (np.outer(p, p) + skew(p))) / den
    dR = np.empty((3, 3, 3))
    ddR = np.empty((3, 3, 3, 3))
    for i, ei in enumerate(AXES):
        dR[i] = (2.0 * (np.outer(ei, p) + np.outer(p, ei) + SPINS[i]) - 2.0 * p[i] * (AXES + R)) / den
    for i, ei in enumerate(AXES):
        for j, ej in enumerate(AXES):
            ddR[i, j] = (
                2.0 * (np.outer(ei, ej) + np.outer(ej, ei))
                - 2.0 * (i == j) * (AXES + R)
                - 2.0 * p[i] * dR[j]
                - 2.0 * p[j] * dR[i]
            ) / den
    return R, dR, ddR


def spin_map(p):
    """Map Gibbs-coordinate variations into spatial incremental rotation."""
    den = 1.0 + p @ p
    L = 2.0 * (AXES + skew(p)) / den
    dL = (2.0 * SPINS - 2.0 * p[:, None, None] * L) / den
    return L, dL


def rib_mesh(area, profile):
    """Conform mesh edges to attachment windows so their size survives refinement."""
    cuts = list(profile.interiors) + [profile.exterior]
    lines = [(15.0, s + a, 24.0, s + a) for s in STATIONS for a in (-1.62, -0.25, 0.25, 1.62)]
    lines += [(0.0, z, 35.0, z) for z in (-45.0, 45.0)]
    for lo, hi in RING_WINDOWS:
        lines += [(0.0, lo, 8.6, lo), (0.0, hi, 8.6, hi), (8.6, lo, 8.6, hi)]
    for z1, z2 in [(-48.0, -30.0), (30.0, 48.0)]:
        lines += [(3.3, z1, 3.3, z2)]
    for x0, z0, x1, z1 in lines:
        line = LineString([(x0, z0), (x1, z1)])
        cuts.append(line.intersection(profile))
    graph = union_all(cuts, grid_size=0.002)
    vertices, segments, ids = [], set(), {}
    for line in graph.geoms:
        if line.geom_type not in ("LineString", "LinearRing"):
            continue
        link = []
        for point in line.coords:
            key = tuple(np.round(point, 7))
            if key not in ids:
                ids[key] = len(vertices)
                vertices.append(key)
            link.append(ids[key])
        segments.update(tuple(sorted((a, b))) for a, b in zip(link, link[1:]) if a != b)
    geometry = dict(vertices=np.array(vertices), segments=np.array(sorted(segments)))
    if profile.interiors:
        from shapely.geometry import Polygon

        geometry["holes"] = np.array(
            [Polygon(r).representative_point().coords[0] for r in profile.interiors]
        )
    mesh = triangle.triangulate(geometry, f"pq26a{area}")
    return mesh["vertices"], mesh["triangles"]


def master_tags(x):
    r, z = x.T
    tol = 2.0e-6
    tags = np.full(len(x), "", dtype="U5")
    tags[(z <= -45.0 + tol) | ((r <= 3.3 + tol) & (z < -30))] = "D0"
    tags[(z >= 45.0 - tol) | ((r <= 3.3 + tol) & (z > 30))] = "D1"
    for j, (lo, hi) in enumerate(RING_WINDOWS):
        tags[(r <= 8.6 + tol) & (z >= lo - tol) & (z <= hi + tol)] = f"R{j}"
    for s in STATIONS:
        tags[(np.abs(z - s) <= 0.25 + tol) & (r > 15) & (r < 24)] = f"G{s:+}"
    return tags


def element_data(x, t, thick):
    """Each strain is quadratic in the three positions and three unit directors."""
    coord = x[t]
    det = np.linalg.det(coord[:, 1:] - coord[:, :1])
    b = (coord[:, [1, 2, 0], 1] - coord[:, [2, 0, 1], 1]) / det[:, None]
    c = (coord[:, [2, 0, 1], 0] - coord[:, [1, 2, 0], 0]) / det[:, None]
    u, v, dr, dz = [np.zeros((len(t), 6)) for _ in range(4)]
    u[:, ::2], v[:, ::2], dr[:, 1::2], dz[:, 1::2] = b, c, b, c

    def outer(a, b):
        return a[:, :, None] * b[:, None, :]

    def sym(a, b):
        return outer(a, b) + outer(b, a)

    terms = [outer(u, u), outer(v, v), sym(u, v), sym(u, dr), sym(v, dz), sym(u, dz) + sym(v, dr)]
    for i in range(3):
        shape = np.zeros_like(u)
        shape[:, 1::2] = 1.0 / 6.0
        shape[:, 2 * i + 1] = 2.0 / 3.0
        terms.extend((sym(u, shape), sym(v, shape)))
    S = np.ascontiguousarray(np.stack(terms, axis=1))
    C = np.zeros((len(t), 12, 12))
    D = E / (1.0 - NU**2) * np.array([[1.0, NU, 0.0], [NU, 1.0, 0.0], [0.0, 0.0, (1.0 - NU) / 2.0]])
    area = abs(det) / 2.0
    C[:, :3, :3] = (area * thick)[:, None, None] * D
    C[:, 3:6, 3:6] = (area * thick**3 / 12.0)[:, None, None] * D
    C[:, 6:, 6:] = (area * thick * (5.0 / 6.0) * E / (2.0 * (1.0 + NU)) / 3.0)[:, None, None] * np.eye(6)
    return S, C


@njit(cache=True)
def shell_elements(values, triangles, coeff, material, want_hessian, block_map=None, blocks=0):
    count = len(triangles)
    eng = np.zeros(count)
    grad = np.empty((count, 18))
    strain = np.empty((count, 6))
    if want_hessian and block_map is not None:
        hess = np.zeros((blocks, 6, 6))
    else:
        hess = np.empty((count if want_hessian else 0, 18, 18))
    for ie in range(count):
        j = ie % len(coeff)
        x = values[triangles[ie]].copy().reshape((6, 3))
        origin = x[0].copy()
        for a in (0, 2, 4):
            x[a] -= origin
        B = (coeff[j].reshape((72, 6)) @ x).reshape((12, 18))
        e = 0.5 * (B @ x.ravel())
        e[0] -= 0.5
        e[1] -= 0.5
        stress = material[j] @ e
        eng[ie] = 0.5 * (e @ stress)
        grad[ie] = B.T @ stress
        strain[ie] = e[:6]
        if want_hessian:
            H = B.T @ (material[j] @ B)
            geometric = (stress @ coeff[j].reshape((12, 36))).reshape((6, 6))
            for a in range(6):
                for b in range(6):
                    for k in range(3):
                        H[3 * a + k, 3 * b + k] += geometric[a, b]
            if block_map is None:
                hess[ie] = H
            else:
                for i in range(3):
                    for jnode in range(3):
                        dest = block_map[ie, i, jnode]
                        for a in range(6):
                            for b in range(6):
                                hess[dest, a, b] += H[6 * i + a, 6 * jnode + b]
    return eng, grad, hess, strain


class Mesh:
    def __init__(self, area):
        cad = trimesh.load(baseline.BODY)
        raw, er, ez, normal = baseline.rib_polygon(cad, 22.5)
        profile = set_precision(raw.simplify(0.003, preserve_topology=True), 0.002)
        x, tri = rib_mesh(area, profile)
        tags = master_tags(x)
        fixed_tri = (tags[tri[:, 0]] != "") & np.all(tags[tri] == tags[tri[:, :1]], axis=1)
        tri = tri[~fixed_tri]
        used, index = np.unique(tri, return_inverse=True)
        self.x, self.t = x[used], index.reshape(-1, 3)
        self.tags = tags[used]
        self.centres = self.x[self.t].mean(axis=1)
        self.thick = baseline.thickness(cad, self.centres, er, ez, normal)
        if not np.isfinite(self.thick).all() or self.thick.min() <= 0:
            raise ValueError("Ray-based active rib thickness is incomplete")
        self.coeff, self.material = element_data(self.x, self.t, self.thick)
        self.n = len(self.x)
        self.theta = 22.5 + 45.0 * np.arange(8)
        self.radial = np.c_[np.cos(np.radians(self.theta)), np.sin(np.radians(self.theta)), np.zeros(8)]
        self.normals = np.cross(self.radial, AXES[2])
        xyz = self.radial[:, None, :] * self.x[:, 0, None] + self.x[:, 1, None] * AXES[2]
        self.xyz = xyz.reshape(-1, 3)
        self.directors = np.repeat(self.normals, self.n, axis=0)
        self.tri = (self.t[None, :, :] + np.arange(8)[:, None, None] * self.n).reshape(-1, 3)
        initial = self.xyz[self.tri]
        ref_cross = np.cross(initial[:, 1] - initial[:, 0], initial[:, 2] - initial[:, 0])
        self.reference_area = np.einsum("ij,ij->i", ref_cross, self.directors[self.tri[:, 0]])
        self.edofs = (6 * self.tri[:, :, None] + np.arange(6)).reshape(-1, 18)
        # The 6 x 6 node-pair sparsity pattern is fixed by connectivity. Assemble
        # directly into its blocks to avoid storing and sorting repeated scalar entries.
        pattern = self.t[:, :, None].astype(np.int64) * self.n + self.t[:, None, :]
        unique, inverse = np.unique(pattern, return_inverse=True)
        self.block_map = (
            (inverse.reshape(-1, 3, 3)[None, :, :, :] + len(unique) * np.arange(8)[:, None, None, None])
            .reshape(-1, 3, 3)
            .astype(np.int32)
        )
        self.block_col = (
            ((unique % self.n)[None, :] + self.n * np.arange(8)[:, None]).ravel().astype(np.int32)
        )
        row_counts = np.bincount(unique // self.n, minlength=self.n)
        self.block_ptr = np.r_[0, np.cumsum(np.tile(row_counts, 8))].astype(np.int32)
        # Harmonic weights extend exact rigid-patch rotations to free nodes for the Newton predictor.
        edges = np.unique(np.sort(self.t[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1), axis=0)
        edge_w = 1.0 / np.linalg.norm(self.x[edges[:, 0]] - self.x[edges[:, 1]], axis=1)
        graph = sparse.coo_matrix((edge_w, (edges[:, 0], edges[:, 1])), shape=(self.n, self.n)).tocsr()
        graph = graph + graph.T
        lap = sparse.diags(np.asarray(graph.sum(1)).ravel()) - graph
        fr = np.flatnonzero(self.tags == "")
        cl = np.flatnonzero(self.tags != "")
        self.patch_names = np.unique(self.tags[cl])
        boundary = (self.tags[cl, None] == self.patch_names).astype(float)
        self.weights = splu(lap[fr][:, fr].tocsc()).solve(-lap[fr][:, cl] @ boundary)
        self.land_centres = {}
        for s in STATIONS:
            line = profile.intersection(LineString([(15.0, s), (24.0, s)]))
            self.land_centres[s] = 0.5 * (line.bounds[0] + line.bounds[2])
        self.info = dict(
            max_triangle_area_mm2=area,
            cad_section_area_mm2=raw.area,
            meshed_section_area_mm2=profile.area,
            boundary_simplification_mm=0.003,
            intersection_grid_mm=0.002,
            active_triangles_per_rib=len(self.t),
            active_nodes_per_rib=self.n,
            thickness_range_mm=[float(self.thick.min()), float(self.thick.max())],
        )

    def minimum_orientation(self, x):
        triangles = x[self.tri]
        cross = np.cross(
            triangles[:, 1, :3] - triangles[:, 0, :3], triangles[:, 2, :3] - triangles[:, 0, :3]
        )
        return np.min(np.einsum("ij,ij->i", cross, triangles[:, :, 3:].mean(1)) / self.reference_area)


@dataclass
class Body:
    centre: np.ndarray
    pos: np.ndarray
    rot: np.ndarray


class Model:
    def __init__(self, mesh, variant):
        self.mesh, self.variant = mesh, variant
        self.bodies, self.rib_lands, self.constraints = {}, {}, []
        self.size = 0
        m = mesh

        def body(name, centre, moving_centre=True):
            pos = self.allocate(3) if moving_centre else None
            self.bodies[name] = Body(np.array(centre), pos, self.allocate(3))

        body("D0", [0.0, 0.0, -48.0])
        body("D1", [0.0, 0.0, 48.0])
        for k, (lo, hi) in enumerate(RING_WINDOWS):
            body(f"R{k}", [0.0, 0.0, (lo + hi) / 2.0])
        if variant != "bare":
            for s in STATIONS:
                body(f"G{s:+}", [0.0, 0.0, s])
        self.free_nodes = np.where(np.tile(m.tags == "", 8))[0]
        self.free = self.allocate(5 * len(self.free_nodes)).reshape(-1, 5)
        self.node_rib = self.free_nodes // m.n
        self.free_basis = np.stack(
            [m.radial[self.node_rib], np.broadcast_to(AXES[2], (len(self.free), 3))], 1
        )
        turns = {name: [] for name in self.bodies}
        shift_nodes, shift_dofs = [], []
        for i, theta in enumerate(m.theta):
            for tag in np.unique(m.tags[m.tags != ""]):
                n = np.flatnonzero(m.tags == tag) + i * m.n
                key = tag
                if tag.startswith("G"):
                    s = int(tag[1:])
                    centre = m.radial[i] * m.land_centres[s] + AXES[2] * s
                    mounted = i % 2 == 1 and variant != "bare"
                    self.rib_lands[(i, s)] = (n, centre, mounted)
                    if not mounted or variant == "point":
                        key = f"L{i}_{s}"
                        body(key, centre, not mounted)
                        turns[key] = []
                    if mounted and variant == "point":
                        turns[tag].append(
                            (6 * n, np.broadcast_to(centre - self.bodies[tag].centre, (len(n), 3)))
                        )
                ref = self.bodies[key]
                translator = ref if ref.pos is not None else self.bodies[tag]
                shift_nodes.append(n)
                shift_dofs.append(np.broadcast_to(translator.pos, (len(n), 3)))
                turns[key].extend([(6 * n, m.xyz[n] - ref.centre), (6 * n + 3, m.directors[n])])
        self.turns = {
            name: (np.concatenate([r for r, v in items]), np.vstack([v for r, v in items]))
            for name, items in turns.items()
            if items
        }
        self.shift_nodes = np.concatenate(shift_nodes)
        self.shift_dofs = np.vstack(shift_dofs)
        self.ref = np.c_[m.xyz, m.directors]
        self.zero = np.zeros(self.size)
        self.clamp = np.r_[self.bodies["D0"].pos, self.bodies["D0"].rot]
        self.end = np.r_[self.bodies["D1"].pos, self.bodies["D1"].rot]
        self.blocks = self.mapping_indices()
        self.external = []

    def allocate(self, n):
        start = self.size
        self.size += n
        return np.arange(start, self.size)

    def mapping_indices(self):
        """Store sparse Jacobian coordinates once; only rotations change its entries."""
        rows = [
            (6 * self.free_nodes[:, None] + np.arange(3)).ravel(),
            (6 * self.shift_nodes[:, None] + np.arange(3)).ravel(),
        ]
        cols = [self.free[:, :3].ravel(), self.shift_dofs.ravel()]
        rows.append(
            np.broadcast_to(
                6 * self.free_nodes[:, None, None] + 3 + np.arange(3)[None, :, None],
                (len(self.free), 3, 2),
            ).ravel()
        )
        cols.append(np.broadcast_to(self.free[:, None, 3:], (len(self.free), 3, 2)).ravel())
        for name, (start, v) in self.turns.items():
            rows.append(
                np.broadcast_to(
                    start[:, None, None] + np.arange(3)[None, :, None], (len(v), 3, 3)
                ).ravel()
            )
            cols.append(np.broadcast_to(self.bodies[name].rot, (len(v), 3, 3)).ravel())
        return np.concatenate(rows), np.concatenate(cols)

    def mapping(self, q):
        x = self.ref.copy()
        p = q[self.free[:, 3:]]
        n = self.ref[self.free_nodes, 3:]
        den = 1.0 + np.einsum("ni,ni->n", p, p)
        director = (2.0 * np.einsum("ni,nij->nj", p, self.free_basis) + (2.0 - den)[:, None] * n) / den[
            :, None
        ]
        jac = (2.0 * self.free_basis - 2.0 * p[:, :, None] * (n + director)[:, None, :]) / den[
            :, None, None
        ]
        x[self.free_nodes, :3] += q[self.free[:, :3]]
        x[self.free_nodes, 3:] = director
        x[self.shift_nodes, :3] += q[self.shift_dofs]
        vals = [np.ones(3 * (len(self.free) + len(self.shift_nodes))), jac.transpose(0, 2, 1).ravel()]
        derivatives = {}
        flat = x.reshape(-1, 3)
        for name, (start, vec) in self.turns.items():
            R, dR, ddR = rotation(q[self.bodies[name].rot])
            flat[start // 3] += vec @ (R - AXES).T
            vals.append(np.einsum("kij,nj->nik", dR, vec).ravel())
            derivatives[name] = (R, dR, ddR)
        P = sparse.coo_matrix((np.concatenate(vals), self.blocks), shape=(x.size, self.size)).tocsr()
        return x, P, (p, n, director, jac, den, derivatives)

    def lift(self, q, sign):
        """Add/remove the smooth rigid-frame displacement for path/mesh predictors."""
        out = q.copy()
        oriented = {key: rotation(q[b.rot])[0] - AXES for key, b in self.bodies.items()}
        fr2 = np.flatnonzero(self.mesh.tags == "")
        for i in range(8):
            sl = slice(i * len(fr2), (i + 1) * len(fr2))
            loc = fr2 + i * self.mesh.n
            total = np.zeros((len(loc), 3))
            for j, tag in enumerate(self.mesh.patch_names):
                key = tag
                offset = 0.0
                if tag.startswith("G"):
                    st = int(tag[1:])
                    _, centre, mounted = self.rib_lands[(i, st)]
                    if not mounted or self.variant == "point":
                        key = f"L{i}_{st}"
                    if mounted and self.variant == "point":
                        offset = oriented[tag] @ (centre - self.bodies[tag].centre)
                b = self.bodies[key]
                trans = b.pos if b.pos is not None else self.bodies[tag].pos
                relative = self.mesh.xyz[loc] - b.centre
                total += self.mesh.weights[:, j, None] * (q[trans] + relative @ oriented[key].T + offset)
            out[self.free[sl, :3]] += sign * total
        return out

    def increment(self, q, dq):
        """Transport a Newton prediction with its neighbouring rigid patches.

        The correction is second order in the step. It keeps short boundary
        elements next to a rotating patch from seeing an artificial strain
        proportional to the square of the rotation divided by their length.
        """
        out = q + dq
        nonlinear = {}
        for name, body in self.bodies.items():
            p = q[body.rot]
            dp = dq[body.rot]
            R, dR, _ = rotation(p)
            nonlinear[name] = rotation(p + dp)[0] - R - np.einsum("a,aij->ij", dp, dR)
        free2 = np.flatnonzero(self.mesh.tags == "")
        for i in range(8):
            block = slice(i * len(free2), (i + 1) * len(free2))
            loc = free2 + i * self.mesh.n
            dx = np.zeros((len(loc), 3))
            for j, tag in enumerate(self.mesh.patch_names):
                key = tag
                extra = np.zeros(3)
                if tag.startswith("G"):
                    st = int(tag[1:])
                    _, centre, mounted = self.rib_lands[(i, st)]
                    if not mounted or self.variant == "point":
                        key = f"L{i}_{st}"
                    if mounted and self.variant == "point":
                        extra = nonlinear[tag] @ (centre - self.bodies[tag].centre)
                rel = self.mesh.xyz[loc] - self.bodies[key].centre
                dx += self.mesh.weights[:, j, None] * (rel @ nonlinear[key].T + extra)
            out[self.free[block, :3]] += dx
        return out

    def assemble(self, q, scale=0.0, hessian=True):
        x, P, aux = self.mapping(q)
        m = self.mesh
        energies, local, h, strain = shell_elements(
            x, m.tri, m.coeff, m.material, hessian, m.block_map, len(m.block_col)
        )
        f = np.bincount(m.edofs.ravel(), weights=local.ravel(), minlength=x.size)
        g = P.T @ f
        p, n, d, jac, den, deriv = aux
        K = None
        extra_r, extra_c, extra_v = [], [], []

        def block(ids, values):
            ids = np.atleast_2d(ids)
            extra_r.append(np.broadcast_to(ids[:, :, None], (*ids.shape, ids.shape[1])).ravel())
            extra_c.append(
                np.broadcast_to(ids[:, None, :], (len(ids), ids.shape[1], ids.shape[1])).ravel()
            )
            extra_v.append(values.ravel())

        if hessian:
            full = sparse.bsr_matrix((h, m.block_col, m.block_ptr), shape=(x.size, x.size)).tocsr()
            del h
            K = (P.T @ (full @ P)).tocsc()
            fd = f.reshape(-1, 6)[self.free_nodes, 3:]
            ident = np.eye(2)
            fj = np.einsum("nk,nik->ni", fd, jac)
            fn = np.einsum("nk,nk->n", fd, n + d)
            dd = (
                -2.0
                * (
                    fn[:, None, None] * ident
                    + fj[:, :, None] * p[:, None, :]
                    + p[:, :, None] * fj[:, None, :]
                )
                / den[:, None, None]
            )
            block(self.free[:, 3:], dd)
            for name, (start, vec) in self.turns.items():
                product = f.reshape(-1, 3)[start // 3].T @ vec
                block(self.bodies[name].rot, np.einsum("ij,abij->ab", product, deriv[name][2]))
        energy = energies.sum()
        for name, offsets, forces in self.external:
            body = self.bodies[name]
            R, dR, ddR = deriv[name]
            F = scale * forces
            g[body.pos] -= F.sum(0)
            product = F.T @ offsets
            g[body.rot] -= np.einsum("kij,ij->k", dR, product)
            energy -= np.sum(F * (q[body.pos] + offsets @ (R - AXES).T))
            if hessian:
                block(body.rot, -np.einsum("abij,ij->ab", ddR, product))
        if hessian:
            K += sparse.coo_matrix(
                (np.concatenate(extra_v), (np.concatenate(extra_r), np.concatenate(extra_c))),
                shape=(self.size, self.size),
            ).tocsc()
        return energy, g, K, (x, f.reshape(-1, 6), strain)
