"""Summarise minimum-force held-elevation sweeps: force range and step-to-step smoothness."""
import json, glob
import numpy as np
from backbone import HERE
OUT = HERE / 'results'
summary = []
for f in sorted(glob.glob(str(OUT / 'minforce_*.json'))):
    rows = [r for r in json.load(open(f)) if r.get('ok8')]
    if not rows: continue
    yaw = np.array([r['yaw_deg'] for r in rows]); peak = np.array([r['peak_n'] for r in rows])
    T = np.array([np.ravel(r['tensions_n']) for r in rows]); H = np.array([r['head_world_mm'] for r in rows])
    el = np.array([r['world_elevation_deg'] for r in rows]); st = np.array([r['max_strain'] for r in rows])
    dT = np.abs(np.diff(T, axis=0)).max(axis=1) if len(T) > 1 else np.array([0.])
    dH = np.linalg.norm(np.diff(H, axis=0), axis=1) if len(H) > 1 else np.array([0.])
    total = len(json.load(open(f)))
    s = dict(file=Path(f).name if False else f.split('/')[-1], variant=rows[0]['variant'], pitch_deg=rows[0]['pitch_deg'], anchors=rows[0]['anchors'],
             exact_elevation='exact' in f, states_passing=len(rows), states_attempted=total, yaw_range_deg=[float(yaw.min()), float(yaw.max())],
             peak_n_min=float(peak.min()), peak_n_max=float(peak.max()), elevation_range_deg=[float(el.min()), float(el.max())],
             max_strain_pct=float(100 * st.max()), max_step_tension_change_n=float(dT.max()), max_step_head_move_mm=float(dH.max()),
             yaw_step_deg=float(np.diff(yaw).max()) if len(yaw) > 1 else None, all_stable=all(r['stable'] for r in rows))
    summary.append(s)
    print(f"{s['file']:48s} {s['states_passing']}/{s['states_attempted']} yaw {s['yaw_range_deg'][0]:.0f}-{s['yaw_range_deg'][1]:.0f} "
          f"peak {s['peak_n_min']:.1f}-{s['peak_n_max']:.1f} N elev {s['elevation_range_deg'][0]:.1f}-{s['elevation_range_deg'][1]:.1f} "
          f"strain<= {s['max_strain_pct']:.2f}% max dT/step {s['max_step_tension_change_n']:.1f} N max head move/step {s['max_step_head_move_mm']:.0f} mm stable {s['all_stable']}")
(OUT / 'minforce_summary.json').write_text(json.dumps(summary, indent=1))
