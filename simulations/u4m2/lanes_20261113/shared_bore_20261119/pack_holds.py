"""Collect per-hold checkpoints without dropping failed or missing states."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from shared_bore import ARCHIVE
from audit_bellmouth_envelope import audit as audit_tank


def tank_envelope(out, metadata):
    """Reuse the archived tank mesh, placements and allowances for the new state vectors."""
    with TemporaryDirectory() as work:
        tmp = Path(work)
        for name in ("design.json", "mass_model.json"):
            (tmp / name).symlink_to((ARCHIVE / name).resolve())
        (tmp / "equilibria_states.npz").symlink_to(
            (out / "rebalanced_states.npz").resolve()
        )
        (tmp / "equilibria.json").write_text(json.dumps(metadata))
        data = audit_tank(tmp, tmp / "envelope")
    data["coverage"]["path"] = "shared_bore_20261119/results/rebalanced_states.npz"
    data["scope"] = (
        "Archived 63 mm front/head envelope, 1.5 mm sampling allowance and source clamp placements, applied to the rebalanced shared-bore states. Actual head, harness and continuous moving geometry require separate checks."
    )
    (out / "tank_envelope.json").write_text(json.dumps(data, indent=2) + "\n")
    return {
        k: data[k]
        for k in (
            "phase_counts",
            "minimum_allowance_adjusted_clearance_mm",
            "clearance_failures",
            "tension_failures",
            "strain_failures",
            "geometry_failures",
        )
    }


def pack(cache, out):
    rows = []
    Z = []
    T = []
    length = []
    command = []
    labels = []
    failures = []
    canonical_hold = {}
    metadata = json.loads((ARCHIVE / "equilibria.json").read_text())
    for i in range(217):
        p = cache / f"{i}.json"
        r = json.loads(p.read_text()) if p.exists() else {"status": "missing"}
        if r["status"] != "converged":
            failures.append(dict(hold=i, status=r["status"], trace=r.get("trace", [])))
            continue
        with np.load(cache / f"{i}.npz") as a:
            Z.append(a["z"])
            T.append(a["tensions_N"])
        length.append(r["rope_lengths_mm"])
        command.append(r["rest_lengths_mm"])
        labels.append(i)
        paths = r["shared_paths"]
        first = canonical_hold.setdefault(r["input_state_sha256"], i)
        result = dict(
            hold=i,
            identical_source_hold=first,
            phase=metadata[i]["phase"],
            max_rest_command_reconstruction_error_mm=r[
                "command_max_reconstruction_error_mm"
            ],
            equilibrium_residual=r["trace"][-1]["residual"],
            min_fixed_winch_eigenvalue=r["minimum_fixed_winch_tangent_eigenvalue"],
            head_change_mm=r["head_change_from_archived_8_cell_mm"],
            yaw_change_deg=r["angle_changes_from_archived_8_cell_deg"][0],
            elevation_change_deg=r["angle_changes_from_archived_8_cell_deg"][2],
            max_tension_change_N=r["max_tension_change_N"],
            minimum_tension_N=float(T[-1].min()),
            maximum_tension_N=float(T[-1].max()),
            min_clearance_mm=min(
                v["minimum_clearance_mm"] for ray in paths for v in ray["cad"].values()
            ),
            min_design_margin_deg=min(min(ray["design_margins_deg"]) for ray in paths),
            max_force_imbalance_N=max(
                ray["tension_N"] * ray["force_balance_residual_per_N"] for ray in paths
            ),
        )
        result.update({f"head_{k}_mm": v for k, v in zip("xyz", r["head_world_mm"])})
        rows.append(result)
    if not rows:
        raise ValueError("No converged checkpoints")
    out.mkdir(exist_ok=True, parents=True)
    with (out / "rebalanced_holds.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    np.savez_compressed(
        out / "rebalanced_states.npz",
        hold_id=labels,
        z=Z,
        tensions_n=T,
        rope_lengths_mm=length,
        winch_rest_lengths_mm=command,
    )
    extrema = {}
    for k in list(rows[0])[3:-3]:
        lo = min(rows, key=lambda r: r[k])
        hi = max(rows, key=lambda r: r[k])
        extrema[k] = dict(
            minimum=lo[k], min_hold=lo["hold"], maximum=hi[k], max_hold=hi["hold"]
        )
    d = dict(
        complete=len(rows) == 217,
        solved=len(rows),
        unique_solved=len(canonical_hold),
        failed_or_missing=failures,
        below_operating_tension_count=sum(r["minimum_tension_N"] < 2.5 for r in rows),
        nonpositive_fixed_winch_tangent_count=sum(
            r["min_fixed_winch_eigenvalue"] <= 0 for r in rows
        ),
        end_CAD_failures_at_minus_0005_mm=0,
        extrema=extrema,
    )
    # Count individual end checks, retaining multiple failures at the same hold if present.
    for i in labels:
        item = json.loads((cache / f"{i}.json").read_text())
        d["end_CAD_failures_at_minus_0005_mm"] += sum(
            end["minimum_clearance_mm"] < -0.005
            for ray in item["shared_paths"]
            for end in ray["cad"].values()
        )
    d["tank_envelope"] = tank_envelope(out, [metadata[i] for i in labels])
    (out / "rebalanced_summary.json").write_text(json.dumps(d, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    pack(a.cache, a.out)
