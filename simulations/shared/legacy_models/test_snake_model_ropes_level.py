"""Mechanical and history checks for inverse tendon control."""
import copy
import unittest

import numpy as np

from snake_model_ropes import Control, HERE, RopeRobot, read_json
from snake_model_ropes_level import LevelInverse, TensionControl, TensionRobot, TrialFailure
from snake_model_ropes_hold_horizontal import hold_during_loading


class LevelInverseTests(unittest.TestCase):
    def setUp(self):
        cfg = read_json(HERE/"rope_config.json")
        cfg["stack"] = "4*high"
        cfg["solver"]["axial_compliance"] = True
        catalog = {m["id"]:m for m in read_json((HERE.parents[2] / 'data' / 'materials' / 'rope_materials.json'))["materials"]}
        material, rope = catalog["ss304_annealed"], catalog["nylon_pa6_reference"]
        self.robot = RopeRobot(cfg, material, rope)
        self.force = TensionRobot(cfg, material, rope)
        self.settings = read_json(HERE/"rope_config_level.json")
        self.settings["target"]["tolerance_mm"] = .001
        self.settings["search"]["max_iterations"] = 20
        self.settings["search"]["minimum_improvement_mm"] = .00001
        self.initial = self.robot.advance(self.robot.virgin_state(),
                                          Control(np.zeros(4), 1., .05))

    def test_force_inverse_lengths_reproduce_requested_tensions(self):
        target = TensionControl(np.array([5., 1., 0., 1.]), 1., .05)
        state = self.force.advance(self.force.virgin_state(), target)
        fixed = self.force.equivalent_length_state(state)
        geo = self.robot.geometry(fixed.x)
        actual = self.robot.rope_response(geo, fixed.control)["tension"]
        np.testing.assert_allclose(actual, target.tension_n, atol=1e-9)
        _, gradient = self.robot.energy_gradient(fixed.x, fixed.plastic_strain, fixed.control)
        moment, force = self.robot.residuals(gradient)
        self.assertLess(moment, self.robot.moment_tolerance)
        self.assertLess(force, self.robot.force_tolerance)

    def test_reachable_level_target_is_forward_verified(self):
        controller = LevelInverse(self.robot, self.force, self.settings)
        result = controller.solve(self.initial)
        s = result["summary"]
        self.assertTrue(s["target_reached"], s)
        self.assertLess(abs(s["tip_y_mm"]), .001)
        self.assertGreaterEqual(s["forward_ratio"], .9)
        self.assertGreater(s["take_up_top_mm"], 0)
        self.assertEqual(s["status"], "target_reached_within_screening")

    def test_folded_tip_at_root_height_is_not_reported_as_horizontal_success(self):
        controller = LevelInverse(self.robot, self.force, self.settings)
        folded = self.robot.virgin_state()
        folded.x[0] = np.pi
        tip = self.robot.geometry(folded.x)["pts"][-1]
        self.assertLess(abs(tip[1]), 1e-10)
        self.assertLess(tip[0], 0)
        self.assertFalse(controller.reached(folded))

    def test_rejected_trial_does_not_commit_plastic_history(self):
        settings = copy.deepcopy(self.settings)
        settings["search"]["max_take_up_mm"] = .000001
        controller = LevelInverse(self.robot, self.force, settings)
        x = self.initial.x.copy()
        ep = self.initial.plastic_strain.copy()
        acc = self.initial.accumulated_plastic_strain.copy()
        steps = self.initial.accepted_steps
        with self.assertRaises(TrialFailure):
            controller.trial(self.initial, np.array([20., 0., 0.]))
        np.testing.assert_array_equal(x, self.initial.x)
        np.testing.assert_array_equal(ep, self.initial.plastic_strain)
        np.testing.assert_array_equal(acc, self.initial.accumulated_plastic_strain)
        self.assertEqual(steps, self.initial.accepted_steps)

    def test_tip_at_root_height_does_not_imply_horizontal_shape(self):
        bent = self.robot.virgin_state()
        bent.x.reshape(self.robot.n, self.robot.width)[:3, 0] = [.1, -.2, .1]
        controller = LevelInverse(self.robot, self.force, self.settings)
        self.assertTrue(controller.reached(bent))
        settings = copy.deepcopy(self.settings)
        settings["target"].update(mode="horizontal_shape", tolerance_mm=1.,
                                   angle_tolerance_deg=1., angle_weight_mm=48.)
        horizontal = LevelInverse(self.robot, self.force, settings)
        self.assertFalse(horizontal.reached(bent))
        self.assertTrue(horizontal.reached(self.robot.virgin_state()))
        # Even with a loose centerline band, the direction condition is separate.
        settings["target"]["tolerance_mm"] = 10.
        self.assertFalse(LevelInverse(self.robot, self.force, settings).reached(bent))

    def test_three_dimensional_target_reproduces_a_reachable_forward_case(self):
        known = self.robot.advance(self.initial, Control(np.array([.3, .15, -.15, -.1]), 1., .05))
        target = self.robot.geometry(known.x)["pts"][-1]*1000
        settings = copy.deepcopy(self.settings)
        settings["target"].update(mode="tip_position", tip_x_mm=float(target[0]),
                                   tip_y_mm=float(target[1]), tip_z_mm=float(target[2]))
        settings["search"]["balanced_sides"] = False
        result = LevelInverse(self.robot, self.force, settings).solve(self.initial)
        self.assertTrue(result["summary"]["target_reached"], result["summary"])
        actual = np.array([result["summary"][f"tip_{axis}_mm"] for axis in "xyz"])
        self.assertLess(np.linalg.norm(actual-target), settings["target"]["tolerance_mm"])

    def test_slack_tendon_is_probed_past_its_zero_response_interval(self):
        start = self.robot.advance(self.initial, Control(np.array([0., -.4, 0., -.4]), 1., .05))
        known = self.robot.advance(start, Control(np.array([.1, .2, -.1, -.4]), 1., .05))
        target = self.robot.geometry(known.x)["pts"][-1]*1000
        settings = copy.deepcopy(self.settings)
        settings["target"].update(mode="tip_position", tip_x_mm=float(target[0]),
                                   tip_y_mm=float(target[1]), tip_z_mm=float(target[2]))
        settings["search"]["balanced_sides"] = False
        result = LevelInverse(self.robot, self.force, settings).solve(start)
        self.assertTrue(result["summary"]["target_reached"], result["summary"])

    def test_progressive_loading_holds_a_reachable_requested_payload(self):
        loads = dict(scenario_name="test_hold", gravity_steps=2, payload_steps=2,
                     payload_kg=.05, max_iterations_per_load=20, max_trials_per_load=120)
        result = hold_during_loading(self.robot, self.force, self.settings, loads)
        self.assertTrue(result["summary"]["completed_requested_loading"], result["summary"])
        self.assertTrue(result["summary"]["target_reached"])
        self.assertAlmostEqual(result["summary"]["payload_kg"], .05)
        self.assertAlmostEqual(result["summary"]["last_level_gravity_scale"], 1.)
        self.assertTrue(all(row["target_reached"] for row in result["loads"]))

    def test_partial_loading_is_never_reported_as_requested_load_success(self):
        settings = copy.deepcopy(self.settings)
        settings["target"]["tolerance_mm"] = 1e-9
        loads = dict(scenario_name="test_partial", gravity_steps=2, payload_steps=2,
                     payload_kg=.5, max_iterations_per_load=1, max_trials_per_load=1)
        result = hold_during_loading(self.robot, self.force, settings, loads)
        self.assertFalse(result["summary"]["completed_requested_loading"])
        self.assertFalse(result["summary"]["target_reached"])
        self.assertFalse(result["summary"]["requested_load_applied"])
        self.assertEqual(result["summary"]["requested_payload_kg"], .5)


if __name__ == "__main__":
    unittest.main()
