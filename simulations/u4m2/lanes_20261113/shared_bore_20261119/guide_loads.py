"""Export simultaneous rope forces on the eight guide stations and the shared bore."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from shared_bore import ARCHIVE, RAYS, load_rod, solve
from bellmouth_model import inspect_routing

STATIONS = [(m, z) for m in ("M5", "M6") for z in (-24, -12, 12, 24)]


def cad_axes(vector):
    """Rod local x distal, y up and z right to the existing part CAD frame."""
    return np.array([-vector[2], vector[1], vector[0]])


def section_wrench(left, right, lane_offset, tangents, tension):
    """Rope on both bore walls together, about the shared disk centre, in joint rod axes."""
    t0, t1 = tangents
    return tension * np.array(
        [t1 - t0, np.cross(right + lane_offset, t1) - np.cross(left + lane_offset, t0)]
    )


def verify_wrench(left, right, off, profiles, tension, reference):
    """Move the common throat in six directions while holding both guides fixed."""
    numeric = np.zeros((2, 3))
    for mode, h in enumerate((2e-4, 2e-5)):
        for k, axis in enumerate(np.eye(3)):
            lengths = []
            for sign in (-1, 1):
                if mode == 0:
                    ends = np.array([left, right]) - sign * h * axis
                else:
                    R = Rotation.from_rotvec(sign * h * axis).as_matrix()
                    ends = (np.array([left, right]) + off) @ R - off
                lengths.append(solve(*ends, profiles, 0.15)[1]["length_mm"])
            numeric[mode, k] = -tension * (lengths[1] - lengths[0]) / (2 * h)
    return dict(
        analytic_rod_axes=reference.tolist(),
        finite_difference_rod_axes=numeric.tolist(),
        force_error_N=float(np.linalg.norm((numeric - reference)[0])),
        moment_error_Nmm=float(np.linalg.norm((numeric - reference)[1])),
    )


def record(rod, profiles, z, T, free, check_work=False):
    _, source_holes = inspect_routing(rod, z, T)
    _, _, detail = rod.evaluate(z, T, detail=True)
    frame, p = detail["frames"], detail["points"]
    c, n = 5 * rod.sub, rod.sub
    i_joint = [c - 3 * n // 8, c - n // 4, c + n // 4, c + 3 * n // 8]
    fi = frame[c]
    joint = np.zeros((4, 2, 3))
    shared = {}
    residuals = []
    work = None
    if free:
        for i, ray in enumerate(RAYS):
            off = rod.offsets3[2, i]
            points = p[i_joint] + frame[i_joint] @ off
            left, right = ((points[1:3] - p[c]) @ fi - off) * 1000
            _, s = solve(left, right, profiles, 0.15)
            tangents = np.array(s["endpoint_directions"])
            tension = T[2, i]
            chord1, chord2 = points[0] - points[1], points[3] - points[2]
            shared["M5", ray] = tension * (
                chord1 / np.linalg.norm(chord1) + fi @ tangents[0]
            )
            shared["M6", ray] = tension * (
                chord2 / np.linalg.norm(chord2) - fi @ tangents[1]
            )
            wrench = section_wrench(left, right, off * 1000, tangents, tension)
            joint[i] = [cad_axes(v) for v in wrench]
            independent_force = -tension * np.array(s["wall_on_rope_normal_sum_per_N"])
            residuals.append(np.linalg.norm(wrench[0] - independent_force))
            if check_work and ray == "up":
                work = verify_wrench(left, right, off * 1000, profiles, tension, wrench)
    hs = []
    keys = []
    for h in source_holes:
        module, station, family, ray = (
            h["module"],
            int(h["station_z_mm"]),
            h["set"],
            h["ray"],
        )
        node = c + (station - 48 if module == "M5" else station + 48) * n // 96
        force_base = np.array(h["force_base_n"])
        if free and family == "C" and (module, station) in (("M5", 24), ("M6", -24)):
            force_base = shared[module, ray]
        f = cad_axes(frame[node].T @ force_base)
        lever = cad_axes(rod.offsets3["ABC".index(family), RAYS.index(ray)]) * 1000
        hs.append([f, np.cross(lever, f)])
        keys.append((module, station, family, ray))
    return keys, np.array(hs), joint, max(residuals, default=0.0), work


def export(states, out):
    _, base, profiles = load_rod()
    rows, holds, holes, joints, wall_res = [], [], [], [], []
    work = None
    keys = None
    with (ARCHIVE / "equilibria.json").open() as f:
        meta = json.load(f)
    with (
        np.load(states, allow_pickle=False) as new,
        np.load(ARCHIVE / "equilibria_states.npz", allow_pickle=False) as old,
    ):
        for i, z, T in zip(new["hold_id"], new["z"], new["tensions_n"], strict=True):
            i = int(i)
            k0, prior, _, _, _ = record(
                base, profiles, old["z"][i], old["tensions_n"][i], False
            )
            k1, current, joint, residual, virtual = record(
                base, profiles, z, T, True, i == 64
            )
            if k0 != k1 or (keys is not None and keys != k1):
                raise ValueError("Guide-hole labels or order changed")
            keys = k1
            if virtual is not None:
                work = virtual
            for m, station in STATIONS:
                inds = [j for j, k in enumerate(keys) if k[:2] == (m, station)]
                total = current[inds].sum(axis=0)
                delta = total - prior[inds].sum(axis=0)
                row = dict(
                    hold=i,
                    phase=meta[i]["phase"],
                    module=m,
                    station_mm=station,
                    holes=len(inds),
                )
                for tag, v in zip(("force", "moment"), total):
                    unit = "N" if tag == "force" else "Nmm"
                    row.update(
                        {f"{tag}_{axis}_{unit}": float(a) for axis, a in zip("xyz", v)}
                    )
                row.update(
                    force_norm_N=np.linalg.norm(total[0]),
                    moment_norm_Nmm=np.linalg.norm(total[1]),
                    force_change_from_archive_N=np.linalg.norm(delta[0]),
                    moment_change_from_archive_Nmm=np.linalg.norm(delta[1]),
                )
                rows.append(row)
            holds.append(i)
            holes.append(current)
            joints.append(joint)
            wall_res.append(residual)
    if not holds:
        raise ValueError("No solved states supplied")
    out.mkdir(exist_ok=True, parents=True)
    with (out / "guide_station_loads.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    np.savez_compressed(
        out / "guide_hole_loads.npz",
        hold=holds,
        hole_module=[k[0] for k in keys],
        station_mm=[k[1] for k in keys],
        family=[k[2] for k in keys],
        ray=[k[3] for k in keys],
        joint_rays=RAYS,
        hole_wrench_CAD=holes,
        joint_wall_wrench_CAD=joints,
    )

    def extreme(items, name):
        r = max(items, key=lambda row: row[name])
        return {k: r[k] for k in ("hold", "phase", "module", "station_mm", name)}

    target_rows = [
        r for r in rows if r["module"] == "M5" and abs(r["station_mm"]) == 12
    ]
    report = dict(
        holds=len(holds),
        simultaneous_stations=len(rows),
        hole_records=len(holds) * len(keys),
        axes="Local to the deformed station or shared joint, in CAD x,y,z. Force on the hardware in N, moment about its centre in N mm.",
        maximum_wall_force_normal_check_error_N=max(wall_res),
        joint_virtual_work_at_hold_64_C_up=work,
        peak_individual_hole_force_N=float(
            np.linalg.norm(np.array(holes)[:, :, 0], axis=-1).max()
        ),
        peak_simultaneous_joint_wall_force_N=float(
            np.linalg.norm(np.sum(joints, axis=1)[:, 0], axis=-1).max()
        ),
        maximum_station_force=extreme(rows, "force_norm_N"),
        maximum_station_moment=extreme(rows, "moment_norm_Nmm"),
        maximum_station_force_change=extreme(rows, "force_change_from_archive_N"),
        maximum_station_moment_change=extreme(rows, "moment_change_from_archive_Nmm"),
        maximum_M5_inner_station_force_change=extreme(
            target_rows, "force_change_from_archive_N"
        ),
        maximum_M5_inner_station_moment_change=extreme(
            target_rows, "moment_change_from_archive_Nmm"
        ),
    )
    (out / "guide_load_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(export(a.states, a.out), indent=2))
