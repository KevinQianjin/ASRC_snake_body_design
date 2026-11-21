"""Identify the part and witness point that limit rigid tilt about CAD y and z (evening, 20 Nov 2026).

At the bisected first-contact angles of `tilt_bisect.py`, reports the per-part gap and the
nearest points just inside the clear bracket (angle - 0.01 deg) for each variant.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evening_20261119"))
import fcl  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from m6_socket_screen import CAD, deformed_body, gap, load_motion, load_variant, mesh_model, save  # noqa: E402
from m6_tilt import rotation  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--bisect", type=Path, required=True)
p.add_argument("--variant", nargs="+", required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
b = json.loads(a.bisect.read_text())
rod, states, _ = load_motion()
module = trimesh.load_mesh(CAD / "end_bellmouth_v1/M6_lane_anchorC.stl")
variants = {k: Path(v).resolve() for k, v in (s.split("=", 1) for s in a.variant)}
meshes = {k: load_variant(v, b["station_mm"]) for k, v in variants.items()}
bounds = trimesh.util.concatenate([m for q in meshes.values() for m in q.values()]).bounds
reach = np.radians(b["max_angle_deg"]) * np.linalg.norm(np.abs(bounds).max(0))
detail = rod.evaluate(states[b["step"]], detail=True)[2]
body, _, _ = deformed_body(module, b["station_mm"], (bounds[0] - reach, bounds[1] + reach), b["spacing_mm"], rod, detail)
rows = []
for r in b["rows"]:
    if r["variant"] not in meshes or r["first_contact_deg"] is None:
        continue
    axis = "xyz".index(r["axis"][-1])
    ang = r["first_contact_deg"] - np.sign(r["first_contact_deg"]) * 0.01
    R = rotation(axis, ang)
    parts = {}
    for name, m in meshes[r["variant"]].items():
        o = fcl.CollisionObject(mesh_model(m.vertices, m.faces)); o.setTransform(fcl.Transform(R, np.zeros(3)))
        d, hit, pts = gap(body, o)
        parts[name] = dict(gap_mm=d, witness_part_CAD_mm=None if pts is None else pts[1].round(3).tolist(),
                           witness_radius_mm=None if pts is None else float(np.hypot(*pts[1][:2])))
    gov = min(parts, key=lambda k: parts[k]["gap_mm"])
    rows.append(dict(variant=r["variant"], axis=r["axis"], angle_deg=float(ang), governing_part=gov, parts=parts))
    print(r["variant"], r["axis"], round(ang, 3), gov, parts[gov], flush=True)
save(a.out, dict(script="plateau_probe.py", source=a.bisect.name, step=b["step"], station_mm=b["station_mm"], rows=rows))
