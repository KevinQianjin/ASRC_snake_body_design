"""Summarize complete saved-hold geometry, tightened mesh, and the selected fixed-winch replays."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def summarize(folder):
    base = json.loads((folder / "shared_217.json").read_text())
    rr = base["records"]
    fine = json.loads((folder / "refined_six.json").read_text())["records"]
    rows = {(r["hold"], r["ray"]): r for r in rr}
    if (
        set(rows)
        != {(i, n) for i in range(217) for n in ("up", "right", "down", "left")}
        or len(rr) != 868
    ):
        raise ValueError("Incomplete or duplicate shared-bore state")
    key = lambda r: (r["hold"], r["ray"])
    out = []
    for q in fine:
        r = rows[key(q)]
        out.append(
            dict(
                hold=q["hold"],
                ray=q["ray"],
                length_change_mm=q["length_mm"] - r["length_mm"],
                interface_shift_mm=float(
                    np.linalg.norm(
                        np.subtract(
                            q["interface_transverse_mm"], r["interface_transverse_mm"]
                        )
                    )
                ),
                wrap_change_deg=float(
                    np.degrees(q["absolute_wrap_rad"] - r["absolute_wrap_rad"])
                ),
                clearance_change_mm=max(
                    abs(
                        r["cad"][m]["minimum_clearance_mm"]
                        - q["cad"][m]["minimum_clearance_mm"]
                    )
                    for m in ("M5", "M6")
                ),
            )
        )

    def limits(fn):
        lo = min(rr, key=fn)
        hi = max(rr, key=fn)
        return dict(
            minimum=fn(lo), min_hold_ray=key(lo), maximum=fn(hi), max_hold_ray=key(hi)
        )

    geom = dict(
        held_poses=base["cases"],
        route_checks=len(rr),
        two_end_CAD_checks=2 * len(rr),
        unique_guide_to_guide_geometries=base["unique_geometry_ropes"],
        interface_radius_mm=limits(
            lambda r: float(np.linalg.norm(r["interface_transverse_mm"]))
        ),
        free_minus_old_mm=limits(lambda r: r["free_minus_old_length_mm"]),
        total_absolute_wrap_deg=limits(
            lambda r: float(np.degrees(r["absolute_wrap_rad"]))
        ),
        assumed_mu015_ratio=limits(
            lambda r: r["sliding_high_over_low_by_assumed_mu"]["0.15"]
        ),
        assumed_mu030_ratio=limits(
            lambda r: r["sliding_high_over_low_by_assumed_mu"]["0.3"]
        ),
        min_design_margin_deg=limits(lambda r: min(r["design_margins_deg"])),
        cad_min_mm=limits(
            lambda r: min(s["minimum_clearance_mm"] for s in r["cad"].values())
        ),
        cad_failures_outside_minus_0005_mm=sum(
            s["minimum_clearance_mm"] < -0.005 for r in rr for s in r["cad"].values()
        ),
        sampled_negative_clearance_end_checks=sum(
            s["minimum_clearance_mm"] < 0 for r in rr for s in r["cad"].values()
        ),
        less_than_one_degree_margin=sum(min(r["design_margins_deg"]) < 1 for r in rr),
        max_force_balance_N=max(
            r["force_balance_residual_per_N"] * r["archived_uniform_tension_N"]
            for r in rr
        ),
        max_cone_violation_mm=max(r["max_cone_violation_mm"] for r in rr),
    )
    with (folder / "refinement_comparison.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    result = dict(
        frozen_shared_bore=geom,
        finer_spacing_comparison={
            k: max(abs(v[k]) for v in out)
            for k in (
                "length_change_mm",
                "interface_shift_mm",
                "wrap_change_deg",
                "clearance_change_mm",
            )
        },
    )
    for sub in (8, 16):
        rs = [
            json.loads(p.read_text())
            for p in sorted((folder / f"fixed_winch_{sub}").glob("*.json"))
        ]
        records = []
        for r in rs:
            one = dict(hold=r["hold"], status=r["status"])
            if r["status"] == "converged":
                one.update(
                    head_change_mm=r["head_change_from_archived_8_cell_mm"],
                    yaw_change_deg=r["angle_changes_from_archived_8_cell_deg"][0],
                    elevation_change_deg=r["angle_changes_from_archived_8_cell_deg"][2],
                    max_tension_change_N=r["max_tension_change_N"],
                    minimum_fixed_winch_tangent_eigenvalue=r[
                        "minimum_fixed_winch_tangent_eigenvalue"
                    ],
                    residual=r["trace"][-1]["residual"],
                    min_CAD_gap_mm=min(
                        v["minimum_clearance_mm"]
                        for x in r["shared_paths"]
                        for v in x["cad"].values()
                    ),
                    minimum_design_margin_deg=min(
                        min(x["design_margins_deg"]) for x in r["shared_paths"]
                    ),
                )
            records.append(one)
        result[f"fixed_winch_{sub}"] = records
    a = folder / "fixed_winch_8/64.json"
    b = folder / "fixed_winch_16/64.json"
    if a.exists() and b.exists():
        x, y = [json.loads(p.read_text()) for p in (a, b)]
        if all(r["status"] == "converged" for r in (x, y)):
            result["same_command_8_to_16_record_64"] = dict(
                head_mm=float(
                    np.linalg.norm(np.subtract(y["head_world_mm"], x["head_world_mm"]))
                ),
                angles_deg=np.subtract(
                    y["head_angles_deg"], x["head_angles_deg"]
                ).tolist(),
                max_tension_change_N=float(
                    np.max(abs(np.subtract(x["tensions_N"], y["tensions_N"])))
                ),
            )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    a = p.parse_args()
    d = summarize(a.results)
    (a.results / "summary.json").write_text(json.dumps(d, indent=2) + "\n")
