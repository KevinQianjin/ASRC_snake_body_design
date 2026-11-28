"""Build and check the second single-leaf U1 fit trial with a recessed backing shoe."""

from itertools import combinations
import json
from pathlib import Path
import sys

import cadquery as cq
import manifold3d as md
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build as original

M = md.Manifold
box, cyl, union = original.box, original.cyl, original.union
OUT = HERE / "results"
X_SCREW, Y_SCREW = 6.4, 20.10
HEAD_RELIEF = 0.16
BRIDGE = (4.44, 10.55, 19.96, 29.17, 0.14, 0.94)
EYE = (4.44, 8.52, 18.23, 20.65, 0.68, 0.94)
WINGS = [
    (x0, x1, y0, y1, 1.53 if z0 == 1.60 else z0, z1)
    for x0, x1, y0, y1, z0, z1 in original.SHOE_BOXES[1:]
]
SHOE = [BRIDGE, EYE, *WINGS]
EPS = 1.0e-5  # cubic millimetres


def key_profile():
    left, right = original.KEY_LEFT, original.KEY_RIGHT
    outer, inner = original.KEY_D0, original.KEY_D1
    radius = original.EDGE_R
    center = (right - radius, outer + radius)
    return left, right, outer, inner, radius, center


def near_joint():
    rail = box(4.15, 12.25, 17.05, 31.4, 2.76, 6.28)
    nut_pedestal = box(4.15, 11.6, 17.75, 23.04, 2.76, 8.55)
    boss = (rail + nut_pedestal) ^ cyl(0, 0, -1, 10, 31.42, sides=360)
    left, right, outer, inner, radius, (cx, cz) = key_profile()
    rounded = [(cx + radius * np.cos(a), cz + radius * np.sin(a))
               for a in np.linspace(-np.pi / 2, 0, 13)]
    key_profile_points = [(left, outer), *rounded, (right, inner), (left, inner)]
    key_blank = md.CrossSection([np.asarray(key_profile_points)]).extrude(
        original.KEY_Y1 - original.KEY_Y0
    ).rotate([90, 0, 0]).translate([0, original.KEY_Y1, 0])
    axis = cyl(X_SCREW, Y_SCREW, -1, 10, .90)
    seat = cyl(X_SCREW, Y_SCREW, -.02, .93, 1.85, .90)
    relieved_seat = cyl(X_SCREW, Y_SCREW, -.02, .93 + HEAD_RELIEF, 1.85 + HEAD_RELIEF, .90)
    shoe_blocks = [box(*limits) for limits in SHOE]
    shoe = union(shoe_blocks) - (axis + relieved_seat)
    key = key_blank - axis
    nut_blank = box(X_SCREW - 1.6, X_SCREW + 1.6, Y_SCREW - 1.6, Y_SCREW + 1.6, 6.30, 7.60)
    nut = nut_blank - cyl(X_SCREW, Y_SCREW, 6.2, 7.7, .82)
    screw_blocks = [cyl(X_SCREW, Y_SCREW, .23, 1.03, 1.60, .80),
                    cyl(X_SCREW, Y_SCREW, 1.03, 8.23, .80)]
    pocket = union([
        box(4.86, 10.14, 23.26, 29.55, 2.75, 9),
        box(4.85, 8.64, 17.93, 43, 3.01, 4.67),
        box(X_SCREW - 1.73, 44, Y_SCREW - 1.73, Y_SCREW + 1.73, 6.17, 7.73),
        box(4.32, 10.67, 19.84, 43, -.03, 1.00),
        box(4.32, 8.64, 18.11, 43, .56, 1.00),
        box(4.32, 4.95, 23.06, 43, .66, 2.74),
        box(10.05, 10.67, 23.06, 43, .66, 2.74),
        box(3.71, 4.95, 23.06, 43, 1.48, 2.74),
        box(10.05, 12.92, 23.06, 43, 1.48, 2.74),
        axis, seat,
    ])
    parts = dict(shoulder_key=key, backstop=shoe, screw=union(screw_blocks), nut=nut)
    sweeps = dict(
        shoulder_key=original.swept([key_blank], [0, 18, 0]),
        backstop=original.swept(shoe_blocks, [0, 18, 0]),
        nut=original.swept([nut_blank], [32, 0, 0]),
        screw=original.swept(screw_blocks, [0, 0, -15]),
        driver=cyl(X_SCREW, Y_SCREW, -25, 0, 2.2),
    )
    return boss, pocket, parts, sweeps


def volume(a, b):
    return original.positive_volume(a ^ b)


def motion(part, displacement):
    return part.translate([0, 0, displacement])


