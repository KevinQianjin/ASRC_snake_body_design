"""Recover selected sliding-loop equilibria and inspect their local active-branch quasi-static tangent."""

from pathlib import Path
import argparse
import numpy as np
from scipy.linalg import eigvalsh
from scipy.optimize import root
from common import input_file, OUT, NAMES, motion_rows, trajectory, read, read_csv, save
from replay import plant
from rope_history import FREE
from pitch_reference import pointing, angle_between
from pose_map import axis, centreline, clearance
from length_cycle import FastTank


def run(out):
    z0, _, _ = trajectory()
    archive = motion_rows()
    rod, _ = plant()
    ea = rod.planar.rope_ea
    tank = FastTank()
    records = []
    for mode in ("open", "feedback", "compensated"):
        tag = "coupled_s0.15_k0.15_b0.1_" + mode
        trace = read_csv(input_file(out, "rope_control", tag + ".csv.gz"))
        summary = read(input_file(out, "rope_control", tag + ".json"))
        events = {
            913,
            1709,
            1710,
            1779,
            1843,
            1885,
            2059,
            2348,
            2432,
            summary["minimum_distal"][1],
            summary["maximum_pointing_error"][1],
            summary["minimum_tank_gap"][1],
        }
        for i in sorted(events):
            row = trace[i]
            a = archive[i]
            T = np.array([float(row[n + "_dist_N"]) for n in NAMES])
            tp = np.array([float(row[n + "_prox_N"]) for n in NAMES])
            slip = np.array([float(row[n + "_slip_mm"]) for n in NAMES])
            R = np.array([float(row[n + "_drum_mm"]) / 1000 for n in NAMES])
            get = lambda z: rod.evaluate(z, T.reshape(3, 4))[1]
            H0 = rod.hessian(z0[i], T.reshape(3, 4))
            fit = root(
                get,
                z0[i],
                jac=lambda _: H0,
                method="hybr",
                options=dict(xtol=1e-10, maxfev=130),
            )
            z = fit.x
            res = rod.residual(get(z))
            err = angle_between(
                pointing(rod, z),
                axis(float(a["target_yaw_deg"]), float(a["target_elevation_deg"])),
            )
            gap = clearance(tank, centreline(rod, z), float(a["clamp_s_mm"]))
            accepted = (
                res < 2e-6
                and abs(gap - float(row["tank_gap_mm"])) < 0.01
                and abs(err - float(row["pointing_error_deg"])) < 0.002
            )
            r = dict(
                mode=mode,
                step=i,
                recovered=bool(accepted),
                residual=res,
                gap_discrepancy_mm=gap - float(row["tank_gap_mm"]),
                angle_discrepancy_deg=err - float(row["pointing_error_deg"]),
            )
            if accepted:
                L = rod.evaluate(z, detail=True)[2]["rope_lengths"].ravel()
                h = L / (1 + T / ea)
                ratio = T / np.maximum(tp, 1e-12)
                x = tp / ea
                slip_slope = (
                    ratio
                    * ea
                    / (1 + ratio * x)
                    / (FREE / (1 + x) ** 2 + L * ratio / (1 + ratio * x) ** 2)
                )
                slope = np.where(abs(slip) > 1e-7, slip_slope, ea / h)
                J = rod.control_jacobian(z)
                H = rod.hessian(z, T.reshape(3, 4)) + J.T @ (slope[:, None] * J)
                r.update(
                    min_scaled_tangent_eigenvalue=eigvalsh(H, subset_by_index=(0, 0))[
                        0
                    ],
                    rod_geometry_margin=rod.geometry_constraints(z).min(),
                    maximum_axial_strain=np.max(
                        abs((z / rod.scale).reshape(-1, 4)[:, 3])
                    ),
                    rest_closure_mm=np.max(abs(h + FREE / (1 + tp / ea) - R)) * 1000,
                )
            records.append(r)
    save(out / "rope_control" / "replay_tangents.json", records)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    run(p.parse_args().out)
