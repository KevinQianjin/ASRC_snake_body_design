"""Resolve a fixed M5 pivot's elastic bending demand versus a signed left-out heading."""

import argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from study_context import RESULTS, SOURCE, motion_rows, trajectory, read, save
from common import ROOT
from m5_contact import (
    shell,
    study,
    pin_seat,
    conditions,
    joint,
    Patch,
    Steel,
    Interface,
    evaluate,
    solvers,
)
from replay import plant

STATION, RIB = 12, 67.5


def run(out, area, contact_mesh):
    material = next(
        v
        for v in read(ROOT / "data/materials/rope_materials.json")["materials"]
        if v["id"] == "ss304_annealed"
    )
    limit = material["yield_strength_pa"] / 1e6
    pin_seat.install(0.30)
    model = shell.Model(shell.Mesh(area), "point")
    solver = study.Solver(model)
    rod = plant()[0].base
    states = trajectory()[0]
    rows = motion_rows()
    ids = [max(i for i, r in enumerate(rows) if r["phase"] == "right_return")]
    ids.extend(i for i, r in enumerate(rows) if r["phase"] == "left_out")
    angles = np.array([float(rows[i]["target_yaw_deg"]) for i in ids])
    with np.load(SOURCE / "guide_hole_loads.npz") as f:
        holes = {k: f[k] for k in ("step", "module", "station_mm", "lane", "direction")}
        holes["wrenches"] = f["local_wrench_CAD"]
    solvers.options.update(
        show_progress=False, maxiters=120, abstol=2e-8, reltol=2e-8, feastol=1e-8
    )
    web = Patch(contact_mesh, 2.7, fit_relief=True)
    shaft = Steel(0.15, "clamped", 200000.0, -2.57)
    cache = {}
    records = {}
    residuals = {}
    samples = []
    tag = f"pin_area_{area:g}_{contact_mesh}"

    def checkpoint():
        save(
            out / (tag + ".json"),
            dict(
                max_shell_triangle_area_mm2=area,
                local_contact_mesh=contact_mesh,
                fixed_station_mm=STATION,
                fixed_rib_deg=RIB,
                reference_yield_MPa=limit,
                pin_grade=None,
                rupture_angle_deg=None,
                rows=samples,
            ),
        )

    def solve_at(ip):
        if ip in cache:
            return
        step = ids[ip]
        data = conditions(rod, states[step], holes, step)
        model.external = data["loads"]
        left = min(cache, key=lambda j: abs(j - ip)) if cache else None
        q = cache[left] if left is not None else model.zero
        end = study.end_pose(data, 1.0)
        try:
            q, _, _, res = solver.step(q, 0, None, end, 1.0)
        except (RuntimeError, ArithmeticError, np.linalg.LinAlgError):
            if left is not None and abs(ip - left) > 1:
                solve_at((left + ip) // 2)
                solve_at(ip)
                return
            q = model.zero
            for scale in np.linspace(1 / 32, 1, 32):
                q, _, _, res = solver.step(
                    q, 0, None, study.end_pose(data, scale), scale
                )
        cache[ip] = q
        residuals[ip] = res

    def observe(ip):
        if ip in records:
            return records[ip]
        solve_at(ip)
        step = ids[ip]
        q = cache[ip]
        model.external = conditions(rod, states[step], holes, step)["loads"]
        mesh = model.mesh
        _, _, _, (x, f, strains) = model.assemble(q, 1, hessian=False)
        lands = study.land_reactions(model, q, x, f)
        land = next(
            v for v in lands if v["station_mm"] == STATION and v["rib_deg"] == RIB
        )
        i = list(mesh.theta).index(RIB)
        basis = Rotation.from_euler(
            "z", RIB, degrees=True
        ).as_matrix() @ joint.web_axes(STATION)
        guide = shell.rotation(q[model.bodies[f"G{STATION:+}"].rot])[0] @ basis
        rib = shell.rotation(q[model.bodies[f"L{i}_{STATION}"].rot])[0] @ basis
        force = guide.T @ land["force_N"]
        value = evaluate(Interface(web, shaft, guide.T @ rib, 32), force)
        if not value["converged"] or value["contact_force_residual_N"] > 1e-4:
            raise ArithmeticError("Local contact did not meet the force tolerance")
        extrema = study.surface_extremes(mesh, strains)
        r = dict(
            step=step,
            phase=rows[step]["phase"],
            yaw_deg=angles[ip],
            pitch_deg=float(rows[step]["target_elevation_deg"]),
            shell_residual=residuals[ip],
            shell_min_oriented_area_ratio=mesh.minimum_orientation(x),
            force_spn_N=force,
            coupon_to_pin=guide.T @ rib,
            shell_peak_tensile=extrema["principal_tensile"],
            peak_pin_bending_MPa=value["maximum_clear_shaft_bending_MPa"],
            local_contact_force_residual_N=value["contact_force_residual_N"],
            p95_local_web_tensile_strain=value["p95_volume_tensile_principal_strain"],
            above_reference=bool(value["maximum_clear_shaft_bending_MPa"] >= limit),
        )
        records[ip] = r
        samples.append(r)
        checkpoint()
        print(tag, step, angles[ip], r["peak_pin_bending_MPa"], flush=True)
        return r

    initial_targets = (0, -30, -60, -90, -120, -150, -175)
    sample_ids = list(
        dict.fromkeys(int(np.argmin(abs(angles - a))) for a in initial_targets)
    )
    for ip in sample_ids:
        observe(ip)
    intervals = []
    for a, b in zip(sample_ids, sample_ids[1:]):
        if records[a]["above_reference"] == records[b]["above_reference"]:
            continue
        while abs(angles[b] - angles[a]) > 1 and b - a > 1:
            mid = (a + b) // 2
            if observe(mid)["above_reference"] == records[a]["above_reference"]:
                a = mid
            else:
                b = mid
        intervals.append([ids[a], ids[b]])
    save(
        out / (tag + ".json"),
        dict(
            max_shell_triangle_area_mm2=area,
            local_contact_mesh=contact_mesh,
            fixed_station_mm=STATION,
            fixed_rib_deg=RIB,
            reference_yield_MPa=limit,
            pin_grade=None,
            rupture_angle_deg=None,
            resolved_sign_changes_step_pairs=intervals,
            rows=sorted(samples, key=lambda r: r["step"]),
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--area", type=float, default=0.1)
    p.add_argument("--contact-mesh", choices=("middle", "fine"), default="fine")
    p.add_argument("--out", type=Path, default=RESULTS / "strength")
    a = p.parse_args()
    run(a.out, a.area, a.contact_mesh)