def first_hit(part, obstacle, direction, bracket):
    start, stop = 0., bracket
    assert volume(part, obstacle) <= EPS < volume(part.translate(np.asarray(direction) * stop), obstacle)
    while stop - start > 0.0001:
        point = (start + stop) / 2
        if volume(part.translate(np.asarray(direction) * point), obstacle) > EPS:
            stop = point
        else:
            start = point
    return round((start + stop) / 2, 4)


def export(part, name):
    path = OUT / (name + ".stl")
    mesh = original.mesh(part)
    mesh.export(path)
    check = trimesh.load_mesh(path)
    assert check.is_volume and check.body_count == 1
    assert abs(check.volume - part.volume()) < max(0.002, part.volume() * 1e-5)


def metal_steps(parts):
    left, right, outer, inner, radius, (cx, cz) = key_profile()
    r45 = radius / np.sqrt(2)
    key = (cq.Workplane("XZ", origin=(0, original.KEY_Y1, 0)).moveTo(left, outer)
        .lineTo(cx, outer).threePointArc((cx + r45, cz - r45), (right, cz))
        .lineTo(right, inner).lineTo(left, inner).close()
        .extrude(original.KEY_Y1 - original.KEY_Y0).val())
    boxes = [cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))
             for x0, x1, y0, y1, z0, z1 in SHOE]
    axis = cq.Solid.makeCylinder(.90, 11, cq.Vector(X_SCREW, Y_SCREW, -1))
    relief = cq.Solid.makeCone(1.85 + HEAD_RELIEF, .90, .95 + HEAD_RELIEF,
                               cq.Vector(X_SCREW, Y_SCREW, -.02))
    result = {}
    for name, shape in (("shoulder_key", key.cut(axis)),
                        ("backstop", boxes[0].fuse(*boxes[1:]).cut(axis, relief).clean())):
        path = OUT / ("proximal_" + name + ".step")
        cq.exporters.export(shape, str(path))
        path.write_text("\n".join(x.rstrip() for x in path.read_text().splitlines()) + "\n")
        loaded = cq.importers.importStep(str(path)).val()
        assert loaded.isValid() and len(loaded.Solids()) == 1
        result[name] = abs(loaded.Volume() - parts[name].volume())
        assert result[name] < .025, (name, result[name])
    return result


def analyze_end(body, blade, parts, base, neighboring_disk):
    shoe, screw, key = (parts[x] for x in ("backstop", "screw", "shoulder_key"))
    specimen = original.coupon(body)
    toward_face = (0, 0, -1)
    pull_shoulder = first_hit(blade, key, (0, 0, 1), .19)
    pull_rail = first_hit(key, specimen, (0, 0, 1), .19)
    heel = first_hit(blade, shoe, toward_face, .15)
    lip = first_hit(shoe, specimen, toward_face, .12)
    head = first_hit(shoe, screw, toward_face, .24)
    face = first_hit(shoe, base, toward_face, .21)
    adjacent = first_hit(shoe, neighboring_disk, toward_face, .21)
    assert lip + .07 < min(head, face, adjacent)
    # Run the assembled parts up to each stop in the coupon. The full body is checked separately.
    states = np.r_[np.linspace(-heel - lip, 0., 13), np.linspace(0., pull_shoulder + pull_rail, 13)[1:]]
    peak = 0.
    for shift in states:
        moving = dict(parts)
        moving["shoulder_key"] = motion(key, max(shift - pull_shoulder, 0.))
        moving["backstop"] = motion(shoe, min(shift + heel, 0.))
        moving["blade"] = motion(blade, shift)
        moving["body"] = specimen
        for a, b in combinations(moving, 2):
            captured = volume(moving[a], moving[b])
            peak = max(peak, captured)
            assert captured <= EPS, (shift, a, b, captured)
    seated = motion(shoe, -lip)
    cut_tests = {name: original.check(seated, part)
                 for name, part in (("screw", screw), ("U1_base", base), ("adjacent_U_end", neighboring_disk))}
    assert all(check["overlap_mm3"] == 0. for check in cut_tests.values())
    supported_shoe_area = volume(motion(seated, -.01), specimen) / .01
    head_seat_area = volume(motion(screw, .01), specimen) / .01
    assert supported_shoe_area > 10 and head_seat_area > 1
    retention = {label: first_hit(obj, screw, (0, 1, 0), .9)
                 for label, obj in (("key", motion(key, pull_rail)), ("shoe", seated))}
    return dict(
        stop_order_outward_mm=dict(PA12_lip=lip, countersunk_head=head, U1_base_face=face,
                                  adjacent_U_face=adjacent),
        blade_to_shoe_mm=heel, total_compression_travel_mm=heel + lip,
        blade_to_key_mm=pull_shoulder, key_to_rail_mm=pull_rail,
        proximal_reversal_mm=heel + lip + pull_shoulder + pull_rail,
        supported_shoe_area_mm2=supported_shoe_area, head_seat_axial_area_mm2=head_seat_area,
        seated_shoe_recess_mm=float(seated.bounding_box()[2]),
        clearance_at_compression_stop=cut_tests,
        lateral_capture_mm=retention,
        sampled_axial_states=len(states), maximum_assembly_overlap_mm3=peak,
    )


