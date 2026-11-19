"""Two shear-flexible beams for the shoulder pin and threaded cap. Units are mm, N and MPa."""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import cho_factor, cho_solve

from inputs import joint

E_NOMINAL = 200000.0
POISSON = 0.30
SHAFT = joint.PIN
PILOT = joint.THRUST_OUTER
CAP_BORE = 0.316
SHAFT_JOIN = float(joint.thrust_height(SHAFT))
CAP_CYL_END = -float(joint.thrust_height(CAP_BORE))
RIM, TANGENT = joint.thrust_rim()
CAP_TIP = -float(RIM[1] - joint.THRUST_FILLET)
KNOTS = [
    -4.13,
    -3.77,
    -3.68,
    -3.60,
    -3.125,
    -2.57,
    -2.46,
    -2.12,
    -1.52,
    CAP_CYL_END,
    0.0,
    SHAFT_JOIN,
    1.52,
    2.12,
    2.935,
    3.75,
]


def cap_aperture(z):
    """Inner radius of the counterbore and the spherical/filleted entrance from the production CAD."""
    h = np.abs(z)
    radius = joint.HALF_THICKNESS + joint.THRUST_GAP
    sphere = np.sqrt(np.maximum(0.0, radius**2 - h**2))
    fillet = RIM[0] - np.sqrt(
        np.maximum(0.0, joint.THRUST_FILLET**2 - (h - RIM[1]) ** 2)
    )
    return np.maximum(CAP_BORE, np.where(h >= TANGENT[1], sphere, fillet))


def beam_element(length, ro, ri, young, nu):
    area = np.pi * (ro**2 - ri**2)
    inertia = np.pi / 4 * (ro**4 - ri**4)
    m2 = (ri / ro) ** 2
    shear_factor = (
        6
        * (1 + nu)
        * (1 + m2) ** 2
        / ((7 + 6 * nu) * (1 + m2) ** 2 + (20 + 12 * nu) * m2)
    )
    shear = young / (2 * (1 + nu)) * shear_factor * area
    phi = 12 * young * inertia / (shear * length**2)
    L = length
    bend = (
        young
        * inertia
        / (L**3 * (1 + phi))
        * np.array(
            [
                [12, 6 * L, -12, 6 * L],
                [6 * L, (4 + phi) * L * L, -6 * L, (2 - phi) * L * L],
                [-12, -6 * L, 12, -6 * L],
                [6 * L, (2 - phi) * L * L, -6 * L, (4 + phi) * L * L],
            ]
        )
    )
    axial = young * area / L * np.array([[1.0, -1.0], [-1.0, 1.0]])
    return bend, axial, phi, inertia


def shapes(x, L, phi):
    """Exact homogeneous Timoshenko fields at the local coordinate x in each element."""
    k = x / L
    a = (
        np.column_stack((np.ones_like(L), L / 2, -np.ones_like(L), L / 2))
        * (6 / (L**3 * (1 + phi)))[:, None]
    )
    v = np.column_stack(
        (np.ones_like(k), x - x * x / (2 * L), np.zeros_like(k), x * x / (2 * L))
    )
    v += a * (x**3 / 3 - L * x * x / 2 - phi * L * L * x / 6)[:, None]
    theta = (
        np.column_stack((np.zeros_like(k), 1 - k, np.zeros_like(k), k))
        + a * (x * x - L * x)[:, None]
    )
    dv = theta - a * (phi * L * L / 6)[:, None]
    curvature = (
        np.column_stack((np.zeros_like(k), -1 / L, np.zeros_like(k), 1 / L))
        + a * (2 * x - L)[:, None]
    )
    return v, theta, dv, curvature


@dataclass
class Line:
    z: np.ndarray
    dofs: np.ndarray
    phi: np.ndarray
    radius: np.ndarray


