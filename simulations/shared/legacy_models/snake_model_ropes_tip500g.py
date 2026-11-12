"""Run the separate D / 31-module / tip +500 g scenario.

Existing no-payload configuration and output files are preserved.
Supports the same optional command-line arguments as snake_model_ropes.py.
"""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from snake_model_ropes import main


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    raise SystemExit(main([
        "--config", str(directory/"rope_config_tip500g.json"),
        "--output-dir", str(directory/"rope_results_tip500g"),
        *sys.argv[1:],
    ]))
