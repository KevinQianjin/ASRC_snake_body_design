"""Check the last screened commands and nearby samples with 16 cells and quarter-millimetre body tessellation."""

import argparse
from pathlib import Path
import numpy as np
from study_context import RESULTS, NAMES, read, read_csv, save, write_table
from free_space import PATHS, coordinates
from mesh_limits import candidate_mass, fixed
from pose_map import axis, equilibrate, correct, is_rope_domain_error
from pitch_reference import pointing
from replay import plant
from spatial_model import refine_seed
from closed_loop_cycle import FeedbackDrive
from cad_screen import Geometry, failed_part


def run(root):
    coarse, _ = plant()
    fine, _ = plant(cells=16)
    candidate_mass(fine)
    drive = FeedbackDrive(coarse)
    rows = []
    details = []
    states = []
    forces = []
    unresolved = []
    for name, (mode, fixed_axis, _, _) in PATHS.items():
        s = read(root / "geometry" / (name + ".json"))["paths"][name]
        low = s["last_contiguous_screened_deg"]
        high = s["first_failed_CAD_deg"]
        if low is None:
            continue
        table = read_csv(root / "angles" / (name + ".csv.gz"))
        seed = float(table[0]["command_deg"])
        with np.load(root / "angles" / (name + "_states.npz")) as f:
            zs = f["z"]
        ok = [r for r in table if r["leg"] != "return" and r["pass_ideal"] == "True"]
        targets = [("last screened", low)]
        if high is not None:
            targets.append(("first geometry rejection", high))
        prev = [
            float(r["command_deg"])
            for r in ok
            if abs(float(r["command_deg"]) - seed) <= abs(low - seed) - 4
        ]
        if prev:
            inward = max(prev, key=lambda a: abs(a - seed))
            targets.append(("inward check", inward))
            if name in ("right", "left", "up", "down"):
                direction = int(np.sign(low - inward))
                targets.extend(
                    ("one-degree witness", float(a))
                    for a in np.arange(inward + direction, low, direction)
                )
        probefile = root / "geometry" / (name + "_probes.csv.gz")
        probes = read_csv(probefile) if probefile.exists() else []
        for kind, a in targets:
            preceding = [
                r
                for r in ok
                if abs(float(r["command_deg"]) - seed) <= abs(a - seed) + 1e-7
            ]
            near = min(preceding, key=lambda r: abs(float(r["command_deg"]) - a))
            z = zs[int(near["index"])]
            R = (
                np.array([float(near[n + "_command_mm"]) for n in NAMES]).reshape(3, 4)
                / 1000
            )
            if abs(float(near["command_deg"]) - a) > 1e-7:
                match = next(
                    (
                        r
                        for r in probes
                        if float(r["command_deg"]) == a and r["pass_ideal"] == "True"
                    ),
                    None,
                )
                if match is None and kind == "one-degree witness":
                    try:
                        z, R, reason = correct(
                            coarse, drive, z, R, axis(*coordinates(mode, fixed_axis, a))
                        )
                    except ValueError as exc:
                        if not is_rope_domain_error(exc):
                            raise
                        reason = str(exc)
                    if reason:
                        unresolved.append(
                            dict(path=name, kind=kind, angle=a, reason=reason)
                        )
                        continue
                elif match is None:
                    unresolved.append(
                        dict(
                            path=name,
                            kind=kind,
                            angle=a,
                            reason="Missing converged coarse state",
                        )
                    )
                    continue
                else:
                    drive.stability(z, R, drive.force(z, R))
                    R = (
                        np.array(
                            [float(match[n + "_command_mm"]) for n in NAMES]
                        ).reshape(3, 4)
                        / 1000
                    )
                    z = equilibrate(coarse, drive, z, R)
                    if z is None:
                        raise RuntimeError("Coarse probe did not replay")
            zn, fine_result = fixed(
                fine,
                refine_seed(z, coarse.base, fine.base),
                R,
                pointing(coarse, z),
                axis(*coordinates(mode, fixed_axis, a)),
            )
            print("fine equilibrium", name, kind, a, flush=True)
            if zn is None:
                unresolved.append(
                    dict(path=name, kind=kind, angle=a, reason=fine_result["reason"])
                )
                continue
            q = zn / fine.scale
            good = bool(
                fine_result["error_deg"] <= 1
                and fine_result["minimum_tangent"] > 0
                and fine_result["geometry_margin"] >= -1e-7
                and fine_result["min_tension_N"] >= 2.5
                and fine_result["max_tension_N"] <= 250
                and np.max(abs(q[3::4])) <= 0.0475
            )
            rows.append(
                dict(
                    path=name,
                    kind=kind,
                    command_deg=a,
                    pointing_error_deg=fine_result["error_deg"],
                    minimum_tangent=fine_result["minimum_tangent"],
                    geometry_margin=fine_result["geometry_margin"],
                    base_axis_separation_deg=fine_result["base_axis_separation_deg"],
                    min_N=fine_result["min_tension_N"],
                    max_N=fine_result["max_tension_N"],
                    rod_pass=good,
                )
            )
            states.append(zn)
            forces.append(fine_result["tensions_N"].reshape(3, 4))
            details.append(fine.base.kinematic_metrics(zn)[1])
    geo = Geometry(fine, 0.25)
    geo.prepare(details)
    for row, d, z, t in zip(rows, details, states, forces, strict=True):
        g = geo.query(d, z, t)
        row.update(g)
        why = failed_part(g)
        row["first_failed_geometry"] = why or ""
        row["all_pass"] = row["rod_pass"] and why is None
        print(
            row["path"],
            row["kind"],
            row["command_deg"],
            row["all_pass"],
            why,
            flush=True,
        )
    write_table(root / "mesh" / "fine_geometry.csv.gz", rows)
    save(
        root / "mesh" / "fine_geometry.json",
        dict(
            cells_per_module=16,
            axial_surface_spacing_mm=0.25,
            face_counts={k: len(v.faces) for k, v in geo.bodies.items()},
            unresolved=unresolved,
            samples=[
                {
                    k: r[k]
                    for k in (
                        "path",
                        "kind",
                        "command_deg",
                        "all_pass",
                        "first_failed_geometry",
                        "pointing_error_deg",
                        "base_axis_separation_deg",
                    )
                }
                for r in rows
            ],
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
