"""Frictionless, one-way local 3-D bearing submodel of the retained M5 web (N, mm, MPa)."""

import argparse
from itertools import product
import json
from pathlib import Path
import time

from cvxopt import matrix, solvers, spmatrix
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.spatial.transform import Rotation

from clearance import CASES, HERE, j

E = 1530.0
NU = 0.40
SIGNS = np.array(
    [
        [-1, -1, -1],
        [1, -1, -1],
        [1, 1, -1],
        [-1, 1, -1],
        [-1, -1, 1],
        [1, -1, 1],
        [1, 1, 1],
        [-1, 1, 1],
    ]
)
LEVELS = {"middle": (28, 5, 10), "fine": (44, 7, 16), "finer": (60, 9, 22)}


def make_mesh(level, length, crown=j.CROWN_RADIUS, fit_relief=False):
    count, nr, ny = LEVELS[level]
    corner = np.arctan2(j.WEB_WIDTH / 2, length)
    angles = np.unique(
        np.round(
            np.r_[
                np.arange(count) * 2 * np.pi / count,
                corner,
                np.pi - corner,
                np.pi + corner,
                2 * np.pi - corner,
            ],
            10,
        )
    )
    na = len(angles)
    ca, sa = np.cos(angles), np.sin(angles)
    outer = np.minimum(
        length / np.maximum(abs(ca), 1e-10),
        j.WEB_WIDTH / 2 / np.maximum(abs(sa), 1e-10),
    )[:, None, None]
    f = (np.arange(nr + 1) / nr)[None, :, None] ** 1.30
    h = np.linspace(-1, 1, ny + 1)[None, None, :]
    y = np.broadcast_to(1.5 * h, (na, nr + 1, ny + 1)).copy()
    inner_layers = (nr - 1) // 2
    blend_layers = max(1, nr // 3)
    upper = np.minimum(j.BLEND, outer - 0.035)
    lower = np.minimum(j.PATCH, upper - 0.035)
    for _ in range(35):
        bore_radius = j.hole_radius(y, crown_radius=crown)
        if fit_relief:
            r = np.empty_like(y)
            for lo, hi, r0, r1 in (
                (0, inner_layers, bore_radius, lower),
                (inner_layers, inner_layers + blend_layers, lower, upper),
                (inner_layers + blend_layers, nr, upper, outer),
            ):
                w = np.linspace(0, 1, hi - lo + 1)[None, :, None]
                start = r0[:, lo : hi + 1, :] if r0.shape[1] > 1 else r0
                r[:, lo : hi + 1, :] = (1 - w) * start + w * r1
        else:
            r = (1 - f) * bore_radius + f * outer
        y = h * j.face_height(r)
    x = np.stack((r * ca[:, None, None], r * sa[:, None, None], y), axis=-1).reshape(
        -1, 3
    )
    idx = np.arange(len(x)).reshape(na, nr + 1, ny + 1)
    aa, rr, tt = np.indices((na, nr, ny))
    q = np.stack(
        [
            idx[
                (aa + (i in (2, 3, 6, 7))) % na, rr + (i in (1, 2, 5, 6)), tt + (i >= 4)
            ]
            for i in range(8)
        ],
        axis=-1,
    ).reshape(-1, 8)
    faces = [
        q[rr.ravel() == 0][:, [0, 3, 7, 4]],
        q[tt.ravel() == 0][:, [0, 1, 2, 3]],
        q[tt.ravel() == ny - 1][:, [4, 5, 6, 7]],
        q[rr.ravel() == nr - 1][:, [1, 5, 6, 2]],
    ]
    area = np.zeros((4, len(x)))
    for k, fs in enumerate(faces):
        pp = x[fs]
        ar = (
            np.linalg.norm(np.cross(pp[:, 1] - pp[:, 0], pp[:, 2] - pp[:, 0]), axis=1)
            + np.linalg.norm(np.cross(pp[:, 2] - pp[:, 0], pp[:, 3] - pp[:, 0]), axis=1)
        ) / 2
        for row in fs.T:
            np.add.at(area[k], row, ar / 4)
    doe = np.sqrt((x[:, :2] ** 2).sum(1))
    bore = area[0] > 0
    shoulder = (
        ((area[1] + area[2] + area[3]) > 0) & (doe < 1.28) & (abs(x[:, 2]) > 0.88)
    )
    ids = np.flatnonzero(bore | shoulder)
    return x, q, ids, bore[ids], shoulder[ids], np.sum(area[:, ids], axis=0)


def strain_matrix(xe, loc):
    factors = (1 + SIGNS * loc) / 2
    der = np.column_stack(
        [
            SIGNS[:, k] / 2 * factors[:, (k + 1) % 3] * factors[:, (k + 2) % 3]
            for k in range(3)
        ]
    )
    jac = np.einsum("ia,eib->eab", der, xe)
    det = np.linalg.det(jac)
    if det.min() <= 0:
        raise ValueError("Folded element")
    grad = np.einsum("ia,eba->eib", der, np.linalg.inv(jac))
    B = np.zeros((len(xe), 6, 24))
    for i in range(3):
        B[:, i, i::3] = grad[:, :, i]
    for row, (i, k) in enumerate(((0, 1), (1, 2), (2, 0)), 3):
        B[:, row, i::3] = grad[:, :, k]
        B[:, row, k::3] = grad[:, :, i]
    return B, det


class Patch:
    def __init__(
        self,
        level,
        length,
        crown=j.CROWN_RADIUS,
        fit_relief=False,
        prescribed_ends=False,
    ):
        self.x, self.hex, self.ids, self.bore, self.shoulder, self.area = make_mesh(
            level, length, crown, fit_relief
        )
        fixed = np.isclose(np.abs(self.x[:, 0]), length, atol=1e-8)
        self.free = np.flatnonzero(np.repeat(~fixed, 3))
        self.fixed_nodes = np.flatnonzero(fixed)
        mp = np.full(3 * len(self.x), -1, int)
        mp[self.free] = np.arange(len(self.free))
        self.fdof = mp[3 * self.ids[:, None] + np.arange(3)].ravel()
        self.edof = (3 * self.hex[:, :, None] + np.arange(3)).reshape(-1, 24)
        E0 = E / (1 + NU)
        D = np.zeros((6, 6))
        D[:3, :3] = E0 * NU / (1 - 2 * NU)
        D[:3, :3] += E0 * np.eye(3)
        D[3:, 3:] = E0 / 2 * np.eye(3)
        xe = self.x[self.hex]
        ek = np.zeros((len(xe), 24, 24))
        self.quad = list(product(*[[-1 / np.sqrt(3), 1 / np.sqrt(3)]] * 3))
        for pt in self.quad:
            B, w = strain_matrix(xe, np.asarray(pt))
            ek += np.einsum("eji,ejk,e->eik", B, D @ B, w, optimize=True)
        K = sparse.coo_matrix(
            (
                ek.ravel(),
                (
                    np.broadcast_to(self.edof[:, :, None], ek.shape).ravel(),
                    np.broadcast_to(self.edof[:, None, :], ek.shape).ravel(),
                ),
            ),
            shape=(len(mp), len(mp)),
        ).tocsc()
        self.lu = splu(K[self.free, :][:, self.free].tocsc())
        if prescribed_ends:
            fixed_dofs = (3 * self.fixed_nodes[:, None] + np.arange(3)).ravel()
            self.end_coupling = K[self.free, :][:, fixed_dofs].tocsr()
        self.comp = np.zeros((len(self.fdof), len(self.fdof)))
        self.ready = np.zeros(len(self.ids), bool)
        self.level = level

    def lift_ends(self, displacement):
        """Static elastic extension of two prescribed end-face displacement fields."""
        out = np.zeros_like(self.x)
        out[self.fixed_nodes] = displacement
        out.ravel()[self.free] = self.lu.solve(
            -self.end_coupling @ displacement.ravel()
        )
        return out

    def ensure(self, nodes):
        new = np.unique(nodes[~self.ready[nodes]])
        for batch in np.array_split(new, max(1, (len(new) + 11) // 12)):
            if not len(batch):
                continue
            d = (3 * batch[:, None] + np.arange(3)).ravel()
            rhs = np.zeros((len(self.free), len(d)), order="F")
            rhs[self.fdof[d], np.arange(len(d))] = 1
            self.comp[:, d] = self.lu.solve(rhs)[self.fdof]
            self.ready[batch] = True

    def stress(self, u):
        xe = self.x[self.hex]
        local = u.ravel()[self.edof]
        peak = -np.inf
        worst = 0
        weighted = []
        weights = []
        max_compression = 0.0
        for pt in self.quad:
            B, weight = strain_matrix(xe, np.asarray(pt))
            e = np.einsum("eij,ej->ei", B, local)
            tensor = np.zeros((len(e), 3, 3))
            tensor[:, np.arange(3), np.arange(3)] = e[:, :3]
            for v, (a, b) in enumerate(((0, 1), (1, 2), (2, 0)), 3):
                tensor[:, a, b] = tensor[:, b, a] = 0.5 * e[:, v]
            val = np.linalg.eigvalsh(tensor)
            inside = np.linalg.norm(xe.mean(1)[:, :2], axis=1) < 2
            i = np.where(inside, val[:, -1], -np.inf).argmax()
            if val[i, -1] > peak:
                peak = float(val[i, -1])
                worst = int(i)
            max_compression = min(max_compression, float(val[inside, 0].min()))
            weighted.extend(val[inside, -1])
            weights.extend(weight[inside])
        order = np.argsort(weighted)
        weights = np.array(weights)[order].cumsum()
        q95 = float(
            np.asarray(weighted)[order[np.searchsorted(weights, 0.95 * weights[-1])]]
        )
        return dict(
            peak_tensile_principal_strain=peak,
            p95_volume_tensile_principal_strain=q95,
            most_compressive_principal_strain=max_compression,
            peak_element_centre_spn_mm=xe[worst].mean(0).tolist(),
        )


def shoulder_distance(p, sign):
    """Signed distance to a finite concave spherical thrust pad with a cylindrical rim."""
    r = np.linalg.norm(p[:, :2], axis=1)
    h = sign * p[:, 2]
    R = j.HALF_THICKNESS + j.THRUST_GAP
    lim = j.THRUST_OUTER
    centre, tangent = j.thrust_rim()
    rho = np.clip(R * r / np.hypot(r, h), 0, tangent[0])
    sphere = np.c_[rho, np.sqrt(R * R - rho * rho)]
    rim = np.c_[np.full(len(p), lim), np.maximum(h, centre[1])]
    pt = np.c_[r, h]
    v = pt - centre
    unit = v / np.maximum(np.linalg.norm(v, axis=1)[:, None], 1e-15)
    arc = centre + j.THRUST_FILLET * unit
    theta = np.arctan2(v[:, 1], v[:, 0])
    theta0 = np.arctan2(*(tangent - centre)[::-1])
    dist = np.stack(
        (
            np.linalg.norm(pt - sphere, axis=1),
            np.linalg.norm(pt - rim, axis=1),
            np.where(
                (theta >= theta0) & (theta <= 0),
                np.linalg.norm(pt - arc, axis=1),
                np.inf,
            ),
        ),
        axis=1,
    )
    which = dist.argmin(1)
    ix = np.arange(len(pt))
    near = np.stack((sphere, rim, arc), 1)[ix, which]
    distance = dist[ix, which]
    inside = (r < lim) & (h >= j.thrust_height(np.minimum(r, lim)))
    sg = np.where(inside, -1.0, 1.0)
    v = (pt - near) * sg[:, None] / np.maximum(distance[:, None], 1e-15)
    # On contact use the unique analytic normal, shared at the two blend tangencies.
    tiny = distance < 3e-5
    normals = np.stack((-sphere / R, np.tile([1.0, 0.0], (len(pt), 1)), unit), axis=1)
    v[tiny] = normals[ix, which][tiny]
    normal = np.c_[v[:, 0, None] * p[:, :2] / r[:, None], v[:, 1] * sign]
    return distance * sg, normal


def constraints(patch, R, u, t):
    nodes = patch.x[patch.ids]
    p = (nodes + u) @ R.T + t
    bid = np.flatnonzero(patch.bore)
    rad = np.linalg.norm(p[bid, :2], axis=1)
    parts = [
        (
            bid,
            rad - j.PIN,
            np.c_[p[bid, :2] / rad[:, None], np.zeros(len(rad))],
            np.zeros(len(bid), int),
        )
    ]
    for code, sign in enumerate((-1, 1), 1):
        ids = np.flatnonzero(patch.shoulder & (sign * nodes[:, 2] > 0))
        gap, normal = shoulder_distance(p[ids], sign)
        parts.append((ids, gap, normal, np.full(len(ids), code)))
    inds, g, ng, code = (np.concatenate(x) for x in zip(*parts))
    return inds, g, ng, ng @ R, code


def linear_contact(patch, idx, g0, n, local, force, seed, normal_translation=None):
    # Dual bound-constrained elastic energy. Introduce omitted inequalities whenever they penetrate.
    cos = np.arctan2(n[:, 1], n[:, 0])
    bins = (
        np.round(cos * 4 / np.pi).astype(int)
        + 5
        + 11 * np.where(n[:, 2] > 0.45, 1, np.where(n[:, 2] < -0.45, 2, 0))
    )
    selected = set(seed)
    for k in np.unique(bins):
        pick = np.flatnonzero(bins == k)
        selected.update(pick[np.argsort(g0[pick])[:3]].tolist())
    for sweep in range(35):
        s = np.array(sorted(selected))
        node = idx[s]
        patch.ensure(node)
        d = 3 * node[:, None] + np.arange(3)
        dense = patch.comp[d[:, None, :, None], d[None, :, None, :]]
        C = np.einsum("ia,ijab,jb->ij", local[s], dense, local[s], optimize=True)
        # A tiny compliance only regularises duplicated normals; its resulting permitted gap is reported below.
        C = (C + C.T) / 2 + 1e-9 * np.eye(len(s))
        G = spmatrix(-1.0, list(range(len(s))), list(range(len(s))))
        controlled = slice(None) if normal_translation is None else slice(0, 2)
        linear = (
            g0[s]
            if normal_translation is None
            else g0[s] + n[s, 2] * normal_translation
        )
        result = solvers.qp(
            matrix(C),
            matrix(linear),
            G,
            matrix(0.0, (len(s), 1)),
            matrix(n[s, controlled].T),
            matrix(force[controlled]),
        )
        if result["status"] != "optimal":
            raise ValueError("Local contact QP " + result["status"])
        lam = np.maximum(0, np.asarray(result["x"]).ravel())
        t = np.asarray(result["y"]).ravel()
        if normal_translation is not None:
            t = np.r_[t, normal_translation]
        loads = np.zeros(len(patch.fdof))
        np.add.at(loads, d, local[s] * lam[:, None])
        ub = (patch.comp[:, d.ravel()] @ (local[s] * lam[:, None]).ravel()).reshape(
            -1, 3
        )
        gaps = g0 + np.einsum("ij,ij->i", local, ub[idx]) + n @ t
        violated = np.flatnonzero(gaps < -2e-6)
        new = set(violated[np.argsort(gaps[violated])[:30]].tolist()) - selected
        if not new:
            return ub, t, s, lam, loads
        selected.update(new)
    raise ValueError("Contact inequality generation did not settle")


def relative_rotation(row):
    rot = np.radians(row["rotation_components_deg_radial_axial_normal"])
    axes = j.web_axes(row["station_mm"])
    rv = axes.T @ np.array([rot[0], -rot[2], rot[1]])
    return Rotation.from_rotvec(rv).as_matrix()


def evaluate(
    patch,
    row,
    field_out=None,
    *,
    relative_matrix=None,
    background=None,
    recover_strain=True,
    normal_translation=None,
):
    R = relative_rotation(row) if relative_matrix is None else relative_matrix
    F = np.array(
        [
            row[k]
            for k in (
                "force_along_web_N",
                "force_perpendicular_inplane_N",
                "force_tangential_N",
            )
        ]
    )
    ub = np.zeros((len(patch.ids), 3))
    base = 0.0 if background is None else background[patch.ids]
    t = np.zeros(3)
    seed = []
    converged = False
    for it in range(34):
        idx, g, n, loc, code = constraints(patch, R, ub + base, t)
        g0 = g - np.einsum("ij,ij->i", loc, ub[idx]) - n @ t
        cand, tn, s, lam, ld = linear_contact(
            patch, idx, g0, n, loc, F, seed, normal_translation
        )
        seed = s[lam > 2e-4].tolist()
        step = max(np.linalg.norm(cand - ub, axis=1).max(), np.linalg.norm(tn - t))
        if step < 3e-6:
            ub, t = cand, tn
            converged = True
            break
        weight = 0.65 if it >= 1 else 1.0
        ub += (cand - ub) * weight
        t += (tn - t) * weight
    # Reconstruct the complete elastic solution associated with the last balanced reactions.
    rhs = np.zeros(len(patch.free))
    np.add.at(rhs, patch.fdof, ld)
    full = np.zeros(patch.x.size)
    full[patch.free] = patch.lu.solve(rhs)
    u = full.reshape(-1, 3)
    if background is not None:
        u += background
    t = tn
    if field_out is not None:
        np.savez_compressed(field_out, u=u, translation=t, R=R)
    _, gap, final_norm, _, _ = constraints(patch, R, u[patch.ids], t)
    reacted = final_norm[s] * lam[:, None]
    p = (patch.x[patch.ids[idx[s]]] + u[patch.ids[idx[s]]]) @ R.T + t
    active = lam > 1e-4
    press = lam / patch.area[idx[s]]
    shaft = code[s] == 0
    span = 3.0
    w = (p[shaft, 2] + span / 2) / span
    point = reacted[shaft, :2]
    support = (point * (1 - w[:, None])).sum(0)
    stations = np.linspace(-span / 2, span / 2, 241)
    leverage = np.maximum(0, stations[:, None] - p[shaft, 2])
    moment = (stations + span / 2)[:, None] * support - leverage @ point
    mm = float(np.linalg.norm(moment, axis=1).max())
    return dict(
        pin_simple_support_span_mm=span,
        pin_max_bending_moment_Nmm=mm,
        pin_nominal_bending_stress_MPa=32 * mm / (np.pi * (2 * j.PIN) ** 3),
        converged=converged,
        normal_iterations=it + 1,
        station_mm=row["station_mm"],
        rib_deg=row["rib_deg"],
        applied_force_spn_N=F.tolist(),
        tilt_deg=float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1)))),
        relative_translation_spn_mm=t.tolist(),
        translation_mm=float(np.linalg.norm(t)),
        max_elastic_deflection_mm=float(np.linalg.norm(u, axis=1).max()),
        minimum_gap_mm=float(gap.min()),
        force_residual_N=float(np.linalg.norm(reacted.sum(0) - F)),
        contact_moment_about_pivot_spn_Nmm=np.cross(p, reacted).sum(0).tolist(),
        peak_nodal_pressure_MPa=float(press.max()),
        active_nodes=int(active.sum()),
        contact_components={
            name: dict(
                normal_force_sum_N=float(lam[code[s] == k].sum()),
                resultant_spn_N=reacted[code[s] == k].sum(0).tolist(),
            )
            for k, name in enumerate(("shaft", "negative_thrust", "positive_thrust"))
        },
        **(patch.stress(u) if recover_strain else {}),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", choices=LEVELS, required=True)
    ap.add_argument("--shell", choices=("0p055", "0p025"), default="0p025")
    ap.add_argument("--length", type=float, default=2.7)
    ap.add_argument("--cases", nargs="+", default=CASES, choices=CASES)
    ap.add_argument("--limit-sites", type=int, default=8)
    ap.add_argument(
        "--fields",
        type=Path,
        help="Optional scratch output of solved nodal displacements for CAD transfer",
    )
    ap.add_argument("--ribs", nargs="*", type=float)
    ap.add_argument("--station", type=int, choices=(-12, 12))
    ap.add_argument(
        "--fit-relief",
        action="store_true",
        help="Place radial layers at the recess and outside blend radii",
    )
    ap.add_argument("--crown", type=float, default=j.CROWN_RADIUS)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(exist_ok=True, parents=True)
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    patch = Patch(a.level, a.length, a.crown, a.fit_relief)
    if a.fields:
        a.fields.mkdir(exist_ok=True, parents=True)
        np.savez_compressed(
            a.fields / "patch_mesh.npz",
            x=patch.x,
            q=patch.hex,
            level=a.level,
            length=a.length,
            crown=a.crown,
            fit_relief=a.fit_relief,
        )
    src = (
        HERE.parent / "evening_20261118/envelope" / f"envelope_pin_r0p30_{a.shell}.json"
    )
    ref = json.loads(src.read_text())
    for case in a.cases:
        dest = a.out / f"{case}.json"
        sc = dict(
            case=case,
            level=a.level,
            length_half_mm=a.length,
            source_shell_area=a.shell,
            hexes=len(patch.hex),
            nodes=len(patch.x),
            youngs_modulus_MPa=E,
            poisson_ratio=NU,
            crown_radius_mm=a.crown,
            feature_fitted_relief=a.fit_relief,
            thrust_rim_fillet_mm=j.THRUST_FILLET,
            sites=[],
        )
        for row in ref["cases"][case][-1]["lands"][: a.limit_sites]:
            if a.ribs and row["rib_deg"] not in a.ribs:
                continue
            if a.station and row["station_mm"] != a.station:
                continue
            start = time.monotonic()
            case_field = (
                a.fields / f"{case}_{row['station_mm']}_{row['rib_deg']:g}.npz"
                if a.fields
                else None
            )
            try:
                result = evaluate(patch, row, case_field)
            except (ValueError, ArithmeticError) as err:
                result = dict(
                    station_mm=row["station_mm"],
                    rib_deg=row["rib_deg"],
                    converged=False,
                    error=str(err),
                )
            sc["sites"].append(result)
            print(
                a.level,
                case,
                row["station_mm"],
                row["rib_deg"],
                result.get("converged"),
                result.get("peak_tensile_principal_strain"),
                result.get("force_residual_N"),
                result.get("error"),
                round(time.monotonic() - start, 1),
                flush=True,
            )
            tmp = dest.with_suffix(".part")
            tmp.write_text(json.dumps(sc, indent=2) + "\n")
            tmp.replace(dest)


if __name__ == "__main__":
    main()