def check_sweeps(body, leaf, parts, sweeps):
    tests = {}
    for name, tool in sweeps.items():
        tests[name + "_vs_body"] = original.check(tool, body)
        tests[name + "_vs_NiTi"] = original.check(tool, leaf)
    for later, earlier in (("backstop", "shoulder_key"), ("nut", "shoulder_key"),
                           ("nut", "backstop"), ("screw", "shoulder_key"), ("screw", "backstop")):
        tests[later + "_vs_" + earlier] = original.check(sweeps[later], parts[earlier])
    for label, test in tests.items():
        assert test["overlap_mm3"] <= EPS, (label, test)
    return tests


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = original.solid(original.read("U_lane_pass.stl"))
    base = original.solid(original.read("base_interface.stl"))
    predecessor = original.frame(baseline, False).mirror([0, 0, 1])
    springs = original.read("U_leaf_springs.stl").split()
    blade = original.solid(next(p for p in springs if np.all(p.centroid[:2] > 0)))
    leaf = original.frame(blade, True)
    all_leaves = original.frame(union([original.solid(s) for s in springs]), True)
    boss, cuts, parts, sweeps = near_joint()
    far_boss, far_cuts, far_parts, _ = original.joint(False)
    reserve = original.protected()
    near = (original.frame(baseline, True) + boss) - cuts
    result = analyze_end(near, leaf, parts, base, predecessor)
    models = {}
    for kind in ("U1", "U4"):
        template = baseline if kind == "U1" else original.solid(original.read("U4_lane_anchorA.stl"))
        end = original.frame(template, True)
        trial = (end + boss) - cuts
        assert len(trial.decompose()) == 1
        model = ((template + original.world(boss, True) + original.world(far_boss, False))
                 - original.world(cuts, True)) - original.world(far_cuts, False)
        assert len(model.decompose()) == 1
        access = union(list(sweeps.values()))
        edited = union([trial - end, end - trial, *parts.values()])
        routing = {name: {
            "modified_solids": original.check(edited, reserve[name]),
            "assembly_tools": original.check(access, reserve[name]),
        } for name in ("bore_mouths", "rope_2mm")}
        assert all(t["overlap_mm3"] <= EPS for checks in routing.values() for t in checks.values())
        feed = original.check(original.swept([blade], [0, 0, -100]), model)
        assert feed["overlap_mm3"] <= EPS, (kind, feed)
        inboard = box(-40, 40, 16, 36, 3.001, 16)
        original_cut = volume(end - trial, inboard)
        assert original_cut <= EPS, (kind, original_cut)
        models[kind] = dict(tool_sweeps=check_sweeps(trial, all_leaves, parts, sweeps),
                            rope_reserves=routing, continuous_leaf_feed=feed,
                            original_inboard_cut_mm3=original_cut)
        if kind == "U1":
            export(model, "U1_one_leaf_trial_body")
            export(original.coupon(trial), "U1_proximal_recessed_coupon")
            far = (original.frame(template, False) + far_boss) - far_cuts
            export(original.coupon(far), "U1_distal_coupon")
            delta = model.volume() - baseline.volume()
    for name, item in parts.items():
        if name in ("backstop", "shoulder_key"):
            export(item, "proximal_" + name)
    steel_volume = sum(p.volume() for p in parts.values()) + sum(p.volume() for p in far_parts.values())
    mass = dict(PA12_volume_change_mm3=delta, steel_envelope_volume_mm3=steel_volume,
                PA12_density_g_per_mm3=.00101, steel_trial_density_g_per_mm3=.00785,
                nominal_added_g=delta * .00101 + steel_volume * .00785)
    result.update(source_revision="d9347e87ab3612342962125580187523a0b42fd5",
                  geometry="One +X,+Y blade in the lane-routed U body", models=models,
                  hardware_mass_screen=mass, STEP_mesh_delta_mm3=metal_steps(parts))
    (OUT / "verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: value for k, value in result.items() if k != "models"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
