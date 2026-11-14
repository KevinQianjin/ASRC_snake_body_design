"""Separate tendon lanes per anchor set (radial spread) for the spatial rod model.

Lives in simulations/u4m2/lanes_20261113 and imports the unchanged solver from
../backbone_20261108 (path set below).

The pinned spatial kernel (steering_63mm_20261106/spatial_model.py) routes all
anchor sets through the same four holes at 24 mm. Physically, three 2 mm ropes
cannot share one hole (see cad/simulation_reference/u4m2_500g/validation.json).
This module gives every anchor set its own radius: by default set A (anchored at
U4) at 21 mm, B (M5) at 24 mm and C (M6) at 27 mm, all on the same up/right/
down/left rays, i.e. 3 mm between rope centres (1 mm gap for 2 mm ropes).

`kernel_lanes` is the pinned kernel with only the rope loop generalised to
per-set offsets (sets x 4 x 3); with all radii equal to 24 mm it reproduces the
pinned kernel exactly (checked by `validate`). `install(radii)` wraps
backbone.spatial_rod so that every rod it returns uses the lanes; call it
BEFORE importing modules that do `from backbone import spatial_rod` (or
`from length_cycle import spatial_rod`). Pinned files are not modified.
"""
import sys
import types
from pathlib import Path
import numpy as np
from numba import njit

# The solver scripts live, unchanged, in ../backbone_20261108; make them importable from here.
BACKBONE_DIR = Path(__file__).resolve().parent.parent / 'backbone_20261108'
if str(BACKBONE_DIR) not in sys.path:
    sys.path.insert(0, str(BACKBONE_DIR))
import backbone  # noqa: E402
from spatial_model import rotation  # noqa: E402

DEFAULT_RADII_MM = (21., 24., 27.)
_original_spatial_rod = backbone.spatial_rod
RADII_MM = None
GUIDE_SPACING_MM = None


