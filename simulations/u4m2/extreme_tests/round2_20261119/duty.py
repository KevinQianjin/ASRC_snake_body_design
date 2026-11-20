"""Mission rainflow ranges at fixed material locations and inverse endurance requirements."""

import argparse
from pathlib import Path
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.transform import Rotation
import trimesh

from common import (
    input_file,
    CAD,
    NAMES,
    OUT,
    R1,
    SOURCE,
    load_motion,
    read,
    read_csv,
    save,
    station_wrenches,
    write_table,
)
from m6_support import STATIONS, build, interfaces, material_points, skew, to_station
from u_springs import CAD_TO_ROD, blade_profile


def reversals(series):
    """Keep endpoints of an open mission, remove consecutive duplicates, then interior non-reversals."""
    s = np.asarray(series)
    ix = np.r_[0, np.flatnonzero(np.diff(s) != 0) + 1]
    s = s[ix]
    if len(s) <= 2:
        return s
    return s[np.r_[True, np.diff(s)[:-1] * np.diff(s)[1:] < 0, True]]


def rainflow(series):
    stack = []
    cycles = []
    for x in reversals(series):
        stack.append(float(x))
        while len(stack) >= 3:
            a, b, c = stack[-3:]
            if abs(c - b) < abs(b - a):
                break
            if len(stack) == 3:
                cycles.append((abs(a - b), (a + b) / 2, 0.5))
                stack.pop(0)
            else:
                cycles.append((abs(a - b), (a + b) / 2, 1.0))
                del stack[-3:-1]
    cycles.extend((abs(b - a), (a + b) / 2, 0.5) for a, b in zip(stack, stack[1:]))
    return np.array(cycles).reshape(-1, 3)


def fixed_blade(history, profiles, module, stiffness, tab):
    """Linearized initially curved beams plus axial cage and two identical elastic tabs.
    Linear fields rank fixed segment sides. The separate nonlinear solve checks the three selected events.
    """
    pos = np.array(
        [d["points"][8 * (module + 1)] - d["points"][8 * module] for d in history]
    )
    base = np.array([d["frames"][8 * module] @ CAD_TO_ROD for d in history])
    tip = np.array([d["frames"][8 * (module + 1)] @ CAD_TO_ROD for d in history])
    R = base.transpose(0, 2, 1) @ tip
    centre = np.einsum("nji,nj->ni", base, pos) * 1000 - [0, 0, 96]
    rot = Rotation.from_matrix(R).as_rotvec()
    q = np.array([d["q"][8 * module : 8 * (module + 1), 3] for d in history])
    R[:, :, 2]
    # The translation/sliding compatibility here uses the nominal axial direction as a linearized mode.
    systems = []
    sum_k = 0.0
    sum_force = np.zeros(len(q))
    for prof in profiles:
        p, ds, t, ea, cm, basis, kb, w, th = prof
        mid = (p[:-1] + p[1:]) / 2
        B = np.array([np.column_stack((skew(p[-1] - m), np.eye(3))) for m in mid])
        a = np.column_stack((t, np.zeros_like(t)))
        C = np.einsum("i,ijk,ijl,ilm->km", ds, B, cm, B) + np.einsum(
            "i,ij,ik->jk", ds / ea, a, a
        )
        C[2, 2] += 2 / tab
        K = np.linalg.inv(C)
        delta = centre + np.einsum("nij,j->ni", R - np.eye(3), p[-1] - [0, 0, 48.0])
        imposed = np.column_stack((delta, rot))
        applied = imposed @ K.T
        sum_force += applied[:, 2]
        sum_k += K[2, 2]
        systems.append((applied, K, B, a, basis, kb, w, th, ea, p))
    target = stiffness["EA"] * q[:, -1]
    corr = (target - sum_force - stiffness["cage"] * 12 * q.sum(1)) / (
        sum_k + stiffness["cage"]
    )
    spread = -np.inf
    best = None
    for j, (f, K, B, a, basis, kb, w, th, ea, p) in enumerate(systems):
        loads = f + corr[:, None] * K[None, :, 2]
        axial = (loads @ a.T) / ea
        moment = np.einsum("nij,njk->nik", basis.transpose(0, 2, 1), B)
        kap = np.einsum("nij,sj->sni", moment, loads) / kb
        for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            strain = axial + sx * kap[:, :, 0] * w / 2 + sy * kap[:, :, 1] * th / 2
            ranges = np.ptp(strain, axis=0)
            k = np.argmax(ranges)
            if ranges[k] > spread:
                spread = ranges[k]
                best = (
                    strain[:, k].copy(),
                    dict(
                        module=module + 1,
                        blade=j,
                        corner=[sx, sy],
                        reference_z_mm=np.mean(p[k : k + 2, 2]),
                        trial_tab_N_mm=tab,
                        trial_cage_N_mm=stiffness["cage"],
                    ),
                )
    return best


