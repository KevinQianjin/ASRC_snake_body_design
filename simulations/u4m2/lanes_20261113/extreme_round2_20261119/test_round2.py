"""Independent unit checks for contact history, swept surfaces, load signs and open-mission cycle counting."""

import unittest
import numpy as np
from common import load_motion
from m6_full import coefficients, to_station
from m6_support import arm, material_points
from rope_history import contact, play
from m6_bores import bore_gap, radial_extent
from duty import rainflow
from disturbed_holds import displaced_paths
from replay import plant
from pose_map import equilibrate
from sliding import material_gradient


class RoundTwo(unittest.TestCase):
    def test_open_rainflow_and_offset(self):
        a = rainflow([0, 3, 1, 2, 0])
        np.testing.assert_allclose(a, [[1, 1.5, 1], [3, 1.5, 0.5], [3, 1.5, 0.5]])
        b = rainflow([10, 10, 13, 11, 12, 10, 10])
        np.testing.assert_allclose(a[:, [0, 2]], b[:, [0, 2]])
        np.testing.assert_allclose(a[:, 1] + 10, b[:, 1])
        self.assertEqual(len(rainflow([2, 2, 2])), 0)

    def test_cable_rest_and_history(self):
        L = np.array([0.51])
        ea = 10000.0
        rest = np.array([1.50])
        h = L / (1 + ((1 + L) / rest - 1))
        for d in (-0.0001, 0.0001):
            p, t, new, mode, _ = contact(
                L, rest + d, h, np.array([np.pi]), ea, 0.2, 0.15
            )
            self.assertEqual(mode[0], 0)
            np.testing.assert_array_equal(new, h)
        for d in (-0.004, 0.005):
            p, t, new, mode, _ = contact(
                L, rest + d, h, np.array([1.0]), ea, 0.15, 0.15
            )
            self.assertNotEqual(mode[0], 0)
            np.testing.assert_allclose(
                1 / (1 + p / ea) + L / (1 + t / ea), rest + d, rtol=1e-12
            )
            np.testing.assert_allclose(np.abs(np.log(p / t)), 0.15)
            np.testing.assert_allclose(new, L / (1 + t / ea))
        p, t, _, _, _ = contact(L, rest, h + 0.001, np.array([1.0]), ea, 0.0, 0.0)
        np.testing.assert_allclose(t, ea * ((L + 1) / rest - 1))
        np.testing.assert_allclose(t, p)
        self.assertAlmostEqual(float(play(1.0, 1.00004, 0.1)), 1.0)
        self.assertAlmostEqual(float(play(1.0, 1.00010, 0.1)), 1.00005)

    def test_finite_bore_and_rigid_arm(self):
        for slope in (0.0, 0.1, 0.4):
            self.assertAlmostEqual(
                radial_extent(np.array([0.13, 0.0]), np.array([slope, 0.0])),
                0.13 + np.hypot(1, slope),
                places=7,
            )
        points = np.array([[0, 0, -12.0], [0, 0, 0.0], [0, 0, 12.0]])
        self.assertAlmostEqual(bore_gap(points, 1.3, 1.5, 0.5, 1.6), 0.3)
        x = np.array([3.0, 2.0, 1.0])
        r = np.array([0.01, -0.03, 0.06])
        np.testing.assert_allclose(
            arm(x) @ np.r_[[1, 2, 3], r], [1, 2, 3] + np.cross(r, x)
        )

    def test_damped_pose_step_preserves_the_finite_rope_domain(self):
        class Rod:
            def residual(self, gradient):
                return np.linalg.norm(gradient)

        class Drive:
            _last_hessian = np.array([[0.75]])

            def energy(self, x, cmd):
                if x[0] > 1:
                    raise ValueError(
                        "Guide lies outside the supported bellmouth tangent domain"
                    )
                return 0, np.array([x[0] ** 3 - cmd])

            def force(self, x, cmd):
                return np.ones(1)

            def tangent(self, x, cmd, force):
                return np.array([[3 * x[0] ** 2]])

        info = {}
        point = equilibrate(Rod(), Drive(), np.array([0.5]), 0.9**3, info)
        self.assertIn("finite rope routing domain", info["reason"])
        self.assertAlmostEqual(point[0], 0.9, places=5)

    def test_bond_tractions_have_outward_normals_on_both_faces(self):
        pads = material_points(67.5, 25)
        self.assertAlmostEqual(sum(v[3] for v in pads), 5.67)
        for _, rel, n, _ in pads:
            self.assertGreater(rel @ n, 0)
        for i in (0, 8):
            np.testing.assert_allclose(pads[i][2], -pads[i + 4][2])
            # The elastic tensor and previously computed land forces are invariant to face orientation.
            np.testing.assert_array_equal(
                np.outer(pads[i][2], pads[i][2]),
                np.outer(pads[i + 4][2], pads[i + 4][2]),
            )

    def test_affine_layer_matches_direct_CAD_map(self):
        rod, z, _ = load_motion()
        v = np.random.default_rng(16).uniform(-25, 25, (60, 3))
        for st in (-12, 12):
            d = rod.kinematic_metrics(z[1709])[1]
            a = coefficients(v[:, 2], st, rod, d)
            np.testing.assert_allclose(
                a[:, 0] + v[:, :1] * a[:, 1] + v[:, 1:2] * a[:, 2],
                to_station(v, 5, st, rod, d),
                atol=1e-9,
            )

    def test_displaced_route_virtual_work(self):
        rod, _ = plant()
        _, z, _ = load_motion()
        x = z[1709]
        shifts = np.array(
            [[0.5, 1.1, 0.02, 0.01, 0.005, 0.003], [-0.4, 0.7, 0.04, -0.015, 0.01, 0.0]]
        )
        d = rod.base.kinematic_metrics(x)[1]
        length, paths = displaced_paths(rod, d, shifts)
        forces = np.array([2.8, 10.0, 8.0, 13.0])
        e = np.zeros_like(d["points"])
        g = np.zeros_like(d["frames"])
        for k, nodes, off, unit in paths:
            f = forces[k] * unit
            e[nodes] += f
            g[nodes] += f[:, :, None] * off[:, None, :]
        grad = material_gradient(
            x, rod.scale, rod.l, rod.planar.u, rod.planar.w, d["frames"], e, g
        )
        delta = np.random.default_rng(4).standard_normal(len(x))
        h = 1e-5
        vals = [
            forces
            @ displaced_paths(
                rod, rod.base.kinematic_metrics(x + s * h * delta)[1], shifts
            )[0]
            for s in (-1, 1)
        ]
        self.assertAlmostEqual(
            (vals[1] - vals[0]) / (2 * h), float(grad @ delta), places=7
        )


if __name__ == "__main__":
    unittest.main()
