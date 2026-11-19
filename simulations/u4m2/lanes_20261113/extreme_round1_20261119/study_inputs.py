"""Shared inputs for the 500 g motion-step screens. All step IDs refer to the motion archive."""

import csv
import gzip
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
LANES = HERE.parent
CYCLE = LANES / "cycle_closeout_20261119"
SOURCE = CYCLE / "results/yaw_pitch"
ROOT = LANES.parents[2]
CAD = ROOT / "cad/lanes_u4m2"
sys.path.insert(0, str(CYCLE))
from replay import plant  # noqa: E402
from tension_report import NAMES as NAMES  # noqa: E402

RAYS = ("up", "right", "down", "left")
EVENTS = (1710, 1843, 2059, 2348, 2432)


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def save(path, data):
    def arrays(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value).__name__)

    path.write_text(json.dumps(data, default=arrays, indent=2, allow_nan=False) + "\n")


def load_motion():
    with np.load(SOURCE / "controller_states.npz") as records:
        states = records["motion_z"]
        tensions = records["motion_tensions_N"]
    rod = plant()[0].base
    assert rod.payload == 0.5 and rod.sub == 8 and len(states) == len(tensions)
    return rod, states, tensions
