"""Condensed CAD rib plates, finite adhesive pads and simultaneous loads at the two M6 seats."""

import argparse
from pathlib import Path
import sys

import fcl
import numpy as np
import trimesh
from scipy.linalg import solve
from scipy.spatial.transform import Rotation

from common import (
    CAD,
    CANDIDATE,
    LANES,
    OUT,
    load_motion,
    read_csv,
    save,
    station_wrenches,
)
from m6_socket_screen import deformed_body, gap, load_variant, mesh_model, to_station

sys.path.insert(0, str(LANES))
import rib_joint_3d as ribs

STATIONS = (-12, 12)
ANGLES = np.arange(22.5, 360, 45)
MOUNT = (67.5, 157.5, 247.5, 337.5)
BODY = CAD / "end_bellmouth_v1/M6_lane_anchorC.stl"


def skew(v):
    return np.cross(v, np.eye(3)).T


def arm(v):
    return np.column_stack((np.eye(3), -skew(v)))


def material_points(angle, radius):
    t = np.radians(angle)
    er = np.array([np.cos(t), np.sin(t), 0])
    et = np.array([-np.sin(t), np.cos(t), 0])
    ez = np.array([0, 0, 1])
    # Rectangular equivalent of the four bonded side walls: measured 3 mm web thickness;
    # 0.5 mm axial land; 2*(3+2.67)*0.5=5.67 mm2. No end faces carry adhesive.
    points = []
    for normal, tangent, a, b in ((er, et, 1.335, 1.5), (et, er, 1.5, 1.335)):
        for side in (-1, 1):
            for u in (-1, 1):
                for h in (-1, 1):
                    rel = (
                        side * a * normal
                        + u * b / np.sqrt(3) * tangent
                        + h * 0.25 / np.sqrt(3) * ez
                    )
                    points.append((radius * er, rel, side * normal, 2 * b * 0.5 / 4))
    return points


def build(area):
    S = ribs.setup(area, 1530.0, 0.4, BODY)
    masters = S["ms"]
    count = 6 * len(masters) + 8 * 2 * 6
    K = np.zeros((count, count))
    maps = {}
    for i, theta in enumerate(ANGLES):
        P = np.zeros((6 * len(masters), count))
        for j, (name, mask, (r, z)) in enumerate(masters):
            sl = slice(6 * j, 6 * j + 6)
            if name.startswith("G"):
                st = int(name[1:])
                k = 6 * len(masters) + 6 * (2 * i + STATIONS.index(st))
                P[sl, k : k + 6] = ribs.projection6(theta, 0.0, 0.0, 0.0)
                maps[theta, st] = (slice(k, k + 6), sl, r)
            else:
                P[sl, sl] = ribs.projection6(theta, r, z, z)
        K += P.T @ S["Kc"] @ P
    return K, maps, S["mesh"]


def interfaces(K, maps, G, thick):
    blocks = []
    total = K.copy()
    for (theta, st), (web, guide, r) in maps.items():
        if theta not in MOUNT:
            continue
        for centre, rel, normal, area in material_points(theta, r):
            B = np.zeros((3, len(K)))
            B[:, guide] = arm(centre + rel)
            B[:, web] = -arm(rel)
            D = (
                area
                / thick
                * G
                * (np.eye(3) + (2 * (1 + 0.35) - 1) * np.outer(normal, normal))
            )
            total += B.T @ D @ B
            blocks.append((theta, st, centre, rel, B, D))
    return total, blocks


def stiffness(K, unattached):
    ids = np.arange(6, len(K))
    if unattached:
        ids = ids[~np.isin(ids, np.arange(36, 48))]
    F = np.zeros((len(K), 3))
    F[9:12] = np.eye(3)
    u = np.zeros_like(F)
    u[ids] = solve(K[np.ix_(ids, ids)], F[ids], assume_a="sym")
    return 96 / np.diag(u[9:12])


def rigid(pts, q):
    return pts @ Rotation.from_rotvec(q[3:]).as_matrix().T + q[:3]


