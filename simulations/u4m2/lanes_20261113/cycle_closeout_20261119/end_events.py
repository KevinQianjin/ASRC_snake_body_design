"""Check finite rope surfaces at the ends of every motion phase and at both tension extrema."""

import argparse
import csv
import json
from pathlib import Path
import numpy as np

from replay import plant, digest, as_relative
from stations import BODIES
from shared_bore import Body, DESIGN, RAYS, audit, solve
from bellmouth_model import inspect_routing


def check_state(rod, z, T, design, bodies, common):
    """Sample every finite rope end on one solved configuration."""
    rows = []
    ends, _ = inspect_routing(rod.base, z, T, sample=True)
    for r in ends:
        module, end = r["module"], r["end"]
        if r["set"] == "C" and (module, end) in (
            ("M5", "distal"),
            ("M6", "proximal"),
        ):
            continue
        pts = r["curve_cad_mm"]
        sel = pts[np.abs(pts[:, 2]) >= 38.0 - 1e-10]
        gap = bodies[module].signed(sel) - 1.0
        worst = gap.argmin()
        rows.append(
            dict(
                **common,
                module=module,
                end=end,
                rope=r["set"] + "_" + r["ray"],
                route="fixed end",
                tension_N=r["tension_n"],
                minimum_rope_gap_mm=float(gap[worst]),
                design_margin_deg=r["design_margin_deg"],
                samples=len(sel),
                worst_cad_xyz_mm=sel[worst].tolist(),
            )
        )
    for k, (left, right) in enumerate(rod.endpoints(z[rod.local])):
        path, meta = solve(left, right, rod.profiles, rod.step)
        hit = audit(path, RAYS[k], design, bodies)
        for j, (module, end) in enumerate((("M5", "distal"), ("M6", "proximal"))):
            r = hit[module]
            rows.append(
                dict(
                    **common,
                    module=module,
                    end=end,
                    rope="C_" + RAYS[k],
                    route="free shared bore",
                    tension_N=T[2, k],
                    minimum_rope_gap_mm=r["minimum_clearance_mm"],
                    design_margin_deg=np.degrees(rod.profiles[j, 2])
                    - meta["exit_angles_deg"][j],
                    samples=int(r["sample_count"]),
                    worst_cad_xyz_mm=r["worst_cad_xyz_mm"],
                )
            )
    return rows


def run(src):
    with (src / "rope_tensions_at_events.csv").open() as f:
        events = list(csv.DictReader(f))
    design = json.loads((DESIGN / "design.json").read_text())
    bodies = {name: Body(path) for name, path in BODIES.items()}
    rod, _ = plant()
    rows = []
    with np.load(src / "controller_states.npz") as data:
        zs = data["motion_z"]
        ts = data["motion_tensions_N"].reshape(-1, 3, 4)
    for step in sorted(set(int(e["step"]) for e in events)):
        z = zs[step]
        T = ts[step]
        labels = [e["event"] for e in events if int(e["step"]) == step]
        common = dict(step=step, event=" + ".join(labels))
        rows.extend(check_state(rod, z, T, design, bodies, common))
    result = dict(
        source_sha256={as_relative(p): digest(p) for p in BODIES.values()},
        rope_diameter_mm=2.0,
        sampling_mm=0.02,
        rigid_end_depth_mm=10.0,
        allowed_mesh_faceting_mm=0.005,
        minimum_required_design_margin_deg=1.0,
        event_count=len(events),
        distinct_motion_steps=len(set(r["step"] for r in rows)),
        checks=len(rows),
        worst_gap=min(rows, key=lambda r: r["minimum_rope_gap_mm"]),
        smallest_design_margin=min(rows, key=lambda r: r["design_margin_deg"]),
        below_faceting_allowance=sum(
            1 for r in rows if r["minimum_rope_gap_mm"] < -0.005
        ),
        below_design_margin=sum(1 for r in rows if r["design_margin_deg"] < 1.0 - 1e-9),
        rows=rows,
    )
    (src / "rope_end_events.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    print(run(p.parse_args().source)["worst_gap"])
