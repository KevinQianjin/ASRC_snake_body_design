"""Deformed-strut envelope inside the M5 +/-12 mm outer-web sockets for the rotating seat.

Test 2, stage 1 of docs/500g_validation_plan.md. Reads converged rotating-seat
("point") equilibria saved by ../m5_large_rotation_20261118/study.py and expresses
both shell faces of every mounting-strut node inside the +/-1.62 mm socket window
in the moving guide frame. It then measures how far the deformed strut moves
toward each socket wall, compared with the undeformed strut, as a function of the
deformed position along the strut, and scores candidate cavity gap profiles.

Coordinates per land follow the V3 socket definition (guide_v3/verify_socket_land.py):
the gap is measured in the plane of the 3.2 mm guide plate, at each local axial
height z of the plate, from the undeformed web faces.
  z  module-axial height relative to the land pivot (socket spans |z| <= 1.62),
  xi radial offset from the undeformed web's line at that z. The M5 mounting web
     crosses the plate at about 32 degrees to the radial direction, so the web
     occupies a fixed interval xi_min..xi_max at every z ("follows the web slope"),
  v  along the rib normal (tangential, shell-thickness direction).
A radial wall sits g(z) outside xi_min..xi_max; a tangential wall g(z) outside +/- h/2.
Units: mm, N, degrees. The fixture and its limitations are those of the source study.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "m5_large_rotation_20261118"
sys.path.insert(0, str(SRC))

from continuation import Checkpoints  # noqa: E402
from shell import Mesh, Model, rotation  # noqa: E402

HALF = 1.62  # socket half-span along the module axis, mm (V3 design.json 3.24 / 2)
BINS = np.linspace(-1.9, 1.9, 39)


def v3_gap(w, g0=0.15, land=0.5, slope=1.5):
    return g0 + slope * np.maximum(np.abs(w) - land / 2.0, 0.0)


def strut_frame(mesh, i, s, centre_r):
    """Undeformed web nodes near the socket and the radial-per-axial slope of the web."""
    r, z = mesh.x.T
    near = (np.abs(z - s) <= HALF + 0.35) & (np.abs(r - centre_r) < 4.0)
    zz, rr = z[near] - s, r[near] - centre_r
    core = np.abs(zz) <= HALF
    # The web edges are parallel lines. Their radial-per-axial slope is the one that
    # minimises the radial width of the web band over the socket window. (A principal
    # axis of the clipped node cloud is biased by the oblique window cuts.)
    res = minimize_scalar(
        lambda k: np.ptp(rr[core] - k * zz[core]), bounds=(-4.0, 4.0), method="bounded",
        options=dict(xatol=1e-7),
    )
    t2 = np.array([res.x, 1.0]) / np.hypot(res.x, 1.0)
    return np.flatnonzero(near), t2


def nodal_thickness(mesh):
    h = np.zeros(mesh.n)
    c = np.zeros(mesh.n)
    for k in range(3):
        np.add.at(h, mesh.t[:, k], mesh.thick)
        np.add.at(c, mesh.t[:, k], 1.0)
    return h / np.maximum(c, 1)


def analyse_state(model, q, h_node, frames):
    m = model.mesh
    x = model.mapping(q)[0]
    out = []
    for (i, s), (ids_land, centre, mounted) in model.rib_lands.items():
        if not mounted:
            continue
        local, t2 = frames[(i, s)]
        g = model.bodies[f"G{s:+}"]
        Rg = rotation(q[g.rot])[0]
        origin = g.centre + q[g.pos]
        pivot = origin + Rg @ (centre - g.centre)
        Rl = rotation(q[model.bodies[f"L{i}_{s}"].rot])[0]
        rv = Rotation.from_matrix(Rg.T @ Rl).as_rotvec()
        er, n = m.radial[i], m.normals[i]
        ez = np.array([0.0, 0.0, 1.0])
        slope = t2[0] / t2[1]  # radial change per unit axial height along the web
        ids = local + i * m.n
        h = h_node[local]
        p0 = m.xyz[ids] - centre
        p = (x[ids, :3] - pivot) @ Rg
        d = x[ids, 3:] @ Rg
        Z0, X0, V0, Z1, X1, V1 = [], [], [], [], [], []
        for side in (-1.0, 1.0):
            f0 = p0 + side * 0.5 * h[:, None] * n
            f1 = p + side * 0.5 * h[:, None] * d
            for F, (Zs, Xs, Vs) in ((f0, (Z0, X0, V0)), (f1, (Z1, X1, V1))):
                zz = F @ ez
                Zs.append(zz)
                Xs.append(F @ er - slope * zz)
                Vs.append(F @ n)
        Z0, X0, V0, Z1, X1, V1 = map(np.concatenate, (Z0, X0, V0, Z1, X1, V1))
        # Along-web frame: s along the web midline (in-plane), p perpendicular in-plane.
        tw = t2[0] * er + t2[1] * ez
        pw = np.cross(n, tw)
        F0 = np.concatenate([p0 + k * 0.5 * h[:, None] * n for k in (-1.0, 1.0)])
        F1 = np.concatenate([p + k * 0.5 * h[:, None] * d for k in (-1.0, 1.0)])
        S0, P0, S1, P1 = F0 @ tw, F0 @ pw, F1 @ tw, F1 @ pw
        core = np.abs(Z0) <= HALF
        xmin, xmax = X0[core].min(), X0[core].max()
        vmin, vmax = V0[core].min(), V0[core].max()
        inside = np.abs(Z1) <= HALF
        z1, x1, v1 = Z1[inside], X1[inside], V1[inside]
        intr_u = np.maximum(x1 - xmax, xmin - x1)
        intr_v = np.maximum(v1 - vmax, vmin - v1)
        centres = 0.5 * (BINS[1:] + BINS[:-1])
        kb = np.digitize(z1, BINS) - 1
        need_u = np.full(len(centres), np.nan)
        need_v = np.full(len(centres), np.nan)
        for b in range(len(centres)):
            sel = kb == b
            if sel.any():
                need_u[b] = intr_u[sel].max()
                need_v[b] = intr_v[sel].max()
        land = np.abs(Z0) <= 0.25
        pmin, pmax = P0[core].min(), P0[core].max()
        intr_p = np.maximum(P1 - pmax, pmin - P1)[inside]
        s1 = S1[inside]
        out.append(
            dict(
                station_mm=s,
                rib_deg=float(m.theta[i]),
                web_axis_rz=[float(t2[0]), float(t2[1])],
                web_radial_width_mm=float(xmax - xmin),
                web_thickness_mm=float(vmax - vmin),
                relative_rotation_deg=float(np.degrees(np.linalg.norm(rv))),
                rotation_components_deg_radial_axial_normal=[
                    float(np.degrees(rv @ a)) for a in (er, ez, n)
                ],
                z_bins_mm=centres.tolist(),
                need_radial_mm=[None if np.isnan(a) else float(a) for a in need_u],
                need_tangential_mm=[None if np.isnan(a) else float(a) for a in need_v],
                max_need_radial_mm=float(np.nanmax(need_u)),
                max_need_tangential_mm=float(np.nanmax(need_v)),
                web_perpendicular_width_mm=float(pmax - pmin),
                _axes_in_guide=(tw, pw, n),
                _Rg=Rg,
                points=dict(w=z1, iu=intr_u, iv=intr_v, s=s1, ip=intr_p),
                land_axial_slip_mm=float(np.abs(Z1[land] - Z0[land]).max()),
            )
        )
    return out


def score(lands, profile):
    worst = None
    for L in lands:
        pts = L["points"]
        g = profile(pts["w"])
        cu = g - pts["iu"]
        cv = g - pts["iv"]
        for name, c in (("radial", cu), ("tangential", cv)):
            k = int(np.argmin(c))
            row = (float(c[k]), name, L["station_mm"], L["rib_deg"], float(pts["w"][k]))
            if worst is None or row[0] < worst[0]:
                worst = row
    return dict(
        min_clearance_mm=worst[0],
        direction=worst[1],
        station_mm=worst[2],
        rib_deg=worst[3],
        z_mm=worst[4],
    )


def bowtie_clearance(lands, land_len, c, k):
    """Minimum clearance of a bow-tie cavity g(s) = c + k max(|s| - land_len/2, 0).

    s is the along-web distance from the land pivot. The same profile is applied
    to both in-plane perpendicular walls and both tangential walls."""
    worst = None
    for L in lands:
        P = L["points"]
        g = c + k * np.maximum(np.abs(P["s"]) - land_len / 2.0, 0.0)
        for name, need in (("perpendicular", P["ip"]), ("tangential", P["iv"])):
            cl = g - need
            j = int(np.argmin(cl))
            row = (float(cl[j]), name, L["station_mm"], L["rib_deg"], float(P["s"][j]))
            if worst is None or row[0] < worst[0]:
                worst = row
    return dict(zip(("min_clearance_mm", "direction", "station_mm", "rib_deg", "s_mm"), worst))


def land_loads(L, src, frac):
    """Copy a land row and resolve its solved guide-on-rib force into seat axes."""
    row = {k: v for k, v in L.items() if not k.startswith("_") and k != "points"}
    if src is None:
        return row
    sample = next((x for x in src["samples"] if abs(x["fraction"] - frac) < 1e-9), None)
    if sample is None:
        return row
    match = next(
        x for x in sample["lands"] if x["station_mm"] == L["station_mm"] and abs(x["rib_deg"] - L["rib_deg"]) < 1e-6
    )
    F = L["_Rg"].T @ np.asarray(match["force_N"])  # proximal axes -> moving guide axes
    tw, pw, n = L["_axes_in_guide"]
    row["force_N"] = float(np.linalg.norm(F))
    row["force_along_web_N"] = float(F @ tw)
    row["force_perpendicular_inplane_N"] = float(F @ pw)
    row["force_tangential_N"] = float(F @ n)
    return row


BOWTIES = [
    (ell, c, k)
    for ell in (0.3, 0.6)
    for c in (0.10, 0.15, 0.20)
    for k in (0.10, 0.20, 0.25, 0.30, 0.35)
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--area", type=float, default=0.18)
    ap.add_argument("--cache", type=Path, nargs="+", required=True)
    ap.add_argument("--cases", nargs="+", default=["bend67.5", "bend0", "146", "141", "47", "64"])
    ap.add_argument("--fractions", type=float, nargs="+", default=[0.25, 0.5, 0.75, 1.0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--results", type=Path, nargs="+", help="study/refine JSON folders of the same runs")
    ap.add_argument("--hole-radius", type=float, help="evaluate pinned-seat states from pin_seat.py")
    a = ap.parse_args()
    if a.hole_radius is not None:
        import pin_seat
        import shell

        pin_seat.install(a.hole_radius)
        mesh = shell.Mesh(a.area)
    else:
        mesh = Mesh(a.area)
    model = Model(mesh, "point")
    h_node = nodal_thickness(mesh)
    frames = {}
    for (i, s), (ids, centre, mounted) in model.rib_lands.items():
        if mounted:
            frames[(i, s)] = strut_frame(mesh, i, s, mesh.land_centres[s])
    profiles = {
        "V3 bonded land 0.15 mm, slope 1.5": lambda w: v3_gap(w, 0.15),
        "V3 variant land 0.25 mm, slope 1.5": lambda w: v3_gap(w, 0.25),
        "Zero land gap, slope 1.5 (kinematic limit of V3 relief)": lambda w: v3_gap(w, 0.0),
        "Uniform 0.15 mm (no relief)": lambda w: 0.15 + 0.0 * w,
    }
    results = dict(mesh=mesh.info, area=a.area, cases={})
    for case in a.cases:
        cache = next(c for c in a.cache if (c / f"point_{case}").exists())
        cp = Checkpoints(model, case, None, cache)
        if not cp.same_mesh:
            raise ValueError("cache mesh differs")
        rows = []
        src = None
        if a.results is not None:
            src = json.loads(next(r for r in a.results if (r / f"point_{case}.json").exists()).joinpath(
                f"point_{case}.json").read_text())
        for f in a.fractions:
            if round(f, 9) not in cp.seeds:
                continue  # only exactly converged checkpoints, never interpolated states
            q, _ = cp.load(round(f, 9))
            lands = analyse_state(model, q, h_node, frames)
            rows.append(
                dict(
                    fraction=f,
                    profile_scores={k: score(lands, p) for k, p in profiles.items()},
                    bowtie={
                        f"land {ell:.2f} mm, clearance {c:.2f} mm, slope {k:.2f}": bowtie_clearance(
                            lands, ell, c, k
                        )
                        for ell, c, k in BOWTIES
                    },
                    lands=[land_loads(L, src, f) for L in lands],
                    _points=lands,
                )
            )
        results["cases"][case] = rows
        print(case, [(r["fraction"], max(L["max_need_radial_mm"] for L in r["lands"])) for r in rows], flush=True)
    # Required profile across all cases and fractions: max need per w bin.
    centres = 0.5 * (BINS[1:] + BINS[:-1])
    env_u = np.full(len(centres), -np.inf)
    env_v = np.full(len(centres), -np.inf)
    allpts = []
    for case_name, rows in results["cases"].items():
        for r in rows:
            for L in r["lands"]:
                env_u = np.fmax(env_u, np.array([np.nan if a is None else a for a in L["need_radial_mm"]]))
                env_v = np.fmax(env_v, np.array([np.nan if a is None else a for a in L["need_tangential_mm"]]))
            allpts.extend((f"{case_name}@{r['fraction']:g}", L) for L in r.pop("_points"))
    results["envelope"] = dict(
        z_bins_mm=centres.tolist(),
        need_radial_mm=[None if not np.isfinite(a) else float(a) for a in env_u],
        need_tangential_mm=[None if not np.isfinite(a) else float(a) for a in env_v],
    )
    arrays = {}
    for case, pts in allpts:
        for key in ("w", "iu", "iv", "s", "ip"):
            name = dict(w="z", iu="radial", iv="tangential", s="s", ip="perpendicular")[key]
            arrays.setdefault(f"{case}__{name}", []).append(pts["points"][key])
    np.savez_compressed(a.out.with_suffix(".npz"), **{k: np.concatenate(v) for k, v in arrays.items()})
    a.out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