def run(out, area, structure_only=False):
    rod, z, _ = load_motion()
    module = trimesh.load_mesh(BODY)
    K, maps, mesh = build(area)
    free = np.arange(12, len(K))  # disk increments held fixed for load-sharing cases
    bare = stiffness(K, True)
    loads = {st: station_wrenches("M6", st) for st in STATIONS}
    full = read_csv(out / "m6_all_steps.csv.gz")
    witness = {(int(r["step"]), int(r["station_mm"])): r for r in full}
    stiffnesses = []
    cases = []
    lands = []
    for step in (1709, 1710, 1885):
        det = rod.kinematic_metrics(z[step])[1]
        for thick in (0.15, 0.25):
            variants = {
                st: load_variant(CANDIDATE if thick == 0.25 else CAD / "guides_v3", st)
                for st in STATIONS
            }
            for G in (500.0, 1500.0):
                A, blocks = interfaces(K, maps, G, thick)
                if step == 1709:
                    stiffnesses.append(
                        dict(
                            gap_mm=thick,
                            G_MPa=G,
                            body_EIxx_EIyy_GJ_Nmm2=stiffness(A, False),
                            bare_body_Nmm2=bare,
                        )
                    )
                F = np.zeros(len(K))
                for j, st in enumerate(STATIONS):
                    F[36 + 6 * j : 42 + 6 * j] = loads[st][step]
                mismatch = []
                for theta, st, centre, rel, B, D in blocks:
                    xyz = centre + rel
                    mapped = to_station((xyz + [0, 0, st])[None, :], 5, st, rod, det)[0]
                    mismatch.append(mapped - xyz)
                    F += B.T @ D @ mismatch[-1]
                q = np.zeros(len(K))
                q[free] = solve(A[np.ix_(free, free)], F[free], assume_a="sym")
                balances = {st: np.zeros(6) for st in STATIONS}
                groups = {}
                for block, delta in zip(blocks, mismatch):
                    th, st, c, v, B, D = block
                    f = D @ (B @ q - delta)
                    g = groups.setdefault((th, st), np.zeros(6))
                    g[:3] += f
                    g[3:] += np.cross(v, f)
                    balances[st] += np.r_[f, np.cross(c + v, f)]
                for (th, st), g in groups.items():
                    lands.append(
                        dict(
                            step=step,
                            station_mm=st,
                            gap_mm=thick,
                            G_MPa=G,
                            rib_deg=th,
                            force_CAD_N=g[:3],
                            moment_at_land_CAD_Nmm=g[3:],
                        )
                    )
                for j, st in enumerate(STATIONS):
                    sl = slice(36 + 6 * j, 42 + 6 * j)
                    transform = q[sl]
                    w = witness[step, st]
                    ref = np.array([float(w["guide_" + a + "_mm"]) for a in "xyz"])
                    normal = np.array([float(w["toward_web_" + a]) for a in "xyz"])
                    theta = min(
                        ANGLES,
                        key=lambda th: abs(
                            (th - np.degrees(np.arctan2(ref[1], ref[0])) + 180) % 360
                            - 180
                        ),
                    )
                    web, _, r = maps[theta, st]
                    centre = material_points(theta, r)[0][0]
                    guide_delta = rigid(ref, transform) - ref
                    web_delta = rigid(ref - centre, q[web]) - (ref - centre)
                    rel = guide_delta - web_delta
                    err = np.linalg.norm(balances[st] - loads[st][step])
                    if err > 2e-5:
                        raise ValueError(f"Land reaction closure {err}")
                    cases.append(
                        dict(
                            step=step,
                            station_mm=st,
                            gap_mm=thick,
                            G_MPa=G,
                            force_and_moment=loads[st][step],
                            guide_increment_mm_rad=transform,
                            witness_rib_deg=theta,
                            web_increment_mm_rad=q[web],
                            candidate_witness_motion_mm=rel,
                            normal_closure_at_candidate_witness_mm=rel @ normal,
                            land_wrench_residual=err,
                            guide_witness_absolute_motion_mm=np.linalg.norm(
                                guide_delta
                            ),
                            relative_motion_mm=np.linalg.norm(rel),
                        )
                    )
            # Actual CAD comparison with the candidate witness web followed as a rigid local patch.
            # Exact for these imposed rigid offsets of the archived CAD, not a new shell-contact equilibrium.
            if thick == 0.25 and not structure_only:
                for st in STATIONS:
                    selected = [
                        x
                        for x in cases
                        if x["step"] == step
                        and x["gap_mm"] == thick
                        and x["station_mm"] == st
                    ]
                    objects = variants[st]
                    transforms = []
                    for line in selected:
                        qg = line["guide_increment_mm_rad"]
                        qw = line["web_increment_mm_rad"]
                        th = line["witness_rib_deg"]
                        rad = maps[th, st][2]
                        centre = material_points(th, rad)[0][0]
                        Rw = Rotation.from_rotvec(qw[3:]).as_matrix()
                        Rg = Rotation.from_rotvec(qg[3:]).as_matrix()
                        delta = Rw.T @ (qg[:3] - qw[:3] - centre + Rw @ centre)
                        transforms.append((Rw.T @ Rg, delta))
                    specs = []
                    for Rp, t in transforms:
                        for tilt in (0.0, -0.2, 0.2):
                            R = (
                                Rotation.from_rotvec(
                                    [np.radians(tilt), 0, 0]
                                ).as_matrix()
                                @ Rp
                            )
                            for offset in (0.0, 0.025):
                                direction = np.array(
                                    [
                                        float(witness[step, st]["toward_web_" + a])
                                        for a in "xyz"
                                    ]
                                )
                                specs.append((R, t + offset * direction))
                    allverts = np.concatenate(
                        [
                            m.vertices @ R.T + t
                            for R, t in specs
                            for m in objects.values()
                        ]
                    )
                    b = (allverts.min(0), allverts.max(0))
                    body, _, _ = deformed_body(module, st, b, 0.5, rod, det)
                    for k, line in enumerate(selected):
                        tests = []
                        for j, (R, t) in enumerate(specs[6 * k : 6 * k + 6]):
                            ds = {}
                            for name, m in objects.items():
                                o = fcl.CollisionObject(
                                    mesh_model(m.vertices, m.faces), fcl.Transform(R, t)
                                )
                                try:
                                    ds[name] = gap(body, o)[0]
                                except ValueError:
                                    ds[name] = None  # gap above cropped search radius
                            tests.append(
                                dict(
                                    tilt_x_deg=(0.0, -0.2, 0.2)[j // 2],
                                    offset_to_web_mm=(0.0, 0.025)[j % 2],
                                    gaps_mm=ds,
                                )
                            )
                        line["local_relative_rigid_CAD_probes"] = tests
        print("bonded support", step, "complete", flush=True)
    filename = "m6_support_refined.json" if structure_only else "m6_support.json"
    save(
        out / filename,
        dict(mesh=mesh, body_only_stiffness=stiffnesses, cases=cases, lands=lands),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--area", type=float, default=0.09)
    p.add_argument("--structure-only", action="store_true")
    a = p.parse_args()
    run(a.out, a.area, a.structure_only)
