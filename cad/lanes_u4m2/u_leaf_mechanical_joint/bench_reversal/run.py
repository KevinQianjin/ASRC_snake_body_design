"""Check axial stop order in the coupon CAD and run a low-force fixture model."""

import argparse
import csv
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
JOINT = HERE.parent
ROOT = HERE.parents[3]
STRIP_STUDY = ROOT / "simulations/u4m2/extreme_tests/round1_20261119"
sys.path.insert(0, str(JOINT))
import build as cad

sys.path.insert(0, str(STRIP_STUDY))
from u_springs import END_Z, E_MPA, NU, blade_profile, solve_blade

OVERLAP_TOL = 1.0e-5  # mm^3
CONTACT_TOL = 0.0002  # mm
DATUM_SPAN = 96.0  # mm
TEST_FORCES = (-5.0, -3.5, -2.0, -1.0, 1.0, 2.0, 3.5, 5.0)


def shifted(part, travel):
    return part.translate([0, 0, travel])


def volume(part, obstacle):
    return cad.positive_volume(part ^ obstacle)


def first_contact(part, obstacle, direction, end):
    """Bracket a known contact from 0 to end, inside its first interference band."""
    def overlap(travel):
        return volume(part.translate(np.array(direction) * travel), obstacle)

    assert overlap(0) <= OVERLAP_TOL < overlap(end)
    clear, blocked = 0.0, end
    while blocked - clear > CONTACT_TOL:
        middle = (clear + blocked) / 2
        if overlap(middle) <= OVERLAP_TOL:
            clear = middle
        else:
            blocked = middle
    return {
        "travel_mm": round((clear + blocked) / 2, 3),
        "last_clear_mm": round(clear, 7),
        "first_blocked_mm": round(blocked, 7),
    }


def end_model(original, leaf, near):
    boss, cuts, retainers, _ = cad.joint(near)
    body = cad.coupon((cad.frame(original, near) + boss) - cuts)
    leaf = cad.frame(leaf, near)
    key = retainers["shoulder_key"]
    contacts = {
        "shoulder_to_key": first_contact(leaf, key, (0, 0, 1), 0.18),
        "key_to_rail": first_contact(key, body, (0, 0, 1), 0.18),
    }
    if near:
        shoe = retainers["backstop"]
        contacts.update({
            "heel_to_shoe": first_contact(leaf, shoe, (0, 0, -1), 0.18),
            "shoe_to_lip": first_contact(shoe, body, (0, 0, -1), 0.18),
            "shoe_to_seated_screw": first_contact(
                shoe, retainers["screw_envelope"], (0, 0, -1), 0.18
            ),
        })
    else:
        contacts["heel_to_blind_floor"] = first_contact(leaf, body, (0, 0, -1), 0.05)
    return body, leaf, retainers, contacts


def gap(contacts, name):
    return contacts[name]["travel_mm"]


def check_axial_motion(model, compression_hard_stop, pin=None):
    body, blade, retainers, contacts = model
    retainers = dict(retainers)
    if pin is not None:
        del retainers["nut_envelope"]
        retainers["screw_envelope"] = pin
    shoulder_gap = gap(contacts, "shoulder_to_key")
    pull = shoulder_gap + gap(contacts, "key_to_rail")
    shoe = retainers.get("backstop")
    heel_gap = gap(contacts, "heel_to_shoe") if shoe is not None else 0.0
    push = heel_gap + compression_hard_stop
    travels = np.r_[np.linspace(-push, 0.0, 13), np.linspace(0.0, pull, 13)[1:]]
    max_overlap = 0.0
    for travel in travels:
        parts = dict(retainers)
        parts["coupon"] = body
        parts["blade"] = shifted(blade, travel)
        parts["shoulder_key"] = shifted(retainers["shoulder_key"], max(0, travel - shoulder_gap))
        if shoe is not None:
            parts["backstop"] = shifted(shoe, min(0, travel + heel_gap))
        for a, b in combinations(parts, 2):
            intrusion = volume(parts[a], parts[b])
            max_overlap = max(max_overlap, intrusion)
            assert intrusion <= OVERLAP_TOL, (travel, a, b, intrusion)
    return {
        "compression_mm": round(push, 3),
        "tension_mm": round(pull, 3),
        "reversal_mm": round(push + pull, 3),
        "sample_count": len(np.unique(travels)),
        "max_overlap_mm3": round(max_overlap, 9),
    }


