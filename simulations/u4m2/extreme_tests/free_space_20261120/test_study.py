"""Focused regressions for the free-space coordinate convention, end screening and cycle counting."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import trimesh
from cad_screen import RopeSurface, failed_part
from duty import rainflow
from free_space import coordinates
from pose_map import axis
from repeat_block import reset_plan
from reset_takeup import plan_reset
from service_life import counted, dose, required
from m6_full import coefficients
from m6_socket_screen import to_station
from replay import plant
from common import trajectory


class StudyTest(unittest.TestCase):
    def test_antipode_and_pole_continuity(self):
        np.testing.assert_allclose(
            axis(*coordinates("pitch", 180, -20)), -axis(0, 20), atol=1e-14
        )
        self.assertLess(np.linalg.norm(axis(0, 91) - axis(0, 89)), 0.036)
        self.assertLess(np.linalg.norm(axis(181, 20) - axis(179, 20)), 0.035)

    def test_mean_range_residual_dose(self):
        for s in ([0, 2, 2, 1, 3, 0, 1], [1, 1], [3, 1, 4, 0, 2, 2, 1]):
            c = counted(s)
            np.testing.assert_allclose(
                np.array([r[2:] for r in c]).reshape(-1, 3), rainflow(s)
            )
            self.assertAlmostEqual(
                sum(r[2] * r[4] for r in c), sum(abs(np.diff(s))) / 2
            )
        # Two half cycles at range 4 give one full cycle at amplitude 2.
        d = dose(counted([0, 4, 0]), 5)
        self.assertAlmostEqual(d, 2**5)
        self.assertAlmostEqual(1e6 * required(d, 5) ** 5 / d, 10000)

    def test_surface_sign_across_a_long_jump(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "box.stl"
            trimesh.creation.box(extents=[2, 2, 2]).export(path)
            pts = np.array(
                [[2.0, 0, 0], [1.5, 0, 0], [0.0, 0, 0], [0.25, 0, 0], [-1.5, 0, 0]]
            )
            np.testing.assert_allclose(
                RopeSurface(path).signed(pts), [1, 0.5, -1, -0.75, 0.5]
            )

    def test_six_station_affine_mapping(self):
        rod = plant()[0].base
        z = trajectory()[0][1796]
        d = rod.kinematic_metrics(z)[1]
        xyz = np.array([[4.0, 2.0, -12.0], [-8.0, 16.0, 20.0]])
        for m in (4, 5):
            a = coefficients(xyz[:, 2], -12, rod, d, m)
            np.testing.assert_allclose(
                a[:, 0] + xyz[:, :1] * a[:, 1] + xyz[:, 1:2] * a[:, 2],
                to_station(xyz, m, -12, rod, d),
                atol=1e-9,
            )

    def test_finite_rope_faceting_and_wrap(self):
        self.assertIsNone(
            failed_part(
                {"x_rope_gap_mm": -0.0049, "x_wrap_margin_deg": 1.0, "guide_mm": 0.001}
            )
        )
        self.assertEqual(failed_part({"x_rope_gap_mm": -0.0051}), "x_rope_gap_mm")
        self.assertEqual(failed_part({"x_wrap_margin_deg": 0.999}), "x_wrap_margin_deg")
        self.assertEqual(failed_part({"cap_mm": 0.0}), "cap_mm")

    def test_direction_aware_reset_returns_material_and_drum(self):
        from rope_history import contact, play

        names = ["line"]
        ea = 3000.0
        length = np.array([[0.3], [0.304], [0.3042]])
        force = np.full_like(length, 4.0)
        wrap = np.full_like(length, 0.8)
        rest = (length + 1) / (1 + force / ea)
        rows = [{"line_internal_path_mm": 1000 * v[0]} for v in length]
        plan = [(i, 1.0, s, "endpoint") for i, s in enumerate(rest)]
        drum = rest[-1].copy()
        h = length[-1] / (1 + force[-1] / ea)
        reset = plan_reset(rows, plan, 1, rest, force, wrap, ea, drum, force[-1], names)
        for i, f, cmd, _ in reset:
            drum = play(drum, cmd, 0.10)
            L = length[max(0, i - 1)] + f * (length[i] - length[max(0, i - 1)])
            pro, dist, h, _, _ = contact(L, drum, h, wrap[i], ea, 0.15, 0.15)
        np.testing.assert_allclose(drum, rest[0], atol=1e-10)
        np.testing.assert_allclose(h, length[0] / (1 + force[0] / ea), atol=1e-9)
        np.testing.assert_allclose([pro, dist], [[4.0], [4.0]], atol=1e-5)

    def test_reset_at_same_clamp_includes_all_startup_commands(self):
        p = [
            (i, 1.0, np.full(12, v), "endpoint")
            for i, v in enumerate((1.0, 1.001, 1.0006))
        ]
        route = reset_plan(p, 1)
        cmds = np.array(
            [p[-1][2]] + [r[2] for r in route if r[3] == "neutral_handover"]
        )
        self.assertLessEqual(abs(np.diff(cmds, axis=0)).max(), 0.00015)
        np.testing.assert_allclose(cmds[-1], p[1][2])
        np.testing.assert_allclose(route[-1][2], p[0][2])


if __name__ == "__main__":
    unittest.main()
