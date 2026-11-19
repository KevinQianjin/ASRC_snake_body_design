"""Extract posed guide holes and paired land loads from the four installed M5 simulations."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from shell import Mesh, rotation
from study import CASES, archive_loads, save


def extract(mesh, checkpoint, sample, variant, source):
    tip = checkpoint["body_D1"]
    np.testing.assert_allclose(tip[:3], sample["tip_displacement_mm"], atol=1e-8)
    np.testing.assert_allclose(rotation(tip[3:])[0], sample["tip_rotation"], atol=1e-8)
    stations = []
    for station in source["stations_detail"]:
        z = station["station_mm"]
        transform = checkpoint[f"body_G{z:+}"]
        origin = transform[:3] + [0.0, 0.0, z]
        frame = rotation(transform[3:])[0]
        archived_frame = station["guide_frame_in_proximal_axes"]
        holes = []
        for hole in station["holes"]:
            offset = hole["offset_in_guide_mm"]
            archived = station["centre_in_proximal_axes_mm"] + archived_frame @ offset
            solved = origin + frame @ offset
            holes.append(
                dict(
                    rope_set=hole["rope_set"],
                    ray=hole["ray"],
                    solved_centre_mm=solved,
                    archived_centre_mm=archived,
                    change_mm=solved - archived,
                )
            )
        lands = []
        for land in sample["lands"]:
            if land["station_mm"] != z:
                continue
            i = mesh.theta.tolist().index(land["rib_deg"])
            Rland = frame if variant == "bond" else rotation(checkpoint[f"body_L{i}_{z}"][-3:])[0]
            relative = np.degrees(Rotation.from_matrix(frame.T @ Rland).as_rotvec())
            np.testing.assert_allclose(np.linalg.norm(relative), land["relative_rotation_deg"], atol=1e-7)
            np.testing.assert_allclose(
                relative @ mesh.normals[i], land["inplane_rotation_deg"], atol=1e-7
            )
            pivot = origin + frame @ (mesh.radial[i] * mesh.land_centres[z])
            lands.append(
                dict(
                    rib_deg=land["rib_deg"],
                    centre_mm=pivot,
                    rotation_vector_in_guide_deg=relative,
                    force_on_rib_in_guide_N=frame.T @ land["force_N"],
                    moment_on_rib_in_guide_Nmm=frame.T @ land["land_moment_Nmm"],
                    socket_travel_3d_mm=land["socket_travel_3d_mm"],
                )
            )
        if len(lands) != 4 or len(holes) != 8:
            raise ValueError("Incomplete installed guide")
        # Static equilibrium of the guide about its own moving centre, in guide axes.
        bore_force = np.array([frame.T @ h["force_in_proximal_axes_N"] for h in station["holes"]])
        bore_offsets = np.array([h["offset_in_guide_mm"] for h in station["holes"]])
        land_force = np.array([land["force_on_rib_in_guide_N"] for land in lands])
        land_offsets = np.array([frame.T @ (land["centre_mm"] - origin) for land in lands])
        land_moment = np.array([land["moment_on_rib_in_guide_Nmm"] for land in lands])
        force_error = np.linalg.norm(land_force.sum(0) - bore_force.sum(0))
        moment_error = np.linalg.norm(
            (np.cross(land_offsets, land_force) + land_moment).sum(0)
            - np.cross(bore_offsets, bore_force).sum(0)
        )
        if force_error > 0.003 or moment_error > 0.3:
            raise ValueError(f"Guide reaction balance failed for {variant} at {z:+} mm")
        stations.append(
            dict(
                station_mm=z,
                centre_mm=origin,
                frame_in_proximal_axes=frame,
                centre_change_mm=origin - station["centre_in_proximal_axes_mm"],
                orientation_change_deg=np.degrees(
                    Rotation.from_matrix(archived_frame.T @ frame).magnitude()
                ),
                land_to_bore_force_error_N=force_error,
                land_to_bore_moment_error_Nmm=moment_error,
                holes=holes,
                lands=lands,
            )
        )
    return stations


def bore_comparisons(cases):
    by_record = {}
    for case in cases:
        holes = {
            (station["station_mm"], hole["rope_set"], hole["ray"]): hole
            for station in case["stations"]
            for hole in station["holes"]
        }
        by_record.setdefault(case["record"], {})[case["variant"]] = holes
    comparisons = []
    for record, mounts in by_record.items():
        bond, seat = mounts["bond"], mounts["point"]
        if len(bond) != 16 or bond.keys() != seat.keys():
            raise ValueError("Inconsistent installed bore IDs")
        peaks = {}
        for key, bonded_hole in bond.items():
            rotating_hole = seat[key]
            differences = {
                "seat_vs_bond": rotating_hole["solved_centre_mm"] - bonded_hole["solved_centre_mm"],
                "seat_vs_source": rotating_hole["change_mm"],
                "bond_vs_source": bonded_hole["change_mm"],
            }
            for label, vector in differences.items():
                distance = np.linalg.norm(vector)
                if label not in peaks or distance > peaks[label]["distance_mm"]:
                    z, rope_set, ray = key
                    peaks[label] = dict(station_mm=z, rope_set=rope_set, ray=ray, distance_mm=distance)
        comparisons.append(dict(record=record, peaks=peaks))
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--coarser", type=Path, help="Include bore displacement peaks from a coarser export"
    )
    args = parser.parse_args()
    sources = archive_loads()
    cases = []
    mesh = None
    for record in CASES:
        for variant in ("bond", "point"):
            name = f"{variant}_{record}"
            data = json.loads((args.results / f"{name}.json").read_text())
            sample = data["samples"][-1]
            if not data["completed"] or sample["fraction"] != 1.0:
                raise ValueError(f"Missing full-load endpoint for {name}")
            if mesh is None:
                mesh = Mesh(data["mesh"]["max_triangle_area_mm2"])
                with np.load(args.cache / "mesh.npz") as saved:
                    if not np.array_equal(saved["x"], mesh.x) or not np.array_equal(saved["t"], mesh.t):
                        raise ValueError("The checkpoint mesh differs from the recorded mesh")
            if data["mesh"] != mesh.info:
                raise ValueError("The mounted cases must share one mesh")
            with np.load(args.cache / name / "1.000000000.npz") as state:
                stations = extract(mesh, state, sample, variant, sources[record])
            cases.append(dict(record=record, variant=variant, stations=stations))
    result = dict(
        mesh=mesh.info,
        reference_frame="Fixed proximal CAD axes, straight M5 centre at the origin.",
        change_reference="Local posed hole centre minus the whole-arm archived hole centre at the same end pose.",
        maximum_bore_displacements=bore_comparisons(cases),
        cases=cases,
    )
    if args.coarser is not None:
        coarse = json.loads(args.coarser.read_text())
        previous = coarse["maximum_bore_displacements"]
        if coarse["mesh"]["max_triangle_area_mm2"] <= mesh.info["max_triangle_area_mm2"]:
            raise ValueError("The reference export must use a coarser mesh")
        if [r["record"] for r in previous] != list(CASES) or coarse["reference_frame"] != result[
            "reference_frame"
        ]:
            raise ValueError("The reference export must use matching pose IDs and axes")
        result["coarser_bore_comparison"] = dict(mesh=coarse["mesh"], maximum_bore_displacements=previous)
    save(args.out, result)


if __name__ == "__main__":
    main()
