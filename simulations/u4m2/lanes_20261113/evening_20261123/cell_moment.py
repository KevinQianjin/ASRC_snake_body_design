"""Consistency check: bending moment carried by the 8 solid CAD struts of the M6 cell when their
cut faces follow the homogenised rod map, compared with the rod model's own cell moment.

If the solid strut cell is much stiffer than the rod model's cell stiffness, driving the struts
with the rod map (as ``solid_bond.py`` and ``coupled_land.py`` do) overstates their deformation.
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261122"))
import crowned_bond as CB  # noqa: E402
import strut_fe as FE  # noqa: E402
from solid_bond import CUTS  # noqa: E402

ANG = np.arange(22.5, 360, 45)


def main(h=0.8, steps=(0, 1709, 1885)):
    rod, z, _ = CB.load_motion()
    module = trimesh.load_mesh(CB.S.BODY)
    K = np.asarray(rod.K)
    rows = []
    struts = {(th, st): FE.Strut(module, th, *CUTS[st], h, np.zeros((1, 3)) + [0, 0, st])
              for st in CUTS for th in ANG}
    for step in steps:
        det = rod.kinematic_metrics(z[step])[1]
        for st in CUTS:
            M = np.zeros(3)
            Fsum = np.zeros(3)
            for th in ANG:
                S = struts[th, st]
                P = S.boundary_points()
                ub = (CB.to_station(P, 5, st, rod, det) - (P - [0, 0, st])).ravel()
                u = S.full_field(ub).ravel()
                r = (S._K @ u).reshape(-1, 3)
                top = S.bnodes[S.X[S.bnodes, 2] > st]
                Fsum += r[top].sum(0)
                M += np.cross(S.X[top] - [0, 0, st], r[top]).sum(0)
            cell = 5 * rod.sub + int((st + 48) // 12)
            q = det["q"][cell]
            phi = np.array([q[0], -q[2], q[1]])  # rod-frame -> CAD-like ordering is not needed for magnitudes
            rows.append(dict(step=step, station_mm=st, cell=int(cell),
                             solid_moment_Nmm=M.tolist(), solid_bending_moment_Nmm=float(np.linalg.norm(M[:2])),
                             solid_torque_Nmm=float(M[2]), solid_axial_force_N=float(Fsum[2]),
                             rod_cell_rotation_deg=float(np.degrees(np.linalg.norm(q[:3]))),
                             rod_bending_moment_Nmm=float(1000 * K[cell, 1] * np.linalg.norm(q[1:3])),
                             rod_K_cell=K[cell].tolist()))
            print(rows[-1], flush=True)
    (HERE / "results" / "cell_moment.json").write_text(json.dumps(dict(h_mm=h, rows=rows), indent=1))


if __name__ == "__main__":
    main()
