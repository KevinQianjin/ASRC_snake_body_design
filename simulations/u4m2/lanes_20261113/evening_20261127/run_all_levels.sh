#!/bin/bash
# Sequential (memory: one q2.5 PARDISO solve needs ~13 GB of the 15 GB session limit)
cd "$(dirname "$0")"
python3.13 hub_variant_fe.py baseline
python3.13 hub_variant_fe.py --q25 baseline
python3.13 hub_variant_fe.py slot_fill
python3.13 hub_variant_fe.py --level q2p5_a040 2.5 0.40 slot_fill
