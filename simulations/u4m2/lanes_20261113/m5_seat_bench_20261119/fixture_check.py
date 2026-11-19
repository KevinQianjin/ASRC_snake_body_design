"""Rigid collision checks for the independent coupon and pin carriages at the prescribed test poses."""

import argparse
from itertools import combinations
import json
from pathlib import Path

import fcl
import numpy as np
from scipy.spatial.transform import Rotation

from bench_inputs import CAD, HERE
from bench_cad import RETAINED, b, carrier_parts, hole, on_pin_frame
from clearance import collider
from assembly import Part, Survey


def fixture(pin_carriage_path=None):
    parts = CAD / "parts"
    moving = {
        n: b.load(parts / f"{n}.stl")
        for n in ("web_coupon", "coupon_carrier", "tab_cover")
    }
    moving["tab_cover_left"] = moving["tab_cover"].mirror((1, 0, 0))
    # Conservative cylindrical bolt heads, smooth shank, and nominal six-sided M2 nut.
    for i, x in enumerate((-6.7, 6.7)):
        moving[f"dowel_{i}"] = hole(1.0, -4.70, 1.30, x, 0)
        for k, y in enumerate((-4.05, 4.05)):
            bolt = b.cyl(1.90, 4, 6) + b.cyl(1.0, -8, 4)
            nut = b.cyl(4 / np.sqrt(3), -7.1, -5.5, 6) - b.cyl(1.015, -7.2, -5.4)
            moving[f"M2_bolt_{i}_{k}"] = bolt.translate((x, y, 0))
            moving[f"M2_nut_{i}_{k}"] = nut.translate((x, y, 0))
    fixed = {"pin_carriage": b.load(pin_carriage_path or parts / "pin_carriage.stl")}
    for n in ("shoulder_pin", "threaded_cap"):
        fixed[n] = on_pin_frame(b.load(RETAINED / f"parts/{n}.stl"))
    return moving, fixed


def exact_intersection(a, bpart):
    return max(0.0, float((a ^ bpart).volume()))


class MotionCheck:
    def __init__(self, moving, fixed):
        self.moving = moving
        self.fixed = fixed
        self.mob = {n: fcl.CollisionObject(collider(s)) for n, s in moving.items()}
        self.fix = {n: fcl.CollisionObject(collider(s)) for n, s in fixed.items()}
        self.intent = {("web_coupon", "shoulder_pin"), ("web_coupon", "threaded_cap")}
        self.maximum_radius = max(
            np.linalg.norm(s.to_mesh64().vert_properties[:, :3], axis=1).max()
            for s in moving.values()
        )
        self.counter = 0
        self.cache = {}
        self.best = None
        self.overlaps = {}
        self.lower_bound = np.inf
        self.unresolved = 0
        self.segments = 0

    def measure(self, R, t):
        key = tuple(np.round(np.r_[R.as_matrix().ravel(), t], 12))
        if key in self.cache:
            return self.cache[key]
        place = fcl.Transform(R.as_matrix(), t)
        best = (np.inf, "", "")
        for n, a in self.mob.items():
            a.setTransform(place)
            for label, bpart in self.fix.items():
                if (n, label) in self.intent:
                    continue
                gap = max(
                    0.0,
                    fcl.distance(a, bpart, fcl.DistanceRequest(), fcl.DistanceResult()),
                )
                best = min(best, (gap, n, label))
                if gap < 1e-7:
                    ov = exact_intersection(
                        self.moving[n].transform(np.column_stack((R.as_matrix(), t))),
                        self.fixed[label],
                    )
                    self.overlaps[n, label] = max(
                        ov, self.overlaps.get((n, label), 0.0)
                    )
        self.counter += 1
        if self.best is None or best[0] < self.best[0]:
            self.best = (*best, R.as_quat().tolist(), t.tolist())
        self.cache[key] = best
        return best

    def segment(self, A, ta, B, tb, depth=0):
        ga = self.measure(A, ta)[0]
        gb = self.measure(B, tb)[0]
        rv = (A.inv() * B).as_rotvec()
        # Any intermediate vertex is at most this far from its nearer endpoint.
        d = (np.linalg.norm(tb - ta) + self.maximum_radius * np.linalg.norm(rv)) / 2
        bound = min(ga, gb) - d
        if bound > 0.0 or depth >= 12 or d < 0.001:
            self.segments += 1
            self.lower_bound = min(self.lower_bound, bound)
            if bound <= 0:
                self.unresolved += 1
            return
        mid = A * Rotation.from_rotvec(rv / 2)
        tm = (ta + tb) / 2
        self.segment(A, ta, mid, tm, depth + 1)
        self.segment(mid, tm, B, tb, depth + 1)


