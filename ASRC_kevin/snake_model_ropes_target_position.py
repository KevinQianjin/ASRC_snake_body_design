"""Inverse winch control for an XYZ endpoint target, preserving old simulations.

Example: python snake_model_ropes_target_position.py --target-mm 1400 0 50
Coordinates are millimetres in the fixed base frame (X forward, Y up, Z lateral).
"""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from snake_model_ropes_level import main


if __name__ == "__main__":
    raise SystemExit(main(["--config", str(Path(__file__).with_name("rope_config_target_position.json")),
                           *sys.argv[1:]]))
