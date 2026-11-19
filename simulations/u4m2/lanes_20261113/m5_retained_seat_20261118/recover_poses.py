"""Recover the two archived pinned-rib mesh families and export verified endpoint fields."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
EVENING = HERE.parent / "evening_20261118"
sys.path.insert(0, str(EVENING))
import pin_seat
from shell import Mesh, Model, rotation
from study import Checkpoints, KAPPA, LENGTH, Solver, archive_loads, end_pose, summarize

CASES = ("bend67.5", "bend0", "146", "141", "47", "64")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", type=float, choices=(0.055, 0.025), required=True)
    ap.add_argument(
        "--seed",
        type=Path,
        required=True,
        help="Pinned checkpoints or solved rotating-band checkpoints",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pin_seat.install(0.30)
    mesh = Mesh(args.area)
    tag = str(args.area).replace(".", "p")
    np.savez_compressed(
        args.out / f"mesh_{tag}.npz", x=mesh.x, t=mesh.t, theta=mesh.theta
    )
    model = Model(mesh, "point")
    solver = Solver(model)
    records = archive_loads() if any(c.isdecimal() for c in args.cases) else {}
    raw_dir = EVENING / "pin_seat/pin_r0p30" / f"results_{tag}"
    for case in args.cases:
        output = args.out / f"{case}_{tag}.npz"
        if output.exists():
            continue
        ref = json.loads((raw_dir / f"point_{case}.json").read_text())["samples"][-1]
        cp = Checkpoints(model, case, None, args.seed)
        if 1.0 not in cp.seeds:
            raise ValueError(f"Missing full-bend seed for {case}")
        q, moment = cp.load(1.0)
        axis, scale = None, 1.0
        if case.isdecimal():
            state = records[int(case)]
            model.external = state["loads"]
            target = end_pose(state, scale)
        else:
            model.external = []
            a = np.deg2rad(float(case[4:]))
            axis, scale = np.array([np.cos(a), np.sin(a), 0.0]), 0.0
            target = np.tan(KAPPA * LENGTH / 2)
        q, moment, it, res = solver.step(q, moment, axis, target, scale)
        row = summarize(solver, q, moment, axis, scale)
        position_error = np.linalg.norm(
            np.array(ref["tip_displacement_mm"]) - row["tip_displacement_mm"]
        )
        force_error = max(
            np.linalg.norm(np.asarray(a["force_N"]) - b["force_N"])
            for a, b in zip(ref["lands"], row["lands"])
        )
        rotation_error = max(
            abs(a["relative_rotation_deg"] - b["relative_rotation_deg"])
            for a, b in zip(ref["lands"], row["lands"])
        )
        if position_error > 0.002 or force_error > 0.005 or rotation_error > 0.002:
            raise ValueError(
                f"{case} disagrees with archive: {position_error}, {force_error}, {rotation_error}"
            )
        fields = model.mapping(q)[0].reshape(8, mesh.n, 6)
        poses = {}
        for z in (-12, 12):
            guide = model.bodies[f"G{z:+}"]
            poses[f"R{z}"] = rotation(q[guide.rot])[0]
            poses[f"C{z}"] = guide.centre + q[guide.pos]
        tmp = output.with_suffix(".part.npz")
        np.savez_compressed(
            tmp,
            fields=fields,
            **poses,
            endpoint_errors=[position_error, force_error, rotation_error],
            residual=res,
        )
        tmp.replace(output)
        print(
            case, args.area, it, "max land force discrepancy", force_error, flush=True
        )


if __name__ == "__main__":
    main()