def installation(moving, fixed):
    metal = {k: fixed[k] for k in ("shoulder_pin", "threaded_cap")}
    survey = Survey(metal, fixed["pin_carriage"], 0.025)
    survey.static = [
        (k, fcl.CollisionObject(collider(o)), o)
        for k, o in (moving | {"pin_carriage": fixed["pin_carriage"]}).items()
    ]
    ez = np.array([0.0, 0.0, 1.0])
    zero = np.zeros(3)
    rows = []
    for name, phases in (
        ("shoulder_pin", [(9.0, 0.0, 0.0, 0.0)]),
        ("threaded_cap", [(-8.4, 0.0, -1.5, 0.0), (-1.5, -3600.0, 0.0, 0.0)]),
    ):
        part = Part(
            name,
            name,
            name,
            0.0,
            zero,
            zero,
            "z",
            0.15 if name == "threaded_cap" else 0.0,
        )
        for lo, dega, hi, degb in phases:
            check = survey.run(part, 0, (lo * ez, dega, hi * ez, degb))
            rows.append(
                dict(
                    part=name,
                    from_n_mm=lo,
                    to_n_mm=hi,
                    from_spin_deg=dega,
                    to_spin_deg=degb,
                    **check,
                )
            )
        survey.static.append(
            (name, fcl.CollisionObject(collider(metal[name])), metal[name])
        )
    return rows


def corner_comparison(prediction, fixed, moving):
    base, cover = carrier_parts(corner_relief=False)
    obj = fcl.CollisionObject(collider(fixed["pin_carriage"]))
    versions = {
        "square": (base, cover, cover.mirror((1, 0, 0))),
        "chamfered": tuple(
            moving[n] for n in ("coupon_carrier", "tab_cover", "tab_cover_left")
        ),
    }
    result = {}
    for name, solids in versions.items():
        mob = [fcl.CollisionObject(collider(o)) for o in solids]
        minimum = None
        for row in prediction["load_states"]:
            trans = fcl.Transform(
                Rotation.from_quat(row["rotation_coupon_to_pin_xyzw"]).as_matrix(),
                np.array(row["relative_translation_spn_mm"]),
            )
            for n, o in zip(("carrier", "cover_right", "cover_left"), mob):
                o.setTransform(trans)
                gap = float(
                    fcl.distance(o, obj, fcl.DistanceRequest(), fcl.DistanceResult())
                )
                if minimum is None or gap < minimum["gap_mm"]:
                    minimum = dict(
                        gap_mm=gap,
                        part=n,
                        target=row["target"],
                        load_multiplier=row["multiplier"],
                    )
        result[name] = minimum
    return result


