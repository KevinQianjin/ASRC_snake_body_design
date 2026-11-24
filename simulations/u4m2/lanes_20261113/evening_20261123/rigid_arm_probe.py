"""Bracket for handoff item 2: exact M6 clearance at +/-0.2 deg tilt with an UNDEFORMED body.

The 19-22 November clearance results map the M6 body with the homogenised rod map, which
distorts the bonded arm walls around the guide by 0.05 mm (land) to 0.37 mm (socket ends)
relative to the land's rigid motion (``socket_distortion.py``). The opposite bracket is a body
that stays rigid around the guide (every arm follows its land rigidly, i.e. the as-designed
CAD relationship between guide and body). This script evaluates that bracket with the same
parts (guide, caps, wire envelope), the same 26 tilts about the station origin
(``evening_20261121/tilt_mission.tilts``), the same 0.5 mm axial refinement and exact FCL
distance as the archived probes. Rigid-CAD clearance only.
"""
import json
import sys
from pathlib import Path

import fcl
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2))
sys.path.insert(0, str(HERE.parent / "evening_20261121"))
import m6_full as R  # noqa: E402
from common import CAD  # noqa: E402
from tilt_mission import tilts  # noqa: E402

FOLDERS = {0.0: CAD / "m6_bond_gap_20261119", 0.06: CAD / "m6_crowned_land_20261120"}


def main(angle=0.2, spacing=0.5, window=3.0):
    mesh = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
    rows = []
    T = [("none", 0, np.eye(4))] + tilts(angle)
    for st in (-12, 12):
        tri = mesh.vertices[mesh.faces]
        keep = np.all(np.abs(tri[:, :, 2] - st) < window + 2, axis=1) | (
            (tri[:, :, 2].min(1) < st + window) & (tri[:, :, 2].max(1) > st - window))
        local = R.patch(mesh.vertices - [0, 0, st], mesh.faces[keep])
        fine = R.refine_axial(local, spacing)
        body = fcl.CollisionObject(R.mesh_model(fine.vertices, fine.faces))
        for crown, folder in FOLDERS.items():
            parts = R.load_variant(folder, st)
            gaps, by_part = {}, {}
            for name, sign, M in T:
                key = name + ("" if sign == 0 else "+" if sign > 0 else "-")
                by_part[key] = {p: R.gap(body, fcl.CollisionObject(R.mesh_model(
                    m.copy().apply_transform(M).vertices, m.faces)))[0] for p, m in parts.items()}
                gaps[key] = min(by_part[key].values())
            tilted = {n: g for n, g in gaps.items() if n != "none"}
            worst = min(tilted, key=tilted.get)
            rows.append(dict(station_mm=st, crown_mm=crown, gap_no_tilt_mm=gaps["none"],
                             min_gap_tilted_mm=tilted[worst], worst_tilt=worst, governing_part=min(by_part[worst], key=by_part[worst].get),
                             no_tilt_by_part_mm=by_part["none"], gaps_mm=gaps))
            print(st, crown, f"{gaps['none']:.5f} {tilted[worst]:.5f} {worst}", rows[-1]["governing_part"], by_part["none"], flush=True)
    (HERE / "results" / "rigid_arm_probe.json").write_text(json.dumps(
        dict(angle_deg=angle, spacing_mm=spacing, body="undeformed CAD, station frame", rows=rows), indent=1))


if __name__ == "__main__":
    main()
