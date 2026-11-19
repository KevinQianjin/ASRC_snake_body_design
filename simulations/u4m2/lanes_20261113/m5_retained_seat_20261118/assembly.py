"""Sweep an explicit installation sequence against the machined M5 and previously seated parts."""

import argparse
from dataclasses import dataclass
import json
import tempfile
from pathlib import Path

import fcl
from scipy.spatial.transform import Rotation

from clearance import CAD, b, collider, j, np, read_parts

I = np.eye(3)
ZERO = np.zeros(3)


def rz(a):
    return Rotation.from_euler("z", a, degrees=True).as_matrix()


def radial(a):
    return rz(a)[:, 0]


@dataclass
class Part:
    label: str
    family: str
    name: str
    angle: float
    centre: np.ndarray
    pivot: np.ndarray
    axis: str = "z"
    pitch: float = 0.0

    def pose(self, offset, spin=0):
        turn = Rotation.from_euler(self.axis, spin, degrees=True).as_matrix()
        A = rz(self.angle)
        return A @ turn, self.centre + offset + A @ (self.pivot - turn @ self.pivot)


def sequence(z):
    base = np.array([0.0, 0.0, z])
    order = (0, 2, 4, 6, 1, 3, 5, 7) if z < 0 else (1, 3, 5, 7, 0, 2, 4, 6)
    for i in order:
        name = "hub_upper_sector" if i % 2 == 0 else "hub_lower_sector"
        yield Part(f"hub_{i}", "hub", name, 45 * i, base, ZERO)
    for i in range(8):
        a = 45 * i + 22.5
        yield Part(
            f"lap_screw_{i}",
            "lap_screw",
            "lap_screw",
            a,
            base + 9.6 * radial(a),
            ZERO,
            "z",
            0.20,
        )
    for i, a in enumerate(j.ANGLES):
        yield Part(f"fork_{i}", "fork", f"fork_{z:+d}", a, base, ZERO)
    for i, a in enumerate(j.ANGLES):
        yield Part(
            f"fork_screw_{i}",
            "fork_screw",
            "hub_screw",
            a,
            base + rz(a) @ np.array([j.HUB_FASTENER_X, j.FORK_Y, 0]),
            ZERO,
            "z",
            0.25,
        )
    for i, a in enumerate(j.ANGLES):
        for name in ("shoulder_pin", "gate", "threaded_cap"):
            pivot = np.array([j.R_PIVOT, 0, 0])
            yield Part(
                f"{name}_{i}",
                name,
                f"gate_{z:+d}" if name == "gate" else name,
                a,
                base,
                pivot,
                "y",
                0.15 if name == "threaded_cap" else 0.0,
            )
    for i in range(4):
        a = 90 * i
        yield Part(f"arm_{i}", "arm", "rope_arm", a, base, ZERO)
        yield Part(
            f"arm_screw_{i}",
            "arm_screw",
            "hub_screw",
            a,
            base + j.HUB_FASTENER_X * radial(a),
            ZERO,
            "z",
            0.25,
        )


def stages(p, z):
    fam = p.family
    er = radial(p.angle)
    et = rz(p.angle)[:, 1]
    ez = I[:, 2]
    if fam in ("hub", "fork", "arm"):
        lift = 1.4 * np.sign(z) * ez if fam == "hub" else ZERO
        return (
            [(36 * er + lift, 0.0, lift, 0.0), (lift, 0.0, ZERO, 0.0)]
            if np.any(lift)
            else [(36 * er, 0.0, ZERO, 0.0)]
        )
    if fam in ("gate", "shoulder_pin", "threaded_cap"):
        offset = {"gate": 6.3, "shoulder_pin": -9.0, "threaded_cap": 8.4}[fam] * et
        stages = [(30 * er + offset, 0.0, offset, 0.0)]
        if fam == "threaded_cap":
            engage = 1.50 * et
            return stages + [
                (offset, 0.0, engage, 0.0),
                (engage, 360 * 1.50 / 0.15, ZERO, 0.0),
            ]
        return stages + [(offset, 0.0, ZERO, 0.0)]
    high = 3.22 * ez
    feed_angle = round(np.degrees(np.arctan2(p.centre[1], p.centre[0])) / 45) * 45
    inner = 9.8 * radial(feed_angle) - p.centre[:] * np.array([1, 1, 0])
    start = 44 * radial(feed_angle) - p.centre[:] * np.array([1, 1, 0])
    engaged = 1.60 if fam == "lap_screw" else 1.75
    engage = engaged * ez
    return [
        (start + high, 0.0, inner + high, 0.0),
        (inner + high, 0.0, high, 0.0),
        (high, 0.0, engage, 0.0),
        (engage, 360 * engaged / p.pitch, ZERO, 0.0),
    ]


