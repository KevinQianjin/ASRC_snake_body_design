"""Evening 2026-11-26: sensitivity of the L2 backbone/bore result at the governing states.

Variants (each at steps 1,866 / 1,869 / 1,709):
  base          arc-length lift, axially floating distal rod end, h = 1.0 mm  (production setting)
  (rod-discretisation convergence is recorded separately by convergence.py)
  fixed_chord   arc-length lift, distal end pinned to the lifted sleeve tip (axially rigid bound; NOT physical:
                the lifted chord carries the ~2 mm second-order shortening that linear lattice shear offsets omit)
  plain_lift    linear-translation lift (rejected) with floating end, to show the lift sensitivity
"""
import json
from pathlib import Path

import numpy as np

import bore_contact as BC

HERE = Path(__file__).resolve().parent
P = np.load(HERE / "results/unit_poses.npz")
S = np.load(HERE.parent / "evening_20261125/results/rod_steps.npz")
Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
ring_z = [tuple(r) for r in P["ring_z"]]


def shear_shortening(rings, d1):
    X = [np.r_[0, 0, BC.Z_LO]] + [np.r_[0, 0, 0.5 * (a + b)] for a, b in ring_z] + [np.r_[0, 0, BC.Z_HI]]
    U = [np.zeros(6)] + list(rings) + [d1]
    tot = 0.0
    for j in range(5):
        dX = X[j + 1] - X[j]; dth = U[j + 1][3:] - U[j][3:]
        res = U[j + 1][:3] - U[j][:3] - np.cross(U[j][3:], dX) - 0.5 * np.cross(dth, dX)
        tot += (res[0] ** 2 + res[1] ** 2) / (2 * dX[2])
    return float(tot)


out = {}
for s in (1866, 1869, 1709):
    rings = np.einsum("jkc,c->jk", P["cad_sleeve_L66_rings"], Cb[s]); d1 = P["cad_sleeve_L66_d1"] @ Cb[s]
    rec = dict(second_order_shear_shortening_mm=shear_shortening(rings, d1))
    for name, arc, flt, h in (("base", True, True, 1.0),
                              ("fixed_chord", True, False, 1.0), ("plain_lift", False, True, 1.0)):
        BC.ARC_LIFT, BC.AXIAL_FLOAT = arc, flt
        r = BC.nonlinear_state(BC.Elastica(h), rings, d1, ring_z)
        rep = r.get("contact", r["free"])
        rec[name] = dict(gap_free_mm=[b["gap_mm"] for b in r["free"]["bores"]],
                         contact_solved="contact" in r,
                         contact_force_N=[b["contact_force_N"] for b in rep["bores"]],
                         max_bending_strain=rep["max_bending_strain"], axial_float_mm=r["free"]["axial_float_mm"],
                         max_axial_strain=rep["max_axial_strain"], chord_mm=r["chord_mm"])
        print(s, name, [round(g, 3) for g in rec[name]["gap_free_mm"]], round(rec[name]["max_bending_strain"], 4),
              round(rec[name]["axial_float_mm"], 3), [round(f, 1) for f in rec[name]["contact_force_N"]], flush=True)
    out[str(s)] = rec
BC.ARC_LIFT, BC.AXIAL_FLOAT = True, True
json.dump(out, open(HERE / "results/sensitivity.json", "w"), indent=1)
