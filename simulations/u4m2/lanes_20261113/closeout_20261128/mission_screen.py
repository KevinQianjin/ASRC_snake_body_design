"""Re-equilibrate all archived winch commands with the nominal mass of the U1 fit trial."""

import argparse
import csv
import gzip
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.transform import Rotation
import trimesh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CYCLE = HERE.parent / "cycle_closeout_20261119"
MOTION = CYCLE / "results/yaw_pitch"
U1 = ROOT / "cad/lanes_u4m2/u_leaf_mechanical_joint/recessed_backstop"
sys.path.insert(0, str(CYCLE))
import replay
from length_cycle import LengthDrive
from tension_report import NAMES
from pitch_reference import target_axis
sys.path.insert(0, str(U1))
import build_recessed as joint

B = joint.original
CAD_TO_ROD = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
CAPSULE_MM = 31.5
RESIDUAL_LIMIT = 2.0e-7
ALLOWANCE_MM = 1.5


def added_part_vertices():
    body = B.solid(B.read("U_lane_pass.stl"))
    result = []
    for near in (True, False):
        old = B.frame(body, near)
        boss, cuts, parts, _ = joint.near_joint() if near else B.joint(False)
        added = ((old + boss) - cuts) - old
        shapes = [added, *parts.values()]
        shapes.append(parts["shoulder_key"].translate([0, 0, .12]))
        if near:
            shapes.append(parts["backstop"].translate([0, 0, -.05]))
        points = np.vstack([B.mesh(p).vertices for p in shapes])
        if not near:
            points[:, 2] *= -1
        result.append(points)
    return result


def capsule_margin(points, frames, added, sub):
    margin = float("inf")
    for vertices, a, b in zip(added, (0, sub), (1, sub - 1)):
        rotated = vertices @ (frames[a] @ CAD_TO_ROD).T
        segment = 1000 * (points[b] - points[a])
        fraction = np.clip((rotated @ segment) / (segment @ segment), 0, 1)
        distance = np.linalg.norm(rotated - fraction[:, None] * segment, axis=1)
        margin = min(margin, CAPSULE_MM - float(distance.max()))
    return margin


class FixedWinch:
    def __init__(self, plant):
        self.plant = plant
        self.drive = LengthDrive(plant)
        self.factor = None
        self.reference = None
        self.factorizations = 0

    def tangent(self, state, lengths):
        tensions = self.drive.force(state, lengths)
        jacobian = self.plant.control_jacobian(state)
        active = tensions.ravel() > 1e-8
        hessian = self.plant.hessian(state, tensions)
        hessian += jacobian[active].T @ (
            self.drive.ea / lengths.ravel()[active, None] * jacobian[active]
        )
        self.factor = cho_factor(hessian, check_finite=False)
        self.reference = state.copy()
        self.factorizations += 1

    def solve(self, original, lengths):
        state = original.copy()
        _, gradient = self.drive.energy(state, lengths)
        if self.reference is None or np.linalg.norm(state - self.reference) > .18:
            self.tangent(state, lengths)
        for i in range(20):
            if self.plant.residual(gradient) <= RESIDUAL_LIMIT:
                return state, self.plant.residual(gradient), i
            delta = cho_solve(self.factor, -gradient, check_finite=False)
            current_norm = np.linalg.norm(gradient)
            for fraction in (1., .5, .25):
                trial = state + fraction * delta
                try:
                    _, next_gradient = self.drive.energy(trial, lengths)
                except ValueError:
                    continue
                if np.linalg.norm(next_gradient) < current_norm:
                    state, gradient = trial, next_gradient
                    break
            else:
                self.tangent(state, lengths)
            if i in (5, 12):
                self.tangent(state, lengths)
        raise RuntimeError("Fixed-winch stationarity did not reach the residual target")


def after_mass_update(plant, grams):
    additional_kg = grams * .001
    model = plant.base
    model.planar.bare_mass[0] += additional_kg
    model.mass[:model.sub] += additional_kg / model.sub
    model.planar.mass = model.mass
    model.planar.weight_after = np.cumsum(model.mass[::-1])[::-1] - model.mass + model.payload


def ang_error(axis, goal):
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(axis, goal)), axis @ goal))


