"""Unit tests for active-reset wrench archive validation and shape alignment."""

import unittest
import numpy as np

from active_reset_pin_inputs import active_m5_candidates, capture_active_reset_inputs, validate_complete_replay


def fixture():
    tags = []
    for station in (-12, 12):
        for family in ("B", "C"):
            for ray in ("up", "right", "down", "left"):
                tags.append(("M5", station, family, ray))
    rows = [
        dict(substep=0, step=1843, phase="mission", kind="initial", fraction=1.0),
        dict(substep=1, step=1843, phase="mission", kind="ramp", fraction=0.5),
    ]
    states = np.vstack((np.zeros(6), np.ones(6)))
    distal = np.zeros((2, 3, 4))
    distal[0] = 1.0
    distal[1] = 2.0
    wrench = np.zeros((2, len(tags), 2, 3))
    wrench[:, :, 0, 0] = 1.0
    return rows, states, distal, tags, wrench


class ActiveResetPinInputs(unittest.TestCase):
    def test_archive_has_aligned_non_object_arrays_and_expected_station_loads(self):
        arrays = capture_active_reset_inputs(*fixture())
        self.assertEqual(arrays["state"].shape, (2, 6))
        self.assertEqual(arrays["distal_tensions_N"].shape, (2, 3, 4))
        self.assertEqual(arrays["hole_wrench_CAD"].shape, (2, 16, 2, 3))
        self.assertTrue(all(value.dtype.kind != "O" for value in arrays.values()))
        self.assertEqual(arrays["archive_step"].tolist(), [1843, 1843])
        for station in (-12, 12):
            ids = (arrays["hole_module"] == "M5") & (arrays["hole_station_mm"] == station)
            self.assertEqual(int(ids.sum()), 8)
            np.testing.assert_array_equal(arrays["hole_wrench_CAD"][:, ids, 0, 0].sum(axis=1), [8, 8])

    def test_candidates_include_force_moment_and_single_hole_peaks(self):
        rows, states, distal, tags, wrench = fixture()
        rows.append(dict(substep=2, step=1844, phase="mission", kind="ramp", fraction=0.5))
        states = np.vstack((states, np.full(6, 2.0)))
        distal = np.concatenate((distal, np.full((1, 3, 4), 3.0)))
        wrench = np.concatenate((wrench, wrench[:1].copy()))
        wrench[1, 8, 0, 0] = 8.0
        wrench[2, 0, 1, 1] = 15.0
        arrays = capture_active_reset_inputs(rows, states, distal, tags, wrench)
        candidates = active_m5_candidates(arrays)
        reasons = {row["index"]: {v["reason"] for v in row["criteria"]} for row in candidates}
        self.assertIn("station_force_peak", reasons[1])
        self.assertIn("individual_hole_force_peak", reasons[1])
        self.assertIn("station_moment_peak", reasons[2])
        self.assertIn("station_force_peak", reasons[0])
    def test_rejects_missing_hole_ray_or_station_data(self):
        rows, states, distal, tags, wrench = fixture()
        with self.assertRaisesRegex(ValueError, "M5 station"):
            capture_active_reset_inputs(rows, states, distal, tags[:-1], wrench[:, :-1])

    def test_rejects_state_load_shape_mismatch(self):
        rows, states, distal, tags, wrench = fixture()
        with self.assertRaisesRegex(ValueError, "one first-axis entry"):
            capture_active_reset_inputs(rows, states[:1], distal, tags, wrench)

    def test_requires_complete_replay_before_screening(self):
        complete = dict(
            expected_substeps=2,
            stopped_at=None,
            all_substeps=dict(states=2),
        )
        validate_complete_replay(complete, csv_row_count=2, input_state_count=2)
        with self.assertRaisesRegex(RuntimeError, "stopped early"):
            validate_complete_replay(
                dict(complete, stopped_at=dict(substep=1)),
                csv_row_count=1,
                input_state_count=1,
            )
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            validate_complete_replay(
                dict(expected_substeps=2, stopped_at=None, all_substeps=dict(states=1)),
                csv_row_count=1,
                input_state_count=1,
            )
        with self.assertRaisesRegex(RuntimeError, "misaligned"):
            validate_complete_replay(complete, csv_row_count=2, input_state_count=1)


if __name__ == "__main__":
    unittest.main()


