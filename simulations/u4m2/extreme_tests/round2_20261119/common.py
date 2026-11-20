"""Inputs and deterministic, portable outputs for the second 500 g extreme-test round."""

import csv
import gzip
import io
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
LANES = HERE.parents[1] / "lanes_20261113"
ROOT = LANES.parents[2]
OUT = HERE / "results"
ROUND1 = HERE.parent / "round1_20261119"
for folder in (ROUND1, LANES / "evening_20261119", LANES / "cycle_closeout_20261119"):
    sys.path.insert(0, str(folder))
from study_inputs import CAD, SOURCE, NAMES, load_motion, read_csv, save as save_json  # noqa: E402,F401

BASE = "d0938c309db9da552ebfeeaac07fc8b5da1693c3"
R1 = ROUND1 / "results"
EV = LANES / "evening_20261119/results"
CANDIDATE = CAD / "m6_bond_gap_20261119"


def input_file(root, group, name):
    """Read the grouped result first, falling back to an older flat output directory."""
    current = root / group / name
    legacy = root / name
    if not current.exists() and legacy.is_file():
        return legacy
    return current


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".partial")
    save_json(pending, data)
    pending.replace(path)


def write_table(path, rows):
    """Use deterministic gzip and no machine path in the gzip header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = iter(rows)
    first = next(rows)
    pending = path.with_suffix(path.suffix + ".partial")
    with pending.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="ascii", newline="") as stream:
                writer = csv.DictWriter(stream, list(first), lineterminator="\n")
                writer.writeheader()
                writer.writerow(first)
                writer.writerows(rows)
    pending.replace(path)


def trajectory():
    with np.load(SOURCE / "controller_states.npz") as f:
        return tuple(f[k] for k in ("motion_z", "motion_rest_m", "motion_tensions_N"))


def motion_rows():
    return read_csv(SOURCE / "rope_tensions_every_step.csv.gz")


def station_wrenches(module, station):
    with np.load(SOURCE / "guide_hole_loads.npz") as f:
        ids = (f["module"] == module) & (f["station_mm"] == station)
        return f["local_wrench_CAD"][:, ids].sum(axis=1).reshape(-1, 6)
