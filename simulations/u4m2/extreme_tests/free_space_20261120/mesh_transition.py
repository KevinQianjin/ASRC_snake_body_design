"""Follow fine-grid steering limits when the coarse first-rejected command also passes or the coarse endpoint fails."""

import argparse
from pathlib import Path
import numpy as np
from study_context import NAMES, RESULTS, read, read_csv, save, write_table
from cad_screen import Geometry, failed_part
from free_space import PATHS, coordinates
from mesh_limits import candidate_mass, fixed
from pose_map import axis, correct, equilibrate
from pitch_reference import pointing
from replay import plant
from spatial_model import refine_seed
from closed_loop_cycle import FeedbackDrive


def command_at(angle, seed, path, states, probes, rod, drive, target):
    inward = [
        r
        for r in path
        if abs(float(r["command_deg"]) - seed) <= abs(angle - seed) + 1e-8
    ]
    near = min(inward, key=lambda r: abs(float(r["command_deg"]) - angle))
    z = states[int(near["index"])]

    def lengths(row):
        return (
            np.array([float(row[n + "_command_mm"]) for n in NAMES]).reshape(3, 4)
            / 1000
        )

    command = lengths(near)
    if abs(float(near["command_deg"]) - angle) < 1e-8:
        return z, command, "archived coarse commands"
    known = next(
        (
            r
            for r in probes
            if float(r["command_deg"]) == angle and r["pass_ideal"] == "True"
        ),
        None,
    )
    if known is not None:
        command = lengths(known)
        drive.stability(z, command, drive.force(z, command))
        z = equilibrate(rod, drive, z, command)
        if z is None:
            raise ArithmeticError("Saved probe did not re-equilibrate")
        return z, command, "published coarse geometry probe"
    z, command, reason = correct(rod, drive, z, command, target)
    if reason:
        raise ValueError(f"Coarse winch reconstruction failed at {angle}: {reason}")
    return z, command, "coarse controller from nearest inward saved state"


def run(root):
    fine_rows = read(root / "mesh/fine_geometry.json")["samples"]
    source, _ = plant()
    fine, _ = plant(cells=16)
    change = candidate_mass(fine)
    drive = FeedbackDrive(source)
    geo = None
    results = {}
    extra = []
    for name, (mode, fixed_axis, _, cap) in PATHS.items():
        old = read(root / "geometry" / (name + ".json"))["paths"][name]
        lo = old["last_contiguous_screened_deg"]
        hi = old["first_failed_CAD_deg"]
        if lo is None or hi is None:
            continue
        rows = {v["command_deg"]: v for v in fine_rows if v["path"] == name}
        if lo not in rows or hi not in rows:
            results[name] = dict(status="missing fixed-command probe")
            continue
        if rows[lo]["all_pass"] and not rows[hi]["all_pass"]:
            results[name] = dict(
                last_pass_deg=lo,
                first_failure_deg=hi,
                limiting_check=rows[hi]["first_failed_geometry"] or "rod gate",
                status="coarse bracket confirmed on fine mesh",
            )
            continue
        trajectory = read_csv(root / "angles" / (name + ".csv.gz"))
        seed = float(trajectory[0]["command_deg"])
        source_path = [
            r for r in trajectory if r["pass_ideal"] == "True" and r["leg"] != "return"
        ]
        probe_file = root / "geometry" / (name + "_probes.csv.gz")
        probes = read_csv(probe_file) if probe_file.exists() else []
        with np.load(root / "angles" / (name + "_states.npz")) as file:
            states = file["z"]
        reach = float(source_path[-1]["command_deg"])
        direction = int(np.sign(hi - lo))
        if geo is None:
            geo = Geometry(fine, 0.25)

        def get(a):
            if a in rows:
                return rows[a]
            target = axis(*coordinates(mode, fixed_axis, a))
            z, R, where = command_at(
                a, seed, source_path, states, probes, source, drive, target
            )
            zf, fr = fixed(
                fine,
                refine_seed(z, source.base, fine.base),
                R,
                pointing(source, z),
                target,
            )
            if zf is None:
                raise ArithmeticError(
                    f"Fine equilibrium failed at {name} {a}: {fr['reason']}"
                )
            d = fine.base.kinematic_metrics(zf)[1]
            geo.prepare([d])
            gaps = geo.query(d, zf, fr["tensions_N"].reshape(3, 4))
            axial = float(np.max(np.abs((zf / fine.scale)[3::4])))
            good = (
                fr["error_deg"] <= 1
                and fr["minimum_tangent"] > 0
                and fr["residual"] < 2e-6
                and fr["geometry_margin"] >= -1e-7
                and fr["min_tension_N"] >= 2.5
                and fr["max_tension_N"] <= 250
                and axial <= 0.0475
            )
            reason = failed_part(gaps)
            r = dict(
                path=name,
                command_deg=a,
                coarse_command_source=where,
                pointing_error_deg=fr["error_deg"],
                base_axis_separation_deg=fr["base_axis_separation_deg"],
                residual=fr["residual"],
                min_tangent=fr["minimum_tangent"],
                geometry_margin=fr["geometry_margin"],
                max_axial_strain=axial,
                rod_pass=bool(good),
                all_pass=bool(good and reason is None),
                first_failed_geometry=reason or "",
                **{
                    n + "_N": float(t)
                    for n, t in zip(NAMES, fr["tensions_N"], strict=True)
                },
                **{
                    n + "_command_mm": float(x) * 1000
                    for n, x in zip(NAMES, R.flat, strict=True)
                },
                **gaps,
            )
            rows[a] = r
            extra.append(r)
            print(name, a, r["all_pass"], reason, flush=True)
            return r

        passing = lo if rows[lo]["all_pass"] else lo - direction
        while not get(passing)["all_pass"] and abs(passing - lo) < 12:
            passing -= direction
        if not get(passing)["all_pass"]:
            results[name] = dict(status="no inward witness inside search window")
            continue
        failed = None
        while abs(passing - lo) < 12 and direction * (reach - passing) > 0:
            following = passing + direction
            trial = get(following)
            if not trial["all_pass"]:
                failed = trial
                break
            passing = following
        results[name] = dict(
            last_pass_deg=passing,
            first_failure_deg=failed["command_deg"] if failed else None,
            limiting_check=(failed["first_failed_geometry"] or "rod gate")
            if failed
            else None,
            status="adjacent fine-grid witnesses"
            if failed
            else "requested target reached"
            if passing == cap
            else "end of search window or source rod branch",
        )
    if extra:
        write_table(root / "mesh/refined_transitions.csv.gz", extra)
    save(
        root / "mesh/refined_transitions.json",
        dict(
            cells_per_module=16,
            axial_surface_spacing_mm=0.25,
            candidate_M6_mass_change_g=change * 1000,
            maximum_extension_from_coarse_deg=12,
            extra_checked_rows=len(extra),
            paths=results,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=RESULTS)
    run(p.parse_args().results)