def geometry():
    original = cad.solid(cad.read("U_lane_pass.stl"))
    blade_mesh = next(blade for blade in cad.read("U_leaf_springs.stl").split()
                      if np.all(blade.centroid[:2] > 0))
    blade = cad.solid(blade_mesh)
    near = end_model(original, blade, near=True)
    far = end_model(original, blade, near=False)
    near_contacts = near[3]
    shoe = near[2]["backstop"]
    base = cad.solid(cad.read("base_interface.stl"))
    previous_disk = cad.frame(original, False).mirror([0, 0, 1])
    lip_travel = gap(near_contacts, "shoe_to_lip")
    mates = {}
    for name, part in (("U1_base", base), ("preceding_U_distal_face", previous_disk)):
        mates[name] = first_contact(shoe, part, (0, 0, -1), 0.18)
        mates[name]["interference_at_lip_mm3"] = round(volume(shifted(shoe, -lip_travel), part), 6)

    pin = cad.cyl(cad.SCREW_X, cad.SCREW_Y, -10, 5.8, 0.80)
    pin_sweep = cad.swept([pin], [0, 0, -12])
    pin_insertion = {
        name: round(volume(part, pin_sweep), 9)
        for name, part in {
            "coupon": near[0], "blade": near[1],
            "shoulder_key": near[2]["shoulder_key"], "backstop": shoe,
        }.items()
    }
    assert max(pin_insertion.values()) <= OVERLAP_TOL
    shoe_at_lip = shifted(shoe, -lip_travel)
    key_at_rail = shifted(near[2]["shoulder_key"], gap(near_contacts, "key_to_rail"))
    lateral_capture = {
        "shoe_at_lip": first_contact(shoe_at_lip, pin, (0, 1, 0), 0.5),
        "key_at_rail": first_contact(key_at_rail, pin, (0, 1, 0), 0.5),
    }
    screw = near[2]["screw_envelope"]
    screw_intrusion_at_lip = volume(shoe_at_lip, screw)
    screw_case = check_axial_motion(near, gap(near_contacts, "shoe_to_seated_screw"))
    pin_case = check_axial_motion(near, lip_travel, pin=pin)
    far_case = check_axial_motion(far, gap(far[3], "heel_to_blind_floor"))
    fixtures = {}
    for name, case in (("Seated screw", screw_case), ("Fixed pin", pin_case)):
        lower = DATUM_SPAN - case["compression_mm"] - far_case["compression_mm"]
        upper = DATUM_SPAN + case["tension_mm"] + far_case["tension_mm"]
        fixtures[name] = {
            "near": case,
            "compression_limit_mm": round(lower, 3),
            "tension_limit_mm": round(upper, 3),
            "reversal_mm": round(upper - lower, 3),
        }

    return blade_mesh, {
        "proximal_contacts": near_contacts,
        "distal_contacts": far[3],
        "distal_response": far_case,
        "nominal_seated_screw_shoe_interference_at_lip_mm3": round(screw_intrusion_at_lip, 6),
        "shoe_protrusion_at_lip_mm": round(max(0, -shoe_at_lip.bounding_box()[2]), 3),
        "mating_faces": mates,
        "fixtures_open_near_face": fixtures,
        "fixed_control_pin": {
            "diameter_mm": 1.6, "tip_depth_mm": 5.8,
            "insertion_overlap_mm3": pin_insertion,
            "lateral_capture_positive_y": lateral_capture,
        },
        "seated_screw_path_stiffness_at_lip_engagement_N_per_mm": {
            str(force): round(force / lip_travel, 4) for force in (2.0, 5.0)
        },
    }


def force_points(mesh, spacing):
    profile = blade_profile(mesh, spacing)
    rotation = np.eye(3)
    zero = solve_blade(profile, rotation, [0, 0, 0], return_seed=True)
    assert zero["converged"]
    seed = zero["shooting_seed"]

    @lru_cache(maxsize=None)
    def evaluate(travel):
        result = solve_blade(profile, rotation, [0, 0, travel], warm=seed)
        assert result["converged"], (spacing, travel, result)
        return float(result["force_in_proximal_CAD_N"][2]), max(result["endpoint_residual_mm"])

    records = []
    for force in TEST_FORCES:
        bracket = (-0.060, 0.0) if force < 0 else (0.0, 0.060)
        travel = brentq(lambda displacement: evaluate(displacement)[0] - force, *bracket, xtol=1e-8)
        actual, residual = evaluate(travel)
        assert abs(actual - force) < 1e-5, (spacing, force, actual)
        records.append({
            "force_N": force,
            "blade_free_span_change_mm": round(travel, 7),
            "residual_mm": residual,
        })
    return records


def fixture_points(fixtures, blade_points):
    records = []
    for name, result in fixtures.items():
        lower = result["compression_limit_mm"]
        upper = result["tension_limit_mm"]
        for point in blade_points:
            force = point["force_N"]
            travel = point["blade_free_span_change_mm"]
            records.append({
                "configuration": name,
                "branch": "compression" if force < 0 else "tension",
                "force_N": force,
                "blade_free_span_change_mm": travel,
                "face_spacing_mm": round((lower if force < 0 else upper) + travel, 7),
            })
        for label, spacing in (("compression", lower), ("tension", upper)):
            records.append({
                "configuration": name, "branch": label, "force_N": 0.0,
                "blade_free_span_change_mm": 0.0, "face_spacing_mm": spacing,
            })
    return sorted(records, key=lambda row: (row["configuration"], row["face_spacing_mm"]))


