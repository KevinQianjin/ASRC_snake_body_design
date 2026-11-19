"""Measure coaxial tool-shank access at the seated fasteners in the actual M5 installation order."""

import argparse
import json
from pathlib import Path

from assembly import ZERO, sequence
from clearance import CAD, b, bounds_distance, j, np, read_parts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    parts = read_parts(CAD / "parts")
    body = b.load(CAD / "parts/M5_machined_body.stl")
    installed = [("M5 body", body)]
    rows = []
    probe_length = 70.0
    for z in j.STATIONS:
        for p in sequence(z):
            A, T = p.pose(ZERO)
            if p.family in ("lap_screw", "fork_screw", "arm_screw"):
                ht = 1.88 if p.family == "lap_screw" else 1.94
                radius = 0.46 if p.family == "lap_screw" else 0.55
                tip = T + A @ np.array([0, 0, ht])
                direction = A[:, 2]
            elif p.family in ("shoulder_pin", "threaded_cap"):
                sign = 1 if p.family == "threaded_cap" else -1
                ht = (j.GATE_TOP + 0.46) if sign == 1 else -(j.CHEEK + 0.42)
                tip = T + A @ np.array([j.R_PIVOT, ht, 0])
                direction = sign * A[:, 1]
                radius = 0.50
            else:
                installed.append(
                    (f"{p.label}@{z}", parts[p.name].transform(np.column_stack((A, T))))
                )
                continue
            up = np.eye(3)[np.argmin(abs(direction))]
            e1 = np.cross(up, direction)
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(direction, e1)
            orient = np.column_stack((e1, e2, direction))
            tool = b.cyl(radius, 0.002, probe_length, 96).transform(
                np.column_stack((orient, tip))
            )
            hits = []
            for name, obj in installed:
                if bounds_distance(tool.bounding_box(), obj.bounding_box()) > 0:
                    continue
                hit = tool ^ obj
                if hit.volume() < 1e-7:
                    continue
                dist = (hit.to_mesh64().vert_properties[:, :3] - tip) @ direction
                hits.append(
                    dict(
                        obstacle=name,
                        start_mm=max(0.0, float(dist.min())),
                        end_mm=float(dist.max()),
                    )
                )
            free = min([r["start_mm"] for r in hits], default=probe_length)
            rows.append(
                dict(
                    station=z,
                    part=p.label,
                    radius_mm=radius,
                    unobstructed_length_mm=free,
                    hits=sorted(hits, key=lambda h: h["start_mm"]),
                )
            )
            installed.append(
                (f"{p.label}@{z}", parts[p.name].transform(np.column_stack((A, T))))
            )
            print(z, p.label, round(free, 3), flush=True)
    a.out.mkdir(exist_ok=True, parents=True)
    (a.out / "tool_access.json").write_text(
        json.dumps(
            dict(
                probe_length_mm=probe_length,
                initial_offset_from_head_mm=0.002,
                rows=rows,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
