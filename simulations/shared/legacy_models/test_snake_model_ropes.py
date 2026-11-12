"""Mechanical invariants and regression checks for the independent extension."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

import snake_model as legacy
from snake_model_ropes import (Control, HERE, RopeRobot, bend_rotation,
                               circular_fibers, database_materials,
                               open_database, original_hashes, read_json)


class RopeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes = original_hashes()
        cls.seed = read_json((HERE.parents[2] / 'data' / 'materials' / 'rope_materials.json'))
        cls.catalog = {m["id"]: m for m in cls.seed["materials"]}

    @classmethod
    def tearDownClass(cls):
        if original_hashes() != cls.hashes:
            raise AssertionError("original files were modified")

    def robot(self, material="ss304_annealed", *, stack="2*high", axial=True, ropes=True):
        config = read_json(HERE/"rope_config.json")
        config["stack"] = stack
        config["solver"]["axial_compliance"] = axial
        return RopeRobot(config, self.catalog[material] if material else None,
                         self.catalog["nylon_pa6_reference"], include_ropes=ropes)

    def test_section_area_and_second_moments(self):
        d = .0042
        uv, w = circular_fibers(d)
        self.assertAlmostEqual(w.sum(), np.pi*d*d/4, places=16)
        np.testing.assert_allclose((uv*w[:, None]).sum(axis=0), 0, atol=1e-20)
        np.testing.assert_allclose((uv**2*w[:, None]).sum(axis=0), np.pi*d**4/64, rtol=1e-13)
        self.assertAlmostEqual(float(np.sum(uv[:, 0]*uv[:, 1]*w)), 0, places=22)

    def test_rotation_derivatives_and_orthogonality(self):
        for q in ([0, 0], [.17, -.21], [1e-5, 2e-5]):
            r, derivatives = bend_rotation(*q)
            np.testing.assert_allclose(r.T@r, np.eye(3), atol=1e-14)
            self.assertAlmostEqual(np.linalg.det(r), 1, places=13)
            for i in range(2):
                dq = np.zeros(2); dq[i] = 1e-6
                numerical = (bend_rotation(*(q+dq))[0]-bend_rotation(*(q-dq))[0])/(2e-6)
                np.testing.assert_allclose(derivatives[i], numerical, atol=1e-9)

    def test_full_energy_gradient_including_plastic_fibers_and_rope_geometry(self):
        robot = self.robot("cu110_o60")
        x = np.array([[.022, .013, -.012], [.017, -.008, -.015]]).ravel()
        control = Control(np.array([2., 1., -1., -.5]), .7, .02)
        state = robot.virgin_state()
        _, grad = robot.energy_gradient(x, state.plastic_strain, control)
        numerical = np.empty_like(grad)
        for i in range(len(x)):
            dx = np.zeros_like(x); dx[i] = 1e-6
            numerical[i] = (robot.energy_gradient(x+dx, state.plastic_strain, control)[0] -
                            robot.energy_gradient(x-dx, state.plastic_strain, control)[0])/(2e-6)
        np.testing.assert_allclose(grad, numerical, rtol=2e-5, atol=2e-7)
        np.testing.assert_array_equal(state.plastic_strain, 0)

    def test_backbone_small_bend_recovers_ei(self):
        robot = self.robot("al1100_o", stack="high")
        x = np.array([1e-4, -2e-4, 0.])
        fibers = robot.fiber_response(x, robot.virgin_state().plastic_strain)
        expected = robot.core_e*robot.backbone_i*x[:2]/robot.length[0]
        np.testing.assert_allclose(fibers["angle_gradient"][0], expected, rtol=1e-12)
        self.assertLess(np.abs(fibers["plastic"]).max(), 1e-18)

    def test_rope_is_tension_only_and_pretension_is_correct(self):
        robot = self.robot()
        geo = robot.geometry(np.zeros(robot.ndof))
        slack = robot.rope_response(geo, Control(np.full(4, -1.)))
        np.testing.assert_array_equal(slack["tension"], 0)
        self.assertEqual(slack["energy"], 0)
        robot.pretension[:] = [1, 2, 3, 4]
        robot.initial_rope_lengths = robot.reference_length/(1+robot.pretension/robot.rope_ea)
        taut = robot.rope_response(geo, Control(np.zeros(4)))
        np.testing.assert_allclose(taut["tension"], robot.pretension, atol=1e-10)
        free = robot.rope_response(geo, Control(np.zeros(4), engagement=0))
        np.testing.assert_array_equal(free["tension"], 0)

    def test_equal_four_rope_takeup_only_compresses_centerline(self):
        robot = self.robot()
        state = robot.advance(robot.virgin_state(), Control(np.full(4, .1)))
        q, strain = robot.angles_and_strain(state.x)
        np.testing.assert_allclose(q, 0, atol=1e-9)
        self.assertTrue((strain < 0).all())
        geo = robot.geometry(state.x)
        tension = robot.rope_response(geo, state.control)["tension"]
        np.testing.assert_allclose(tension, tension[0], rtol=1e-9)
        # Module and backbone carry the sum of all four rope tensions.
        force = -(robot.ea+robot.core_e*robot.backbone_area)*strain
        np.testing.assert_allclose(force, tension.sum(), atol=.001)

    def test_opposing_tendon_commands_mirror_and_two_planes_are_active(self):
        robot = self.robot(axial=False)
        plus = robot.advance(robot.virgin_state(), Control(np.array([.3, 0, -.3, 0])))
        minus = robot.advance(robot.virgin_state(), Control(np.array([-.3, 0, .3, 0])))
        p = robot.geometry(plus.x)["pts"][-1]
        m = robot.geometry(minus.x)["pts"][-1]
        self.assertGreater(p[1], 0)
        np.testing.assert_allclose(p, m*np.array([1, -1, 1]), atol=1e-7)
        both = robot.advance(robot.virgin_state(), Control(np.array([.3, .3, -.3, -.3])))
        tip = robot.geometry(both.x)["pts"][-1]
        self.assertGreater(tip[2], 0)
        self.assertAlmostEqual(tip[1], tip[2], places=7)

    def test_modules_only_planar_solution_matches_original(self):
        robot = self.robot(None, stack="3*high", axial=False, ropes=False)
        state = robot.virgin_state()
        for scale in np.linspace(.05, 1, 20):
            state = robot.advance(state, Control(np.zeros(4), float(scale)))
        old = legacy.solve(legacy.build_chain("3*high", carrier_len=0))
        pts = robot.geometry(state.x)["pts"]
        np.testing.assert_allclose(pts[:, :2], old["pts"], atol=1e-7)
        np.testing.assert_allclose(pts[:, 2], 0, atol=1e-9)

    def test_tip_payload_force_and_attachment_node(self):
        robot = self.robot(stack="high", axial=False, ropes=False)
        robot.mass[:] = 0  # Isolate the point load from all distributed weight.
        state = robot.advance(robot.virgin_state(), Control(np.zeros(4), 1., .5, 0.))
        q, _ = robot.angles_and_strain(state.x)
        theta = q[0, 0]
        stiffness = (robot.ei_pos[0]+robot.core_e*robot.backbone_i)/robot.length[0]
        # Independent one-link equilibrium: spring moment + tip-force moment.
        self.assertAlmostEqual(stiffness*theta + .5*9.81*robot.length[0]*np.cos(theta), 0, places=7)
        self.assertLess(theta, 0)
        result = robot.result(state, "tip_payload_500g")["summary"]
        self.assertEqual(result["payload_node"], 1)
        self.assertEqual(result["payload_kg"], .5)
        self.assertAlmostEqual(result["payload_force_n"], 4.905)
        self.assertIsNone(result["residual_tip_mm"])
        robot.payload_node = 0
        base_load = robot.advance(robot.virgin_state(), Control(np.zeros(4), 1., .5, 0.))
        np.testing.assert_allclose(base_load.x, 0, atol=1e-10)

    def test_plastic_backbone_leaves_residual_after_complete_external_unload(self):
        robot = self.robot("al1100_o", stack="high")
        results = robot.run([
            dict(name="pull", take_up_mm=[1., 0, -1., 0], gravity_scale=0, steps=12),
            dict(name="release", take_up_mm=[0]*4, gravity_scale=0, free_spool=True, steps=12)])
        pulled, released = [r["summary"] for r in results]
        self.assertGreater(pulled["plastic_module_count"], 0)
        self.assertIsNone(pulled["residual_tip_mm"])
        self.assertEqual(pulled["take_up_top_mm"], 1.)
        self.assertEqual(pulled["take_up_bottom_mm"], -1.)
        self.assertGreater(released["transverse_tip_mm"], .01)
        self.assertEqual(released["residual_tip_mm"], released["transverse_tip_mm"])
        self.assertIsNone(released["take_up_top_mm"])
        self.assertLess(released["transverse_tip_mm"], pulled["transverse_tip_mm"])
        self.assertGreater(released["dissipated_energy_j"], 0)
        np.testing.assert_array_equal(results[-1]["rope_tension_n"], 0)
        gravity_loaded = robot.advance(robot.virgin_state(), Control(np.zeros(4), 1., engagement=0))
        self.assertIsNone(robot.result(gravity_loaded, "free_spool_with_gravity")["summary"]["residual_tip_mm"])

    def test_database_can_be_reseeded_without_losing_sources_or_runs(self):
        with tempfile.TemporaryDirectory(prefix="asrc-rope-test-") as tmp:
            path = Path(tmp)/"materials.sqlite3"
            con = open_database(path, self.seed)
            self.assertEqual(len(database_materials(con)), 4)
            con.execute("INSERT INTO runs(created_utc,config_json,catalog_json,original_sha256_json) VALUES(?,?,?,?)",
                        ("test", "{}", "{}", "{}"))
            con.commit()
            con.close()
            con = open_database(path, self.seed)
            self.assertEqual(con.execute("SELECT count(*) FROM property_sources").fetchone()[0], 11)
            self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            con.close()

    def test_invalid_guide_radius_is_rejected(self):
        config = read_json(HERE/"rope_config.json")
        config["ropes"]["routing_radius_mm"] = 16
        with self.assertRaisesRegex(ValueError, "exceeds module radius"):
            RopeRobot(config, self.catalog["al1100_o"], self.catalog["nylon_pa6_reference"])


if __name__ == "__main__":
    unittest.main()