def plot(path, contacts, rows):
    import matplotlib.pyplot as plt

    fig, (ax0, ax1) = plt.subplots(
        2, 1, figsize=(8.9, 7.4), gridspec_kw={"height_ratios": [1, 2]},
        layout="constrained",
    )
    fig.suptitle("U1 leaf joint reversal bench check", fontsize=19, fontweight="bold")
    screw = gap(contacts["proximal_contacts"], "shoe_to_seated_screw")
    mate = contacts["mating_faces"]["U1_base"]["travel_mm"]
    lip = gap(contacts["proximal_contacts"], "shoe_to_lip")
    points = [
        (screw, "Seated screw head", "#ad472b"),
        (mate, "Flush base face", "#7156a0"),
        (lip, "PA12 disk lip", "#167b74"),
    ]
    for y, (x, label, color) in enumerate(points[::-1]):
        ax0.hlines(y, 0, x, color=color, lw=3)
        ax0.scatter(x, y, color=color, s=65, zorder=3)
        ax0.text(x + 0.006, y, f"{x:.2f} mm  {label}", va="center", fontsize=10)
    ax0.set(xlim=(-0.006, 0.231), ylim=(-0.55, 2.55), yticks=[],
            xlabel="Proximal shoe travel toward the mating face (mm)",
            title="Independent stops in the straight CAD")
    ax0.set_xticks([0, 0.04, 0.08, 0.12, 0.16, 0.20])
    ax0.spines[["right", "top", "left"]].set_visible(False)
    ax0.grid(axis="x", alpha=0.18)
    for name, color, style in (("Fixed pin", "#167b74", "-"), ("Seated screw", "#ad472b", "--")):
        data = [r for r in rows if r["configuration"] == name]
        ax1.plot([r["face_spacing_mm"] for r in data], [r["force_N"] for r in data],
                 color=color, linestyle=style, marker="o", markersize=3, lw=2, label=name)
    ax1.axvline(DATUM_SPAN, color="#9da3aa", lw=1, alpha=0.8)
    ax1.set(xlabel="Distance between coupon datum faces (mm)",
            ylabel="Applied axial force (N)",
            title="Open-face fixture response with an elastic blade and rigid stops")
    ax1.grid(alpha=0.20)
    ax1.spines[["right", "top"]].set_visible(False)
    ax1.legend(frameon=False, loc="upper left")
    fig.savefig(path, dpi=165, facecolor="white")
    plt.close(fig)


def run(out):
    out.mkdir(exist_ok=True, parents=True)
    mesh, contacts = geometry()
    coarse = force_points(mesh, 1.0)
    fine = force_points(mesh, 0.5)
    difference = max(abs(a["blade_free_span_change_mm"] - b["blade_free_span_change_mm"])
                     for a, b in zip(coarse, fine))
    assert difference < 0.001
    rows = fixture_points(contacts["fixtures_open_near_face"], fine)
    with (out / "virtual_load_steps.csv").open("w", newline="", encoding="utf-8") as stream:
        table = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        table.writeheader()
        table.writerows(rows)
    files = [JOINT / "build.py", STRIP_STUDY / "u_springs.py",
             *(cad.SOURCE / name for name in (
                 "U_lane_pass.stl", "U_leaf_springs.stl", "base_interface.stl",
             ))]
    summary = {
        "upstream_joint_revision": "93a008af6977d6ca052cd2fb8cf6697661509f94",
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files},
        "versions": {package: version(package) for package in (
            "manifold3d", "trimesh", "numpy", "scipy", "numba", "shapely", "clarabel", "matplotlib",
        )},
        "overlap_tolerance_mm3": OVERLAP_TOL,
        "contact_bracket_tolerance_mm": CONTACT_TOL,
        "geometry": contacts,
        "elastic_blade": {
            "elastic_modulus_MPa": E_MPA, "poisson_ratio": NU, "free_span_mm": 2 * END_Z,
            "boundary": "Fixed end rotations with pure axial displacement in a straight fixture",
            "spacing_1_mm": coarse, "spacing_0p5_mm": fine,
            "max_spacing_difference_mm": round(difference, 7),
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    plot(out / "reversal_check.png", contacts, rows)
    print(f"Wrote {len(rows)} load steps. Maximum mesh-spacing displacement change {difference:.7f} mm.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    run(parser.parse_args().out)
