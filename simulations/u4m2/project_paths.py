"""Shared repository paths for the active U4+M2 studies."""
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
SHARED = REPOSITORY / 'simulations' / 'shared'
KERNEL_PATH = SHARED / 'h8u12_front5to8_payload500g' / 'rope_planar.py'
STIFFNESS_DATABASE = REPOSITORY / 'data' / 'materials' / 'module_stiffness.sqlite3'
TANK_STEP = REPOSITORY / 'cad' / 'tank' / 'tank-v2.step'
ROPE_CATALOGUE = SHARED / 'h8u12_front5to8_payload500g' / 'inputs' / 'rope_materials.json'
