"""Mechanical patch tests and synchronized two-face metrology checks."""

import json
import unittest
import numpy as np
from scipy.linalg import solve
from cvxopt import solvers

from inputs import BENCH, p3_input
from bench_inputs import program, load_targets
from contact import Patch
from steel import Steel, beam_element, shapes, cap_aperture, CAP_CYL_END, CAP_TIP
from supported_contact import Interface, evaluate
from witness import observe, assess, FIELDS
from score_bench import COUPON


class Mechanics(unittest.TestCase):
    def test_three_point_bending_and_shear(self):
        L = 3.0
        r = 0.3
        E = 200000.0
        nu = 0.3
        for clamp in (True, False):
            k, _, phi, I = beam_element(L / 2, r, 0.0, E, nu)
            K = np.zeros((6, 6))
            K[:4, :4] += k
            K[2:, 2:] += k
            free = [2, 3] if clamp else [1, 2, 3, 5]
            f = np.eye(6)[2]
            u = solve(K[np.ix_(free, free)], f[free])
            v = u[free.index(2)]
            kGA = 12 * E * I / (phi * (L / 2) ** 2)
            self.assertAlmostEqual(
                v, L**3 / ((192 if clamp else 48) * E * I) + L / (4 * kGA), places=12
            )

    def test_shape_functions_and_rigid_motion(self):
        L = np.full(3, 2.0)
        x = np.array([0.0, 0.6, 2.0])
        phi = np.full(3, 0.3)
        v, r, d, k = shapes(x, L, phi)
        dofs = np.array([0.4, 0.25, 0.9, 0.25])
        np.testing.assert_allclose(v @ dofs, 0.4 + 0.25 * x)
        np.testing.assert_allclose(r @ dofs, 0.25)
        np.testing.assert_allclose(d @ dofs, 0.25)
        np.testing.assert_allclose(k @ dofs, 0.0, atol=1e-12)
        np.testing.assert_allclose(v[[0, 2]], np.eye(4)[[0, 2]], atol=1e-12)

    def test_cad_cap_profile(self):
        self.assertAlmostEqual(cap_aperture(-2.3), 0.316)
        self.assertAlmostEqual(cap_aperture(CAP_CYL_END), 0.316)
        self.assertAlmostEqual(cap_aperture(CAP_TIP), 0.66, places=7)
        self.assertTrue(
            np.all(
                np.diff(cap_aperture(np.linspace(CAP_CYL_END, CAP_TIP, 100)))
                >= -1.0e-10
            )
        )

    def test_gap_virtual_work(self):
        steel = Steel(0.3, "hinged")
        web = Patch("middle", 2.7, fit_relief=True)
        _, _, R = p3_input()
        c = Interface(web, steel, R, 12)
        rng = np.random.default_rng(4)
        u = rng.normal(0.0, 0.0001, (len(web.ids), 3))
        q = rng.normal(0.0, 2.0e-4, len(steel.free))
        t = np.array([0.002, -0.007, 0.003])
        g, n, local, A = c.rows(u, t, q)
        dq = rng.normal(0, 0.003, len(q))
        du = rng.normal(0, 0.004, u.shape)
        dt = rng.normal(0, 0.004, 3)
        h = 3e-5
        fd = (
            c.rows(u + h * du, t + h * dt, q + h * dq)[0]
            - c.rows(u - h * du, t - h * dt, q - h * dq)[0]
        ) / (2 * h)
        pred = n @ dt - A @ dq
        pred[: len(c.idx)] += np.sum(local * du[c.idx], axis=1)
        np.testing.assert_allclose(fd, pred, atol=1e-6, rtol=1e-4)

    def test_rigid_limit_matches_archived_P3(self):
        _, F, R = p3_input()
        w = Patch("middle", 2.7, fit_relief=True)
        c = Interface(w, Steel(0.3, "clamped", 2e12), R, 12)
        solvers.options.update(
            show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
        )
        old = json.loads((BENCH / "results/coupon_middle.json").read_text())
        for sign in (1, -1):
            actual = evaluate(c, sign * F)
            ref = next(
                r
                for r in old["load_states"]
                if r["target"] == "P3" and r["multiplier"] == sign
            )
            self.assertTrue(actual["converged"])
            np.testing.assert_allclose(
                actual["coupon_carriage_spn_mm"],
                ref["relative_translation_spn_mm"],
                atol=2e-7,
            )


