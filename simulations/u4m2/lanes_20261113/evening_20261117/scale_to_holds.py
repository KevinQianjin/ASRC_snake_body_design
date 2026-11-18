"""Scale the worst-axis rib-level joint loads to every saved 500 g hold (linear, magnitude only).

Uses the per-record M5 module maximum curvature recorded by the 16 Nov
full-coverage screen. The bending direction of each record is not used: the
worst bending axis (67.5 deg) is assumed, so the per-record values are upper
bounds under the linear rib model. Run from lanes_20261113/.
"""
import json, collections
import numpy as np
rows = json.load(open('evening_20261116/v3_compatibility/summary_rows.json'))
d3 = json.load(open('evening_20261117/rib_joint_3d/rib_joint_3d_results.json'))
p = d3['parameters']; run = d3['runs'][-1]
none = [c for c in run['cases'] if c['variant'] == 'none'][0]
Ecal = p['E'] * np.mean([p['database_EA_N'] / run['global_stiffness']['none']['EA_N'],
                         p['database_EI_Nmm2'] / none['EI_Nmm2'], p['database_GJ_Nmm2'] / run['global_stiffness']['none']['GJ_Nmm2']])
s = Ecal / p['E']
worst = {c['variant']: c for c in run['cases'] if c['bending_axis_deg'] == 67.5}
def peak(v, key): return s * max(abs(x[key]) for st in worst[v]['stations'].values() for x in st)
per = {}
for r in rows:
    if r['part'].startswith('M5'):
        per[r['state']] = (r['phase'], r['module_max_curvature_rad_per_mm'])
k146 = p['kappa']
out = dict(scope=__doc__, E_calibrated_MPa=Ecal, reference_curvature=k146, records=len(per), by_phase={}, variants={})
for v in ('rigid_bond', 'hinge_t', 'ball'):
    pk = {k: peak(v, k) for k in ('axial_N', 'radial_N', 'tangential_N', 'inplane_moment_Nmm', 'moment_about_r_Nmm', 'moment_about_z_Nmm')}
    out['variants'][v] = dict(record146_worst_axis=pk)
ph = collections.defaultdict(list)
for st, (phase, k) in per.items(): ph[phase].append(k / k146)
for phase, f in sorted(ph.items()):
    f = np.array(f)
    out['by_phase'][phase] = dict(records=len(f), max_curvature_ratio=float(f.max()), median_curvature_ratio=float(np.median(f)),
                                  rigid_bond_max_axial_N=float(f.max() * out['variants']['rigid_bond']['record146_worst_axis']['axial_N']),
                                  rigid_bond_max_moment_Nmm=float(f.max() * out['variants']['rigid_bond']['record146_worst_axis']['inplane_moment_Nmm']),
                                  ball_max_radial_N=float(f.max() * out['variants']['ball']['record146_worst_axis']['radial_N']))
allf = np.array([k / k146 for _, k in per.values()])
out['records_with_curvature_ratio_above'] = {str(t): int((allf > t).sum()) for t in (0.25, 0.5, 0.75, 0.9)}
json.dump(out, open('evening_20261117/rib_joint_3d/hold_scaling.json', 'w'), indent=1)
print(json.dumps(out['by_phase'], indent=0)); print(out['records_with_curvature_ratio_above'], 'Ecal', round(Ecal))
