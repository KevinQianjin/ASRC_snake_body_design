"""Regression checks for vertical pointing, cable-length bookkeeping and bounded surface reuse."""

import json
import gzip
from argparse import Namespace
import tempfile
import unittest
from pathlib import Path
import numpy as np

from pitch_cycle import plan
from pitch_reference import angle_between, angular_error, pitch_axes, target_axis
from perturb_poles import matched_commands
from replay import BASE, SHARED, Runner, controller_settings, plant
from shared_bore import DESIGN
from sliding import elastic_tensions
from sliding_turns import command_signs
from stations import movement_bound, to_station
from tension_report import NAMES
from transmission import turns


class CycleTests(unittest.TestCase):
    def test_vertical_coordinate_and_small_cross_plane_errors(self):
        for pitch in (-90, -88, 20, 88, 90, 90.1):
            axis = target_axis(pitch)
            np.testing.assert_allclose(pitch_axes(axis), [0, pitch], atol=1e-12)
            tilt = np.radians(0.12)
            perturbed = axis * np.cos(tilt) + np.array([0.0, 0.0, np.sin(tilt)])
            self.assertAlmostEqual(angle_between(perturbed, axis), 0.12)
            np.testing.assert_allclose(
                angular_error([0, pitch], pitch_axes(perturbed)), [-0.12, 0], atol=1e-10
            )
        self.assertAlmostEqual(
            angular_error([-179.9, 20], np.array([179.9, 20]))[0], 0.2
        )

    def test_turning_point_sliding_signs_use_neighbouring_command_change(self):
        rows = [
            dict(target_yaw_deg=0.0, target_elevation_deg=v)
            for v in [88.0, 90.0, 90.0, 88.0]
        ]
        rest = np.ones((4, 3, 4))
        rest[1:3, 0, 0] -= 0.0003
        rest[1:3, 0, 1] += 0.0002
        rest[1:3, 0, 2] += 0.0000005
        for side, k, expect in ((-1, 0, [-1, 1, 0, 0]), (1, 3, [1, -1, 0, 0])):
            neighbour, _, signs = command_signs(rest, rows, 2, side)
            self.assertEqual(neighbour, k)
            self.assertEqual(signs[:4].tolist(), expect)

    def test_twelve_distinct_physical_channels(self):
        self.assertEqual(
            NAMES,
            [
                a + "_" + ray
                for a in ["A", "B", "C"]
                for ray in ["up", "right", "down", "left"]
            ],
        )
        span = np.array([0.2, 0.1, 0.3])
        wrap = np.array([0.0, 0.44, 0.88])
        ea = 6000.0
        free = 1.0
        rest = 1.598
        for sign in (-1, 1):
            t, ts = elastic_tensions(span, wrap, 0.15, sign, rest, ea, free)
            self.assertAlmostEqual(
                free / (1 + t / ea) + np.sum(span / (1 + ts / ea)), rest, places=12
            )
            self.assertAlmostEqual(ts[-1] / t, np.exp(sign * 0.15 * 0.88))
        t, ts = elastic_tensions(span, wrap, 0.0, 1, rest, ea, free)
        np.testing.assert_allclose(ts, t)
        self.assertAlmostEqual(t, ea * (1.6 / rest - 1))
        softer = 0.8 * ea
        updated = matched_commands(rest, t, ea, softer)
        self.assertLess(updated, rest)
        self.assertAlmostEqual(softer * ((free + span.sum()) / updated - 1), t)
        self.assertAlmostEqual(
            turns(np.array([[0, 0, 0], [1, 0, 0], [1, 0, 0], [1, 1, 0]]))[1], np.pi / 2
        )

    def test_station_motion_bound_is_positive_symmetric_and_zero_for_identical(self):
        a = np.array([[0.1, 0.2, -0.1, 0.003], [0.05, 0.08, 0.0, -0.001]])
        b = a + 0.001
        self.assertEqual(movement_bound(a, a[None], 9.0, 34.0, 12.0)[0], 0.0)
        np.testing.assert_allclose(
            movement_bound(a, b[None], 9.0, 34.0, 12.0),
            movement_bound(b, a[None], 9.0, 34.0, 12.0),
        )
        self.assertGreater(movement_bound(a, b[None], 9.0, 34.0, 12.0)[0], 0.04)

    def test_station_bound_covers_points_on_both_sides_of_real_guide(self):
        rod = plant()[0].base
        with np.load(SHARED / "results/rebalanced_states.npz") as f:
            z = f["z"][64]
        rng = np.random.default_rng(53)
        module = 5
        st = -12
        # Perturb upstream cells too. Their rigid-body motion must cancel in the station frame.
        z1 = z + rod.scale * rng.normal(0.0, 0.0005, len(z))
        points = np.c_[
            rng.uniform(-19, 19, 60),
            rng.uniform(-18, 18, 60),
            st + rng.uniform(-8, 8, 60),
        ]
        distance = np.max(abs(points[:, 2] - st))
        radius = np.max(np.linalg.norm(points[:, :2], axis=1))
        node = module * rod.sub + round((st + 48) / (1000 * rod.l))
        strains = [(v / rod.scale).reshape(-1, 4)[node - 1 : node + 1] for v in (z, z1)]
        bound = movement_bound(
            strains[0], strains[1][None], distance, radius, 1000 * rod.l
        )[0]
        pos = [
            to_station(points, module, st, rod, rod.evaluate(v, detail=True)[2])
            for v in (z, z1)
        ]
        actual = np.max(np.linalg.norm(pos[1] - pos[0], axis=1))
        self.assertLessEqual(actual, bound + 1.0e-10)
        self.assertGreater(actual, 1.0e-3)

    def test_live_continuation_matches_uninterrupted_yaw_to_withdrawal(self):
        source = Path(__file__).parent / "results"
        with gzip.open(source / "controller_records.json.gz", "rt") as f:
            rows = json.load(f)
        cut = next(i for i, r in enumerate(rows) if r["phase"] == "exit") - 1
        prev = rows[cut - 1]
        with np.load(source / "controller_states.npz") as f:
            z = f["settled_z"]
            rest = f["settled_rest_m"]
        args = Namespace(
            ref=BASE / "reference",
            gains=BASE / "closed_loop/nominal_gains.npz",
            limit=cut + 2,
        )
        controller_settings(args)
        model = Runner("nominal", args, rod=plant()[0])
        continued = []

        def capture(i, row, pose, applied, runner):
            continued.append(i)
            np.testing.assert_allclose(pose, z[i], atol=2.0e-9, rtol=0)
            np.testing.assert_allclose(applied, rest[i], atol=2.0e-11, rtol=0)
            np.testing.assert_allclose(
                row["tensions_n"], rows[i]["tensions_n"], atol=5.0e-7, rtol=0
            )

        model.run(
            capture,
            continuation=dict(
                start_index=cut,
                z=z[cut - 1],
                rest_m=rest[cut - 1],
                clamp_s_mm=prev["clamp_s_mm"],
                target=np.array([prev["target_yaw_deg"], prev["target_elevation_deg"]]),
                offset_mm=np.array(prev["offset_mm"]),
                correction_scale=prev["correction_scale"],
                phase=prev["phase"],
            ),
        )
        self.assertEqual(continued, [cut, cut + 1])

    def test_reference_inserts_both_round_trips_before_original_exit(self):
        prefix = Path(__file__).parent / "results/pitch_reference_minimum_tension"
        source = json.loads((BASE / "reference/nominal.json").read_text())
        with tempfile.TemporaryDirectory() as t:
            ref, target, split, _, attempts = plan(prefix, Path(t))
            self.assertEqual(len(ref), len(source) + 180)
            self.assertEqual(
                split, next(i for i, r in enumerate(source) if r["phase"] == "exit")
            )
            self.assertEqual(ref[split - 1]["phase"], "left_return")
            self.assertTrue(all(x["preflight_reached_target"] for x in attempts))
            self.assertEqual(ref[split + 180]["phase"], "exit")
            self.assertEqual(
                [target[split + j - 1, 1] for j in (35, 70, 125, 180)],
                [90.0, 20.0, -90.0, 20.0],
            )
            np.testing.assert_allclose(
                np.abs(np.diff(target[split - 1 : split + 180, 1])), 2.0
            )

    def test_rod_refinement_preserves_guide_mass_payload_and_lanes(self):
        rays = json.loads((DESIGN / "design.json").read_text())["rays_cad_xy"]
        directions = np.array([rays[ray] for ray in ("up", "right", "down", "left")])
        lane_radii = np.array([21, 24, 28])
        for sub in (8, 16):
            rod, mass = plant(cells=sub)
            self.assertAlmostEqual(rod.payload, 0.5)
            self.assertEqual(rod.sub, sub)
            self.assertAlmostEqual(mass["M5_net_added_g"], 2.197166, places=5)
            cad_xy_mm = 1000 * np.stack(
                (-rod.offsets3[:, :, 2], rod.offsets3[:, :, 1]), axis=-1
            )
            np.testing.assert_allclose(
                cad_xy_mm, lane_radii[:, None, None] * directions, atol=1e-12
            )

        nominal, _ = plant()
        stiff, _ = plant(variant="niti18_E75")
        np.testing.assert_allclose(nominal.mass, stiff.mass, atol=1.0e-12)
        np.testing.assert_allclose(
            nominal.planar.module_EI[:4], stiff.planar.module_EI[:4], atol=1.0e-12
        )
        self.assertTrue(
            np.all(stiff.planar.module_EI[4:] > nominal.planar.module_EI[4:])
        )


if __name__ == "__main__":
    unittest.main()
