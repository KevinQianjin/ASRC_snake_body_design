"""Regression checks for the cross-study component limit sweep."""

import csv
import tempfile
import unittest
from pathlib import Path

import design_limit_sweep as sweep


class DesignLimitSweepTest(unittest.TestCase):
    def test_crossing_bracket_includes_the_neutral_seed(self):
        before, after, value = sweep.first_crossing(
            [
                {"yaw": 0, "stress": 180.0},
                {"yaw": -30, "stress": 210.0},
            ],
            ("stress",),
            205.0,
        )
        self.assertEqual(before["yaw"], 0)
        self.assertEqual(after["yaw"], -30)
        self.assertEqual(value, 210.0)

    def test_component_sweep_keeps_unmeasured_resistance_unrated(self):
        rows = sweep.stress_component_rows()
        self.assertEqual(len(rows), 32)  # eight demand channels × four load factors
        self.assertTrue(all("UNRATED" in row["rating_status"] for row in rows))
        self.assertTrue(all(row["measured_lower_bound_resistance"] == "" for row in rows))

    def test_outputs_cover_all_archived_fatigue_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = sweep.run(Path(folder))
            with (Path(folder) / "fatigue_demand.csv").open() as stream:
                fatigue = list(csv.DictReader(stream))
            self.assertEqual(len(fatigue), 46)
            self.assertEqual(summary["fatigue"]["physical_life_missions"], None)
            self.assertEqual(len(summary["files"]), 6)


if __name__ == "__main__":
    unittest.main()
