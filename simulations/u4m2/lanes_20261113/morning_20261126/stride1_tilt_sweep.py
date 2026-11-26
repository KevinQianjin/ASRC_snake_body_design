"""Stride-1 FCL tilt sweep around every per-phase minimum of the 25 Nov sampled sweep.

Handoff item 2 from evening_20261125/HANDOFF.md:
Evaluates the exact FCL distance (untilted + 26 rigid +/-0.2 deg tilts) at stride 1 on
[s_min - 10, s_min + 10] around every per-phase minimum from evening_20261125/results/probe_sweep.json
for both stations (z = -12, +12 mm) and both land variants (uncrowned, crowned 0.06 mm),
using the regenerated G = 500 MPa q5 unit patch fields.
"""
import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PREV25 = HERE.parent / "evening_20261125"
sys.path.insert(0, str(PREV25))
import mission_envelope as ME  # noqa: E402
import probe_sweep as PS  # noqa: E402


def _install_safe_tet_mesh():
    """Fallback to TetGen T1e-9 / T1e-6 tolerance if default switch hits removevertexbyflips."""
    import tetgen
    BS = ME.BB.BS

    def safe_tet_mesh(solid, quality, max_vol):
        verts = np.asarray(solid.vertices, float)
        faces = np.asarray(solid.faces, np.int32)
        for tol in ("", "T1e-9", "T1e-6", "T1e-5"):
            try:
                tg = tetgen.TetGen(verts, faces)
                nodes, tets = tg.tetrahedralize(switches=f"pq{quality}a{max_vol}{tol}Q")[:2]
                return np.asarray(nodes, float), np.asarray(tets, np.int64)
            except RuntimeError:
                continue
        raise RuntimeError(f"TetGen failed for q={quality}, a={max_vol}")

    BS.tet_mesh = safe_tet_mesh


def ensure_patch_units(units_path):
    """Regenerate patch_units.npz (G=500, q5) if not present on disk."""
    p = Path(units_path)
    if p.exists():
        return
    print(f"{p} not found; regenerating G=500 q5 patch units...", flush=True)
    _install_safe_tet_mesh()
    orig_argv = sys.argv
    sys.argv = [
        "mission_envelope.py", "--G", "500", "--no-probe", "--save-patch",
        "--out", str(p.parent),
    ]
    try:
        ME.main()
    finally:
        sys.argv = orig_argv
    assert p.exists(), f"Failed to generate {p}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default=str(PREV25 / "results/patch_q5/patch_units.npz"))
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--angle", type=float, default=0.2)
    ap.add_argument("--out", default=str(HERE / "results/stride1_tilt_sweep.json"))
    a = ap.parse_args()

    ensure_patch_units(a.units)

    t0 = time.monotonic()
    S = np.load(PREV25 / "results/rod_steps.npz")
    n = len(S["end_rotvec"])
    phase = ME.phase_of(n)
    prev = json.loads((PREV25 / "results/probe_sweep.json").read_text())

    jobs = []
    windows_by_key = {}
    prev_summary = {}
    for s in prev["summary"]:
        key = (float(s["crown_mm"]), int(s["station_mm"]))
        prev_summary[key] = s
        steps = set()
        for ph, info in s["by_phase"].items():
            cstep = int(info["step"])
            for stp in range(max(0, cstep - a.window), min(n, cstep + a.window + 1)):
                steps.add(stp)
        sorted_steps = sorted(steps)
        windows_by_key[key] = sorted_steps
        for stp in sorted_steps:
            jobs.append((key[0], key[1], stp))

    print(f"Running {len(jobs)} stride-1 FCL probes on {a.workers} workers...", flush=True)
    rows = []
    with Pool(a.workers, initializer=PS._init, initargs=(a.units, a.angle)) as p:
        for k, r in enumerate(p.imap_unordered(PS.one, jobs, chunksize=8)):
            r["phase"] = ME.PHASES[phase[r["step"]]]
            rows.append(r)
            if (k + 1) % 100 == 0 or (k + 1) == len(jobs):
                print(f"  {k + 1}/{len(jobs)} ({time.monotonic() - t0:.1f}s)", flush=True)

    rows.sort(key=lambda r: (r["crown_mm"], r["station_mm"], r["step"]))

    summary = []
    max_drop_overall = 0.0
    for (cr, st), s_prev in prev_summary.items():
        rr = [r for r in rows if r["crown_mm"] == cr and r["station_mm"] == st]
        w = min(rr, key=lambda r: r["min_gap_tilted_mm"])
        w0 = min(rr, key=lambda r: r["gap_no_tilt_mm"])
        prev_min = float(s_prev["min_gap_tilted_mm"])
        delta_mm = w["min_gap_tilted_mm"] - prev_min  # negative means lower than stride-5
        drop_mm = max(0.0, prev_min - w["min_gap_tilted_mm"])
        max_drop_overall = max(max_drop_overall, drop_mm)

        by_phase = {}
        for ph in ME.PHASES:
            pr = [r for r in rr if r["phase"] == ph]
            if not pr:
                continue
            bp = min(pr, key=lambda r: r["min_gap_tilted_mm"])
            prev_ph_min = float(s_prev["by_phase"][ph]["min_gap_tilted_mm"])
            ph_drop = max(0.0, prev_ph_min - bp["min_gap_tilted_mm"])
            max_drop_overall = max(max_drop_overall, ph_drop)
            by_phase[ph] = dict(
                stride1_min_mm=bp["min_gap_tilted_mm"],
                stride1_step=bp["step"],
                worst_tilt=bp["worst_tilt"],
                stride5_min_mm=prev_ph_min,
                stride5_step=int(s_prev["by_phase"][ph]["step"]),
                delta_mm=bp["min_gap_tilted_mm"] - prev_ph_min,
                n_checked=len(pr),
            )

        rec = dict(
            crown_mm=cr,
            station_mm=st,
            n_steps_checked=len(rr),
            stride1_min_tilted_mm=w["min_gap_tilted_mm"],
            stride1_at_step=w["step"],
            stride1_phase=w["phase"],
            stride1_worst_tilt=w["worst_tilt"],
            stride5_min_tilted_mm=prev_min,
            stride5_at_step=int(s_prev["at_step"]),
            delta_vs_stride5_mm=delta_mm,
            min_gap_no_tilt_mm=w0["gap_no_tilt_mm"],
            no_tilt_step=w0["step"],
            below_0p025_mm=sum(r["min_gap_tilted_mm"] < 0.025 for r in rr),
            contacts_tilted=sum(r["min_gap_tilted_mm"] <= 0 for r in rr),
            acceptance_drop_le_0p001_mm=bool(drop_mm <= 0.001),
            by_phase=by_phase,
        )
        summary.append(rec)
        print(
            f"crown={cr} st={st:+d}: stride1={w['min_gap_tilted_mm']:.6f}@{w['step']} ({w['phase']}) "
            f"vs stride5={prev_min:.6f}@{s_prev['at_step']} | delta={delta_mm:+.6f} mm",
            flush=True,
        )

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(
        scope=__doc__,
        window_half_width=a.window,
        angle_deg=a.angle,
        n_jobs=len(jobs),
        max_drop_vs_stride5_mm=max_drop_overall,
        all_drops_le_0p001_mm=bool(max_drop_overall <= 0.001),
        summary=summary,
        rows=rows,
        elapsed_s=time.monotonic() - t0,
    )
    out_path.write_text(json.dumps(doc, indent=1, default=float))
    print(f"Saved {out_path} in {time.monotonic() - t0:.1f}s | max_drop={max_drop_overall:.6f} mm", flush=True)


if __name__ == "__main__":
    main()
