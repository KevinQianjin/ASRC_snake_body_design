"""Build an offline 3-D viewer with selectable physical rope paths and all twelve step tensions."""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from replay import plant
from length_cycle import FastTank, to_tank
from tension_report import NICE
from transmission import material_path


def simplify(points, tolerance=0.1):
    """Subdivide at the largest polyline-to-chord distance until the display tolerance is met."""
    a, b = points[0], points[-1]
    chord = b - a
    t = np.clip((points - a) @ chord / max(chord @ chord, 1.0e-20), 0.0, 1.0)
    distance = np.linalg.norm(points - (a + t[:, None] * chord), axis=1)
    k = int(np.argmax(distance))
    if distance[k] <= tolerance or k in (0, len(points) - 1):
        return points[[0, -1]]
    return np.vstack(
        (simplify(points[: k + 1], tolerance)[:-1], simplify(points[k:], tolerance))
    )


def build(src):
    with gzip.open(src / "motion_trace.json.gz", "rt") as f:
        trace = json.load(f)
    with np.load(src / "controller_states.npz") as f:
        zs = f["motion_z"]
        T = f["motion_tensions_N"].reshape(-1, 12)
    rod, _ = plant()
    tank = FastTank()
    points = []
    angles = []
    groups = []
    cache = {}
    paths = []
    shape_index = []
    phases = list(dict.fromkeys(r["phase"] for r in trace))
    for z, r in zip(zs, trace, strict=True):
        key = z.tobytes()
        if key not in cache:
            detail = rod.base.evaluate(z, detail=True)[2]
            p = (
                np.vstack((np.zeros(3), detail["points"] + [0.02, 0.0, 0.0])) @ rod.R0.T
            ) * 1000.0
            axis = rod.R0 @ detail["frames"][-1, :, 0]
            ends = rod.endpoints(z[rod.local])
            ropes = []
            for lane, ray in np.ndindex(3, 4):
                route, _, closure, _ = material_path(rod, detail, ends, lane, ray)
                if closure > 1.0e-6:
                    raise ValueError("Discontinuous display rope")
                lab = (simplify(route) + [20.0, 0.0, 0.0]) @ rod.R0.T
                ropes.append(np.rint(10 * lab).astype(int).ravel().tolist())
            cache[key] = (np.vstack((p, p[-1] + 38 * axis)), axis, len(paths))
            paths.append(ropes)
        p, axis, shape = cache[key]
        coord = to_tank(p, 20.0, r["clamp_s_mm"], tank.entry_h)
        points.append(np.round(10 * coord).astype(int).reshape(-1).tolist())
        angles.append(
            [
                round(r["yaw_deg"], 3),
                round(r["elevation_deg"], 3),
                round(
                    r.get(
                        "signed_pitch_deg",
                        float(np.degrees(np.arctan2(axis[1], axis[0]))),
                    ),
                    3,
                ),
                round(r["clearance_mm"] - 1.5, 3),
                round(r["clamp_s_mm"], 2),
            ]
        )
        groups.append(phases.index(r["phase"]))
        shape_index.append(shape)
    event_labels = {
        "right_out": "Right turn · target +175°",
        "left_out": "Left turn · target −175°",
        "pitch_up": "Pitch up · target +90°",
        "pitch_down": "Pitch down · target −90°",
    }
    events = {
        "Loaded start": 0,
        **{
            event_labels.get(ph, NICE[ph]): max(
                i for i, r in enumerate(trace) if r["phase"] == ph
            )
            for ph in phases
        },
    }
    events["Highest rope tension"] = int(np.unravel_index(T.argmax(), T.shape)[0])
    events["Lowest rope tension"] = int(np.unravel_index(T.argmin(), T.shape)[0])
    d = dict(
        points=points,
        loads=np.round(1000 * T).astype(int).tolist(),
        phases=[NICE[k] for k in phases],
        group=groups,
        angles=angles,
        events=events,
        paths=paths,
        shape=shape_index,
    )
    page = Path(__file__).with_name("viewer_template.html").read_text()
    (src / "motion_viewer.html").write_text(
        page.replace(
            '"__ASRC_SIMULATION_DATA__"',
            json.dumps(d, separators=(",", ":"), allow_nan=False),
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    build(p.parse_args().source)