def run(out, samples):
    t0 = time.monotonic()
    out.mkdir(exist_ok=True, parents=True)
    input_files = (
        MOTION / "controller_states.npz", MOTION / "rope_tensions_every_step.csv.gz",
        MOTION / "adapter_clearance.csv.gz", U1 / "results/verification.json",
        ROOT / "cad/lanes_u4m2/guides_v2/head_adapter.stl",
        ROOT / "cad/lanes_u4m2/guides_v2/U_lane_pass.stl",
    )
    with np.load(input_files[0]) as archive:
        states, lengths, baseline_tensions = (archive[k] for k in
            ("motion_z", "motion_rest_m", "motion_tensions_N"))
    with gzip.open(input_files[1], "rt") as f:
        reference = list(csv.DictReader(f))
    with gzip.open(input_files[2], "rt") as f:
        adapter = list(csv.DictReader(f))
    assert len(states) == len(reference) == len(adapter) == 3405
    assert all(int(r["step"]) == i == int(a["step"]) and r["phase"] == a["phase"]
               for i, (r, a) in enumerate(zip(reference, adapter)))
    assert np.allclose(baseline_tensions, [[float(r[n + "_N"]) for n in NAMES] for r in reference],
                       atol=1e-11, rtol=0)
    verified = json.loads(input_files[3].read_text())
    added_g = verified["hardware_mass_screen"]["nominal_added_g"]
    assert max(s["overlap_mm3"] for s in verified["clearance_at_compression_stop"].values()) == 0
    adapter_mesh = trimesh.load_mesh(input_files[4])
    assert adapter_mesh.is_volume and np.allclose(adapter_mesh.bounds[:, 2], [0, 6])
    adapter_radius = float(np.linalg.norm(adapter_mesh.vertices, axis=1).max())
    plant, _ = replay.plant()
    assert plant.payload == .500
    after_mass_update(plant, added_g)
    solver = FixedWinch(plant)
    added = added_part_vertices()
    requested = samples if samples else range(len(states))
    evidence = []
    updated_states = []
    previous_step = -2
    last_pair = None
    per_step = out / "per_step.csv.gz"
    pending = out / "per_step.csv.gz.partial"
    with gzip.open(pending, "wt", newline="", encoding="utf-8") as stream:
        writer = None
        for i in requested:
            old = states[i]
            rest = lengths[i]
            pair = (old.tobytes(), rest.tobytes())
            if pair != last_pair:
                current, residual, iterations = solver.solve(old, rest)
                last_pair = pair
            updated_states.append(current)
            old_world = plant.base.kinematic_metrics(old)[1]
            world = plant.base.kinematic_metrics(current)[1]
            tension = solver.drive.force(current, rest).ravel()
            geometry_pass = bool(np.min(plant.geometry_constraints(current, world)) >= -1e-7)
            node_motion = float(1000 * np.linalg.norm(world["points"] - old_world["points"], axis=1).max())
            capsule = capsule_margin(world["points"], world["frames"], added, plant.sub)
            frame = plant.R0 @ world["frames"][-1]
            previous_frame = plant.R0 @ old_world["frames"][-1]
            orientation = Rotation.from_matrix(frame)
            axial_rotation = (Rotation.from_matrix(previous_frame).inv() * orientation).magnitude()
            yaw = float(reference[i]["target_yaw_deg"])
            elevation = float(reference[i]["target_elevation_deg"])
            y, p = np.radians([yaw, elevation])
            phase = reference[i]["phase"]
            goal = (target_axis(elevation) if phase.startswith("pitch") else
                    np.array([np.cos(p) * np.cos(y), np.sin(p), np.cos(p) * np.sin(y)]))
            pointed = ang_error(frame[:, 0], goal)
            head = np.asarray([float(reference[i][f"head_tank_{a}_mm"]) for a in "xyz"]) + (
                1000 * (plant.R0 @ (world["points"][-1] - old_world["points"][-1]))
            )
            bound = float(reference[i]["tank_clearance_after_allowance_mm"]) - node_motion + min(capsule, 0.)
            adapter_bound = (float(adapter[i]["adapter_triangle_gap_mm"]) - ALLOWANCE_MM - node_motion
                             - 2 * adapter_radius * np.sin(axial_rotation / 2))
            adapter_interpolated_bound = None
            if i == previous_step + 1:
                sweep = (np.linalg.norm(head - last_head)
                         + adapter_radius * (last_orientation.inv() * orientation).magnitude())
                adapter_interpolated_bound = min(adapter_bound, last_adapter_bound) - sweep / 2
            previous_step, last_head, last_orientation, last_adapter_bound = i, head, orientation, adapter_bound
            axis = frame[:, 0]
            row = dict(
                step=i, phase=phase, target_index=int(reference[i]["target_index"]),
                clamp_s_mm=float(reference[i]["clamp_s_mm"]),
                equilibrium_residual=residual, iterations=iterations, body_geometry_pass=geometry_pass,
                maximum_absolute_axial_strain=float(abs(world["q"][:, 3]).max()),
                max_node_displacement_mm=node_motion, added_CAD_capsule_margin_mm=capsule,
                body_tank_gap_lower_bound_mm=bound, adapter_gap_lower_bound_mm=adapter_bound,
                adapter_interpolated_gap_lower_bound_mm=adapter_interpolated_bound,
                target_yaw_deg=yaw, target_elevation_deg=elevation, pointing_error_deg=pointed,
                signed_forward_up_pitch_deg=float(np.degrees(np.arctan2(axis[1], axis[0]))),
                **{f"head_frame_q{component}": q for component, q in zip("xyzw", orientation.as_quat())},
                **{f"head_tank_{axis}_mm": head[k] for k, axis in enumerate("xyz")},
                **{f"head_axis_{component}": value for component, value in zip("xyz", axis)},
                **{name + "_N": force for name, force in zip(NAMES, tension)},
                maximum_rope_change_N=float(abs(tension - baseline_tensions[i]).max()),
            )
            if writer is None:
                writer = csv.DictWriter(stream, fieldnames=list(row), lineterminator="\n")
                writer.writeheader()
            writer.writerow(row)
            evidence.append(row)
            if (len(evidence) % 100) == 0:
                stream.flush()
                print("Re-equilibrated", len(evidence), "states in", round(time.monotonic() - t0, 1), "s", flush=True)

    def extreme(key, op):
        matches = [r for r in evidence if r[key] is not None]
        if not matches:
            return None
        row = op(matches, key=lambda r: r[key])
        return dict(value=row[key], step=row["step"], phase=row["phase"])

    tensions = [dict(value=r[n + "_N"], rope=n, step=r["step"]) for r in evidence for n in NAMES]
    failed = [r["step"] for r in evidence if not (
        r["body_geometry_pass"] and r["maximum_absolute_axial_strain"] <= .05
        and r["body_tank_gap_lower_bound_mm"] >= 5
        and r["adapter_gap_lower_bound_mm"] >= 5
        and (r["adapter_interpolated_gap_lower_bound_mm"] is None
             or r["adapter_interpolated_gap_lower_bound_mm"] >= 5)
        and r["added_CAD_capsule_margin_mm"] >= 0
        and r["pointing_error_deg"] <= 1
        and min(r[n + "_N"] for n in NAMES) >= 2.5
        and max(r[n + "_N"] for n in NAMES) <= 250
    )]
    record = dict(
        source_revision="d9347e87ab3612342962125580187523a0b42fd5", recalculated_states=len(evidence),
        phases=list(dict.fromkeys(r["phase"] for r in evidence)), added_U1_mass_g=added_g,
        head_payload_g=500, next_run_M6_cad="Published baseline",
        stresses="Original homogenized stiffness. Single-leaf fit candidate with nominal hardware envelope mass.",
        calculation="Fixed-winch equilibrium at archived commands and clamp positions.",
        adapter_CAD_radius_from_mount_mm=adapter_radius,
        min_rope_N=min(tensions, key=lambda b: b["value"]), max_rope_N=max(tensions, key=lambda b: b["value"]),
        max_rope_difference_N=extreme("maximum_rope_change_N", max),
        max_pointing_error_deg=extreme("pointing_error_deg", max),
        minimum_adjusted_body_gap_bound_mm=extreme("body_tank_gap_lower_bound_mm", min),
        minimum_adjusted_adapter_gap_bound_mm=extreme("adapter_gap_lower_bound_mm", min),
        minimum_interpolated_adapter_gap_bound_mm=extreme("adapter_interpolated_gap_lower_bound_mm", min),
        minimum_added_CAD_capsule_margin_mm=extreme("added_CAD_capsule_margin_mm", min),
        maximum_node_displacement_mm=extreme("max_node_displacement_mm", max),
        maximum_equilibrium_residual=extreme("equilibrium_residual", max),
        failed_steps=failed, tangent_factorizations=solver.factorizations,
        versions={p: version(p) for p in ("numpy", "scipy", "numba", "manifold3d", "trimesh", "clarabel")},
        input_sha256={str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in input_files},
        elapsed_s=time.monotonic() - t0,
    )
    np.savez_compressed(out / "equilibria.npz", steps=np.array(list(requested)), z=np.array(updated_states))
    pending.replace(per_step)
    (out / "mission_screen.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(json.dumps(record, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "results" / "mission")
    parser.add_argument("--steps", type=int, nargs="+")
    args = parser.parse_args()
    run(args.out, args.steps)