@njit(cache=True)
def kernel_lanes(z, C, scale, K, mass, length, sub, guide_cells, routes, offsets3, gauss_u, gauss_w, gravity, gw, payload):
    """Pinned spatial kernel with per-set lanes and optional M-module guide stations.

    M5/M6 ropes are represented as consecutive straight spans between material-frame
    stations separated by guide_cells. U modules retain one span per module.
    """
    cells = len(mass); ndof = 4 * cells; modules = cells // sub; sets = len(C)
    q = (z / scale).reshape((cells, 4))
    F = np.zeros((cells + 1, 3, 3)); F[0] = np.eye(3)
    p = np.zeros((cells + 1, 3)); R = np.empty((cells, 3, 3)); dR = np.empty((cells, 3, 3, 3))
    v = np.empty((cells, 3)); vc = np.empty((cells, 3)); dv = np.empty((cells, 4, 3)); dc = np.empty((cells, 4, 3))
    mapping = np.array([0, 2, 1]); signs = np.array([1., 1., -1.])
    energy = .5 * np.sum(K * q * q)
    for i in range(cells):
        phi = np.array([q[i, 0], -q[i, 2], q[i, 1]])
        Ri, DR = rotation(phi); R[i] = Ri
        for k in range(3): dR[i, k] = DR[mapping[k]] * signs[k]
        t = np.zeros(3); c = np.zeros(3); jt = np.zeros((3, 3)); jc = np.zeros((3, 3))
        for j in range(len(gauss_u)):
            u = gauss_u[j]; w = gauss_w[j]; Rq, DQ = rotation(phi * u)
            t += w * Rq[:, 0]; c += w * (1 - u) * Rq[:, 0]
            for k in range(3):
                jt[k] += w * u * signs[k] * DQ[mapping[k], :, 0]
                jc[k] += w * (1 - u) * u * signs[k] * DQ[mapping[k], :, 0]
        lam = 1 + q[i, 3]
        v[i] = length * lam * t; vc[i] = length * lam * c
        for k in range(3): dv[i, k] = length * lam * jt[k]; dc[i, k] = length * lam * jc[k]
        dv[i, 3] = length * t; dc[i, 3] = length * c
        p[i + 1] = p[i] + F[i] @ v[i]
        F[i + 1] = F[i] @ Ri
        energy += mass[i] * gravity * np.dot(gw, p[i] + F[i] @ vc[i])
    energy += payload * gravity * np.dot(gw, p[-1])
    ap = np.zeros((cells + 1, 3)); af = np.zeros((cells + 1, 3, 3))
    ap[-1] += payload * gravity * gw
    for i in range(cells):
        force = mass[i] * gravity * gw
        ap[i] += force; af[i] += np.outer(force, vc[i])
    rope_lengths = np.zeros((sets, 4))
    for j in range(modules):
        module_start = j * sub; module_end = (j + 1) * sub
        step = guide_cells if j >= 4 else sub
        for rope in range(4):
            for k in range(sets):
                if routes[k, j] == 0.:
                    continue
                off = offsets3[k, rope]
                tension = routes[k, j] * C[k, rope]
                if j >= 4 and step == 2 and sub >= 8:
                    # Four internal supports at local z=-24,-12,+12,+24 mm
                    # for 8 cells/module, where the M-body CAD scan is clear.
                    # End-to-end rope spans are 2,1,2,1,2 cells (max 24 mm).
                    spans = ((0, 2), (2, 3), (3, 5), (5, 6), (6, sub))
                    for a_cell, b_cell in spans:
                        i0 = module_start + a_cell
                        i1 = module_start + b_cell
                        a = p[i0] + F[i0] @ off; b = p[i1] + F[i1] @ off
                        chord = b - a; ll = np.sqrt(np.dot(chord, chord))
                        if ll < 1e-10: ll = 1e-10
                        rope_lengths[k, rope] += routes[k, j] * ll
                        energy += tension * ll
                        force = tension * chord / ll
                        ap[i0] -= force; ap[i1] += force
                        af[i0] -= np.outer(force, off); af[i1] += np.outer(force, off)
                else:
                    for i0 in range(module_start, module_end, step):
                        i1 = i0 + step
                        a = p[i0] + F[i0] @ off; b = p[i1] + F[i1] @ off
                        chord = b - a; ll = np.sqrt(np.dot(chord, chord))
                        if ll < 1e-10: ll = 1e-10
                        rope_lengths[k, rope] += routes[k, j] * ll
                        energy += tension * ll
                        force = tension * chord / ll
                        ap[i0] -= force; ap[i1] += force
                        af[i0] -= np.outer(force, off); af[i1] += np.outer(force, off)
    grad = K * q
    for i in range(cells - 1, -1, -1):
        pv = F[i].T @ ap[i + 1]; fr = F[i].T @ af[i + 1]
        force_local = F[i].T @ (mass[i] * gravity * gw)
        for k in range(3): grad[i, k] += np.sum(fr * dR[i, k]) + np.dot(pv, dv[i, k]) + np.dot(force_local, dc[i, k])
        grad[i, 3] += np.dot(pv, dv[i, 3]) + np.dot(force_local, dc[i, 3])
        af[i] += af[i + 1] @ R[i].T + np.outer(ap[i + 1], v[i])
        ap[i] += ap[i + 1]
    return energy, grad.ravel() / scale, p, F, q, rope_lengths


def lane_offsets(radii_mm, n_sets):
    dirs = np.array([[0., 1., 0.], [0., 0., 1.], [0., -1., 0.], [0., 0., -1.]])  # up, right, down, left
    radii = np.asarray(radii_mm, float)[-n_sets:] if n_sets < len(radii_mm) else np.asarray(radii_mm, float)
    return np.ascontiguousarray(radii[:, None, None] / 1000. * dirs[None, :, :])


def _evaluate(self, z, T=None, gravity=9.81, detail=False):
    C = np.zeros((self.k, 4)) if T is None else np.asarray(T, dtype=float).reshape(self.k, 4)
    result = kernel_lanes(np.asarray(z), C, self.scale, self.K, self.mass, self.l, self.sub, self.guide_cells, self.routes, self.offsets3,
                          self.planar.u, self.planar.w, gravity, self.gw, self.payload)
    if not detail:
        return result[:2]
    E, g, p, F, q, lengths = result
    return E, g, dict(points=p, frames=F, q=q, rope_lengths=lengths)


