"""Free lateral travel of a 2 mm C rope through the common M5-distal/M6-proximal rigid bore."""

import argparse
import csv
import json
from pathlib import Path
import sys

import clarabel
import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
LANES = HERE.parent
ROOT = LANES.parents[2]
sys.path.insert(0, str(LANES))
import lanes
from bellmouth_model import RAYS, apply_bellmouth
from bellmouth_cad_check import Body
from end_bellmouth_kernel import span_geometry
from state_archives import load_states

DESIGN = ROOT / "cad/lanes_u4m2/end_bellmouth_v1"
ARCHIVE = LANES / "morning_20261116/fixed_winch_holds"


def wall_grid(profile, spacing):
    """An inscribed polyline bound of the offset wall, then its conservative tangent to the free face."""
    depth, wall, angle, hole, rope = profile
    if not (0 < angle < np.pi / 2 and depth > wall * np.sin(angle)):
        raise ValueError("Invalid bellmouth")
    s0 = depth - wall * np.sin(angle)
    rc = wall + rope
    s1 = s0 + rc * np.sin(angle)
    axial = np.r_[
        0.0,
        s0,
        np.linspace(s0, s1, int(np.ceil((s1 - s0) / spacing)) + 1)[1:],
        depth + rope,
    ]
    arc = np.clip(axial - s0, 0, s1 - s0)
    radius = (
        hole
        + wall
        - np.sqrt(rc * rc - arc * arc)
        + np.maximum(0, axial - s1) * np.tan(angle)
    )
    slope = arc / np.sqrt(rc * rc - arc * arc)
    # Convex arc interpolation overestimates the allowed radius. Tighten the two endpoints of each arc chord.
    buffer = np.zeros(len(axial))
    for i in range(1, len(axial) - 2):
        err = (axial[i + 1] - axial[i]) ** 2 / (8 * rc * np.cos(angle) ** 3)
        buffer[i : i + 2] = np.maximum(buffer[i : i + 2], err)
    return axial, radius - buffer, slope


def solve(left, right, profiles, step):
    """Second-order cone program with fixed endpoints and a free cross-section position at the interface."""
    L, R = (wall_grid(p, step) for p in profiles)
    x = np.r_[left[0], -L[0][:0:-1], R[0], right[0]]
    if np.any(np.diff(x) <= 0):
        raise ValueError("Guide endpoint inside an end disk")
    bound = np.r_[L[1][:0:-1], R[1]]
    slope = np.r_[-L[2][:0:-1], R[2]]
    m = len(x) - 2
    nseg = m + 1
    nt = 2 * m
    nv = nt + nseg
    rows = []
    cols = []
    vals = []
    rhs = []
    cones = []
    # Conic form is A y + slack = b. Segment cone slacks are [t, dx, dy, dz].
    for k, dx in enumerate(np.diff(x)):
        start = len(rhs)
        d = np.zeros(2)
        if k == 0:
            d -= left[1:]
        if k == nseg - 1:
            d += right[1:]
        rhs.extend((0.0, dx, *d))
        cones.append(clarabel.SecondOrderConeT(4))
        rows.append(start)
        cols.append(nt + k)
        vals.append(-1.0)
        for node, sgn in ((k, -1), (k + 1, 1)):
            if 1 <= node <= m:
                for j in range(2):
                    rows.append(start + 2 + j)
                    cols.append(2 * (node - 1) + j)
                    vals.append(-sgn)
    for k, r in enumerate(bound):
        start = len(rhs)
        rhs.extend((r, 0.0, 0.0))
        cones.append(clarabel.SecondOrderConeT(3))
        for j in range(2):
            rows.append(start + 1 + j)
            cols.append(2 * k + j)
            vals.append(-1.0)
    A = sparse.csc_matrix((vals, (rows, cols)), shape=(len(rhs), nv))
    q = np.r_[np.zeros(nt), np.ones(nseg)]
    opt = clarabel.DefaultSettings()
    opt.verbose = False
    opt.max_iter = 180
    opt.tol_gap_abs = 3e-9
    opt.tol_gap_rel = 6e-11
    opt.tol_feas = 5e-10
    s = clarabel.DefaultSolver(
        sparse.csc_matrix((nv, nv)), q, A, np.array(rhs), cones, opt
    ).solve()
    if str(s.status) not in ("Solved", "AlmostSolved"):
        raise ValueError(f"Shared bore cone solve: {s.status}")
    u = np.asarray(s.x)
    p = np.c_[x, np.vstack([left[1:], u[:nt].reshape(m, 2), right[1:]])]
    d = np.diff(p, axis=0)
    ll = np.linalg.norm(d, axis=1)
    t = d / ll[:, None]
    z = np.asarray(s.z)[4 * nseg :].reshape(m, 3)
    wall = np.r_[z[:, 0] @ slope, z[:, 1:].sum(0)]
    turns = np.arctan2(
        np.linalg.norm(np.cross(t[:-1], t[1:]), axis=1),
        np.einsum("ij,ij->i", t[:-1], t[1:]),
    )
    return p, dict(
        segments=nseg,
        solver_status=str(s.status),
        solver_primal_residual=s.r_prim,
        solver_dual_residual=s.r_dual,
        length_mm=float(ll.sum()),
        interface_transverse_mm=p[np.argmin(abs(x)), 1:].tolist(),
        max_cone_violation_mm=float(
            max(0.0, np.max(np.linalg.norm(p[1:-1, 1:], axis=1) - bound))
        ),
        absolute_wrap_rad=float(turns.sum()),
        exit_angles_deg=np.degrees(np.arccos(np.clip(t[[0, -1], 0], -1, 1))).tolist(),
        endpoint_directions=t[[0, -1]].tolist(),
        wall_on_rope_normal_sum_per_N=wall.tolist(),
        force_balance_residual_per_N=float(np.linalg.norm(t[-1] - t[0] + wall)),
    )