class Survey:
    def __init__(self, parts, body, precision):
        self.parts = parts
        self.geom = {k: collider(v) for k, v in parts.items()}
        self.static = [("M5_body", fcl.CollisionObject(collider(body)), body)]
        self.request = fcl.DistanceRequest()
        self.precision = precision

    def run(self, p, z, stage):
        a, ar, bp, br = stage
        span = float(np.linalg.norm(bp - a))
        rot = abs(br - ar)
        solid = self.parts[p.name]
        query = fcl.CollisionObject(self.geom[p.name])
        bounds = np.array(solid.bounding_box())
        # Radius about the rotation axis by the extrema of the small moving part's box.
        which = (0, 1) if p.axis == "z" else (0, 2)
        radius = np.linalg.norm(
            [
                max(abs(bounds[i] - p.pivot[i]), abs(bounds[i + 3] - p.pivot[i]))
                for i in which
            ]
        )
        travel = span + np.radians(rot) * radius
        min_gap = 1e6
        checked = 0
        closest = None
        unresolved = 0.0
        bad = None
        cache = {}

        def sample(u):
            nonlocal min_gap, checked, closest, bad
            if u in cache:
                return cache[u]
            A, T = p.pose(a + u * (bp - a), ar + u * (br - ar))
            query.setRotation(A)
            query.setTranslation(T)
            near = 1e6
            item = None
            for name, other, obs in self.static:
                res = fcl.DistanceResult()
                d = fcl.distance(query, other, self.request, res)
                if d < near:
                    near = d
                    item = name
                if d < 1e-8:
                    moved = solid.transform(np.column_stack((A, T)))
                    volume = max(0.0, (moved ^ obs).volume())
                    if volume > 1e-7:
                        bad = dict(obstacle=name, volume_mm3=volume, progress=u)
                        break
            near = max(0.0, near)
            checked += 1
            if near < min_gap:
                min_gap = near
                closest = item
            cache[u] = near
            return near

        if travel < 1e-10:
            return dict(samples=0, surface_travel_mm=0)
        sample(0.0)
        sample(1.0)
        # End faces of threaded or seated pairs can intentionally touch. Label unresolved subintervals.
        # A sampled survey first identifies assembly collisions before spending time on fine certification.
        if self.precision == 0 or rot > 0:
            count = max(2, int(np.ceil(max(span / 0.65, rot / 22.5))))
            for u in np.linspace(0, 1, count + 1)[1:-1]:
                if bad:
                    break
                sample(float(u))
            unresolved = travel / count
        else:
            stack = [(0.0, 1.0)]
            while stack and not bad:
                l, h = stack.pop()
                mid = (l + h) / 2
                lower = sample(mid)
                upper_motion = (h - l) * travel / 2
                if lower > upper_motion + 1e-6:
                    continue
                if 2 * upper_motion <= self.precision:
                    unresolved = max(unresolved, 2 * upper_motion)
                    continue
                stack.extend([(l, mid), (mid, h)])
        return dict(
            method="sampled helix"
            if rot > 0
            else (
                "sampled translation"
                if self.precision == 0
                else "distance-bounded translation"
            ),
            samples=checked,
            surface_travel_mm=travel,
            min_sampled_gap_mm=min_gap,
            closest=closest,
            unresolved_interval_max_surface_travel_mm=unresolved,
            intersection=bad,
        )

    def install(self, p, z):
        results = []
        for stage in stages(p, z):
            seg = self.run(p, z, stage)
            seg["from_offset_mm"] = np.asarray(stage[0]).tolist()
            seg["to_offset_mm"] = np.asarray(stage[2]).tolist()
            seg["from_spin_deg"] = stage[1]
            seg["to_spin_deg"] = stage[3]
            results.append(seg)
        A, T = p.pose(ZERO)
        obj = fcl.CollisionObject(self.geom[p.name], fcl.Transform(A, T))
        self.static.append(
            (p.label, obj, self.parts[p.name].transform(np.column_stack((A, T))))
        )
        return dict(
            component=p.label,
            geometry=p.name,
            station=z,
            stages=results,
            passed_samples=all(s.get("intersection") is None for s in results),
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts", type=Path, default=CAD / "parts")
    ap.add_argument(
        "--stations", type=int, nargs="+", default=j.STATIONS, choices=j.STATIONS
    )
    ap.add_argument(
        "--extended-forks",
        action="store_true",
        help="Test the conservative, wider pre-trim fork envelope",
    )
    ap.add_argument(
        "--precision",
        type=float,
        default=0,
        help="0 for survey; otherwise max uncertified interval surface travel, mm",
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    parts = read_parts(a.parts)
    body = b.load(a.parts / "M5_machined_body.stl")
    if a.extended_forks:
        with tempfile.TemporaryDirectory() as scratch:
            for z in j.STATIONS:
                name = f"fork_{z:+d}"
                target = Path(scratch) / (name + ".stl")
                b.export(b.saddle(z, radial_limit=None)[0], target)
                parts[name] = b.load(target)
    survey = Survey(parts, body, a.precision)
    if a.stations == [12]:
        for p in sequence(-12):
            A, T = p.pose(ZERO)
            survey.static.append(
                (
                    p.label + " at -12",
                    fcl.CollisionObject(survey.geom[p.name], fcl.Transform(A, T)),
                    parts[p.name].transform(np.column_stack((A, T))),
                )
            )
    for z in a.stations:
        rows = []
        fn = a.out / f"assembly_{z:+d}.json"
        for p in sequence(z):
            row = survey.install(p, z)
            rows.append(row)
            print(
                z,
                p.label,
                row["passed_samples"],
                [s.get("intersection") for s in row["stages"] if s.get("intersection")],
                flush=True,
            )
            tmp = fn.with_suffix(".part")
            tmp.write_text(
                json.dumps(
                    dict(
                        precision_mm=a.precision,
                        stations_in_order=list(j.STATIONS)
                        if a.stations == [12]
                        else a.stations,
                        extended_fork_envelope=a.extended_forks,
                        parts=rows,
                    ),
                    indent=2,
                )
                + "\n"
            )
            tmp.replace(fn)


if __name__ == "__main__":
    main()
