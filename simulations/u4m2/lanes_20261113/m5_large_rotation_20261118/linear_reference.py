"""Check the straight-state land force slopes against the archived linear rib model."""

import argparse
import json
from pathlib import Path

import numpy as np

from shell import E, Mesh, Model
from study import Factor, KAPPA, LANES, LENGTH, end_work, land_reactions, save


def peak_slopes(model, direction, epsilon):
    pair = []
    for sign in (-1.0, 1.0):
        q = epsilon * sign * direction
        _, _, _, (x, forces, _) = model.assemble(q, hessian=False)
        pair.append(land_reactions(model, q, x, forces))
    result = {}
    for key in ("force_N", "land_moment_Nmm"):
        slopes = [(pos[key] - neg[key]) / (2.0 * epsilon) for neg, pos in zip(*pair)]
        result[key] = max(np.linalg.norm(v) for v in slopes)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area", type=float, default=0.025)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads((LANES / "evening_20261117/rib_joint_3d/rib_joint_3d_results.json").read_text())
    mesh = Mesh(args.area)
    axis = np.array([np.cos(np.radians(67.5)), np.sin(np.radians(67.5)), 0.0])
    result = dict(mesh=mesh.info, axis_deg=67.5, reference_bend_rad=KAPPA * LENGTH, variants={})
    for name, old in [("point", "ball"), ("bond", "rigid_bond")]:
        model = Model(mesh, name)
        _, _, K, _ = model.assemble(model.zero)
        free = np.setdiff1d(np.arange(model.size), model.clamp)
        load = model.zero.copy()
        load[model.end] = end_work(model.zero[model.end], axis)[0]
        dq = model.zero.copy()
        dq[free] = Factor(K[free][:, free]).solve(load[free])
        del K
        # Scale infinitesimal land reaction derivatives to the reference bend, as in the linear study.
        couple = KAPPA * LENGTH / (2.0 * axis @ dq[model.end[3:]])
        dq *= couple
        estimates = {str(eps): peak_slopes(model, dq, eps) for eps in (2.0e-5, 1.0e-5)}
        case = next(
            c for c in raw["runs"][-1]["cases"] if c["variant"] == old and c["bending_axis_deg"] == 67.5
        )
        lands = [l for rows in case["stations"].values() for l in rows]
        ref = {}
        for key, fields in [
            ("force_N", ("radial_N", "axial_N", "tangential_N")),
            ("land_moment_Nmm", ("inplane_moment_Nmm", "moment_about_r_Nmm", "moment_about_z_Nmm")),
        ]:
            ref[key] = (
                E / raw["parameters"]["E"] * max(np.linalg.norm([l[k] for k in fields]) for l in lands)
            )
        result["variants"][name] = dict(
            linear_couple_Nmm=couple,
            linear_EI_Nmm2=couple / KAPPA,
            archive_mesh_mm2=raw["runs"][-1]["mesh"]["max_triangle_area_mm2"],
            archived_land_peaks=ref,
            linear_land_peaks_by_perturbation=estimates,
        )
        save(args.out, result)
        print(name, ref, estimates, flush=True)


if __name__ == "__main__":
    main()
