"""Independent directional checks of the corrected fixed-winch energy tangent at hold 64."""

import argparse
import json
from pathlib import Path

import numpy as np
from shared_bore import load_rod, lanes, apply_bellmouth
from rebalance import SharedRod
from length_cycle import LengthDrive


def check(folder):
    design, old, profiles = load_rod()
    rows = []
    for sub in (8, 16):
        base = (
            old
            if sub == 8
            else apply_bellmouth(
                lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, sub), design
            )
        )
        rod = SharedRod(base, profiles, 0.15)
        drive = LengthDrive(rod)
        path = folder / f"fixed_winch_{sub}/64.json"
        rec = json.loads(path.read_text())
        rest = np.asarray(rec["rest_lengths_mm"]) / 1000.0
        with np.load(path.with_suffix(".npz")) as data:
            z = data["z"]
        T = drive.force(z, rest)
        J = rod.control_jacobian(z)
        active = T.ravel() > 1e-8
        H = rod.hessian(z, T) + J[active].T @ (
            (drive.ea / rest.ravel()[active])[:, None] * J[active]
        )
        vals, V = np.linalg.eigh(H)
        rng = np.random.default_rng(26)
        direction = rng.normal(size=len(z))
        direction /= np.linalg.norm(direction)
        local = np.zeros(len(z))
        local[rod.local] = rng.normal(size=len(rod.indices))
        local /= np.linalg.norm(local)
        dirs = {
            "first_eigenvector": V[:, 0],
            "full_random": direction,
            "shared_cells_only": local,
        }
        scores = []
        for name, d in dirs.items():
            hd = H @ d
            for step in (1e-4, 4e-5):
                u = (
                    drive.energy(z + step * d, rest)[1]
                    - drive.energy(z - step * d, rest)[1]
                ) / (2 * step)
                scores.append(
                    dict(
                        direction=name,
                        step_scaled_dof=step,
                        relative_tangent_vector_error=float(
                            np.linalg.norm(u - hd) / np.linalg.norm(hd)
                        ),
                        analytic_rayleigh=float(hd @ d),
                        independent_rayleigh=float(u @ d),
                    )
                )
        rows.append(
            dict(
                cells_per_module=sub,
                hold=64,
                minimum_eigenvalue=float(vals[0]),
                checks=scores,
            )
        )
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    a = p.parse_args()
    (a.results / "tangent_check_64.json").write_text(
        json.dumps(check(a.results), indent=2) + "\n"
    )
