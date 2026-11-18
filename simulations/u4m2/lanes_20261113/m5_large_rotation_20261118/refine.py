"""Re-equilibrate selected poses on a finer mesh and split the last load increment."""

import argparse
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation

from continuation import Checkpoints
from shell import Mesh, Model, rotation, skew, spin_map
from study import (
    CASES,
    KAPPA,
    LENGTH,
    TOL,
    Factor,
    Solver,
    archive_loads,
    end_pose,
    end_work,
    save,
    summarize,
)


def twist_probe(solver, start, bend_couple, axis, increment=0.001):
    """Apply positive and negative twists with the bend held and other loads free."""
    model = solver.m
    I, tip = solver.inside, model.end
    R0 = rotation(start[tip[3:]])[0]
    direction = R0[:, 2]
    fixed_bend = axis @ start[tip[3:]]
    solutions = []
    for angle in (-increment, increment):
        q = start.copy()
        loads = np.array([bend_couple, 0.0])
        for iteration in range(12):
            _, grad, tangent, _ = model.assemble(q)
            p = q[tip[3:]]
            rv = Rotation.from_matrix(rotation(p)[0] @ R0.T).as_rotvec()
            phi = np.linalg.norm(rv)
            H = skew(rv)
            # The inverse left Jacobian differentiates the spatial rotation logarithm.
            c = 1.0 / 12.0 if phi < 0.001 else (1.0 - 0.5 * phi / np.tan(0.5 * phi)) / phi**2
            log_jac = np.eye(3) - 0.5 * H + c * H @ H
            C = np.zeros((2, 6))
            C[0, 3:] = axis
            C[1, 3:] = direction @ log_jac @ spin_map(p)[0]
            Q1, d1 = end_work(q[tip], axis)
            Q2, d2 = end_work(q[tip], direction)
            Q = np.column_stack((Q1, Q2))
            error = np.array([fixed_bend - axis @ p, angle - direction @ rv])
            forces = Q @ loads - grad[tip]
            residual = max(np.max(abs(grad[I])), np.max(abs(forces)))
            if residual < TOL and np.max(abs(error)) < 1.0e-10:
                break
            Kie = tangent[I][:, tip].toarray()
            Y = Factor(tangent[I][:, I]).solve(np.column_stack((-grad[I], Kie)))
            S = tangent[tip][:, tip].toarray() - Kie.T @ Y[:, 1:] - loads[0] * d1 - loads[1] * d2
            A = np.block([[S, -Q], [C, np.zeros((2, 2))]])
            sol = np.linalg.solve(A, np.r_[forces - Kie.T @ Y[:, 0], error])
            dq = np.zeros_like(q)
            dq[tip] = sol[:6]
            dq[I] = Y[:, 0] - Y[:, 1:] @ sol[:6]
            q = model.increment(q, dq)
            loads = loads + sol[6:]
        else:
            raise RuntimeError("Finite twist did not equilibrate")
        solutions.append(
            dict(
                target_twist_rad=angle,
                applied_twist_rad=direction @ rv,
                bend_couple_Nmm=loads[0],
                torsional_couple_Nmm=loads[1],
                bend_angle_rad=2.0 * np.arctan(axis @ p),
                iterations=iteration,
                equilibrium_residual=residual,
            )
        )
    gj = (
        LENGTH
        * (solutions[1]["torsional_couple_Nmm"] - solutions[0]["torsional_couple_Nmm"])
        / (2 * increment)
    )
    return dict(states=solutions, central_GJ_Nmm2=gj)


