"""Summarise side-pull runs: yaw per mm of pull-in, yaw kept within the elevation band, limits."""
import json, glob
import numpy as np
from backbone import HERE
OUT = HERE / 'results'
summary = []
for f in sorted(glob.glob(str(OUT / 'sidepull_*_niti18_*.json'))):
    R = json.load(open(f)); ok = [q for q in R if 'yaw_deg' in q]
    yaw = np.array([q['yaw_deg'] for q in ok]); el = np.array([q['world_elevation_deg'] for q in ok])
    rr = np.array([max(q['right_rope_n']) for q in ok]); pk = np.array([q['peak_n'] for q in ok])
    jumps = np.array([q['head_jump_mm'] or 0 for q in ok])
    band = np.flatnonzero(np.abs(el - 20) > 5)
    i_band = (band[0] - 1) if len(band) else len(ok) - 1
    last = R[-1]
    stop = last.get('status') or ('geometry' if not ok[-1]['geometry_pass'] else ('yaw_180' if abs(ok[-1]['yaw_deg']) >= 180 else 'end_of_pull_range'))
    s = dict(file=f.split('/')[-1], mode=ok[0]['mode'], variant=ok[0]['variant'], pull=ok[0]['pull'],
             yaw_per_mm_initial=float((yaw[4] - yaw[0]) / (ok[4]['pull_in_mm'] - ok[0]['pull_in_mm'])) if ok[0]['mode'] == 'winch' else None,
             yaw_in_band_deg=float(yaw[i_band]), pull_in_band_mm=ok[i_band]['pull_in_mm'], right_rope_in_band_n=float(rr[i_band]),
             max_yaw_deg=float(yaw.max()), elevation_at_max_yaw_deg=float(el[np.argmax(yaw)]), right_rope_at_max_n=float(rr[np.argmax(yaw)]),
             peak_rope_n=float(pk.max()), last_pull_mm=ok[-1].get('pull_in_mm'), stop_reason=stop, max_head_jump_mm=float(jumps.max()),
             all_stable=all(q['stable'] for q in ok), max_strain_pct=float(100 * max(q['max_strain'] for q in ok)))
    summary.append(s)
    print(f"{s['variant']:10s} {s['pull']:3s} {s['mode']:7s}: initial {s['yaw_per_mm_initial'] or 0:.2f} deg/mm | in 20+/-5 band up to yaw {s['yaw_in_band_deg']:5.1f} "
          f"(pull {s['pull_in_band_mm']} mm, right rope {s['right_rope_in_band_n']:.0f} N) | max yaw {s['max_yaw_deg']:5.1f} at elev {s['elevation_at_max_yaw_deg']:5.1f}, "
          f"right {s['right_rope_at_max_n']:.0f} N, peak {s['peak_rope_n']:.0f} N | stop: {s['stop_reason']} at {s['last_pull_mm']} | max jump {s['max_head_jump_mm']:.1f} mm stable {s['all_stable']}")
(OUT / 'sidepull_summary.json').write_text(json.dumps(summary, indent=1))
