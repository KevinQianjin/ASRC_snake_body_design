"""Boundary, load sign, interface equilibrium and hardware-intake regression checks."""

import json
import unittest
from copy import deepcopy

from cvxopt import solvers
import numpy as np
from scipy.spatial.transform import Rotation
from bench_inputs import HERE, load_targets, program
from coupled import couple_potential, rotation, rotation_fit, skew
from contact import Patch, evaluate
from score_bench import (
    COUPON,
    CAGE,
    DIMENSIONS,
    assess_coupon,
    assess_metrology,
    assess_cage,
)


class Interfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = Patch("middle", 2.7, fit_relief=True, prescribed_ends=True)
        solvers.options["show_progress"] = False

    def test_lift_transmits_rigid_translation_without_strain(self):
        p = self.patch
        v = np.array([0.017, -0.02, 0.035])
        u = p.lift_ends(np.tile(v, (len(p.fixed_nodes), 1)))
        np.testing.assert_allclose(u, np.tile(v, (len(p.x), 1)), atol=1e-12)
        self.assertLess(p.stress(u)["peak_tensile_principal_strain"], 1e-12)

    def test_rotation_fit_recovers_arbitrary_frame(self):
        x = self.patch.x[self.patch.fixed_nodes]
        R = Rotation.from_rotvec([0.7, 0.2, -0.4]).as_matrix()
        t = np.array([0.02, -0.03, 0.1])
        rr, tt = rotation_fit(x, x @ R.T + t)
        np.testing.assert_allclose(R, rr, atol=1e-12)
        np.testing.assert_allclose(t, tt, atol=1e-12)

    def test_couple_gradient_hessian_and_objectivity(self):
        q = np.array([0.1, -0.08, 0.03, -0.1, 0.03, 0.14])
        a = (
            0.5
            * skew(np.array([1.0, 2.0, -3.0]))
            @ rotation(q[:3])[0].T
            @ rotation(q[3:])[0]
        )
        fn = lambda x: couple_potential(rotation(x[:3]), rotation(x[3:]), a, True)
        v, g, H = fn(q)
        h = 1e-6
        for k, row in enumerate(np.eye(6)):
            vp, gp, _ = fn(q + h * row)
            vm, gm, _ = fn(q - h * row)
            self.assertAlmostEqual((vp - vm) / (2 * h), g[k], places=8)
            np.testing.assert_allclose((gp - gm) / (2 * h), H[:, k], atol=2e-8)
        W = Rotation.from_rotvec([0.55, -0.8, 0.2]).as_matrix()
        G = rotation(q[:3])[0]
        L = rotation(q[3:])[0]
        self.assertAlmostEqual(v, -np.sum(a * ((W @ G).T @ (W @ L))), places=12)

    def test_mirror_row_uses_prescribed_normal_and_recovers_force(self):
        source, _, _ = load_targets()["P1"]
        p = self.patch
        conv = evaluate(p, source)
        mixed = evaluate(p, source, normal_translation=0)
        self.assertTrue(mixed["converged"])
        self.assertLess(mixed["force_residual_N"], 0.005)
        self.assertAlmostEqual(mixed["relative_translation_spn_mm"][2], 0, places=12)
        np.testing.assert_allclose(
            conv["relative_translation_spn_mm"][:2],
            mixed["relative_translation_spn_mm"][:2],
            atol=5e-6,
        )

    def test_mixed_off_axis_thrust_matches_loaded_force_solution(self):
        source, applied, _ = load_targets()["P2"]
        original = evaluate(self.patch, source, recover_strain=False)
        self.assertTrue(original["converged"])
        t = original["relative_translation_spn_mm"][2]

        def reaction(offset):
            row = evaluate(
                self.patch, source, normal_translation=offset, recover_strain=False
            )
            self.assertTrue(row["converged"])
            sums = np.sum(
                [v["resultant_spn_N"] for v in row["contact_components"].values()],
                axis=0,
            )
            return row, sums

        equal, matched = reaction(t)
        np.testing.assert_allclose(matched, applied, atol=0.005)
        np.testing.assert_allclose(
            equal["relative_translation_spn_mm"],
            original["relative_translation_spn_mm"],
            atol=5e-6,
        )
        _, below = reaction(t - 0.0005)
        _, above = reaction(t + 0.0005)
        self.assertGreater(below[2], above[2])


class HardwareIntake(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((HERE / "results/coupon_fine.json").read_text())
        self.rows = []
        for c in program(load_targets()):
            r = dict.fromkeys(COUPON, "0")
            r.update(
                specimen="fixture",
                print_lot="test",
                calibration_id="test",
                target=c["target"],
                direction=c["direction"],
                phase=c["phase"],
                elapsed_s=str(c["order"]),
                force_vector_uncertainty_N=".10",
                pose_uncertainty_deg=".1",
                position_vector_uncertainty_mm=".01",
                visible_damage="no",
            )
            for k in "xyzw":
                r["q" + k] = str(c["coupon_to_pin_q" + k])
            for k in "spn":
                r[f"pin_on_web_{k}_N"] = str(c[f"pin_on_web_{k}_N"])
            self.rows.append(r)

    def test_empty_complete_incomplete_and_reference_shift(self):
        self.assertEqual(
            assess_coupon([], self.model)["status"], "awaiting_measurements"
        )
        self.assertEqual(
            assess_coupon(self.rows, self.model)["status"], "measured_program_complete"
        )
        self.assertEqual(
            assess_coupon(self.rows[:-1], self.model)["status"], "review_required"
        )
        self.rows[10]["coupon_s_mm"] = ".035"
        self.assertIn(
            "reference shift exceeds declared uncertainty",
            assess_coupon(self.rows, self.model)["flags"],
        )

    def test_duplicate_bad_quaternion_timing_and_nonfinite(self):
        for col, value in (
            ("phase", "pre_ref"),
            ("qw", "8"),
            ("elapsed_s", "0"),
            ("pin_on_web_p_N", "nan"),
        ):
            rows = deepcopy(self.rows)
            rows[1][col] = value
            with self.assertRaises(ValueError):
                assess_coupon(rows, self.model)

    def test_cage_torque_and_dimensional_specifications(self):
        r = dict.fromkeys(CAGE, "")
        r.update(
            cage_id="test",
            print_lot="test",
            calibration_id="test",
            trial_id="test",
            station_mm="12",
            observation="lap_torque_Nmm",
            feature="lap_0",
            value="2",
            uncertainty=".1",
        )
        status = lambda: assess_cage([r])["trials"][0]["observations"][0]["status"]
        self.assertEqual(status(), "awaiting_predeclared_criterion")
        r.update(
            requirement="1.0", upper_requirement="2.05", criterion_id="synthetic test"
        )
        self.assertEqual(status(), "flagged")
        r["upper_requirement"] = "2.15"
        self.assertEqual(status(), "meets_criterion")
        self.assertEqual(assess_metrology([])["status"], "awaiting_measurements")
        self.assertAlmostEqual(DIMENSIONS["minimum_side_ligament"], 0.1952, places=4)


if __name__ == "__main__":
    unittest.main()