def bond_duty(rod, history):
    K, maps, _ = build(0.09)
    A, blocks = interfaces(K, maps, 500.0, 0.25)
    n = len(history)
    m = len(blocks)
    F = np.zeros((n, len(K)))
    for j, st in enumerate(STATIONS):
        F[:, 36 + 6 * j : 42 + 6 * j] = station_wrenches("M6", st)
    deltas = np.zeros((n, m, 3))
    for st in STATIONS:
        ids = [i for i, v in enumerate(blocks) if v[1] == st]
        xyz = np.array([blocks[i][2] + blocks[i][3] for i in ids])
        for j, d in enumerate(history):
            deltas[j, ids] = to_station(xyz + [0, 0, st], 5, st, rod, d) - xyz
    B = np.array([v[4] for v in blocks])
    D = np.array([v[5] for v in blocks])
    F += np.einsum("gak,gab,sgb->sk", B, D, deltas, optimize=True)
    q = np.zeros_like(F)
    q[:, 12:] = cho_solve(cho_factor(A[12:, 12:]), F[:, 12:].T).T
    slip = np.einsum("gak,sk->sga", B, q, optimize=True) - deltas
    best = {}
    for i, (theta, st, _, _, _, d) in enumerate(blocks):
        _, _, normal, area = material_points(theta, 1.0)[i % 16]
        stress = slip[:, i] @ d.T / area
        for name, along in (
            ("normal", normal),
            ("axial_shear", np.array([0.0, 0.0, 1.0])),
            ("cross_shear", np.cross(normal, [0, 0, 1.0])),
        ):
            val = stress @ along
            if name not in best or np.ptp(val) > np.ptp(best[name][0]):
                best[name] = (
                    val,
                    dict(
                        station_mm=st,
                        rib_deg=theta,
                        quadrature_point=i % 16,
                        G_MPa=500,
                        bond_mm=0.25,
                        positive_direction=along.tolist(),
                    ),
                )
    return best