def run(prediction, pin_carriage_path=None):
    moving, fixed = fixture(pin_carriage_path)
    study = MotionCheck(moving, fixed)
    static = []
    for group, solids in (("moving", moving), ("fixed", fixed)):
        for (n, a), (m, bpart) in combinations(solids.items(), 2):
            vol = exact_intersection(a, bpart)
            if vol > 1e-7:
                static.append(dict(group=group, a=n, b=m, overlap_mm3=vol))
    # Conservative axial shaft for access to each driver slot, beginning outside the head.
    tools = {}
    for n, lo, hi in (("positive", 4.19, 34.19), ("negative", -34.61, -4.61)):
        probe = b.cyl(0.5, lo, hi)
        tools[n] = min(
            (probe.min_gap(p, 40.0), k)
            for k, p in (moving | {"pin_carriage": fixed["pin_carriage"]}).items()
        )
    rows = []
    bearing = []
    for target in sorted({r["target"] for r in prediction["load_states"]}):
        vals = [r for r in prediction["load_states"] if r["target"] == target]
        R = Rotation.from_quat(vals[0]["rotation_coupon_to_pin_xyzw"])
        states = {
            v["multiplier"]: np.array(v["relative_translation_spn_mm"]) for v in vals
        }
        ref = next(x for x in states if x > 0 and x < 0.25)
        identity = Rotation.identity()
        zero = np.zeros(3)
        study.segment(identity, zero, R, states[ref])
        # The zero-force equilibrium is not unique. The interpolated path is a commanded carriage sweep.
        for sign in (1, -1):
            previous = states[ref]
            for scale in [
                0.0,
                0.25 * sign,
                0.5 * sign,
                0.75 * sign,
                sign,
                0.75 * sign,
                0.5 * sign,
                0.25 * sign,
                0.0,
                ref,
            ]:
                t = states.get(scale, zero)
                study.segment(R, previous, R, t)
                previous = t
        for scale, t in states.items():
            gap, a, bpart = study.measure(R, t)
            rows.append(
                dict(target=target, factor=scale, gap_mm=gap, moving=a, fixed=bpart)
            )
            obj = moving["web_coupon"].transform(np.column_stack((R.as_matrix(), t)))
            bearing.append(
                dict(
                    target=target,
                    factor=scale,
                    **{
                        k + "_rigid_overlap_mm3": exact_intersection(obj, fixed[k])
                        for k in ("shoulder_pin", "threaded_cap")
                    },
                )
            )
    straight = study.measure(Rotation.identity(), np.zeros(3))
    return dict(
        rigid_carriage_nominal_only=True,
        installation=installation(moving, fixed),
        carrier_corner_comparison=corner_comparison(prediction, fixed, moving),
        unloaded_internal_positive_overlaps=static,
        static_internal_pairs=sum(len(g) * (len(g) - 1) // 2 for g in (moving, fixed)),
        unloaded_driver_probe_radius_mm=0.5,
        unloaded_driver_probe_length_mm=30,
        driver_clearance_mm=tools,
        straight_nearest=straight,
        solved_nonzero_poses=rows,
        rigid_bearing_diagnostic=bearing,
        unique_sampled_poses=study.counter,
        cross_group_pairs_per_pose=len(moving) * len(fixed) - len(study.intent),
        nearest_sample=dict(
            zip(
                ("gap_mm", "moving", "fixed", "rotation_xyzw", "translation_spn_mm"),
                study.best,
            )
        ),
        interpolated_segments=study.segments,
        lower_bound_on_interpolated_clearance_mm=study.lower_bound,
        uncertified_subintervals=study.unresolved,
        unintended_contact_pairs=[
            dict(moving=a, fixed=bpart, volume_mm3=v)
            for (a, bpart), v in study.overlaps.items()
        ],
        limitations="Bounds apply to the specified rigid carriage paths. The two steel-to-coupon bearing interfaces are evaluated by the separate elastic model. Stage outside the M3 mounting faces, camera, load cell, real grip slip and unique zero-load carriage motion are not characterized.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prediction", type=Path, default=HERE / "results/coupon_fine.json")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--pin-carriage", type=Path, help="Substitute a bench pin-carriage STL in the same coordinates")
    a = p.parse_args()
    d = run(json.loads(a.prediction.read_text()), a.pin_carriage)
    a.out.write_text(json.dumps(d, indent=2) + "\n")
    print(
        {
            k: d[k]
            for k in (
                "unloaded_internal_positive_overlaps",
                "nearest_sample",
                "driver_clearance_mm",
                "uncertified_subintervals",
                "unintended_contact_pairs",
            )
        }
    )
