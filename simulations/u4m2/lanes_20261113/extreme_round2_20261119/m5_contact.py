"""Carry two simultaneous mission loads through the rotating M5 shell into the finite pin and relieved web."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np
from scipy.spatial.transform import Rotation

from common import LANES, OUT, R1, ROOT, SOURCE, load_motion, read, save
from m5_seats import conditions, pin_seat, shell, study

sys.path.insert(0, str(LANES / "p3_pin_fixture_20261119"))
from inputs import joint
from supported_contact import Interface, Patch, Steel, evaluate, solvers


def moving_frames(out):
    rod, states, _ = load_motion()
    holes = dict(np.load(SOURCE / "guide_hole_loads.npz"))
    holes["wrenches"] = holes["local_wrench_CAD"]
    pin_seat.install(0.30)
    model = shell.Model(shell.Mesh(0.055), "point")
    original = study.land_reactions

    def resolve(m, q, x, f):
        rows = original(m, q, x, f)
        for row in rows:
            st = row["station_mm"]
            i = list(m.mesh.theta).index(row["rib_deg"])
            guide_R = shell.rotation(q[m.bodies[f"G{st:+}"].rot])[0]
            land_R = shell.rotation(q[m.bodies[f"L{i}_{st}"].rot])[0]
            basis = Rotation.from_euler(
                "z", row["rib_deg"], degrees=True
            ).as_matrix() @ joint.web_axes(st)
            axes = guide_R @ basis
            row["force_spn_N"] = axes.T @ row["force_N"]
            row["coupon_to_pin"] = axes.T @ land_R @ basis
        return rows

    study.land_reactions = resolve
    targets = []
    try:
        for step, st in ((1843, 12), (2059, -12)):
            with TemporaryDirectory() as temp:
                data = study.run_case(
                    model,
                    {step: conditions(rod, states[step], holes, step)},
                    str(step),
                    0.25,
                    Path(temp) / "solver.json",
                )
            if not data["completed"]:
                raise RuntimeError(f"Shell continuation failed at {step}")
            lands = data["samples"][-1]["lands"]
            old = read(R1 / f"m5_step_{step}_area_0p055.json")["lands"]
            for a, b in zip(lands, old, strict=True):
                np.testing.assert_allclose(a["force_N"], b["force_N"], atol=1e-5)
            land = max(
                (v for v in lands if v["station_mm"] == st),
                key=lambda v: np.linalg.norm(v["force_N"]),
            )
            targets.append(dict(step=step, **land))
    finally:
        study.land_reactions = original
    save(out / "m5_moving_frames.json", targets)
    return targets


def run(out):
    targets = moving_frames(out)
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    rows = []
    for level in ("middle", "fine"):
        web = Patch(level, 2.7, fit_relief=True)
        steel = Steel(0.15, "clamped", 200000.0, -2.57)
        for case in targets:
            interface = Interface(web, steel, np.asarray(case["coupon_to_pin"]), 32)
            for scale in (0.5, 1.0, 1.5, 2.0):
                force = np.asarray(case["force_spn_N"]) * scale
                try:
                    state = evaluate(interface, force)
                except (ValueError, ArithmeticError) as exc:
                    state = dict(converged=False, error=str(exc))
                rows.append(
                    dict(
                        step=case["step"],
                        station_mm=case["station_mm"],
                        rib_deg=case["rib_deg"],
                        mesh=level,
                        scale=scale,
                        **state,
                    )
                )
                print(level, case["step"], scale, state.get("converged"), flush=True)
                save(out / "m5_local.json", rows)


def conditional_yield_brackets(out):
    """Refine the elastic demand crossing for one catalog steel without assigning a grade to the pin."""
    materials = read(ROOT / "data/materials/rope_materials.json")["materials"]
    steel_case = next(m for m in materials if m["id"] == "ss304_annealed")
    limit = steel_case["yield_strength_pa"] * 1e-6
    archived = read(out / "m5_local.json")
    targets = read(out / "m5_moving_frames.json")
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    web = Patch("fine", 2.7, fit_relief=True)
    shaft = Steel(0.15, "clamped", 200000.0, -2.57)
    result = []
    for target in targets:
        step = target["step"]
        force = np.asarray(target["force_spn_N"])
        geometry = Interface(web, shaft, np.asarray(target["coupon_to_pin"]), 32)
        samples = {
            r["scale"]: r["maximum_clear_shaft_bending_MPa"]
            for r in archived
            if r["step"] == step and r["mesh"] == "fine" and r["converged"]
        }
        lo = max(x for x, y in samples.items() if y < limit)
        hi = min(x for x, y in samples.items() if y >= limit)
        estimate = np.interp(limit, [samples[lo], samples[hi]], [lo, hi])
        proposals = [estimate - 0.008, estimate + 0.008]
        checks = []
        outcome = "refined"
        while hi - lo > 0.02:
            x = proposals.pop(0) if proposals else (lo + hi) / 2
            if not lo < x < hi:
                continue
            try:
                proof = evaluate(geometry, x * force)
            except (ValueError, ArithmeticError) as exc:
                proof = dict(converged=False, error=str(exc))
            check = dict(
                load_factor=x,
                converged=bool(proof.get("converged")),
                bending_MPa=proof.get("maximum_clear_shaft_bending_MPa"),
                force_residual_N=proof.get("contact_force_residual_N"),
                error=proof.get("error"),
            )
            checks.append(check)
            if not check["converged"] or check["force_residual_N"] > 1e-4:
                outcome = "intermediate contact solve failed"
                break
            samples[x] = check["bending_MPa"]
            if samples[x] < limit:
                lo = x
            else:
                hi = x
        result.append(
            dict(
                step=step,
                station_mm=target["station_mm"],
                material_scenario=steel_case["id"],
                catalog_yield_MPa=limit,
                installed_pin_grade=None,
                status=outcome,
                probe_solutions=checks,
                lower_scale=lo,
                upper_scale=hi,
                lower_force_N=lo * np.linalg.norm(force),
                upper_force_N=hi * np.linalg.norm(force),
                lower_bending_MPa=samples[lo],
                upper_bending_MPa=samples[hi],
            )
        )
        save(out / "pin_yield_brackets.json", result)
        print("Conditional pin yield", step, outcome, lo, hi, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument(
        "--yield-brackets",
        action="store_true",
        help="refine a catalog-material yield crossing using the completed fine baseline",
    )
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.yield_brackets:
        conditional_yield_brackets(a.out)
    else:
        run(a.out)
