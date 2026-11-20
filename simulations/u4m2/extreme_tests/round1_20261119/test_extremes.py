"""Independent closed-form limits for the strip boundary reduction and a rigid CAD-clearance check."""

import unittest

import fcl
import numpy as np
from scipy.spatial.transform import Rotation
import trimesh

from m6_clearance import proximity
from adapter import mesh_model
from u_springs import E_MPA, NU, solve_blade


def straight_strip():
    z = np.linspace(-45.0, 45.0, 46)
    p = np.c_[np.zeros_like(z), np.zeros_like(z), z]
    ds = np.diff(z)
    b = np.full_like(ds, 6)
    h = np.ones_like(ds)
    tangent = np.tile([0.0, 0.0, 1.0], (len(ds), 1))
    basis = np.tile(np.eye(3), (len(ds), 1, 1))
    area = b * h
    stiffness = (
        E_MPA
        * np.c_[
            h * b**3 / 12,
            b * h**3 / 12,
            b * h**3 * (1 / 3 - 0.21 * h / b) / (2 * (1 + NU)),
        ]
    )
    return (
        p,
        ds,
        tangent,
        E_MPA * area,
        basis / stiffness[:, None, :],
        basis,
        stiffness,
        b,
        h,
    )


class StripTests(unittest.TestCase):
    def test_free_and_axially_extended_straight_strip(self):
        p = straight_strip()
        for extension in [0.0, 0.0005]:
            result = solve_blade(p, np.eye(3), np.array([0, 0, 90 * extension]))
            self.assertTrue(result["converged"])
            self.assertAlmostEqual(result["peak_tension_strain"], extension, places=8)
            self.assertAlmostEqual(
                result["peak_compression_strain"], extension, places=8
            )
            self.assertAlmostEqual(
                result["geometric_extension_lower_bound"], extension, places=8
            )
            np.testing.assert_allclose(
                result["force_in_proximal_CAD_N"],
                [0, 0, p[3][0] * extension],
                atol=2e-6,
            )

    def test_pure_constant_curvature_in_both_directions(self):
        p = straight_strip()
        for axis, depth in [(0, 6.0), (1, 1.0)]:
            k, length = 0.0008, 90.0
            vector = np.eye(3)[axis]
            R = Rotation.from_rotvec(vector * k * length).as_matrix()
            tip = np.cross(vector, [0, 0, 1.0]) * (1 - np.cos(k * length)) / k
            tip[2] += np.sin(k * length) / k
            d = tip - (p[0][-1] - p[0][0]) - (R - np.eye(3)) @ (p[0][-1] - [0, 0, 48])
            result = solve_blade(p, R, d)
            self.assertTrue(result["converged"])
            np.testing.assert_allclose(
                result["force_in_proximal_CAD_N"], np.zeros(3), atol=1e-5
            )
            np.testing.assert_allclose(
                result["proximal_internal_moment_Nmm"],
                vector * p[6][0, axis] * k,
                atol=1e-4,
            )
            self.assertAlmostEqual(
                result["peak_tension_strain"], k * depth / 2, places=7
            )
            self.assertAlmostEqual(
                result["peak_compression_strain"], -k * depth / 2, places=7
            )


class RigidClearanceTests(unittest.TestCase):
    def test_nearest_points_and_translation_sign(self):
        mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
        moving = fcl.CollisionObject(mesh_model(mesh.vertices, mesh.faces))
        fixed = fcl.CollisionObject(
            mesh_model(mesh.vertices + [1.02, 0, 0], mesh.faces)
        )
        gap, hit, points = proximity(fixed, moving, np.zeros(3))
        self.assertFalse(hit)
        self.assertAlmostEqual(gap, 0.02, places=8)
        np.testing.assert_allclose((points[0] - points[1]) / gap, [1, 0, 0], atol=1e-8)
        self.assertTrue(proximity(fixed, moving, np.array([0.021, 0, 0]))[1])


if __name__ == "__main__":
    unittest.main()