def apply_lanes(r, radii_mm=DEFAULT_RADII_MM, guide_spacing_mm=None):
    """Add per-set lanes and optional ideal M5/M6 cable guides to a spatial rod.

    A guide station is placed every ``guide_spacing_mm`` along M5/M6. U modules
    keep their endpoint-only rope spans. The requested spacing must align with
    the rod's cell resolution.
    """
    if r.k != len(radii_mm):
        raise ValueError(f'{r.k} anchor sets but {len(radii_mm)} lane radii')
    r.offsets3 = lane_offsets(radii_mm, r.k)
    if guide_spacing_mm is None:
        r.guide_cells = r.sub
    else:
        cells = int(round((float(guide_spacing_mm) / 1000.) / r.l))
        if cells < 1 or cells > r.sub or r.sub % cells != 0 or abs(cells * r.l - float(guide_spacing_mm) / 1000.) > 1e-8:
            raise ValueError(f'guide spacing {guide_spacing_mm:g} mm is not aligned with {r.sub} cells/module at {r.l * 1000:g} mm/cell')
        r.guide_cells = cells
    r.guide_spacing_mm = guide_spacing_mm
    r.lane_radii_mm = tuple(float(x) for x in radii_mm)
    r.evaluate = types.MethodType(_evaluate, r)
    return r


def install(radii_mm=DEFAULT_RADII_MM, guide_spacing_mm=None):
    """Install lane and optional M-module guide geometry before importing dependents."""
    global RADII_MM, GUIDE_SPACING_MM
    RADII_MM = tuple(radii_mm)
    GUIDE_SPACING_MM = guide_spacing_mm

    def spatial_rod(u, m, anchors, pitch=20, sub=2, variant='niti18_E40'):
        return apply_lanes(_original_spatial_rod(u, m, anchors, pitch, sub, variant), RADII_MM, GUIDE_SPACING_MM)
    backbone.spatial_rod = spatial_rod
    return spatial_rod


def validate():
    rng = np.random.default_rng(3)
    out = {}
    r0 = _original_spatial_rod(4, 2, [4, 5, 6], 20, 4, 'niti18_E40')
    r1 = apply_lanes(_original_spatial_rod(4, 2, [4, 5, 6], 20, 4, 'niti18_E40'), (24., 24., 24.))
    r2 = apply_lanes(_original_spatial_rod(4, 2, [4, 5, 6], 20, 4, 'niti18_E40'), DEFAULT_RADII_MM)
    rg = apply_lanes(_original_spatial_rod(4, 2, [4, 5, 6], 20, 4, 'niti18_E40'), DEFAULT_RADII_MM, 24.)
    worst_e = worst_g = worst_fd = worst_guided_fd = 0.
    for _ in range(5):
        z = rng.normal(size=r0.ndof) * .02; T = rng.uniform(0, 20, size=(3, 4))
        E0, g0, d0 = r0.evaluate(z, T, detail=True); E1, g1, d1 = r1.evaluate(z, T, detail=True)
        worst_e = max(worst_e, abs(E0 - E1)); worst_g = max(worst_g, float(np.abs(g0 - g1).max()))
        assert np.allclose(d0['rope_lengths'], d1['rope_lengths'], atol=1e-13)
        v = rng.normal(size=r2.ndof); v /= np.linalg.norm(v); h = 1e-6
        E2, g2 = r2.evaluate(z, T)
        fd = (r2.evaluate(z + h * v, T)[0] - r2.evaluate(z - h * v, T)[0]) / (2 * h)
        worst_fd = max(worst_fd, abs(fd - g2 @ v))
        Eg, gg = rg.evaluate(z, T)
        fdg = (rg.evaluate(z + h * v, T)[0] - rg.evaluate(z - h * v, T)[0]) / (2 * h)
        worst_guided_fd = max(worst_guided_fd, abs(fdg - gg @ v))
    # Straight rod: routed length of set k equals its anchor length; lanes change length only via bending.
    out = dict(equal_radii_energy_diff=worst_e, equal_radii_gradient_diff=worst_g, lanes_fd_gradient_error=worst_fd,
               guided_24mm_fd_gradient_error=worst_guided_fd, guided_cells_per_module=rg.guide_cells)
    assert worst_e < 1e-10 and worst_g < 1e-8 and worst_fd < 1e-6 and worst_guided_fd < 1e-6, out
    return out


if __name__ == '__main__':
    print(validate())
