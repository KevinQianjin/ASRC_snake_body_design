"""Tests for the offset-wall constraint, free joint route and directional tension measurements."""

import unittest

import numpy as np
from shared_bore import ARCHIVE, RAYS, geometry, load_rod, load_states, solve, wall_grid
from rebalance import SharedRod, gradient_check
from pullthrough import score
from guide_loads import cad_axes, record

PROFILES = np.array(
    [[7, 3.9, np.radians(29), 1.25, 1.0], [3, 7.0, np.radians(18), 1.25, 1.0]]
)


class Geometry(unittest.TestCase):
    def test_inscribed_wall_bounds_at_interior_positions(self):
        for prof in PROFILES:
            x, r, _ = wall_grid(prof, 0.15)
            depth, wall, angle, hole, rope = prof
            rc = wall + rope
            s0 = depth - wall * np.sin(angle)
            s1 = s0 + rc * np.sin(angle)
            q = np.linspace(x[0], x[-1], 2001)
            arc = np.clip(q - s0, 0, s1 - s0)
            exact = (
                wall
                + hole
                - np.sqrt(rc**2 - arc**2)
                + np.maximum(q - s1, 0) * np.tan(angle)
            )
            self.assertLess(np.max(np.interp(q, x, r) - exact), 1e-12)

    def test_free_shared_bore_has_exact_straight_solution(self):
        l = np.array([-24.0, 0.12, -0.08])
        r = np.array([24.0, 0.12, -0.08])
        q, d = solve(l, r, PROFILES, 0.16)
        self.assertAlmostEqual(d["length_mm"], 48.0, places=7)
        np.testing.assert_allclose(q[[0, -1]], [l, r], atol=1e-14)
        np.testing.assert_allclose(d["interface_transverse_mm"], l[1:], atol=5e-4)
        self.assertLess(d["force_balance_residual_per_N"], 0.0005)

    def test_reflection_reversal_and_geometry_refinement(self):
        l = np.array([-22.0, -3.0, 1.0])
        r = np.array([20.0, 3.0, -2.0])
        pm, d = solve(l, r, PROFILES, 0.15)
        pf, f = solve(l, r, PROFILES, 0.075)
        flip = np.array([-1, 1, 1])
        _, rev = solve(flip * r, flip * l, PROFILES[::-1], 0.15)
        self.assertAlmostEqual(rev["length_mm"], d["length_mm"], places=8)
        np.testing.assert_allclose(
            rev["interface_transverse_mm"], d["interface_transverse_mm"], atol=2e-5
        )
        self.assertLess(abs(f["length_mm"] - d["length_mm"]), 0.002)
        self.assertLess(
            max(f["max_cone_violation_mm"], d["max_cone_violation_mm"]), 1e-7
        )


class RodIntegration(unittest.TestCase):
    def test_only_c_routes_change_and_energy_gradient_matches(self):
        _, base, profiles = load_rod()
        rod = SharedRod(base, profiles, 0.15)
        states, _ = load_states(ARCHIVE / "equilibria_states.npz")
        _, z, T, _ = states[64]
        v0, g0, d0 = base.evaluate(z, T, detail=True)
        v, g, d = rod.evaluate(z, T, detail=True)
        np.testing.assert_allclose(
            d["rope_lengths"][:2], d0["rope_lengths"][:2], atol=1e-13
        )
        dl = d["rope_lengths"][2] - d0["rope_lengths"][2]
        self.assertTrue(np.all(dl < 0))
        self.assertAlmostEqual(v - v0, float(dl @ T[2]), places=11)
        np.testing.assert_allclose(
            rod.endpoints(z[rod.local]),
            [geometry(base, z, T)[ray] for ray in RAYS],
            atol=1e-9,
        )
        rng = np.random.default_rng(194)
        dq = rng.normal(size=len(z))
        dq /= np.linalg.norm(dq)
        h = 5e-5
        xp = rod.evaluate(z + h * dq, T, detail=True)
        xm = rod.evaluate(z - h * dq, T, detail=True)
        self.assertAlmostEqual((xp[0] - xm[0]) / (2 * h), float(g @ dq), places=6)
        numerical = (xp[2]["rope_lengths"] - xm[2]["rope_lengths"]).ravel() / (2 * h)
        np.testing.assert_allclose(rod.control_jacobian(z) @ dq, numerical, atol=2e-7)
        checked = gradient_check(rod, z)
        self.assertLess(max(c["max_length_gradient_error_m"] for c in checked), 2e-7)
        row, detail, _ = rod.metrics(z, T, stability=False)
        np.testing.assert_allclose(
            detail["rope_lengths"], d["rope_lengths"], atol=1e-12
        )

    def test_shared_guide_forces_and_joint_virtual_work(self):
        _, base, profiles = load_rod()
        states, _ = load_states(ARCHIVE / "equilibria_states.npz")
        _, z, T, _ = states[64]
        keys, old, _, _, _ = record(base, profiles, z, T, False)
        keys2, new, joint, residual, work = record(base, profiles, z, T, True, True)
        self.assertEqual(keys, keys2)
        self.assertEqual(len(keys), 48)
        for i, (module, station, family, ray) in enumerate(keys):
            if family != "C" or (module, station) not in (("M5", 24), ("M6", -24)):
                np.testing.assert_array_equal(old[i], new[i])
            offset = (
                cad_axes(base.offsets3["ABC".index(family), RAYS.index(ray)]) * 1000
            )
            np.testing.assert_allclose(
                np.cross(offset, new[i, 0]), new[i, 1], atol=1e-9
            )
        self.assertLess(work["force_error_N"], 1e-3)
        self.assertLess(work["moment_error_Nmm"], 1e-3)
        self.assertLess(residual, 0.005)
        self.assertTrue(np.all(np.isfinite(joint)))


