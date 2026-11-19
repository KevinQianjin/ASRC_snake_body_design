"""Re-equilibrate the actual +69-degree feedforward substep in each direction at fixed winch commands."""

import argparse
from pathlib import Path
import numpy as np
from scipy.optimize import root

from study_inputs import SOURCE, NAMES, read_csv, save, write_csv
from replay import plant
from pitch_reference import angle_between, pointing, position, target_axis
from sliding import on_material, virtual_work
from closed_loop_cycle import FeedbackDrive


def run(out):
    rod = plant()[0]
    drive = FeedbackDrive(rod)
    trace = read_csv(SOURCE / "rope_tensions_every_step.csv.gz")
    with np.load(SOURCE / "controller_states.npz") as archive:
        poses, rests = archive["motion_z"], archive["motion_rest_m"]
    cases, channels = [], []
    for step in (2348, 2432):
        z0, rest = poses[step], rests[step]
        nominal = drive.force(z0, rest)
        H = drive.tangent(z0, rest, nominal)
        delta = 1000 * (rest - rests[step - 1]).ravel()
        signs = np.where(abs(delta) < 0.001, 0, np.sign(delta)).astype(int)
        if (
            float(trace[step]["target_elevation_deg"]) != 69
            or int(trace[step]["step"]) != step
        ):
            raise ValueError("Expected the moving +69-degree substep")
        if abs(float(trace[step]["target_yaw_deg"])) > 1e-9:
            raise ValueError("Expected zero yaw at the reference pitch")
        target = target_axis(69.0)
        seed = z0.copy()
        for mu in (
            0.0,
            0.05,
            0.15,
            0.16,
            0.17,
            0.18,
            0.19,
            0.20,
            0.225,
            0.25,
            0.275,
            0.30,
        ):

            def evaluate(z, record=False):
                T = drive.force(z, rest)
                common = (
                    rod.base.evaluate(z, detail=True)[2],
                    rod.endpoints(z[rod.local]),
                    T,
                )
                grad = drive.energy(z, rest)[1].copy()
                lines = []
                for k, sign in enumerate(signs):
                    extra, data, nodes, local, point = on_material(
                        rod, z, rest, drive, k, mu, sign, common
                    )
                    grad += extra
                    if record:
                        lines.append(
                            dict(
                                step=step,
                                mu=mu,
                                rope=NAMES[k],
                                incoming_sign=sign,
                                delta_command_mm=delta[k],
                                nominal_N=nominal.flat[k],
                                winch_N=data["winch_N"],
                                distal_N=data["distal_N"],
                                wrap_deg=data["wrap_deg"],
                                rest_error_mm=data["rope_unstretched_closure_mm"],
                                virtual_work_error=virtual_work(
                                    rod, z, nodes, local, point, extra
                                ),
                            )
                        )
                return grad, lines

            sol = root(
                lambda z: evaluate(z)[0],
                seed,
                jac=lambda _: H,
                method="hybr",
                options=dict(xtol=2e-9, maxfev=110),
            )
            grad, lines = evaluate(sol.x, True)
            residual = rod.residual(grad)
            q = (sol.x / rod.scale).reshape(-1, 4)
            ok = bool(
                residual < 2e-6
                and np.max(abs(q[:, 3])) <= 0.0475
                and np.max(abs(q[:, :3])) <= 1.5
            )
            row = dict(
                step=step,
                phase=trace[step]["phase"],
                mu=mu,
                converged=ok,
                residual=residual,
            )
            if ok:
                seed = sol.x.copy()
                limiting = min(lines, key=lambda v: v["distal_N"])
                row.update(
                    min_distal_N=limiting["distal_N"],
                    weakest=limiting["rope"],
                    below_floor=[v["rope"] for v in lines if v["distal_N"] < 2.5],
                    pointing_error_deg=angle_between(pointing(rod, sol.x), target),
                    change_in_tip_mm=float(
                        np.linalg.norm(position(rod, sol.x) - position(rod, z0))
                    ),
                    geometry_pass=bool(rod.geometry_constraints(sol.x).min() >= -1e-7),
                )
                channels.extend(lines)
            else:
                row["message"] = str(sol.message)
            cases.append(row)
            save(out / "pitch_sliding.json", cases)
            if channels:
                write_csv(out / "pitch_sliding_channels.csv", channels)
            print(step, mu, ok, row.get("min_distal_N"), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    run(a.out)
