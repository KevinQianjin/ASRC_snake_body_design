"""Compare the coupon, common-guide solutions and assembled CAD at their recorded resolutions."""

import argparse
import json
from pathlib import Path

import numpy as np
from bench_inputs import HERE, PREVIOUS


def read(p):
    return json.loads(p.read_text())


def summarize(folder):
    cases = ("bend67.5", "bend0", "146", "141", "47", "64")
    levels = ("middle", "fine")
    mesh = {
        v: {c: read(folder / f"coupled_{v}/{c}.json") for c in cases} for v in levels
    }
    cadrows = read(folder / "coupled_cad_fine.json")["stations"]
    midrows = read(folder / "coupled_cad_middle_targets.json")["stations"]
    refined_rows = {
        (r["case"], r["station"]): r
        for name in (
            "coupled_cad_refined_targets.json",
            "coupled_cad_refined_transverse.json",
        )
        for r in read(folder / name)["stations"]
    }
    prior = read(PREVIOUS / "results/corrected_edge0p15.json")["stations"]
    size = read(folder / "hub_sweep_original_pose.json")["rows"]
    parsed = []
    all_sites = []
    changes = []
    for c in cases:
        middle, fine = (mesh[v][c] for v in levels)
        if any(t["status"] != "converged" for t in (middle, fine)):
            raise ValueError(f"Missing converged solution for {c}")
        ff = {(s["station"], s["rib_deg"]): s for s in fine["last_sites"]}
        mf = {(s["station"], s["rib_deg"]): s for s in middle["last_sites"]}
        dr = [
            np.linalg.norm(np.subtract(v["force_world_N"], mf[k]["force_world_N"]))
            for k, v in ff.items()
        ]

        def mesh_value(v):
            return max(
                x["maximum_bore_shift_mm"]
                for x in v["guide_changes_from_ideal"].values()
            )

        item = dict(
            case=c,
            finer_shell_area_mm2=fine["shell_area_mm2"],
            stations={},
            interface_iterations_fine=fine["iterations"],
            iterations_middle=middle["iterations"],
            max_site_force_change_from_ideal_N=fine["maximum_site_force_change_N"],
            peak_bore_shift_from_ideal_mm=mesh_value(fine),
            maximum_bearing_force_N=max(
                np.linalg.norm(v["force_world_N"]) for v in ff.values()
            ),
            fine_local_force_balance_N=max(
                v["contact"]["force_residual_N"] for v in ff.values()
            ),
            peak_strain=max(
                v["contact"]["peak_tensile_principal_strain"] for v in ff.values()
            ),
            peak_nodal_pressure_MPa=max(
                v["contact"]["peak_nodal_pressure_MPa"] for v in ff.values()
            ),
            medium_to_fine_max_site_force_change_N=max(dr),
            medium_to_fine_absolute_bore_shift_difference_mm=abs(
                mesh_value(fine) - mesh_value(middle)
            ),
            maximum_ideal_source_reaction_reconstruction_error_N=fine[
                "maximum_reconstructed_force_error_N"
            ],
            translation_mismatch_mm=fine["history"][-1][
                "maximum_translation_mismatch_mm"
            ],
            moment_mismatch_Nmm=fine["history"][-1]["maximum_moment_mismatch_Nmm"],
            peak_shell_ring_moment_balance_Nmm=max(
                v["shell_ring_moment_balance_Nmm"] for v in ff.values()
            ),
        )
        if c.startswith("bend"):
            item.update(
                ideal_pure_bend_couple_Nmm=fine["baseline_fixture_couple_Nmm"],
                coupled_pure_bend_couple_Nmm=fine["fixture_couple_Nmm"],
                end_position_change_at_same_bend_mm=fine["end_translation_change_mm"],
            )
        for z in (-12, 12):
            row = next(r for r in cadrows if r["case"] == c and r["station"] == z)
            pr = next(r for r in prior if r["case"] == c and r["station"] == z)
            local = row["relieved"]["nearest_unintended"]
            info = dict(
                original=row["original"]["nearest_unintended"],
                relieved=local,
                closest_remaining_hub=next(
                    (
                        r
                        for r in sorted(
                            row["near_nonlocal_pairs"], key=lambda q: q["gap_mm"]
                        )
                        if r["variant"] == "relieved"
                    ),
                    None,
                ),
                guide_bore_change_mm=fine["guide_changes_from_ideal"][str(z)][
                    "maximum_bore_shift_mm"
                ],
                old_single_fit_residual_mm=pr["rigid_fit"][
                    "maximum_incompatibility_mm"
                ],
                intended_overlap_mm3=0.0
                if row["intended_bearing"] is None
                else row["intended_bearing"]["overlap_mm3"],
            )
            if (c, z) in refined_rows:
                refined = refined_rows[(c, z)]
                info["tighter_surface_nearest_mm"] = {
                    v: refined[v]["nearest_unintended"]["gap_mm"]
                    for v in ("original", "relieved")
                }
                info["tighter_surface_change_mm_at_same_equilibrium"] = {
                    v: info["tighter_surface_nearest_mm"][v]
                    - row[v]["nearest_unintended"]["gap_mm"]
                    for v in ("original", "relieved")
                }
            if c in ("bend67.5", "146"):
                mr = next(r for r in midrows if r["case"] == c and r["station"] == z)
                info["medium_to_fine_nearest_change_mm"] = {
                    v: row[v]["nearest_unintended"]["gap_mm"]
                    - mr[v]["nearest_unintended"]["gap_mm"]
                    for v in ("original", "relieved")
                }
            item["stations"][str(z)] = info
        for k, v in ff.items():
            m = mf[k]["contact"]
            f = v["contact"]
            rel = lambda val: abs(f[val] - m[val]) / max(abs(m[val]), 1e-12)
            changes.append(
                (rel("peak_tensile_principal_strain"), rel("peak_nodal_pressure_MPa"))
            )
        all_sites.extend(ff.values())
        parsed.append(item)
    coupon = {}
    for level in ("middle", "fine", "finer"):
        fp = folder / f"coupon_{level}.json"
        if fp.is_file():
            coupon[level] = read(fp)["peak_pairs"]
    cp = {}
    for i, r in enumerate(coupon["fine"]):
        out = dict(
            fine_travel_mm=r["loaded_reversal_travel_mm"],
            fine_strain=r["forward_peak_strain"],
            fine_peak_pressure_MPa=r["forward_peak_pressure_MPa"],
        )
        if "finer" in coupon:
            high = coupon["finer"][i]
            out.update(
                finer_travel_mm=high["loaded_reversal_travel_mm"],
                relative_travel_mesh_change=abs(
                    high["loaded_reversal_travel_mm"] / r["loaded_reversal_travel_mm"]
                    - 1
                ),
                finer_peak_strain=high["forward_peak_strain"],
                finer_peak_pressure_MPa=high["forward_peak_pressure_MPa"],
            )
        cp[r["target"]] = out
    return dict(
        covered_cases=len(cases),
        coupled_sites_per_mesh=len(all_sites),
        fixture_cases=parsed,
        strain_mesh_5pct_passes=int(np.count_nonzero(np.array(changes)[:, 0] < 0.05)),
        pressure_mesh_5pct_passes=int(np.count_nonzero(np.array(changes)[:, 1] < 0.05)),
        simultaneous_contact_mesh_5pct_passes=int(
            np.sum(np.max(changes, axis=1) < 0.05)
        ),
        nominal_cad_interference_unintended=sum(
            r["overlap_mm3"] > 1e-7
            for s in cadrows
            for zone in ("near_local_pairs", "near_nonlocal_pairs")
            for r in s[zone]
            if (
                zone == "near_nonlocal_pairs"
                or r["kind"] not in ("threaded_cap", "shoulder_pin")
            )
            and r["variant"] in ("both", "relieved")
        ),
        maximum_intended_steel_web_mesh_overlap_mm3=max(
            s["intended_bearing"]["overlap_mm3"] for s in cadrows
        ),
        maximum_join_band_difference_mm=max(
            s["largest_difference_in_join_band_mm"]
            for s in read(folder / "coupled_cad_fine.json")["join_checks"]
        ),
        minimum_station_to_station_envelope_gap_mm=min(
            s["station_envelope_gap_mm"] for s in cadrows
        ),
        unchanged_global_bend_hub_size_comparison=size,
        coupon_peak_comparison=cp,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=HERE / "results")
    a = p.parse_args()
    (a.results / "summary.json").write_text(
        json.dumps(summarize(a.results), indent=2) + "\n"
    )
