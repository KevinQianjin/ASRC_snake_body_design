"""Sampled whole-mission FCL tilt probe of the bonded guides against the superposed solid body field.

Uses the unit body-relative-to-guide patch fields saved by ``mission_envelope.py --save-patch``
(G = 500 MPa, q5 mesh) and the per-step coefficients of ``rod_steps.npz``. For every STRIDE-th
mission state (plus the targeted steps of ``mission_probe.json``) and each station and land variant,
the exact FCL distance is evaluated for the untilted guide and the 26 +/-0.2 deg tilts of the
24 Nov ``solid_arm_probe.py`` method. Rigid-CAD clearance only; this is a SAMPLED sweep, not a
certification of the unsampled steps.
"""
import argparse, json, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mission_envelope as ME  # noqa: E402

BB, R, fcl = ME.BB, ME.R, ME.fcl
_ctx = {}


def _init(units, angle):
    P = np.load(units)
    _ctx["P"] = {k: P[k] for k in P.files}
    _ctx["S"] = np.load(HERE / "results/rod_steps.npz")
    _ctx["C"] = {st: ME.coeffs(_ctx["S"], st)[0] for st in BB.STATIONS}
    _ctx["T"] = [("none", 0, np.eye(4))] + ME.tilts(angle)
    _ctx["parts"] = {(cr, st): R.load_variant(f, st) for cr, f in ME.FOLDERS.items() for st in BB.STATIONS}


def one(job):
    crown, st, s = job
    P = _ctx["P"]; x = P[f"st{st:+d}_vertices"]; faces = P[f"st{st:+d}_faces"]
    rel = np.einsum("pik,k->pi", P[f"c{int(round(crown * 100)):02d}_st{st:+d}_rel"], _ctx["C"][st][s])
    near = P[f"c{int(round(crown * 100)):02d}_st{st:+d}_near"]
    body = fcl.CollisionObject(R.mesh_model(x + rel, faces))
    gaps = {}
    for name, sign, Mt in _ctx["T"]:
        key = name + ("" if sign == 0 else "+" if sign > 0 else "-")
        gaps[key] = min(R.gap(body, fcl.CollisionObject(R.mesh_model(
            m.copy().apply_transform(Mt).vertices, m.faces)))[0] for m in _ctx["parts"][(crown, st)].values())
    tilted = {k: g for k, g in gaps.items() if k != "none"}
    worst = min(tilted, key=tilted.get)
    return dict(crown_mm=crown, station_mm=st, step=int(s), gap_no_tilt_mm=gaps["none"],
                min_gap_tilted_mm=tilted[worst], worst_tilt=worst,
                near_guide_relative_motion_mm=float(np.linalg.norm(rel[near], axis=1).max()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default=str(HERE / "results/patch_q5/patch_units.npz"))
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--angle", type=float, default=0.2)
    ap.add_argument("--crown", type=float, nargs="+", default=[0.0, 0.06])
    ap.add_argument("--out", default=str(HERE / "results/probe_sweep.json"))
    a = ap.parse_args()
    t0 = time.monotonic()
    S = np.load(HERE / "results/rod_steps.npz"); n = len(S["end_rotvec"]); phase = ME.phase_of(n)
    extra = set()
    tp = HERE / "results/mission_probe.json"
    if tp.exists():
        extra = {r["step"] for r in json.loads(tp.read_text())["rows"]}
    steps = sorted(set(range(0, n, a.stride)) | extra | {n - 1})
    jobs = [(cr, st, s) for cr in a.crown for st in BB.STATIONS for s in steps]
    rows = []
    with Pool(a.workers, initializer=_init, initargs=(a.units, a.angle)) as p:
        for k, r in enumerate(p.imap_unordered(one, jobs, chunksize=8)):
            r["phase"] = ME.PHASES[phase[r["step"]]]
            rows.append(r)
            if k % 200 == 0:
                print(k, len(jobs), f"{time.monotonic() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: (r["crown_mm"], r["station_mm"], r["step"]))
    summ = []
    for cr in a.crown:
        for st in BB.STATIONS:
            rr = [r for r in rows if r["crown_mm"] == cr and r["station_mm"] == st]
            w = min(rr, key=lambda r: r["min_gap_tilted_mm"]); w0 = min(rr, key=lambda r: r["gap_no_tilt_mm"])
            byph = {}
            for r in rr:
                b = byph.setdefault(r["phase"], r)
                if r["min_gap_tilted_mm"] < b["min_gap_tilted_mm"]: byph[r["phase"]] = r
            summ.append(dict(crown_mm=cr, station_mm=st, n_steps=len(rr),
                             min_gap_tilted_mm=w["min_gap_tilted_mm"], at_step=w["step"], phase=w["phase"], worst_tilt=w["worst_tilt"],
                             min_gap_no_tilt_mm=w0["gap_no_tilt_mm"], no_tilt_step=w0["step"],
                             below_0p025_mm=sum(r["min_gap_tilted_mm"] < 0.025 for r in rr),
                             contacts_tilted=sum(r["min_gap_tilted_mm"] <= 0 for r in rr),
                             by_phase={p: dict(min_gap_tilted_mm=b["min_gap_tilted_mm"], step=b["step"]) for p, b in byph.items()}))
            print(summ[-1], flush=True)
    Path(a.out).write_text(json.dumps(dict(scope=__doc__, stride=a.stride, angle_deg=a.angle, units=str(Path(a.units).relative_to(HERE)),
                                          n_jobs=len(jobs), summary=summ, rows=rows, elapsed_s=time.monotonic() - t0), indent=1, default=float))
    print("done", f"{time.monotonic() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