def run(model, case, data, seed, cache, out, angles, split, probe):
    solver = Solver(model)
    warm = Checkpoints(model, case, cache, seed)
    if max(warm.seeds) < 1.0 - 1.0e-9:
        raise ValueError(f"Source continuation for {case} has not reached full load")
    axis = None
    model.external = []
    if case.startswith("bend"):
        rad = np.radians(float(case[4:]))
        axis = np.array([np.cos(rad), np.sin(rad), 0.0])
    else:
        model.external = data["loads"]
    output = dict(
        variant=model.variant,
        case=case,
        mesh=model.mesh.info,
        completed=False,
        boundary_extrapolation_nodes_per_rib=warm.fallback_nodes,
        inputs=None if data is None else dict(stations=data["checks"], target=end_pose(data, 1.0)),
        steps=[],
        samples=[],
    )
    start = time.monotonic()
    keep = [0.0, 0.25, 0.5, 0.75, 1.0] if angles and axis is not None else [0.0, 1.0]

    def solve_at(fraction, initial):
        target = np.tan(fraction * KAPPA * LENGTH / 2.0) if axis is not None else end_pose(data, fraction)
        q, M, it, res = solver.step(*initial, axis, target, 0.0 if axis is not None else fraction)
        output["steps"].append(dict(fraction=fraction, accepted=True, iterations=it, residual=res))
        print(
            case,
            model.variant,
            f"{fraction:.5f}",
            it,
            f"{res:.2g}",
            f"{time.monotonic() - start:.1f}s",
            flush=True,
        )
        return q, M

    def log_sample(fraction, state):
        row = summarize(solver, *state, axis, 0.0 if axis is not None else fraction)
        row["fraction"] = fraction
        return row

    def predictor(old, new, state):
        # Preserve the fine-mesh correction at the previous equilibrated pose while
        # advancing by the change of the independently saved coarse trajectory.
        qa, ma = warm.load(old)
        qb, mb = warm.load(new)
        q, M = state
        lifted = model.lift(q, -1.0) + model.lift(qb, -1.0) - model.lift(qa, -1.0)
        return model.lift(lifted, 1.0), M + mb - ma

    low = 1.0 - 1.0 / 16.0
    previous = None
    last_fraction = 0.0
    last_state = model.zero.copy(), 0.0

    def advance(low_fraction, low_state, fraction):
        predicted = (
            warm.load(fraction) if low_fraction == 0.0 else predictor(low_fraction, fraction, low_state)
        )
        try:
            return solve_at(fraction, predicted)
        except (RuntimeError, np.linalg.LinAlgError) as exc:
            output["steps"].append(dict(fraction=fraction, accepted=False, reason=str(exc)))
            save(out, output)
            if (fraction - low_fraction) / 2.0 < 1.0 / 256.0:
                raise
            middle = 0.5 * (fraction + low_fraction)
            midway = advance(low_fraction, low_state, middle)
            return advance(middle, midway, fraction)

    stages = sorted(set(keep + ([low] if split else [])))
    try:
        for f in stages:
            if f == 0.0:
                state = model.zero.copy(), 0.0
            elif split and f == 1.0:
                state = solve_at(f, predictor(low, f, previous))
            else:
                state = advance(last_fraction, last_state, f)
            if f in keep:
                row = log_sample(f, state)
                output["samples"].append(row)
            if f == low:
                previous = state
            last_fraction, last_state = f, state
            warm.save(f, *state)
            save(out, output)
        if split:
            mid = 0.5 * (1.0 + low)
            middle = solve_at(mid, predictor(low, mid, previous))
            half = solve_at(1.0, predictor(mid, 1.0, middle))
            output["split_last_step"] = dict(
                start_fraction=low,
                full_increment=1.0 - low,
                half_increment=mid - low,
                endpoint=log_sample(1.0, half),
            )
        if probe and axis is not None:
            output["finite_twist"] = twist_probe(solver, *state, axis)
        output["completed"] = True
    except (RuntimeError, np.linalg.LinAlgError) as exc:
        output["failure"] = str(exc)
        print(case, model.variant, str(exc), flush=True)
    output["elapsed_s"] = time.monotonic() - start
    save(out, output)
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", required=True, type=float)
    ap.add_argument("--variants", required=True, nargs="+", choices=["bare", "bond", "point"])
    ap.add_argument("--cases", required=True, nargs="+", choices=["bend0", "bend67.5", *map(str, CASES)])
    ap.add_argument("--seed", required=True, type=Path)
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--all-samples", action="store_true", help="Include all five pure bending fractions")
    ap.add_argument("--split", action="store_true", help="Independently halve the final 1/16 increment")
    ap.add_argument(
        "--twist", action="store_true", help="Apply two extra finite twists at full pure bend"
    )
    args = ap.parse_args()
    if args.area <= 0:
        ap.error("Mesh area must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    mesh = Mesh(args.area)
    print(mesh.info, flush=True)
    archive = archive_loads() if any(not s.startswith("bend") for s in args.cases) else {}
    unfinished = []
    for variant in args.variants:
        model = Model(mesh, variant)
        for case in args.cases:
            if variant == "bare" and not case.startswith("bend"):
                continue
            output = args.out / f"{variant}_{case}.json"
            if output.exists():
                raise FileExistsError(output)
            result = run(
                model,
                case,
                archive.get(int(case)) if case.isdecimal() else None,
                args.seed,
                args.cache,
                output,
                args.all_samples,
                args.split,
                args.twist,
            )
            if not result["completed"]:
                unfinished.append(output.name)
    if unfinished:
        raise SystemExit("Incomplete refinements saved in " + ", ".join(unfinished))


if __name__ == "__main__":
    main()