def densify(p, step):
    return np.vstack(
        [
            *(
                np.linspace(
                    a, b, max(1, int(np.ceil(np.linalg.norm(b - a) / step))) + 1
                )[:-1]
                for a, b in zip(p, p[1:])
            ),
            p[-1:],
        ]
    )


def audit(p, ray, design, bodies):
    # In the shared rod frame x points distally, +y maps to CAD +y and +z to CAD -x.
    q = densify(p, 0.02)
    origin = 28 * np.array(design["rays_cad_xy"][ray])
    yx = np.c_[origin[0] - q[:, 2], origin[1] + q[:, 1]]
    out = {}
    # Across the coplanar interface, include spheres on both sides out to one rope radius.
    for name, face, lo, hi in (("M5", 48, -10.0, 1.0), ("M6", -48, -1.0, 10.0)):
        mask = (q[:, 0] >= lo) & (q[:, 0] <= hi)
        world = np.c_[yx[mask], face + q[mask, 0]]
        signed = bodies[name].signed(world) - 1.0
        i = int(np.argmin(signed))
        out[name] = dict(
            sample_count=len(world),
            minimum_clearance_mm=float(signed[i]),
            worst_cad_xyz_mm=world[i].tolist(),
        )
    return out


def geometry(rod, z, T):
    _, _, detail = rod.evaluate(z, T, detail=True)
    centre = 5 * rod.sub
    frame = detail["frames"][centre]
    p = detail["points"]
    pair = [centre - rod.sub // 4, centre + rod.sub // 4]
    ends = {}
    for ray, name in enumerate(RAYS):
        offset = rod.offsets3[2, ray]
        points = p[pair] + np.einsum("nij,j->ni", detail["frames"][pair], offset)
        ends[name] = ((points - p[centre]) @ frame - offset) * 1000.0
    return ends


def load_rod():
    design = json.loads((DESIGN / "design.json").read_text())
    mass = json.loads((ARCHIVE / "mass_model.json").read_text())
    lanes.install((21, 24, 28), 24, mass)
    rod = apply_bellmouth(lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8), design)
    profiles = np.array([rod.bellmouth_profiles[0, 1], rod.bellmouth_profiles[1, 0]])
    profiles[:, [0, 1, 3, 4]] *= 1000.0
    return design, rod, profiles


