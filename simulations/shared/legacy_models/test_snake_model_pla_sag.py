"""Original-paper input checks and independent numerical self-weight checks."""
import math
import unittest

import numpy as np
from scipy.integrate import quad, solve_bvp
from scipy.optimize import root

import craft_data as D
import snake_model_pla_sag as S


class PLASagTests(unittest.TestCase):
    def setUp(self):
        self.config = S.read_config()

    def test_complete_fixed_order_enumeration_and_zero_option(self):
        combos = list(S.combinations(31))
        self.assertEqual(len(combos), math.comb(30, 3))
        self.assertEqual(len(set(combos)), len(combos))
        self.assertTrue(all(sum(c) == 31 and min(c) >= 1 for c in combos))
        self.assertEqual(sum(len(list(S.combinations(n))) for n in range(4, 32)), 31465)
        self.assertEqual(len(list(S.combinations(4, 0))), math.comb(7, 3))
        props = S.properties(self.config)
        _, mass, _ = S.cell_arrays((1, 2, 3, 4), props, 1)
        np.testing.assert_allclose(mass[0] * 1000, np.repeat([p["mass_g"] for p in props], [1, 2, 3, 4]))

    def test_original_paper_properties_without_conversion(self):
        p = S.properties(self.config)
        expected = ((.028, 5.1), (.061, 3.9), (.0035, 4.), (.0024, 3.6))
        for row, (ei, mass_g) in zip(p, expected):
            self.assertEqual(row["EI_down_nm2"], ei)
            self.assertAlmostEqual(row["mass_g"], mass_g, places=12)
            m = D.MODULES[row["kind"]]
            self.assertEqual(row["mass_g"], m["pc_g"] + m["pla_g"])
            self.assertFalse(row["material_conversion_applied"])
        self.config["axes"]["unidirectional"] = "x"
        soft = S.properties(self.config)
        self.assertEqual(soft[1]["EI_down_nm2"], .0057)
        self.config["axes"]["directional"] = "x"
        self.assertEqual(S.properties(self.config)[2]["EI_down_nm2"], .0030)
        self.config["axes"]["directional"] = "-x"
        self.assertEqual(S.properties(self.config)[2]["EI_down_nm2"], .0037)

    def test_conversion_overrides_and_rescaling_are_rejected(self):
        for key, value in (("material", {}), ("property_overrides", {"high": {"mass_g": 100}}),
                           ("extras_g_per_module", 1), ("module_diameter_mm", 16),
                           ("module_length_mm", 24), ("data_mode", "all_PLA_estimate")):
            with self.subTest(setting=key):
                cfg = self.config.copy()
                cfg[key] = value
                with self.assertRaises(ValueError):
                    S.properties(cfg)

    def test_nonlinear_uniform_cantilever_against_continuum_BVP(self):
        # Independent continuum: theta'=M/EI, M'=q*(L-s)*cos(theta).
        n, length, ei, total_mass, g = 320, 1., .03, .1, 9.81
        x = np.linspace(0, length, 160)
        q = total_mass * g / length

        def fun(s, values):
            return np.vstack((values[1] / ei, q * (length - s) * np.cos(values[0])))

        def boundary(left, right):
            return np.array([left[0], right[1]])

        continuum = solve_bvp(fun, boundary, x, np.zeros((2, len(x))), tol=1e-9, max_nodes=6000)
        self.assertTrue(continuum.success)
        expected = -quad(lambda s: np.sin(continuum.sol(s)[0]), 0, length, epsabs=1e-10)[0] * 1000
        ll = np.full((1, n), length / n)
        mass = np.full((1, n), total_mass / n)
        k = np.full((1, n), ei / (length / n)); k[:, 0] *= 2
        result = S.solve_cells(ll, mass, k)
        self.assertTrue(result["converged"][0])
        self.assertLess(abs(result["tip_drop_mm"][0] - expected), .02)

    def test_mixed_stiffness_small_load_against_virtual_work(self):
        self.config["gravity_m_s2"] = 1e-5
        counts = (2, 3, 2, 1)
        props = S.properties(self.config)
        ei = np.repeat([p["EI_down_nm2"] for p in props], counts)
        masses = np.repeat([p["mass_g"] / 1000 for p in props], counts)
        cell_length = .048
        span = sum(counts) * cell_length

        def moment(x):
            total = 0.
            for j, mass in enumerate(masses):
                left, right = max(x, j * cell_length), (j + 1) * cell_length
                if left < right:
                    total += mass / cell_length * ((right - x)**2 - (left - x)**2) / 2
            return total * self.config["gravity_m_s2"]

        expected = sum(quad(lambda x: moment(x) * (span - x) / rigidity,
                            j * cell_length, (j + 1) * cell_length, epsabs=1e-14)[0]
                       for j, rigidity in enumerate(ei)) * 1000
        result = S.solve_counts(counts, self.config, cells=32)
        self.assertLess(abs(result["tip_drop_mm"][0] / expected - 1), .0005)

    def test_batch_agrees_with_independent_root_and_zero_gravity(self):
        counts = [(2, 2, 2, 2), (1, 4, 1, 2), (4, 1, 2, 1)]
        out = S.solve_counts(counts, self.config)
        for i in range(3):
            k, mass, ll = out["k"][i], out["mass"][i], out["length"][i]
            a = 9.81 * ll * (np.cumsum(mass[::-1])[::-1] - .5 * mass)
            # Dense independent stiffness assembly, no batch gradient helper.
            b = np.eye(len(k)) - np.eye(len(k), k=-1)
            stiffness = b.T @ np.diag(k) @ b
            independent = root(lambda phi: stiffness @ phi + a * np.cos(phi), np.zeros(len(k)), tol=1e-11)
            self.assertTrue(independent.success)
            np.testing.assert_allclose(out["phi"][i], independent.x, atol=1e-7)
        self.config["gravity_m_s2"] = 0
        zero = S.solve_counts(counts, self.config)
        np.testing.assert_array_equal(zero["tip_drop_mm"], 0.)
        np.testing.assert_allclose(zero["tip_x_mm"], 8 * 48)

    def test_refinement_bounds_and_invalid_inputs(self):
        counts = (8, 13, 8, 2)
        coarse = S.solve_counts(counts, self.config, cells=4)
        medium = S.solve_counts(counts, self.config, cells=8)
        fine = S.solve_counts(counts, self.config, cells=16)
        e1 = abs(coarse["tip_drop_mm"][0] - medium["tip_drop_mm"][0])
        e2 = abs(medium["tip_drop_mm"][0] - fine["tip_drop_mm"][0])
        self.assertLess(e2, e1 / 3)
        self.assertTrue(0 < fine["tip_drop_mm"][0] < 31 * 48)
        self.assertTrue((fine["phi"] <= 0).all())
        self.assertTrue((fine["phi"] >= -np.pi / 2).all())
        for counts in ((-1, 2, 3, 4), (0, 0, 0, 0), (1.5, 1, 1, 1)):
            with self.assertRaises(ValueError):
                S.solve_counts(counts, self.config)
        with self.assertRaises(ValueError):
            S.solve_counts((1, 1, 1, 1), self.config, cells=0)


if __name__ == "__main__":
    unittest.main()