class Steel:
    def __init__(
        self, spacing=0.15, support="clamped", young=E_NOMINAL, thread_limit=-2.57
    ):
        if support not in ("clamped", "hinged") or spacing <= 0 or young <= 0:
            raise ValueError("Invalid steel mesh or pilot restraint")
        if thread_limit not in (-2.57, -3.125):
            raise ValueError("Choose a published tied-thread sensitivity")
        self.support = support
        self.spacing = spacing
        self.young = young
        grid = np.r_[
            *[
                np.linspace(a, b, int(np.ceil((b - a) / spacing)) + 1)[:-1]
                for a, b in zip(KNOTS, KNOTS[1:])
            ],
            KNOTS[-1],
        ]
        # A pin and a hollow cap can bend separately. Ideal engaged thread rings share all five DOFs.
        ids = {}
        lines = {}
        for name, lo, hi in (("pin", -3.68, 3.75), ("cap", -4.13, CAP_CYL_END)):
            z = grid[(grid >= lo) & (grid <= hi)]
            groups = []
            for x in z:
                key = ("tie" if -3.60 <= x <= thread_limit else name, float(x))
                if key not in ids:
                    ids[key] = np.arange(5 * len(ids), 5 * len(ids) + 5)
                groups.append(ids[key])
            lines[name] = Line(
                z, np.stack(groups), np.zeros(len(z) - 1), np.zeros(len(z) - 1)
            )
        self.lines = lines
        self.size = 5 * len(ids)
        K = np.zeros((self.size, self.size))
        fixed = set()
        for name, line in lines.items():
            for z, dd in zip(line.z, line.dofs):
                on_pilot = (name == "cap" and z <= -2.12) or (
                    name == "pin" and z >= 2.12
                )
                at_mid = (name == "cap" and z == -3.125) or (
                    name == "pin" and z == 2.935
                )
                if support == "clamped" and on_pilot:
                    fixed.update(dd[:4])
                if support == "hinged" and at_mid:
                    fixed.update(dd[[0, 2]])
                if at_mid:
                    fixed.add(
                        dd[4]
                    )  # the assembled axial datum, with zero initial preload
            for i, L in enumerate(np.diff(line.z)):
                mid = (line.z[i + 1] + line.z[i]) / 2
                if name == "pin":
                    ro = 0.206 if mid < -2.46 else SHAFT if mid < SHAFT_JOIN else PILOT
                    ri = 0.0
                else:
                    ro = PILOT
                    ri = 0.0 if mid < -3.77 else 0.307 if mid < -2.46 else CAP_BORE
                bend, axial, line.phi[i], _ = beam_element(L, ro, ri, young, POISSON)
                line.radius[i] = ro
                left, right = line.dofs[i : i + 2]
                for j in (0, 2):
                    dof = np.r_[left[j : j + 2], right[j : j + 2]]
                    K[np.ix_(dof, dof)] += bend
                dof = [left[4], right[4]]
                K[np.ix_(dof, dof)] += axial
        self.fixed = np.array(sorted(fixed))
        self.free = np.setdiff1d(np.arange(self.size), self.fixed)
        self.K = K
        self.factor = cho_factor(K[np.ix_(self.free, self.free)])
        self.local_index = np.full(self.size, -1, int)
        self.local_index[self.free] = np.arange(len(self.free))

    def solve(self, rhs):
        return cho_solve(self.factor, rhs, check_finite=False)

    def basis(self, name, z):
        line = self.lines[name]
        z = np.asarray(z).ravel()
        if np.any(z < line.z[0] - 1e-8) or np.any(z > line.z[-1] + 1e-8):
            raise ValueError(f"Point outside {name} section")
        i = np.clip(np.searchsorted(line.z, z, side="right") - 1, 0, len(line.z) - 2)
        x = z - line.z[i]
        L = line.z[i + 1] - line.z[i]
        v, theta, dv, curv = shapes(x, L, line.phi[i])
        dof = np.stack((line.dofs[i], line.dofs[i + 1]), axis=1)
        return dof, v, theta, dv, curv, np.column_stack((1 - x / L, x / L))

    def components(self, q, name, z):
        dof, v, theta, dv, curvature, w = self.basis(name, z)
        full = np.zeros(self.size)
        full[self.free] = q
        bend = np.stack(
            [full[dof[:, :, j : j + 2]].reshape(-1, 4) for j in (0, 2)], axis=-1
        )
        dot = lambda weights: np.einsum("ni,nik->nk", weights, bend)
        return (
            dot(v),
            dot(theta),
            dot(dv),
            dot(curvature),
            np.sum(w * full[dof[:, :, 4]], axis=1),
        )

    def normal_rows(self, p, name, z, normals):
        """H projected onto the undeformed surface normal. The lever is relative to the selected section."""
        dof, v, theta, _, _, w = self.basis(name, z)
        n = len(p)
        row = np.arange(n)
        A = np.zeros((n, self.size))
        for k, j in enumerate((0, 2)):
            rot_weight = normals[:, k] * (p[:, 2] - z) - normals[:, 2] * p[:, k]
            values = normals[:, k, None] * v + rot_weight[:, None] * theta
            ids = dof[:, :, j : j + 2].reshape(n, 4)
            A[row[:, None], ids] = values
        A[row[:, None], dof[:, :, 4]] = normals[:, 2, None] * w
        return A

    def counterbore(self, facets):
        if facets < 8:
            raise ValueError("Use at least eight inner contact directions")
        z = np.unique(
            np.r_[
                np.linspace(
                    -2.46,
                    CAP_CYL_END,
                    int(np.ceil((CAP_CYL_END + 2.46) / (self.spacing / 2))) + 1,
                ),
                -2.12,
                np.linspace(CAP_CYL_END, CAP_TIP, 21),
                -TANGENT[1],
            ]
        )
        a = np.arange(facets) * 2 * np.pi / facets
        zz = np.repeat(z, len(a))
        p = np.column_stack((np.zeros_like(zz), np.zeros_like(zz), zz))
        normals = np.tile(
            np.column_stack((np.cos(a), np.sin(a), np.zeros_like(a))), (len(z), 1)
        )
        # Carry the short lip beyond the last full annular section as a rigid overhang.
        A = self.normal_rows(p, "pin", zz, normals) - self.normal_rows(
            p, "cap", np.minimum(zz, CAP_CYL_END), normals
        )
        return (
            (cap_aperture(zz) - SHAFT) * np.cos(np.pi / facets),
            A[:, self.free],
            zz,
            normals,
        )

    def recover(self, q):
        z = np.linspace(-2.46 + 1e-8, SHAFT_JOIN - 1e-8, 641)
        v, rot, _, k, _ = self.components(q, "pin", z)
        stress = self.young * SHAFT * np.linalg.norm(k, axis=1)
        i = int(stress.argmax())
        zc = np.unique(
            np.r_[np.linspace(-2.46, CAP_TIP, 401), CAP_CYL_END, -TANGENT[1]]
        )
        ref = np.minimum(zc, CAP_CYL_END)
        cap, tilt, *_ = self.components(q, "cap", ref)
        metal_offset = (
            self.components(q, "pin", zc)[0] - cap - (zc - ref)[:, None] * tilt
        )
        radial_gap = cap_aperture(zc) - SHAFT - np.linalg.norm(metal_offset, axis=1)
        centre = self.components(q, "pin", [0.0])[0][0]
        witness = {}
        if self.support == "hinged":
            # Project the unslotted flange rim centre to its outer witness plane.
            # The overhang is rigid relative to its adjacent pilot end section.
            for label, member, pilot_end, flange_face in (
                ("head", "pin", 3.75, 4.17),
                ("cap", "cap", -4.13, -4.59),
            ):
                offset, angle, _, _, _ = self.components(q, member, [pilot_end])
                witness[label + "_outer_face_sp_mm"] = (
                    offset[0] + (flange_face - pilot_end) * angle[0]
                ).tolist()
        # With clamped pilot lands both transverse face motions are exactly zero.
        return dict(
            **witness,
            shaft_centre_sp_mm=centre.tolist(),
            maximum_clear_shaft_bending_MPa=float(stress[i]),
            peak_shaft_bending_z_mm=float(z[i]),
            maximum_clear_shaft_deflection_mm=float(np.linalg.norm(v, axis=1).max()),
            maximum_clear_shaft_rotation_deg=float(
                np.degrees(np.linalg.norm(rot, axis=1).max())
            ),
            minimum_dense_cap_counterbore_gap_mm=float(radial_gap.min()),
        )