def run(a):
    design, rod, profiles = load_rod()
    states, _ = load_states(ARCHIVE / "equilibria_states.npz")
    bs = (
        {
            m: Body(DESIGN / n)
            for m, n in (("M5", "M5_lane_anchorB.stl"), ("M6", "M6_lane_anchorC.stl"))
        }
        if a.cad
        else None
    )
    stored = {}
    rows = []
    examples = []
    with (LANES / "morning_20261116/rigid_end_audit/rope_exits.csv").open() as f:
        reference = {
            (r["state"], r["ray"], r["module"]): float(r["span_length_mm"])
            for r in csv.DictReader(f)
            if r["set"] == "C"
            and (r["module"], r["end"]) in (("M5", "distal"), ("M6", "proximal"))
        }
    for label, z, T, _ in states:
        if a.cases and label not in a.cases:
            continue
        ends = geometry(rod, z, T)
        for i, name in enumerate(RAYS):
            left, right = ends[name]
            key = (name, z.tobytes())
            if key not in stored:
                p, cv = solve(left, right, profiles, a.step)
                # The old origin-constrained pair must reproduce both published lengths in their common frame.
                old = sum(
                    span_geometry(pt, sign, prof)[0]
                    for pt, sign, prof in (
                        (left, -1.0, profiles[0]),
                        (right, 1.0, profiles[1]),
                    )
                )
                check = reference[label, name, "M5"] + reference[label, name, "M6"]
                if abs(old - check) > 2e-7:
                    raise ValueError(
                        f"Published length mismatch {label}/{name}: {old - check}"
                    )
                cv.update(
                    old_origin_constrained_length_mm=float(old),
                    free_minus_old_length_mm=float(cv["length_mm"] - old),
                    design_margins_deg=(
                        np.degrees(profiles[:, 2]) - cv["exit_angles_deg"]
                    ).tolist(),
                )
                if bs:
                    cv["cad"] = audit(p, name, design, bs)
                stored[key] = p, cv
            p, cv = stored[key]
            t = float(T[2, i])
            angles = cv["absolute_wrap_rad"]
            tt = np.array(cv["endpoint_directions"])
            ratios = {
                f"{mu:g}": float(np.exp(mu * angles)) for mu in (0.0, 0.05, 0.15, 0.30)
            }
            row = dict(
                hold=int(label),
                ray=name,
                archived_uniform_tension_N=t,
                **cv,
                ideal_rope_on_joint_N=(t * (tt[-1] - tt[0])).tolist(),
                sliding_high_over_low_by_assumed_mu=ratios,
                high_tension_if_low_is_archived_mu015_N=t * ratios["0.15"],
            )
            rows.append(row)
            if label in ("64", "146") and name == "up":
                examples.append(
                    dict(hold=int(label), ray=name, guide_to_guide_xyz_mm=p.tolist())
                )
        if int(label) % 20 == 0:
            print("completed hold", label, flush=True)
    if not rows:
        raise ValueError("No requested holds found")
    out = dict(
        head_g=500.0,
        axis_order=["axial distal", "rod transverse y", "rod transverse z"],
        step_mm=a.step,
        unique_geometry_ropes=len(stored),
        cases=len(set(r["hold"] for r in rows)),
        checks=len(rows),
        friction_assumptions=[0, 0.05, 0.15, 0.30],
        examples=examples,
        records=rows,
    )
    a.out.parent.mkdir(exist_ok=True, parents=True)
    a.out.write_text(json.dumps(out, indent=2) + "\n")
    print("finished", out["cases"], "holds", len(rows), "ropes", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", type=float, default=0.15)
    ap.add_argument("--cases", nargs="+")
    ap.add_argument("--cad", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.step <= 0:
        ap.error("positive spacing required")
    run(a)
