"""Whole-mission bond-demand and relative-motion envelope of the bonded whole-body solid M6 model by
linear superposition — evening, 25 November 2026 (handoff item 1 of the 24 November evening run).

The 24 November model (``evening_20261124/body_bond.py``) is linear in its two step inputs: the
rotation prescribed on the D1 end master and the two guide wrenches. One factorisation per
(G, crown) case is solved for 15 unit right-hand sides (three unit D1 rotations, six unit wrench
components per guide). Every recovered quantity used here (layer tractions, layer slip, guide-
minus-land rotation, non-rigid socket-wall motion and the body-relative-to-guide motion of the
clearance patch) is a linear map of the solution, so each is stored as a (quantity x 15) matrix and
combined per step with that step's coefficients

    c_st(step) = [ s_st(step) * omega(step) (3) | W_-12(step) (6) | W_+12(step) (6) ],

omega = rod relative D0->D1 end rotation, s_st = rod local-to-mean moment ratio at the station
("local" scaling of the 24 Nov run), W = archived Round 2 station wrenches. This is exactly the
24 November "total_local" field, evaluated at all 3,405 states of the archived 500 g yaw/pitch
mission instead of two. The step-1,709/1,885 values are re-derived and compared with the archived
direct solves as a consistency check.

Then the exact FCL tilt probe (26 tilts of +/-0.2 deg, the 24 Nov ``solid_arm_probe.py`` method) is
run on selected steps: the archived baselines, the 20 Nov low-margin steps (787 at -12 mm, 430 at
+12 mm) and the steps with the largest body-relative-to-guide motion NEAR THE GUIDE.

Scope limits unchanged: linear small-strain FE (linearised rotations to ~0.85 rad, checked to ~1%
by the 24 Nov total-Lagrangian run for end rotation only), assumed adhesive G, PA12 E = 1,530 MPa,
no NiTi backbone in the body, no rope contact, no adhesive failure, rigid-CAD clearance only.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PREV = HERE.parent / "evening_20261124"
sys.path.insert(0, str(PREV))
import body_bond as BB  # noqa: E402
from coupled_land import HALF  # noqa: E402

ROUND2 = HERE.parents[1] / "extreme_tests/round2_20261119"
sys.path.insert(0, str(ROUND2)); sys.path.insert(0, str(HERE.parent / "evening_20261121"))
import m6_full as R  # noqa: E402
from common import CAD, SOURCE  # noqa: E402
from tilt_mission import tilts  # noqa: E402

FOLDERS = {0.0: CAD / "m6_bond_gap_20261119", 0.06: CAD / "m6_crowned_land_20261120"}
COMP = ("normal", "axial", "cross")
PHASES = ["straighten", "entry", "right_out", "right_return", "left_out", "left_return", "pitch_up",
          "pitch_up_return", "pitch_down", "pitch_down_return", "exit"]


def phase_of(n):
    import csv
    rows = list(csv.DictReader(open(SOURCE / "phase_results.csv")))
    counts = [int(r["motion_states_including_start"]) for r in rows]
    assert [r["phase"] for r in rows] == PHASES and sum(counts) == n, (counts, n)
    return np.repeat(np.arange(len(counts)), counts)


def unit_maps(B, U, patches):
    """Linear recovery matrices (quantity x 15) from the 15 unit solutions."""
    n = B.n
    ub = np.stack([(B.T @ U[:n, j]).reshape(-1, 3) for j in range(U.shape[1])], -1)  # (N,3,15)
    maps = []
    for L in B.lands:
        g = n + 6 * BB.STATIONS.index(L["st"])
        q = U[g:g + 6]                                  # (6,15)
        us = (B.MT[L["rows"]] @ U[:n]).reshape(-1, 3, U.shape[1])
        slip = np.einsum("aij,jk->aik", L["A"].reshape(-1, 3, 6), q) - us  # (m,3,15)
        f = np.einsum("mij,mjk->mik", L["D"], slip)
        tr = f / L["ws"][:, None, None]
        ns = L["ns"]; ez = np.array([0, 0, 1.0])
        ax = ez - ns * ns[:, 2:3]; ax /= np.linalg.norm(ax, axis=1, keepdims=True)
        cr = np.cross(ns, ax)
        comps = np.stack([np.einsum("mik,mi->mk", tr, v) for v in (ns, ax, cr)], 1)  # (m,3,15)
        P = B.X[L["band"]] - [0, 0, L["st"]]
        Afit = np.zeros((3 * len(P), 6)); Afit[:, :3] = np.tile(np.eye(3), (len(P), 1))
        Afit[:, 3:] = -np.vstack([BB.CB.S.skew(p) for p in P])
        land = np.linalg.pinv(Afit) @ ub[L["band"]].reshape(-1, U.shape[1])   # (6,15)
        Ps = B.X[L["sock"]] - [0, 0, L["st"]]
        rig = land[None, :3] + np.cross(land[3:].T[None], Ps[:, None]).transpose(0, 2, 1)  # (s,3,15)
        dist = ub[L["sock"]] - rig
        zh = Ps[:, 2]
        maps.append(dict(key=f"{L['st']:+d}@{L['th']}", st=L["st"], comps=comps, ws=L["ws"], slip=slip,
                         rel_rot=q[3:] - land[3:], sock_in=dist[np.abs(zh) <= HALF + 1e-9],
                         sock_end=dist[np.abs(zh) >= BB.SOCKET_HALF - 0.3]))
    pm = {}
    for st, (fine, MT, mb, near) in patches.items():
        g = n + 6 * BB.STATIONS.index(st)
        x = np.asarray(fine.vertices)
        u = (MT @ U[:n]).reshape(-1, 3, U.shape[1])
        q = U[g:g + 6]
        rel = u - (q[None, :3] + np.cross(q[3:].T[None], x[:, None]).transpose(0, 2, 1))
        pm[st] = dict(all=rel, near=rel[near])
    return maps, pm


def coeffs(steps_npz, st):
    end = steps_npz["end_rotvec"]; loc = steps_npz["local_rotvec"][:, BB.STATIONS.index(st)]
    uniform = np.linalg.norm(end, axis=1) * 24.0 / (BB.BS.Z_HI - BB.BS.Z_LO)
    s = np.linalg.norm(loc, axis=1) / uniform
    W = steps_npz["station_wrench"]
    return np.c_[s[:, None] * end, W[:, 0], W[:, 1]], s


def norm_max(F, C, chunk=400):
    """max over points of |F . c| (vector field (p,3,15)) for every step row of C."""
    out = np.empty(len(C))
    for i in range(0, len(C), chunk):
        v = np.einsum("pik,sk->spi", F, C[i:i + chunk], optimize=True)
        out[i:i + chunk] = np.sqrt((v ** 2).sum(-1)).max(1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", type=float, default=5.0)
    ap.add_argument("--max-vol", type=float, default=0.4)
    ap.add_argument("--max-edge", type=float, default=0.08)
    ap.add_argument("--G", type=float, nargs="+", default=[500.0, 1500.0])
    ap.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    ap.add_argument("--probe-G", type=float, default=500.0)
    ap.add_argument("--probe-top", type=int, default=3)
    ap.add_argument("--angle", type=float, default=0.2)
    ap.add_argument("--near-r", type=float, default=12.0, help="near-guide patch: r > near-r and |z-st| < near-z")
    ap.add_argument("--near-z", type=float, default=3.0)
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--no-probe", action="store_true", help="skip the FCL probe stage")
    ap.add_argument("--save-patch", action="store_true",
                    help="save the probe-G unit patch fields for probe_sweep.py (results/patch_units.npz)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    S = np.load(HERE / "results/rod_steps.npz")
    nst = len(S["end_rotvec"]); phase = phase_of(nst)
    C = {st: coeffs(S, st) for st in BB.STATIONS}
    B = BB.Body(a.quality, a.max_vol, a.max_edge)
    print("mesh", B.mesh, f"{time.monotonic() - t0:.0f}s", flush=True)
    import trimesh
    mesh = trimesh.load_mesh(BB.BS.BODY)
    patches = {}
    for st in BB.STATIONS:
        tri = mesh.vertices[mesh.faces]
        keep = np.all(np.abs(tri[:, :, 2] - st) < 5, axis=1) | ((tri[:, :, 2].min(1) < st + 3) & (tri[:, :, 2].max(1) > st - 3))
        fine = R.refine_axial(R.patch(mesh.vertices - [0, 0, st], mesh.faces[keep]), 0.5)
        x = np.asarray(fine.vertices)
        M, mb = BB.locate(B.X, B.conn, x + [0, 0, st])
        near = (np.hypot(x[:, 0], x[:, 1]) > a.near_r) & (np.abs(x[:, 2]) < a.near_z)
        patches[st] = (fine, (M @ B.T).tocsr(), mb, near)
    rhs = [(e, np.zeros(12)) for e in np.eye(3)] + [(np.zeros(3), w) for w in np.eye(12)]
    cases, store, unit = [], {}, {}
    for G in a.G:
        for crown in a.crown:
            tc = time.monotonic()
            U, resid = B.solve(B.system(G, crown), rhs)
            maps, pm = unit_maps(B, U, patches)
            if G == a.probe_G:
                unit[crown] = (U, pm)
            res = {}
            for m in maps:
                Cs = C[m["st"]][0]
                w = m["ws"] / m["ws"].sum()
                pk = np.empty((nst, 3)); mean = np.empty((nst, 3))
                for i in range(0, nst, 400):
                    v = np.einsum("pik,sk->spi", m["comps"], Cs[i:i + 400], optimize=True)
                    pk[i:i + 400] = np.abs(v).max(1); mean[i:i + 400] = np.einsum("spi,p->si", np.abs(v), w)
                res[m["key"]] = dict(peak=pk, mean=mean, slip=norm_max(m["slip"], Cs),
                                     rel_rot_deg=np.degrees(np.linalg.norm(Cs @ m["rel_rot"].T, axis=1)),
                                     sock_in=norm_max(m["sock_in"], Cs), sock_end=norm_max(m["sock_end"], Cs))
            for st in BB.STATIONS:
                Cs = C[st][0]
                res[f"patch{st:+d}"] = dict(near=norm_max(pm[st]["near"], Cs), all=norm_max(pm[st]["all"], Cs))
            store[(G, crown)] = res
            env = {}
            for k, r in res.items():
                if k.startswith("patch"):
                    env[k] = {q: dict(max=float(r[q].max()), step=int(r[q].argmax()), phase=PHASES[phase[r[q].argmax()]])
                              for q in ("near", "all")}
                    continue
                e = {}
                for qn in ("peak", "mean"):
                    for ci, c in enumerate(COMP):
                        s = int(r[qn][:, ci].argmax())
                        e[f"{qn}_{c}_MPa"] = dict(max=float(r[qn][s, ci]), step=s, phase=PHASES[phase[s]],
                                                  at_1709=float(r[qn][1709, ci]))
                for qn in ("slip", "rel_rot_deg", "sock_in", "sock_end"):
                    s = int(r[qn].argmax())
                    e[qn] = dict(max=float(r[qn][s]), step=s, phase=PHASES[phase[s]], at_1709=float(r[qn][1709]))
                env[k] = e
            cases.append(dict(G_MPa=G, crown_mm=crown, solve_residual=resid, envelope=env,
                              seconds=time.monotonic() - tc))
            print(f"G {G} crown {crown} resid {resid:.1e} {time.monotonic() - tc:.0f}s", flush=True)
            for k, e in env.items():
                if not k.startswith("patch"):
                    print(f"  {k} ax pk {e['peak_axial_MPa']['max']:.2f}@{e['peak_axial_MPa']['step']} "
                          f"(1709 {e['peak_axial_MPa']['at_1709']:.2f}) mean {e['mean_axial_MPa']['max']:.2f}@{e['mean_axial_MPa']['step']} "
                          f"(1709 {e['mean_axial_MPa']['at_1709']:.2f}) n pk {e['peak_normal_MPa']['max']:.2f}@{e['peak_normal_MPa']['step']}", flush=True)
                else:
                    print(f"  {k} near {e['near']['max']:.4f}@{e['near']['step']} all {e['all']['max']:.3f}@{e['all']['step']}", flush=True)
            np.savez_compressed(out / f"mission_G{int(G)}_c{int(round(crown * 100)):02d}.npz",
                                **{f"{k}__{q}": v for k, r in res.items() for q, v in r.items()},
                                local_scale=np.stack([C[st][1] for st in BB.STATIONS], 1), phase=phase)
            doc = dict(scope=__doc__, mesh=B.mesh, parameters=vars(a), n_steps=nst, phases=PHASES,
                       phase_step_ranges={p: [int(np.flatnonzero(phase == i)[0]), int(np.flatnonzero(phase == i)[-1])]
                                          for i, p in enumerate(PHASES)}, cases=cases)
            (out / "mission_envelope.json").write_text(json.dumps(doc, indent=1, default=float))
    if a.save_patch:
        np.savez_compressed(out / "patch_units.npz", **{
            f"c{int(round(cr * 100)):02d}_st{st:+d}_{k}": v for cr, (U, pm) in unit.items() for st in BB.STATIONS
            for k, v in (("rel", pm[st]["all"]), ("near", patches[st][3]))},
            **{f"st{st:+d}_vertices": np.asarray(patches[st][0].vertices) for st in BB.STATIONS},
            **{f"st{st:+d}_faces": np.asarray(patches[st][0].faces) for st in BB.STATIONS},
            probe_G=a.probe_G)
    if a.no_probe:
        print("done (no probe)", f"{time.monotonic() - t0:.0f}s", flush=True)
        return
    # ---- FCL tilt probe at selected steps (G = probe_G) ----
    T = [("none", 0, np.eye(4))] + tilts(a.angle)
    rows = []
    for crown, (U, pm) in unit.items():
        res = store[(a.probe_G, crown)]
        for st in BB.STATIONS:
            near = res[f"patch{st:+d}"]["near"]
            rr = np.concatenate([res[f"{st:+d}@{th}"]["rel_rot_deg"][None] for th in BB.MOUNT]).max(0)
            sel = [1709, 1885, 787 if st == -12 else 430]
            for s in list(np.argsort(near)[::-1]) :
                if len([x for x in sel if x not in (1709, 1885, 787, 430)]) >= a.probe_top: break
                if all(abs(int(s) - x) > 20 for x in sel): sel.append(int(s))
            s_rr = int(rr.argmax())
            if all(abs(s_rr - x) > 20 for x in sel): sel.append(s_rr)
            fine, MT, mb, nearmask = patches[st]
            x = np.asarray(fine.vertices)
            parts = R.load_variant(FOLDERS[crown], st)
            for s in sel:
                c = C[st][0][s]
                rel = np.einsum("pik,k->pi", pm[st]["all"], c)
                body = fcl.CollisionObject(R.mesh_model(x + rel, fine.faces))
                gaps, by_part = {}, {}
                for name, sign, Mt in T:
                    key = name + ("" if sign == 0 else "+" if sign > 0 else "-")
                    by_part[key] = {p: R.gap(body, fcl.CollisionObject(R.mesh_model(
                        mm.copy().apply_transform(Mt).vertices, mm.faces)))[0] for p, mm in parts.items()}
                    gaps[key] = min(by_part[key].values())
                tilted = {k: g for k, g in gaps.items() if k != "none"}
                worst = min(tilted, key=tilted.get)
                rows.append(dict(step=int(s), phase=PHASES[phase[s]], station_mm=st, crown_mm=crown, G_MPa=a.probe_G,
                                 local_moment_scale=float(C[st][1][s]),
                                 end_rotation_deg=float(np.degrees(np.linalg.norm(S["end_rotvec"][s]))),
                                 near_guide_relative_motion_mm=float(near[s]),
                                 max_relative_body_motion_mm=float(np.linalg.norm(rel, axis=1).max()),
                                 gap_no_tilt_mm=gaps["none"], min_gap_tilted_mm=tilted[worst], worst_tilt=worst,
                                 governing_part=min(by_part[worst], key=by_part[worst].get), gaps_mm=gaps))
                print("probe", s, PHASES[phase[s]], st, crown, f"near {near[s]:.4f} gap {gaps['none']:.5f} "
                      f"tilted {tilted[worst]:.5f} {worst}", flush=True)
                (out / "mission_probe.json").write_text(json.dumps(dict(
                    scope="Exact FCL clearance (26 tilts) with the superposed solid field; see mission_envelope.py",
                    angle_deg=a.angle, spacing_mm=0.5, near_patch=dict(r_gt_mm=a.near_r, abs_dz_lt_mm=a.near_z),
                    rows=rows, elapsed_s=time.monotonic() - t0), indent=1, default=float))
    print("done", f"{time.monotonic() - t0:.0f}s", flush=True)


import fcl  # noqa: E402

if __name__ == "__main__":
    main()
