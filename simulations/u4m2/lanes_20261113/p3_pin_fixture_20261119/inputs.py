"""Published P3 orientation, load vector and bench coordinate system."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent / "m5_seat_bench_20261119"
sys.path.insert(0, str(BENCH))
from bench_inputs import CAD as CAD, load_targets
from bench_cad import j as joint

__all__ = ["HERE", "BENCH", "CAD", "joint", "p3_input"]


def p3_input():
    land, force, rotation = load_targets()["P3"]
    return land, force, rotation
