"""Independent mechanics checks for the rear-only backbone model."""
import copy
import unittest

import numpy as np
from scipy.integrate import solve_bvp

import snake_model_pla_sag as S
import snake_model_rear_backbone as R


def independent_continuum(config, material, tip_moment=0., guess=None):
    counts = np.asarray(config['reference_counts'])
    props = S.properties(config)
    core = R.backbone_properties(material, config['backbone']['diameter_mm'])
    length = counts * .048
    ei = np.array([p['EI_down_nm2'] for p in props])
    ei[:2] += core['EI_nm2']
    mass = counts * np.array([p['mass_g'] / 1000 for p in props])
    mass[:2] += length[:2] * core['linear_mass_kg_m']
    downstream = np.cumsum(mass[::-1])[::-1] - mass
    gravity = config['gravity_m_s2']

    def ode(t, values):
        a = values.reshape(4, 4, -1)
        weight = gravity * (downstream[:, None] + mass[:, None] * (1 - t[None, :]))
        d = np.empty_like(a)
        d[:, 0] = length[:, None] * a[:, 1] / ei[:, None]
        d[:, 1] = length[:, None] * weight * np.cos(a[:, 0])
        d[:, 2] = length[:, None] * np.cos(a[:, 0])
        d[:, 3] = length[:, None] * np.sin(a[:, 0])
        return d.reshape(16, -1)

    def bc(left, right):
        a, b = left.reshape(4, 4), right.reshape(4, 4)
        return np.r_[a[0, 0], a[0, 2], a[0, 3], b[-1, 1] - tip_moment,
                     (b[:-1] - a[1:]).ravel()]

    t = np.linspace(0, 1, 160)
    if guess is None:
        discrete = R.solve_counts(counts, config, material, cells=32)
        phi, ll = discrete['phi'][0], discrete['length'][0]
        sc, sn = np.cumsum(ll) - ll / 2, np.r_[0, np.cumsum(ll)]
        xy = np.vstack((np.zeros(2), np.cumsum(np.c_[ll * np.cos(phi), ll * np.sin(phi)], axis=0)))
        torque = discrete['k'][0] * np.diff(phi, prepend=0.)
        initial = np.zeros((4, 4, len(t)))
        starts = np.r_[0, np.cumsum(length)[:-1]]
        for j in range(4):
            s = starts[j] + length[j] * t
            initial[j, 0] = np.interp(s, sc, phi, left=0.)
            initial[j, 1] = np.interp(s, sn, np.r_[torque, 0.])
            initial[j, 2] = np.interp(s, sn, xy[:, 0])
            initial[j, 3] = np.interp(s, sn, xy[:, 1])
        initial = initial.reshape(16, -1)
    else:
        initial = guess.sol(t)
    result = solve_bvp(ode, bc, t, initial, tol=1e-8, max_nodes=4000)
    if not result.success:
        raise AssertionError(result.message)
    return result


class RearBackboneTests(unittest.TestCase):
    def setUp(self):
        self.config, self.material, _ = R.read_inputs()
        self.counts = self.config['reference_counts']

    def test_core_stops_at_module_disk_and_front_properties_are_original(self):
        body = R.build_cells(self.counts, self.config, self.material)
        b = body['rear_cells']
        self.assertEqual(b, 20 * 8)
        self.assertAlmostEqual(body['length'][0, b:].sum(), .528)
        self.assertAlmostEqual(body['length'][0, :b].sum(), .960)
        np.testing.assert_array_equal(body['core_mass'][:, b:], 0.)
        np.testing.assert_array_equal(body['EI_effective'][:, b:], body['EI_module'][:, b:])
        np.testing.assert_allclose(body['EI_effective'][:, :b] - body['EI_module'][:, :b], body['core']['EI_nm2'])
        expected_mass = 7900 * np.pi * .0042**2 / 4 * .960
        self.assertAlmostEqual(body['core_mass'].sum(), expected_mass)
        self.assertAlmostEqual(body['module_mass'].sum() * 1000, 8 * 5.1 + 12 * 3.9 + 8 * 4. + 3 * 3.6)

    def test_scan_front_length_and_count_completeness(self):
        total = 0
        for rear in range(2, 21):
            counts = list(R.count_combinations(rear))
            self.assertEqual(len(counts), (rear - 1) * 10)
            self.assertEqual(len(set(counts)), len(counts))
            self.assertTrue(all(h + u == rear and d + low == 11 for h, u, d, low in counts))
            total += len(counts)
        self.assertEqual(total, 1900)
        self.assertEqual(len(list(R.count_combinations(20))), 190)

    def test_zero_core_and_zero_gravity_analytical_tip_moment_response(self):
        baseline = R.solve_counts(self.counts, self.config, None)
        original = S.solve_counts(self.counts, self.config)
        np.testing.assert_array_equal(baseline['phi'], original['phi'])
        cfg = copy.deepcopy(self.config)
        cfg['gravity_m_s2'] = 0.
        zero = R.solve_counts(self.counts, cfg, self.material)
        row = R.case_rows(zero, cfg)[0]
        expected_front = (.048 * 8 / .0035 + .048 * 3 / .0024) * R.DEG_PER_NMM
        core_ei = R.backbone_properties(self.material, 4.2)['EI_nm2']
        expected_rear = (.048 * 8 / (.028 + core_ei) + .048 * 12 / (.061 + core_ei)) * R.DEG_PER_NMM
        self.assertAlmostEqual(row['front_compliance_gravity_deg_per_nmm'], expected_front, places=8)
        self.assertAlmostEqual(row['rear_compliance_gravity_deg_per_nmm'], expected_rear, places=8)
        self.assertEqual(row['tip_drop_mm'], 0.)

    def test_root_moment_balance_and_reference_yield_screen(self):
        result = R.solve_counts(self.counts, self.config, self.material)
        row = R.case_rows(result, self.config)[0]
        shape = R.shape(result)
        xy = np.asarray(shape['points_mm']) / 1000
        x_mid = (xy[:-1, 0] + xy[1:, 0]) / 2
        direct = self.config['gravity_m_s2'] * result['mass'][0] @ x_mid
        self.assertAlmostEqual(row['root_reaction_moment_nm'], direct, places=7)
        weak = copy.deepcopy(self.material)
        weak['yield_strength_pa'] = 5e6
        weak_result = R.solve_counts(self.counts, self.config, weak)
        weak_row = R.case_rows(weak_result, self.config)[0]
        self.assertFalse(weak_row['passes_reference_yield_screen'])
        self.assertEqual(R.pareto_rows([weak_row]), [])

    def test_against_independent_continuum_and_moment_perturbation(self):
        reference = independent_continuum(self.config, self.material)
        discrete = R.solve_counts(self.counts, self.config, self.material, cells=32)
        row = R.case_rows(discrete, self.config)[0]
        self.assertLess(abs(row['tip_drop_mm'] + reference.y[-1, -1] * 1000), .01)
        self.assertLess(abs(row['tip_x_mm'] - reference.y[-2, -1] * 1000), .01)
        delta = 1e-6
        up = independent_continuum(self.config, self.material, delta, reference)
        down = independent_continuum(self.config, self.material, -delta, reference)
        # Block 3: tip tangent; block 1: tangent at end of rear uni-d region.
        relative_up = up.y[12, -1] - up.y[4, -1]
        relative_down = down.y[12, -1] - down.y[4, -1]
        compliance = (relative_up - relative_down) / (2 * delta) * R.DEG_PER_NMM
        self.assertLess(abs(compliance - row['front_compliance_gravity_deg_per_nmm']), .001)


if __name__ == '__main__':
    unittest.main()
