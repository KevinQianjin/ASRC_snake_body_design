"""Regression checks for the contact geometry, submodel and guide-frame transfers."""

import unittest
import numpy as np

from contact import make_mesh, shoulder_distance, strain_matrix
from corrected import rigid_fit, local_transfer
from clearance import b, j
from side_drive import DRIVERS, sweeps


class RetainedSeatChecks(unittest.TestCase):
    def test_low_driver_encloses_the_housing_inside_both_strokes(self):
        envelopes = dict(sweeps(*DRIVERS["low"]))
        probe = b.box((-0.01, -0.01, -0.01), (0.01, 0.01, 0.01))
        for phase, centre in [
            ("side entry", (27.5, 1.0, 2.30)),
            ("tightening stroke", (0.85, 0.72, 1.80)),
        ]:
            self.assertLess(
                (probe.translate(centre) - envelopes[phase]).volume(), 1e-14
            )
        outside = probe.translate((27.5, 1.50, 2.30))
        self.assertLess((outside ^ envelopes["side entry"]).volume(), 1e-14)

    def test_relieved_bore_accepts_six_case_maximum_tilt_at_zero_load(self):
        y = np.linspace(-1.5, 1.5, 1001)
        beta = np.radians(6.565)
        envelope = j.PIN / np.cos(beta) + np.abs(y) * np.tan(beta)
        self.assertGreater(np.min(j.hole_radius(y) - envelope), 0.010)
        self.assertLess(np.min(j.PIN + j.HOLE_CLEARANCE / 2 - envelope), -0.15)

    def test_spherical_face_and_rounded_rim_normals(self):
        rc, tan = j.thrust_rim()
        point = np.array([[0.59, 0, j.face_height(0.59)]])
        gap, n = shoulder_distance(point, 1)
        np.testing.assert_allclose(gap, 0.020, atol=1e-12)
        np.testing.assert_allclose(n, -point / np.linalg.norm(point), atol=1e-10)
        angle = -0.78
        direction = np.array([np.cos(angle), np.sin(angle)])
        surface = rc + j.THRUST_FILLET * direction
        for delta in (0.001, -0.001):
            p = surface + delta * direction
            g, n = shoulder_distance(np.array([[p[0], 0, p[1]]]), 1)
            np.testing.assert_allclose(g, delta, atol=1e-12)
            np.testing.assert_allclose(n[0, [0, 2]], direction, atol=1e-10)
        self.assertAlmostEqual(j.thrust_height(tan[0]), tan[1], places=10)

    def test_hex8_reproduces_affine_displacement_and_engineering_shear(self):
        x, q, *_ = make_mesh("middle", 2.7)
        xe = x[q[::100]]
        F = np.array(
            [[0.020, 0.003, -0.005], [0.009, -0.010, 0.007], [0.015, -0.008, 0.012]]
        )
        u = (xe @ F.T + [3.0, -2.0, 4.0]).reshape(len(xe), 24)
        for q in ((0.44, -0.30, 0.67), (-0.7, 0.6, -0.9)):
            B, det = strain_matrix(xe, np.array(q))
            e = np.einsum("eij,ej->ei", B, u)
            np.testing.assert_allclose(
                e,
                np.tile([0.020, -0.010, 0.012, 0.012, -0.001, 0.010], (len(e), 1)),
                atol=1e-12,
            )
            self.assertGreater(det.min(), 0)

    def test_feature_mesh_tracks_the_two_machined_recess_transitions(self):
        points, cells, *_ = make_mesh("fine", 2.7, fit_relief=True)
        line = points[(abs(points[:, 1]) < 1e-10) & (points[:, 0] > 0)]
        self.assertTrue(np.isclose(line[:, 0], j.PATCH).any())
        self.assertTrue(np.isclose(line[:, 0], j.BLEND).any())
        _, weights = strain_matrix(points[cells], np.zeros(3))
        self.assertGreater(weights.min(), 0.0)

    def test_cad_transfer_reproduces_patch_nodes(self):
        x, q, *_ = make_mesh("middle", 2.7)
        points = x[::13]
        sel, elem, w, err = local_transfer(
            points, {"x": x, "q": q}, "middle", 2.7, j.CROWN_RADIUS
        )
        self.assertTrue(sel.all())
        self.assertLess(err.max(), 1e-7)
        np.testing.assert_allclose(
            np.einsum("ij,ijk->ik", w, x[elem]), points, atol=1e-7
        )

    def test_rigid_station_fit_recovers_common_shift_and_rotation(self):
        a = np.radians(j.ANGLES)
        r = j.R_PIVOT * np.c_[np.cos(a), np.sin(a), np.zeros(4)]
        t = np.array([0.023, -0.008, 0.002])
        omega = np.array([0.0007, -0.0011, 0.0008])
        ret = rigid_fit(j.ANGLES, -t - np.cross(omega, r))
        np.testing.assert_allclose(ret["translation_xyz_mm"], t, atol=1e-10)
        np.testing.assert_allclose(ret["rotation_xyz_rad"], omega, atol=1e-10)
        self.assertLess(ret["maximum_incompatibility_mm"], 1e-10)


if __name__ == "__main__":
    unittest.main()
