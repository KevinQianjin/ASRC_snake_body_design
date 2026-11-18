"""Summary figure for the 17 Nov evening rib-level joint study (run from lanes_20261113/)."""
import json, sys, numpy as np, trimesh
sys.path.insert(0, '.')
import rib_joint_model as R
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
b = trimesh.load(R.BODY); poly, e_r, e_z, n = R.rib_polygon(b, 22.5); X, T = R.mesh_polygon(poly, 0.05)
d3 = json.load(open('evening_20261117/rib_joint_3d/rib_joint_3d_results.json'))
p = d3['parameters']; run = d3['runs'][-1]            # finest mesh
gs = run['global_stiffness']['none']
Ecal = p['E'] * np.mean([p['database_EA_N'] / gs['EA_N'],
                         p['database_EI_Nmm2'] / [c for c in run['cases'] if c['variant'] == 'none'][0]['EI_Nmm2'],
                         p['database_GJ_Nmm2'] / gs['GJ_Nmm2']])
s = Ecal / p['E']
cases = {c['variant']: c for c in run['cases'] if c['bending_axis_deg'] == 67.5}
EI0 = cases['none']['EI_Nmm2']
fig = plt.figure(figsize=(12, 7.5))
ax0 = fig.add_axes([0.04, 0.08, 0.25, 0.84]); ax1 = fig.add_axes([0.37, 0.56, 0.6, 0.34]); ax2 = fig.add_axes([0.37, 0.09, 0.6, 0.34])
ax0.triplot(X[:, 0], X[:, 1], T, lw=0.1, color='0.6')
for st in (-12, 12):
    ax0.axhspan(st - 0.25, st + 0.25, xmin=15 / 33, xmax=24 / 33, color='tab:red', alpha=.8)
    ax0.axhspan(st - 1.62, st + 1.62, xmin=13 / 33, xmax=26 / 33, color='tab:orange', alpha=.25)
ax0.set_aspect('equal'); ax0.set_xlim(0, 33); ax0.set_xlabel('r (mm)'); ax0.set_ylabel('z (mm)')
ax0.set_title('M5 rib mid-plane, CAD cut at 22.5°\n(3.0 mm plate; red = 0.5 mm land,\norange = ±1.62 mm socket)', fontsize=9)
V = ['rigid_bond', 'hinge_t', 'ball']; lab = ['rigid bond\n(V3 concept)', 'hinge about\ntangential axis', 'ball (translations\nonly)']
keys = [('axial_N', 'axial'), ('radial_N', 'radial'), ('tangential_N', 'tangential')]
w = 0.25
for i, (k, nm) in enumerate(keys):
    vals = [s * max(abs(x[k]) for x in cases[v]['stations']['G+12']) for v in V]
    ax1.bar(np.arange(3) + (i - 1) * w, vals, w, label=nm)
lab1 = [f"{l}\nEI +{100 * (cases[v]['EI_Nmm2'] / EI0 - 1):.1f}%, in-plane rotation {max(abs(x['hinge_rotation_rad']) for x in cases[v]['stations']['G+12']):.2f} rad" for l, v in zip(lab, V)]
ax1.set_xticks(range(3)); ax1.set_xticklabels(lab1, fontsize=8); ax1.set_ylabel('max land force (N)'); ax1.legend(fontsize=8)
ax1.set_title(f'Per-land loads at record-146 curvature ({p["kappa"]:.4f} rad/mm, bending axis 67.5°), E calibrated {Ecal:.0f} MPa', fontsize=9, loc='left')
mk = [('inplane_moment_Nmm', 'about tangential axis'), ('moment_about_r_Nmm', 'about radial axis'), ('moment_about_z_Nmm', 'about z axis')]
for i, (k, nm) in enumerate(mk):
    vals = [s * max(abs(x[k]) for x in cases[v]['stations']['G+12']) for v in V]
    ax2.bar(np.arange(3) + (i - 1) * w, vals, w, label=nm)
ax2.set_xticks(range(3)); ax2.set_xticklabels(lab, fontsize=9); ax2.set_ylabel('max land moment (N·mm)'); ax2.legend(fontsize=8)
ax2.set_title('Linear rib-level FE (membrane + Mindlin plate); first-order estimate, not a nonlinear or contact result', fontsize=8, loc='left')
fig.savefig('evening_20261117/rib_joint_3d/rib_joint_summary.png', dpi=110)
print('E_cal', Ecal)