class Optics(unittest.TestCase):
    def rows(self):
        a = []
        b = []
        for cmd in (r for r in program(load_targets()) if r["target"] == "P3"):
            direction = cmd["direction"]
            i = cmd["order"]
            factor = cmd["load_multiplier"]
            before = {
                "specimen": "S",
                "print_lot": "lot1",
                "calibration_id": "cal1",
                "fixture_id": "fx",
                "trace_id": direction,
                "frame_id": str(i),
                "direction": direction,
                "phase": cmd["phase"],
                "elapsed_s": i + 1.0,
            }
            # A rigid translation and tilt are shared by the metal endpoints; only the coupon adds a relative movement.
            base = 0.02 * factor
            slope = 0.008 * factor
            a.append(
                before
                | dict(
                    coupon_datum_s_mm=base + 0.03 * factor,
                    coupon_datum_p_mm=0.0,
                    head_datum_s_mm=base + 4 * slope,
                    head_datum_p_mm=0.0,
                    head_face_n_mm=4.0,
                    cap_datum_s_mm=base - 5 * slope,
                    cap_datum_p_mm=0.0,
                    cap_face_n_mm=-5.0,
                    coupon_sp_bound_mm=0.001,
                    head_sp_bound_mm=0.001,
                    cap_sp_bound_mm=0.001,
                    axial_coordinate_bound_mm=0.002,
                )
            )
            item = {
                k: before[k]
                for k in (
                    "specimen",
                    "print_lot",
                    "calibration_id",
                    "direction",
                    "phase",
                    "elapsed_s",
                )
            }
            item.update(
                target="P3",
                visible_damage="no",
                force_vector_uncertainty_N=0.05,
                pose_uncertainty_deg=0.1,
                position_vector_uncertainty_mm=0.001,
            )
            for xyz in "spn":
                item["pin_on_web_" + xyz + "_N"] = cmd["pin_on_web_" + xyz + "_N"]
                item["coupon_" + xyz + "_mm"] = 0.0
            for j in "xyzw":
                item["q" + j] = cmd["coupon_to_pin_q" + j]
            a[-1] = {k: str(a[-1][k]) for k in FIELDS}
            b.append({k: str(item[k]) for k in COUPON})
        return a, b

    def test_registered_peak_reversal_and_reference(self):
        w, b = self.rows()
        r = assess(w, b)
        self.assertEqual(r["status"], "synchronized_P3_observed")
        s = r["specimens"][0]
        self.assertAlmostEqual(
            s["paired_peak_reversal"]["relative"]["magnitude_mm"], 0.06
        )
        self.assertAlmostEqual(s["paired_peak_reversal"]["raw"]["magnitude_mm"], 0.10)
        for pair in s["matched_positive_1N_reference_shifts"].values():
            self.assertFalse(pair["relative"]["resolved"])

    def test_missing_phase_damage_and_empty(self):
        w, b = self.rows()
        b[0]["visible_damage"] = "yes"
        s = assess(w[:-1], b)
        self.assertEqual(s["status"], "review_required")
        self.assertFalse(s["specimens"][0]["complete_synchronized_P3"])
        self.assertEqual(assess([], [])["status"], "awaiting_measurements")
        self.assertEqual(assess([], b)["matched_coupon_rows"], 0)

    def test_duplicate_clock_and_registration(self):
        w, b = self.rows()
        with self.assertRaises(ValueError):
            assess(w + w[:1], b)
        w[0]["elapsed_s"] = "1.0001"
        with self.assertRaises(ValueError):
            assess(w, b)
        w[0]["head_face_n_mm"] = "0."
        with self.assertRaises(ValueError):
            observe(w[0])


if __name__ == "__main__":
    unittest.main()
