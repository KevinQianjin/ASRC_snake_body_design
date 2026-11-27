"""Evening 2026-11-26: rod-discretisation convergence of the L2 elastica at the governing states.

Coarse-to-fine continuation h = 2.0 -> 1.0 -> 0.5 -> 0.25 mm (each level initialised from the previous,
max_nfev = 1500, unit x_scale), compared with the production setting (h = 1.0 mm, Hermite start,
max_nfev = 400). The first production attempt (h = 0.5 mm, Hermite start, max_nfev = 400) is kept
in results/superseded_h0p5_* and was under-converged (ring_1 gap 0.509 vs converged ~0.39 mm).
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import bore_contact as BC

HERE = Path(__file__).resolve().parent
P = np.load(HERE / "results/unit_poses.npz")
S = np.load(HERE.parent / "evening_20261125/results/rod_steps.npz")
Cb = np.c_[S["end_rotvec"], S["station_wrench"][:, 0], S["station_wrench"][:, 1]]
ring_z = [tuple(r) for r in P["ring_z"]]
out = {}
for s in (1866, 1869, 1709):
    rings = np.einsum("jkc,c->jk", P["cad_sleeve_L66_rings"], Cb[s]); d1 = P["cad_sleeve_L66_d1"] @ Cb[s]
    R, p = BC.chain_poses(rings, d1, ring_z); RB = R[-1]; tB = RB[:, 2]
    pB = p[-1] + RB @ np.r_[0, 0, BC.Z_TIP - BC.Z_HI]; pA = np.r_[0, 0, -BC.Z_TIP]; tA = np.r_[0, 0, 1.0]
    bores = [(R[j + 1], p[j + 1], lo - 0.5 * (lo + hi), hi - 0.5 * (lo + hi)) for j, (lo, hi) in enumerate(ring_z)]
    rec = {}
    prod = BC.nonlinear_state(BC.Elastica(1.0), rings, d1, ring_z)
    rec["production_h1p0_nfev400"] = dict(gap_mm=[b["gap_mm"] for b in prod["free"]["bores"]],
                                          max_bending_strain=prod["free"]["max_bending_strain"])
    prev = None
    for h in (2.0, 1.0, 0.5, 0.25):
        el = BC.Elastica(h); el.setup(pA, tA, pB, tB, bores)
        if prev is None:
            v0 = el.guess(pA, tA, pB, tB)
        else:
            xo, fo = prev; so = np.linspace(0, 1, len(xo)); sn = np.linspace(0, 1, el.N + 1)
            xn = np.stack([np.interp(sn, so, xo[:, k]) for k in range(3)], 1)
            v0 = np.r_[xn[2:-2].ravel(), fo]
        sol = least_squares(el.residual, v0, jac_sparsity=el.sparsity, method="trf", x_scale=1.0, xtol=1e-15,
                            ftol=1e-15, gtol=1e-11, max_nfev=1500, kwargs=dict(contact=False))
        rep = el.report(sol.x); prev = (el.nodes(sol.x), sol.x[-1])
        rec[f"continuation_h{h}"] = dict(gap_mm=[b["gap_mm"] for b in rep["bores"]], energy_Nmm=float(sol.cost),
                                         optimality=float(sol.optimality), nfev=int(sol.nfev), status=int(sol.status),
                                         max_bending_strain=rep["max_bending_strain"], axial_float_mm=rep["axial_float_mm"])
        print(s, h, [round(g, 3) for g in rec[f"continuation_h{h}"]["gap_mm"]], round(rep["max_bending_strain"], 4), flush=True)
    g1 = np.array(rec["production_h1p0_nfev400"]["gap_mm"]); gc = np.array(rec["continuation_h0.25"]["gap_mm"])
    rec["production_minus_converged_min_gap_mm"] = float(g1.min() - gc.min())
    rec["h0p5_vs_h0p25_max_gap_change_mm"] = float(np.abs(np.array(rec["continuation_h0.5"]["gap_mm"]) - gc).max())
    out[str(s)] = rec
json.dump(out, open(HERE / "results/convergence.json", "w"), indent=1)
