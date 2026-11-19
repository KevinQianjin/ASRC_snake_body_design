"""Predictors and optional scratch checkpoints. Every prediction is re-equilibrated."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from matplotlib.tri import Triangulation
from shapely import STRtree, points, polygons


def interpolate(history, fraction):
    # Prefer a nearby quadratic stencil and fall back to a secant across a short last step.
    nearby = sorted(sorted(history, key=lambda a: abs(a[0] - fraction))[:3], key=lambda a: a[0])
    if len(nearby) == 3:
        x = np.array([a[0] for a in nearby])
        if np.min(np.diff(x)) < 0.12 * max(np.ptp(x), abs(fraction - x[-1])):
            nearby = sorted(nearby, key=lambda a: abs(a[0] - fraction))[:2]
    weights = []
    for i, (x, _) in enumerate(nearby):
        w = 1.0
        for j, (xx, _) in enumerate(nearby):
            if i != j:
                w *= (fraction - xx) / (x - xx)
        weights.append(w)
    return sum(w * val for w, (_, val) in zip(weights, nearby))


def transfer_weights(vertices, t, targets):
    """Barycentric transfer including points on, or just outside, cut boundaries."""
    finder = Triangulation(*vertices.T, t).get_trifinder()
    which = finder(*targets.T)
    missing = which < 0
    if np.any(missing):
        # A point on a cut or free outer edge can fall just outside the source
        # triangulation. Evaluate the closest triangle's affine field at the
        # actual target position. Copying a nearest vertex breaks rigid motion.
        tree = STRtree(polygons(vertices[t]))
        nearest = tree.nearest(points(targets[missing]))
        which[missing] = nearest
    corners = t[which]
    coords = vertices[corners]
    bary = np.linalg.solve(
        (coords[:, 1:] - coords[:, :1]).transpose(0, 2, 1), (targets - coords[:, 0])[:, :, None]
    )[:, :, 0]
    weights = np.c_[1.0 - bary.sum(1), bary]
    if not np.allclose(np.einsum("ij,ijk->ik", weights, coords), targets, atol=1.0e-11, rtol=0.0):
        raise ValueError("Source triangle extrapolation violates affine reproduction")
    return corners, weights, int(missing.sum())


class Checkpoints:
    def __init__(self, model, case, cache, seed):
        self.m = model
        self.name = f"{model.variant}_{case}"
        self.cache = None if cache is None else Path(cache) / self.name
        self.seeds = {}
        self.nodes = len(model.free) // 8
        if self.cache is not None:
            self.cache.mkdir(parents=True, exist_ok=True)
            ref = Path(cache) / "mesh.npz"
            if ref.exists():
                with np.load(ref) as previous:
                    if not np.array_equal(previous["x"], model.mesh.x) or not np.array_equal(
                        previous["t"], model.mesh.t
                    ):
                        raise ValueError("The checkpoint directory belongs to a different mesh")
            else:
                with NamedTemporaryFile(dir=self.cache.parent, suffix=".npz", delete=False) as tmp:
                    path = Path(tmp.name)
                    np.savez_compressed(
                        tmp, x=model.mesh.x, t=model.mesh.t, free=np.flatnonzero(model.mesh.tags == "")
                    )
                path.replace(ref)
        if seed is not None:
            directory = Path(seed) / self.name
            self.seeds = {float(p.stem): p for p in directory.glob("*.npz")}
            if not self.seeds:
                raise FileNotFoundError(f"Missing seed trajectory {directory}")
            with np.load(Path(seed) / "mesh.npz") as src:
                self.src_free = src["free"]
                self.src_x = src["x"]
                t = src["t"]
            self.same_mesh = np.array_equal(self.src_x, model.mesh.x) and np.array_equal(t, model.mesh.t)
            targets = model.mesh.x[model.mesh.tags == ""]
            if self.same_mesh:
                self.tris = np.tile(self.src_free[:, None], (1, 3))
                self.weights = np.zeros(self.tris.shape)
                self.weights[:, 0] = 1.0
                self.fallback_nodes = 0
                return
            self.tris, self.weights, self.fallback_nodes = transfer_weights(self.src_x, t, targets)

    def save(self, frac, q, M):
        if self.cache is None:
            return
        m = self.m
        # Coordinates relative to the harmonic rigid-frame extension vanish on all masters.
        z = m.lift(q, -1.0)
        transforms = {
            f"body_{key}": np.r_[q[b.pos] if b.pos is not None else [], q[b.rot]]
            for key, b in m.bodies.items()
        }
        # Free director parameters use the reference radial/axial axes for this rib.
        # Boundary values are needed when interpolating element fields next to a tied patch.
        x, _, _ = m.mapping(q)
        d = x[:, 3:]
        n = m.mesh.directors
        er = np.repeat(m.mesh.radial, m.mesh.n, axis=0)
        denom = 1.0 + np.einsum("ni,ni->n", d, n)
        orient = np.c_[np.einsum("ni,ni->n", d, er), d[:, 2]] / denom[:, None]
        field = np.zeros((8, m.mesh.n, 5))
        field[:, :, 3:] = orient.reshape(8, m.mesh.n, 2)
        field[:, m.mesh.tags == "", :3] = z[m.free[:, :3]].reshape(8, self.nodes, 3)
        np.savez_compressed(
            self.cache / f"{frac:.9f}.npz",
            field=field,
            moment=M,
            displacement=(x[:, :3] - m.mesh.xyz).reshape(8, m.mesh.n, 3),
            **transforms,
        )

    def load(self, frac):
        if not self.seeds:
            return None
        nearby = [frac] if frac in self.seeds else sorted(self.seeds, key=lambda x: abs(x - frac))[:3]
        hist = []
        for f in nearby:
            with np.load(self.seeds[f]) as st:
                q = self.m.zero.copy()
                for key, b in self.m.bodies.items():
                    v = st[f"body_{key}"]
                    if b.pos is not None:
                        q[b.pos] = v[:3]
                    q[b.rot] = v[-3:]
                values = np.einsum("ijkd,jk->ijd", st["field"][:, self.tris, :], self.weights)
                q[self.m.free] = values.reshape(-1, 5)
                if not self.same_mesh:
                    # Physical displacement is affine on a source triangle under rigid motion.
                    # Remove the target mesh's harmonic field only after spatial interpolation.
                    u = np.einsum("ijkd,jk->ijd", st["displacement"][:, self.tris, :], self.weights)
                    q[self.m.free[:, :3]] = u.reshape(-1, 3)
                    q = self.m.lift(q, -1.0)
                hist.append((f, np.r_[q, st["moment"]]))
        val = interpolate(hist, frac)
        return self.m.lift(val[:-1], 1.0), val[-1]
