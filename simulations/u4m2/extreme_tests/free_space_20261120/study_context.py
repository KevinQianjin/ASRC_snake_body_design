"""Shared repository inputs for the free-space and repeat-duty study."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "round2_20261119"))
from common import (  # noqa: E402, F401
    CAD,
    CANDIDATE,
    NAMES,
    OUT as ROUND2,
    SOURCE,
    motion_rows,
    read,
    read_csv,
    save,
    trajectory,
    write_table,
)

RESULTS = HERE / "results"
REVISION = "bbed30bde93a03fc8d7135533bc2b4c7fac02eec"
MODULES = ("U1", "U2", "U3", "U4", "M5", "M6")
