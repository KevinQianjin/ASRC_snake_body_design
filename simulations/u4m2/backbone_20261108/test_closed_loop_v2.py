import unittest, types
import numpy as np
from closed_loop_v2 import qp, Runner


class V2Tests(unittest.TestCase):
    def test_qp_enforces_operating_tension_and_bounds(self):
        # Two angle outputs, 12 tensions that rise 1 N per mm of pay-in on their own rope.
        A = np.zeros((2, 12)); A[0, 0] = 2; A[1, 1] = 2
        C = np.eye(12)
        T = np.full(12, 3.5); T[4] = 2.6; T[7] = 2.9  # two ropes below the 3 N target, reachable within 0.5 mm
        off = np.zeros(12); off[0] = 4.9
        x, ok = qp(A, C, T, np.array([5., -5.]), off, 3., .5)
        self.assertTrue(ok)
        self.assertLessEqual(np.abs(x).max(), .5 + 1e-9)
        self.assertLessEqual(np.abs(off + x).max(), 5 + 1e-9)
        self.assertTrue(np.all(T + C @ x >= 3. - 1e-7))

    def test_qp_reports_infeasible_tension_target(self):
        # 0.8 N deficit with 1 N/mm gain cannot be met within a 0.5 mm step: reported, and the step stays bounded.
        A = np.zeros((2, 12)); C = np.eye(12); T = np.full(12, 3.5); T[4] = 2.2
        x, ok = qp(A, C, T, np.zeros(2), np.zeros(12), 3., .5)
        self.assertFalse(ok)
        self.assertLessEqual(np.abs(x).max(), .5 + 1e-9)

    def test_qp_precompensation_leaves_angles_alone_when_possible(self):
        # Rope 3 affects only tension; the arrival pre-correction should use it and not disturb the angles.
        A = np.zeros((2, 12)); A[0, 0] = 1; A[1, 1] = 1
        C = np.zeros((12, 12)); C[3, 3] = 2.
        T = np.full(12, 4.); T[3] = 2.5
        x, ok = qp(A, C, T, np.zeros(2), np.zeros(12), 3., .5)
        self.assertTrue(ok)
        self.assertGreaterEqual(T[3] + 2 * x[3], 3. - 1e-7)
        self.assertLess(np.abs(A @ x).max(), 1e-6)

    def test_transition_subdivides_until_node_motion_is_small(self):
        # Fake plant: the state is the command; node positions move 10 mm per mm of command.
        r = Runner.__new__(Runner)
        r.a = types.SimpleNamespace(node_step=4.5, max_depth=8, rope_step=.25, mid_tol=None, mid_max=4)
        r.trace = []; r.last_points = np.zeros((3, 3)); r.max_move = 0.; r.case = 'fake'; r.n_mid = 0
        r.trace_states = []; r.trace_rest = []
        r.d = types.SimpleNamespace(solve=lambda z, R: np.array(R, float))
        def check(z, R, s, target, kind, index, phase):
            P = np.full((3, 3), float(np.max(R)) * 1000 * 10.)
            move = float(np.linalg.norm(P - r.last_points, axis=1).max())
            return dict(node_move_mm=move, kind=kind), P
        r.check = check
        z = r.transition(np.zeros((3, 4)), np.zeros((3, 4)), 0., [0, 20], np.full((3, 4), .002), 0., [10, 20], 'feedforward', 0, 'test')
        self.assertAlmostEqual(float(np.max(z)), .002)
        moves = [t['node_move_mm'] for t in r.trace]
        self.assertTrue(len(moves) >= 8)
        self.assertLessEqual(max(moves), 4.5 + 1e-9)
        self.assertTrue(np.allclose(r.offset_extra, 0))
        self.assertEqual(len(r.trace), len(r.trace_states))
        self.assertEqual(len(r.trace), len(r.trace_rest))
        np.testing.assert_allclose(r.trace_states, r.trace_rest)
        self.assertTrue(all(np.max(b) > np.max(a) for a, b in zip(r.trace_rest, r.trace_rest[1:])))
        saved = r.trace_states[-1].copy()
        z[:] = -1
        np.testing.assert_array_equal(r.trace_states[-1], saved)


if __name__ == '__main__':
    unittest.main()
