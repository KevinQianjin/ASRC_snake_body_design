"""Re-equilibrate screened-boundary winch commands with the candidate guide mass and a finer rod."""

import argparse
from pathlib import Path
import numpy as np
from study_context import CANDIDATE, NAMES, RESULTS, read, read_csv, save
from free_space import PATHS, coordinates
from pose_map import axis, equilibrate, is_rope_domain_error
from replay import plant
from closed_loop_cycle import FeedbackDrive
from pitch_reference import pointing, angle_between, position
from spatial_model import refine_seed


def candidate_mass(rod):
    change = (
        sum(
            sum(group.values())
            for group in read(CANDIDATE / "geometry_check.json")[
                "mass_delta_g"
            ].values()
        )
        / 1000
    )
    base = rod.base
    bare = base.planar.bare_mass.copy()
    bare[5] += change
    base.planar.bare_mass = bare
    base.mass = base.planar.mass = np.repeat(
        (bare + base.planar.rope_module_mass) / base.sub, base.sub
    )
    base.planar.weight_after = (
        np.cumsum(base.mass[::-1])[::-1] - base.mass + base.payload
    )
    return change


def saved_state(name, angle, angles, geometry, rod, drive):
    rows = read_csv(angles / (name + ".csv.gz"))
    ok = [r for r in rows if r["pass_ideal"] == "True" and r["leg"] != "return"]
    with np.load(angles / (name + "_states.npz")) as data:
        near = min(ok, key=lambda r: abs(float(r["command_deg"]) - angle))
        z = data["z"][int(near["index"])]
    R = np.array([float(near[n + "_command_mm"]) for n in NAMES]).reshape(3, 4) / 1000
    if abs(float(near["command_deg"]) - angle) < 1e-7:
        return z, R
    match = next(
        r
        for r in read_csv(geometry / (name + "_probes.csv.gz"))
        if float(r["command_deg"]) == angle and r["out_pass"] == "True"
    )
    drive.stability(z, R, drive.force(z, R))
    R = np.array([float(match[n + "_command_mm"]) for n in NAMES]).reshape(3, 4) / 1000
    z = equilibrate(rod, drive, z, R)
    if z is None:
        raise ValueError("Saved geometry probe did not replay")
    return z, R


def fixed(rod, z, R, coarse_axis, target):
    drive = FeedbackDrive(rod)
    try:
        drive.stability(z, R, drive.force(z, R))
        diag = {}
        zn = equilibrate(rod, drive, z, R, diag)
        if zn is None:
            return None, dict(
                converged=False, reason=diag.get("reason", "equilibrium convergence")
            )
        t = drive.force(zn, R)
        return zn, dict(
            converged=True,
            axis=pointing(rod, zn),
            error_deg=angle_between(pointing(rod, zn), target),
            change_from_archived_axis_deg=angle_between(pointing(rod, zn), coarse_axis),
            base_axis_separation_deg=angle_between(pointing(rod, zn), axis(0, 20)),
            position_mm=position(rod, zn),
            minimum_tangent=drive.stability(zn, R, t),
            residual=rod.residual(drive.energy(zn, R)[1]),
            geometry_margin=rod.geometry_constraints(zn).min(),
            min_tension_N=t.min(),
            max_tension_N=t.max(),
            tensions_N=t.ravel(),
        )
    except ValueError as exc:
        if not is_rope_domain_error(exc):
            raise
        return None, dict(converged=False, reason=str(exc))


def run(root, out, names):
    source, _ = plant()
    archive_drive = FeedbackDrive(source)
    coarse, _ = plant()
    fine, _ = plant(cells=16)
    m = candidate_mass(coarse)
    if candidate_mass(fine) != m:
        raise ValueError("Inconsistent module mass change")
    for name in names:
        g = read(root / "geometry" / (name + ".json"))["paths"][name]
        a = g["last_contiguous_screened_deg"]
        if a is None:
            continue
        z, R = saved_state(
            name, a, root / "angles", root / "geometry", source, archive_drive
        )
        mode, fixed_axis, _, _ = PATHS[name]
        target = axis(*coordinates(mode, fixed_axis, a))
        original = pointing(source, z)
        c, cr = fixed(coarse, z, R, original, target)
        _, fr = fixed(
            fine,
            refine_seed(c if c is not None else z, coarse.base, fine.base),
            R,
            original,
            target,
        )
        result = dict(
            path=name,
            command_deg=a,
            M6_mass_change_g=m * 1000,
            head_mass_g=1000 * coarse.payload,
            archived_axis_error_deg=angle_between(original, target),
            archive_axis=original,
            command_mm=1000 * R.ravel(),
            coarse_candidate=cr,
            fine_candidate=fr,
        )
        if cr["converged"] and fr["converged"]:
            result.update(
                axis_change_deg=angle_between(cr["axis"], fr["axis"]),
                head_position_change_mm=np.linalg.norm(
                    np.subtract(cr["position_mm"], fr["position_mm"])
                ),
                maximum_tension_change_N=np.max(
                    abs(np.subtract(cr["tensions_N"], fr["tensions_N"]))
                ),
            )
        save(out / (name + ".json"), result)
        print(name, a, fr.get("error_deg", fr.get("reason")), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("paths", nargs="*", metavar="PATH")
    p.add_argument("--results", type=Path, default=RESULTS)
    a = p.parse_args()
    run(a.results, a.results / "mesh", a.paths or PATHS)
