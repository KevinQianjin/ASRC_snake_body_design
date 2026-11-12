"""Summarise winch_sensitivity.py results: required winch accuracy, slack and stability."""
import json
import numpy as np
from backbone import HERE
OUT = HERE / 'results'
summary = {}
for case in ['E40', 'E75']:
    R = json.loads((OUT / f'winch_sensitivity_{case}.json').read_text())
    P = R['poses']; names = R['ropes']
    singles = [s for p in P for s in p['singles'] if 'd_yaw_deg' in s]
    slack = lambda e: [s for s in singles if abs(s['error_mm']) == e and s['min_tension_n'] < 1e-6]
    checks = [c for p in P for c in p['full_model_check_1mm'] if 'true_yaw' in c]
    Jabs = np.mean([np.abs(np.array(p['J_per_mm'])) for p in P], axis=0)
    s = dict(yaws=[p['yaw'] for p in P],
             single_1mm_yaw_deg=[p['max_single_1mm']['yaw_deg'] for p in P], single_1mm_elev_deg=[p['max_single_1mm']['elev_deg'] for p in P],
             single_1mm_head_mm=[p['max_single_1mm']['head_mm'] for p in P],
             all12_p99_1mm_yaw_deg=[p['random_p99']['1mm']['yaw_p99_deg'] for p in P], all12_p99_1mm_elev_deg=[p['random_p99']['1mm']['elev_p99_deg'] for p in P],
             all12_p99_1mm_head_mm=[p['random_p99']['1mm']['head_p99_mm'] for p in P],
             allow_1deg_p99_mm=[p['allowable_winch_error']['1deg_p99_mm'] for p in P], allow_1deg_worst_mm=[p['allowable_winch_error']['1deg_worst_case_mm'] for p in P],
             allow_2deg_p99_mm=[p['allowable_winch_error']['2deg_p99_mm'] for p in P], allow_2deg_worst_mm=[p['allowable_winch_error']['2deg_worst_case_mm'] for p in P],
             rope_EA_minus10_max_deg=max(max(abs(p['rope_stretch']['EAx0.9']['d_yaw_deg']), abs(p['rope_stretch']['EAx0.9']['d_elev_deg'])) for p in P),
             rope_EA_plus10_max_deg=max(max(abs(p['rope_stretch']['EAx1.1']['d_yaw_deg']), abs(p['rope_stretch']['EAx1.1']['d_elev_deg'])) for p in P),
             singles_solved=len(singles), singles_failed=sum(p['singles_failed'] for p in P),
             singles_all_stable=all(s['stable'] for s in singles), singles_all_geometry=all(s['geometry'] for s in singles),
             singles_with_slack_rope_at_0p5mm=len(slack(.5)), singles_with_slack_rope_at_1mm=len(slack(1.)),
             singles_at_0p5mm=sum(abs(s['error_mm']) == .5 for s in singles),
             combined_checks=len(checks), combined_checks_all_stable=all(c['stable'] for c in checks),
             combined_checks_all_geometry=all(c['geometry'] for c in checks),
             combined_checks_with_slack=sum(c['min_tension_n'] < 1e-6 for c in checks),
             combined_linear_prediction_max_error_deg=max(max(abs((c['true_yaw'] - c['pred_yaw'] + 180) % 360 - 180), abs(c['true_elev'] - c['pred_elev'])) for c in checks),
             mean_abs_J_yaw_deg_per_mm={n: float(Jabs[0, k]) for k, n in enumerate(names)},
             mean_abs_J_elev_deg_per_mm={n: float(Jabs[1, k]) for k, n in enumerate(names)})
    summary[case] = s
    print(case, json.dumps({k: (np.round(v, 2).tolist() if isinstance(v, list) else (round(v, 3) if isinstance(v, float) else v)) for k, v in s.items() if not k.startswith('mean_abs')}))
    print('   mean |J| yaw', {k: round(v, 2) for k, v in s['mean_abs_J_yaw_deg_per_mm'].items()})
    print('   mean |J| elev', {k: round(v, 2) for k, v in s['mean_abs_J_elev_deg_per_mm'].items()})
(OUT / 'winch_sensitivity_summary.json').write_text(json.dumps(summary, indent=1))
