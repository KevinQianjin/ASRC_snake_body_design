"""Apply the same-step rod end pose and sixteen bore loads to the two rotating M5 seats."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np

from study_inputs import LANES, SOURCE, RAYS, load_motion, save

sys.path.insert(0, str(LANES / "evening_20261118"))
import pin_seat
from pin_seat import shell, study


def conditions(rod, state, holes, step):
    detail = rod.evaluate(state, detail=True)[2]
    frame = detail["frames"][32] @ study.CAD_TO_ROD
    cells = detail["q"][32:40]
    end_R = frame.T @ detail["frames"][40] @ study.CAD_TO_ROD
    end_mm = frame.T @ (1000 * (detail["points"][40] - detail["points"][32])) - [
        0,
        0,
        96,
    ]
    target = study.end_pose(dict(cells=cells), 1.0)
    np.testing.assert_allclose(target, np.r_[end_mm, study.rotpar(end_R)], atol=1e-7)
    loads, checks = [], []
    if holes["step"][step] != step:
        raise ValueError("Mismatched hole and state index")
    for station, node in ((-12, 35), (12, 37)):
        ids = np.flatnonzero(
            (holes["module"] == "M5") & (holes["station_mm"] == station)
        )
        labels = list(zip(holes["lane"][ids], holes["direction"][ids], strict=True))
        if (
            set(labels) != {(lane, ray) for lane in "BC" for ray in RAYS}
            or len(ids) != 8
        ):
            raise ValueError("Incomplete M5 load set")
        offsets = np.array(
            [
                1000
                * study.CAD_TO_ROD.T
                @ rod.offsets3["ABC".index(lane), RAYS.index(ray)]
                for lane, ray in labels
            ]
        )
        local = holes["wrenches"][step, ids]
        np.testing.assert_allclose(
            np.cross(offsets, local[:, 0]), local[:, 1], atol=1e-8
        )
        R = frame.T @ detail["frames"][node] @ study.CAD_TO_ROD
        loads.append((f"G{station:+}", offsets, local[:, 0] @ R.T))
        checks.append(
            dict(
                station_mm=station,
                F_CAD_N=local[:, 0].sum(0),
                M_CAD_Nmm=local[:, 1].sum(0),
            )
        )
    return dict(cells=cells, loads=loads, checks=checks)


def run(out, area):
    rod, states, _ = load_motion()
    with np.load(SOURCE / "guide_hole_loads.npz") as data:
        holes = {
            k: data[k] for k in ("module", "station_mm", "step", "lane", "direction")
        }
        holes["wrenches"] = data["local_wrench_CAD"]
    pin_seat.install(0.30)
    model = shell.Model(shell.Mesh(area), "point")
    for step in (1843, 2059):
        conditions_at_step = conditions(rod, states[step], holes, step)
        with TemporaryDirectory() as tmp:
            raw = study.run_case(
                model,
                {step: conditions_at_step},
                str(step),
                0.25,
                Path(tmp) / "log.json",
            )
        row = dict(
            step=step,
            status="converged" if raw["completed"] else "incomplete",
            maximum_element_area_mm2=area,
            shell_mesh=model.mesh.info,
            inputs=raw["inputs"],
            continuation=[
                {k: v for k, v in line.items() if k != "seconds"}
                for line in raw["steps"]
            ],
        )
        if raw["completed"]:
            final = raw["samples"][-1]
            row.update(
                {
                    k: final[k]
                    for k in (
                        "lands",
                        "force_balance_N",
                        "moment_balance_Nmm",
                        "free_residual_inf",
                        "surface_extremes",
                        "minimum_oriented_area_ratio",
                    )
                }
            )
            row["largest_pivot_force_N"] = max(
                np.linalg.norm(s["force_N"]) for s in final["lands"]
            )
        save(out / f"m5_step_{step}_area_{str(area).replace('.', 'p')}.json", row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--area", type=float, default=0.1)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    run(args.out, args.area)