class Measurements(unittest.TestCase):
    def test_direction_order_uncertainty_and_zero_rows(self):
        geometry = [dict(hold=64, ray="up", absolute_wrap_rad=0.3)]
        self.assertEqual(score([], geometry)["status"], "awaiting_measurements")
        r = dict(
            specimen="fixture",
            rope_lot="test",
            calibration_id="test",
            hold="64",
            ray="up",
            cycle="1",
            direction="pull_M6",
            elapsed_s="1",
            speed_mm_s="1",
            steady_sliding="yes",
            M5_tension_N="5",
            M6_tension_N="6",
            M5_uncertainty_N=".02",
            M6_uncertainty_N=".02",
            wear="no",
        )
        self.assertTrue(score([r], geometry)["missing_steady_direction"])
        back = r | dict(
            direction="pull_M5", speed_mm_s="-1", M5_tension_N="6", M6_tension_N="5"
        )
        d = score([r, back], geometry)
        self.assertEqual(d["status"], "paired_sliding_data_recorded")
        self.assertAlmostEqual(
            d["observations"][0]["directions"]["pull_M5"][0]["effective_mu"],
            np.log(1.2) / 0.3,
        )
        self.assertEqual(
            score([r, back | {"M5_tension_N": "4"}], geometry)["status"],
            "review_required",
        )
        with self.assertRaises(ValueError):
            score([r, r], geometry)
        with self.assertRaises(ValueError):
            score([r | {"speed_mm_s": "-2"}], geometry)

    def test_measured_wrap_and_two_tension_bounds(self):
        geometry = [dict(hold=64, ray="up", absolute_wrap_rad=0.3)]
        row = dict(
            specimen="fixture",
            rope_lot="test",
            calibration_id="test",
            hold="64",
            ray="up",
            cycle="1",
            direction="pull_M6",
            elapsed_s="1",
            speed_mm_s="1",
            steady_sliding="yes",
            M5_tension_N="5",
            M6_tension_N="6",
            M5_uncertainty_N=".02",
            M6_uncertainty_N=".03",
            wear="no",
            measured_wrap_deg="20",
            wrap_uncertainty_deg="2",
        )

        def measurement(changes):
            out = score([row | changes], geometry)
            return out["observations"][0]["directions"]["pull_M6"][0]

        result = measurement({})
        self.assertEqual(result["wrap_source"], "measured")
        self.assertAlmostEqual(result["effective_mu"], np.log(6 / 5) / np.radians(20))
        np.testing.assert_allclose(
            result["effective_mu_bounds"],
            [
                np.log(5.97 / 5.02) / np.radians(22),
                np.log(6.03 / 4.98) / np.radians(18),
            ],
        )
        reversed_result = measurement({"M6_tension_N": "4"})
        self.assertTrue(reversed_result["high_tension_inconsistent"])
        self.assertAlmostEqual(
            reversed_result["effective_mu_bounds"][0],
            np.log(3.97 / 5.02) / np.radians(18),
        )
        near_straight = measurement({"measured_wrap_deg": "1"})
        self.assertNotIn("effective_mu", near_straight)
        self.assertIn("tension_ratio", near_straight)
        with self.assertRaises(ValueError):
            measurement({"wrap_uncertainty_deg": ""})


if __name__ == "__main__":
    unittest.main()