def run(out):
    rod, z, T = load_motion()
    rows = read_csv(SOURCE / "rope_tensions_every_step.csv.gz")
    hist = [rod.kinematic_metrics(v)[1] for v in z]
    data = {}
    sites = {}
    for j, name in enumerate(NAMES):
        data["rope_" + name + "_nominal_N"] = T[:, j]
    for m in (4, 5):
        q = np.array([d["q"][m * 8 : m * 8 + 8] for d in hist])
        # Constant-strain cell, a fixed material fibre on the circular 1.8 mm backbone.
        best = (-1.0, None, None)
        for a in np.arange(0, 360, 15):
            th = np.radians(a)
            strain = q[:, :, 3] + 0.9 / 12 * (
                q[:, :, 1] * np.cos(th) + q[:, :, 2] * np.sin(th)
            )
            i = np.argmax(np.ptp(strain, axis=0))
            if np.ptp(strain[:, i]) > best[0]:
                best = (
                    np.ptp(strain[:, i]),
                    strain[:, i],
                    dict(cell=int(i + 1), fibre_deg=int(a)),
                )
        key = f"M{m + 1}_backbone_strain"
        data[key] = best[1]
        sites[key] = best[2]
    # Signed axial virtual gauge at the archived PA12 build-direction hotspot. This samples the homogenized map.
    site = read(R1 / "m5_step_1843_area_0p055.json")["surface_extremes"][
        "build_Z_tensile"
    ]
    r, s, normal = site["reference_r_z_through_mm"]
    angle = np.radians(site["rib_deg"])
    pt = np.array(
        [
            r * np.cos(angle) + normal * np.sin(angle),
            r * np.sin(angle) - normal * np.cos(angle),
            s,
        ]
    )
    pair = np.array([pt - [0, 0, 0.25], pt + [0, 0, 0.25]])
    data["M5_build_Z_kinematic_strain"] = np.array(
        [
            np.linalg.norm(np.diff(to_station(pair, 4, -12, rod, d), axis=0)) / 0.5 - 1
            for d in hist
        ]
    )
    sites["M5_build_Z_kinematic_strain"] = dict(
        reference_CAD_mm=pt.tolist(),
        gauge_mm=0.5,
        archived_shell_build_Z_strain=site["strain"],
    )
    for name, (v, loc) in bond_duty(rod, hist).items():
        key = "M6_bond_" + name + "_MPa"
        data[key] = v
        sites[key] = loc
    u = read(input_file(out, "u_structure", "u_assembly.json"))
    body = trimesh.load_mesh(CAD / "guides_v2/U_leaf_springs.stl")
    blades = [
        blade_profile(b, 1.0)
        for b in sorted(body.split(), key=lambda b: tuple(np.sign(b.centroid[:2])))
    ]
    for m in range(4):
        k = u["cage_sections"][-1]["estimated_kinematic_upper_N_mm"] * 0.10
        v, loc = fixed_blade(
            hist, blades, m, dict(EA=rod.planar.EA[m * 8], cage=k), 250.0
        )
        key = f"U{m + 1}_linear_blade_strain"
        data[key] = v
        sites[key] = loc
    comp = read_csv(
        input_file(out, "rope_control", "coupled_s0.15_k0.15_b0.1_compensated.csv.gz")
    )
    if len(comp) != len(rows):
        raise ValueError(
            "An incomplete transmission trace cannot stand for one mission"
        )
    travel = {}
    for name in NAMES:
        data[f"rope_{name}_distal_N"] = np.array(
            [float(r[name + "_dist_N"]) for r in comp]
        )
        data[f"rope_{name}_winch_N"] = np.array(
            [float(r[name + "_prox_N"]) for r in comp]
        )
        slide = np.array([float(r[name + "_slip_mm"]) for r in comp])
        cmd = np.array([float(r[name + "_drum_mm"]) for r in comp])
        travel[name] = dict(
            material_transfer_travel_mm=float(abs(slide).sum()),
            actual_drum_travel_mm=float(abs(np.diff(cmd)).sum()),
        )
    counts = []
    summ = []
    for name, v in data.items():
        cyc = rainflow(v)
        for amp, mean, num in cyc:
            counts.append(dict(channel=name, range=amp, mean=mean, count=num))
        row = dict(
            channel=name,
            minimum=v.min(),
            maximum=v.max(),
            governing_range=max(cyc[:, 0]),
            rainflow_cycles=sum(cyc[:, 2]),
        )
        if name == "M5_build_Z_kinematic_strain":
            row["interpretation"] = (
                "Displacement gradient in the homogenized rod map; kinematic indicator only"
            )
        elif name.startswith("M6_bond_"):
            row["interpretation"] = (
                "Linear-elastic adhesive pad traction; requires an installed joint traction law"
            )
        elif name.startswith("U") and name.endswith("_strain"):
            row["interpretation"] = (
                "Linearized CAD blade demand; requires measured end restraint"
            )
        elif name.endswith("_strain"):
            row["interpretation"] = (
                "Elastic fixed fibre demand; requires identified NiTi cyclic response"
            )
        else:
            row["interpretation"] = (
                "Simulated tensile force; requires matched assembly test data"
            )
        # A rod-map displacement gradient on a perforated web has no coupon-equivalent material amplitude.
        # Other channels give inverse reference demands for 10,000 open missions under the trial law.
        for b in (3, 5, 8):
            row[f"required_A_at_1e6_for_10000_missions_b{b}"] = (
                (0.01 * np.sum(cyc[:, 2] * (cyc[:, 0] / 2) ** b)) ** (1 / b)
                if name != "M5_build_Z_kinematic_strain"
                else None
            )
        summ.append(row)
    table = [
        dict(step=i, phase=r["phase"], **{k: v[i] for k, v in data.items()})
        for i, r in enumerate(rows)
    ]
    write_table(out / "fatigue_and_strength" / "duty_channels.csv.gz", table)
    write_table(out / "fatigue_and_strength" / "rainflow.csv.gz", counts)
    write_table(out / "fatigue_and_strength" / "endurance_requirements.csv.gz", summ)
    turns = [
        max(i for i, r in enumerate(rows) if r["phase"] == p)
        for p in ("right_out", "left_out", "pitch_up", "pitch_down")
    ]
    dwell = {
        str(minutes): {
            n: sum(float(comp[i][n + "_dist_N"]) for i in turns) * minutes / 60
            for n in NAMES
        }
        for minutes in (1, 10, 60)
    }
    save(
        out / "fatigue_and_strength" / "duty.json",
        dict(
            mission_steps=len(rows),
            channels=len(data),
            sites=sites,
            counts=len(counts),
            four_holds_distal_N_hours=dwell,
            rope_travel=travel,
            turn_steps=turns,
            actual_duration_s=None,
            physical_life_missions=None,
        ),
    )
    print("duty channels", len(data), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    run(a.out)
