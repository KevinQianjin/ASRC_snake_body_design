"""Compare P3 measurements on three datums and check the free-pivot assumption against the steel and cheek CAD."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import linprog

from inputs import BENCH, CAD, p3_input
from bench_cad import b, on_pin_frame, RETAINED
from pilot_fit import DEFAULT_CAD, PILOTS, section


def read(p):
    return json.loads(p.read_text())


def pair(states):
    rows = {r["factor"]: r for r in states}
    a, b = rows[1], rows[-1]
    stage = np.array(b["coupon_carriage_spn_mm"]) - a["coupon_carriage_spn_mm"]
    centre = np.array(b["shaft_centre_sp_mm"]) - a["shaft_centre_sp_mm"]
    heads = np.asarray([r.get("head_outer_face_sp_mm", [0.0, 0.0]) for r in (a, b)])
    caps = np.asarray([r.get("cap_outer_face_sp_mm", [0.0, 0.0]) for r in (a, b)])
    # Positive and negative optical faces are at +4.17 and -4.59 relative to the pivot.
    chord = np.diff((4.59 * heads + 4.17 * caps) / (4.17 + 4.59), axis=0)[0]
    return dict(
        stage_reversal_spn_mm=stage.tolist(),
        stage_reversal_mm=float(np.linalg.norm(stage)),
        transverse_reversal_mm=float(np.linalg.norm(stage[:2])),
        shaft_centre_reversal_mm=float(np.linalg.norm(centre)),
        coupon_relative_to_local_shaft_transverse_mm=float(
            np.linalg.norm(stage[:2] - centre)
        ),
        optical_face_chord_reversal_mm=float(np.linalg.norm(chord)),
        coupon_relative_to_optical_chord_transverse_mm=float(
            np.linalg.norm(stage[:2] - chord)
        ),
        shaft_to_chord_reversal_mm=float(np.linalg.norm(centre - chord)),
        peak_clear_shaft_bending_MPa=max(
            r["maximum_clear_shaft_bending_MPa"] for r in (a, b)
        ),
        peak_web_nodal_pressure_MPa=max(r["peak_nodal_pressure_MPa"] for r in (a, b)),
        peak_web_tensile_strain=max(r["peak_tensile_principal_strain"] for r in (a, b)),
    )


def extreme(carriage, metal, direction):
    A = []
    g = []
    for key, (name, (lo, hi)) in PILOTS.items():
        for z in np.linspace(lo + 0.001, hi - 0.001, 5):
            _, h = section(carriage, z, 0.69, 0.77)
            pts, _ = section(metal[key], z, 0.70, 0.74)
            normals = h.equations[:, :2]
            A.extend(normals)
            g.extend(-h.equations[:, 2] - (normals @ pts.T).max(axis=1))
    offsets = []
    for sign in (1.0, -1.0):
        v = linprog(
            sign * direction, A_ub=A, b_ub=g, bounds=[(None, None)] * 2, method="highs"
        )
        if not v.success:
            raise ValueError(v.message)
        offsets.append(v.x)
    return np.stack(offsets)


def hardware(states, base_dir):
    direction = p3_input()[1][:2]
    direction /= np.linalg.norm(direction)
    metal = {
        k: on_pin_frame(b.load(RETAINED / f"parts/{n}.stl"))
        for k, (n, _) in PILOTS.items()
    }
    upper = metal["head"] ^ b.box((-2, -2, 2.935), (2, 2, 4.3))
    bore_region = b.box((-2, -2, 2.94), (2, 2, 3.72))
    result = {}
    for label, path in (
        ("original_1p50", CAD / "parts/pin_carriage.stl"),
        ("candidate_1p46", base_dir / "pin_carriage_bore_1p46.stl"),
    ):
        carriage = b.load(path)
        offsets = extreme(carriage, metal, direction)
        volumes = []
        for pt in offsets:
            volumes.append(
                max(
                    float((carriage ^ v.translate((*pt, 0.0))).volume())
                    for v in metal.values()
                )
            )
        if max(volumes) > 1e-7:
            raise ValueError("Off-axis seating check intersects the delivered hardware")
        by = {r["factor"]: r for r in states["finer_clamped"]}
        stage = [
            np.array(by[f]["coupon_carriage_spn_mm"]) + np.r_[pt, 0.0]
            for f, pt in zip((1.0, -1.0), offsets)
        ]
        swing = np.linalg.norm(stage[1] - stage[0])
        blocked = []
        for row in states["fine_hinged"]:
            # Positive-n land is unloaded beyond the model's hinged midpoint. Its free overhang is straight.
            slope = np.array(row["head_outer_face_sp_mm"]) / (4.17 - 2.935)
            rot = Rotation.from_rotvec(np.r_[-slope[1], slope[0], 0.0]).as_matrix()
            mid = np.array([0.0, 0.0, 2.935])
            posed = upper.transform(np.column_stack((rot, mid - rot @ mid)))
            overlap = posed ^ carriage
            blocked.append(
                dict(
                    factor=row["factor"],
                    outer_head_slope_rad=float(np.linalg.norm(slope)),
                    head_half_cheek_total_overlap_mm3=max(0.0, float(overlap.volume())),
                    overlap_in_cylindrical_land_mm3=max(
                        0.0, float((overlap ^ bore_region).volume())
                    ),
                )
            )
        result[label] = dict(
            seated_centres_source_reverse_sp_mm=offsets.tolist(),
            endpoint_CAD_volumes_mm3=volumes,
            free_parallel_projection_width_mm=float(
                direction @ (offsets[1] - offsets[0])
            ),
            conditional_stage_reversal_including_parallel_seating_mm=float(swing),
            hinged_outer_head_CAD_check=blocked,
        )
    return result


def summarize(results, cad):
    data = {}
    states = {}
    for p in sorted(results.glob("*.json")):
        if not p.name.startswith(("fine", "middle")):
            continue
        study = read(p)
        states[p.stem] = study["states"]
        if not all(r["converged"] for r in study["states"]):
            raise ValueError(f"Unsettled P3 result in {p}")
        data[p.stem] = pair(study["states"])
    rigid = next(
        r
        for r in read(BENCH / "results/coupon_finer.json")["peak_pairs"]
        if r["target"] == "P3"
    )
    allstates = [r for rows in states.values() for r in rows]
    fit = read(results / "pilot_fit.json")
    optics = read(results / "optics.json")
    assembly = read(results / "candidate_assembly.json")
    return dict(
        state_solves=len(allstates),
        reference_rigid_reversal_mm=rigid["loaded_reversal_travel_mm"],
        max_final_force_residual_N=max(
            r["contact_force_residual_N"] for r in allstates
        ),
        minimum_web_gap_mm=min(r["minimum_web_contact_gap_mm"] for r in allstates),
        minimum_dense_cap_counterbore_gap_mm=min(
            r["minimum_dense_cap_counterbore_gap_mm"] for r in allstates
        ),
        maximum_summed_counterbore_load_N=max(
            r["summed_counterbore_normal_load_N"] for r in allstates
        ),
        mesh_and_restraint=data,
        reductions=hardware(states, cad),
        pilot_fit_reduction_percent=100
        * (
            1
            - fit["alternatives"]["1.46"]["on_axis_full_reversal_mm"]
            / fit["alternatives"]["1.50"]["on_axis_full_reversal_mm"]
        ),
        candidate_installation_sampled_poses=sum(
            p["samples"] for p in assembly["installation"]
        ),
        minimum_clear_edge_samples_per_72=min(
            v[k]["clear_edge_samples"] for v in optics["views"] for k in ("head", "cap")
        ),
        minimum_clear_edge_samples_in_each_quadrant=min(
            min(v[k]["clear_samples_by_quadrant"])
            for v in optics["views"]
            for k in ("head", "cap")
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--cad", type=Path, default=DEFAULT_CAD)
    a = p.parse_args()
    s = summarize(a.results, a.cad)
    (a.results / "summary.json").write_text(
        json.dumps(s, indent=2, allow_nan=False) + "\n"
    )
    print(
        s["state_solves"],
        s["reductions"]["candidate_1p46"][
            "conditional_stage_reversal_including_parallel_seating_mm"
        ],
    )
