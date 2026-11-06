"""Order-of-magnitude EA/EI requirement for the 0.48 m front carrying a 500 g head.

Small-deflection Euler-Bernoulli cantilever (root fixed at pitch theta), top tendon
at r = 13 mm. Three architectures:
  A passive  : no tendon, EI alone limits sag.
  B single   : one top tendon anchored at head (constant tendon moment T*r).
  C per-module: one top tendon group anchored at each module end (staircase moment).
Criteria copied from the study's provisional straightness test: max offset 10 mm,
max tangent error 5 deg, axial strain <= 5 %. Not a design certification.
"""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar

L, N_MOD, R = 0.48, 10, 0.013
G, PAYLOAD = 9.81, 0.5
ROPE_LIN = 1140*np.pi*0.001**2           # PA6 proxy, kg/m per rope (study value)
W = G*(0.004/0.048 + 4*ROPE_LIN)          # N/m: module + four ropes
P = G*PAYLOAD
OFF, TAN, STRAIN = 0.010, np.radians(5), 0.05
s = np.linspace(0, L, 4801)
ds = s[1]-s[0]


def cumtrapz(f):
    return np.r_[0, np.cumsum((f[1:]+f[:-1])/2*ds)]


def shape_unit(m):
    """Slope and offset for EI = 1 under bending moment m(s) (sag positive)."""
    phi = cumtrapz(m)
    return phi, cumtrapz(phi)


def gravity_moment(theta):
    c = np.cos(theta)
    return c*(P*(L-s) + W*(L-s)**2/2)


def axial_gravity(theta):
    return np.sin(theta)*(P + W*(L-s))


def ei_needed(m):
    phi, y = shape_unit(m)
    return max(np.max(np.abs(y))/OFF, np.max(np.abs(phi))/TAN), phi, y


def run(theta_deg):
    th = np.radians(theta_deg)
    Mg, Ng = gravity_moment(th), axial_gravity(th)
    out = {'pitch_deg': theta_deg, 'root_gravity_moment_nm': Mg[0]}
    # A passive
    ei, *_ = ei_needed(Mg)
    out['A_passive'] = dict(EI_nm2=ei, EA_n=Ng.max()/STRAIN, tendon_n=0.)
    # B single head anchor: choose T minimising required EI
    f = lambda T: ei_needed(Mg - T*R)[0]
    T = minimize_scalar(f, bounds=(0, Mg[0]/R), method='bounded').x
    out['B_single'] = dict(EI_nm2=f(T), EA_n=(T+Ng).max()/STRAIN, tendon_n=T)
    # C per-module anchors: tendon moment in module i = mean gravity moment there
    idx = np.minimum((s/(L/N_MOD)).astype(int), N_MOD-1)
    Mt = np.array([Mg[idx == i].mean() for i in range(N_MOD)])
    ei, *_ = ei_needed(Mg - Mt[idx])
    Nmod = Mt/R + np.array([Ng[idx == i].max() for i in range(N_MOD)])
    out['C_per_module'] = dict(EI_nm2=ei, EA_n=Nmod.max()/STRAIN,
                               tendon_root_n=Mt[0]/R,
                               EA_per_module_n=(Nmod/STRAIN).tolist())
    return out


if __name__ == '__main__':
    rows = [run(p) for p in (15, 20, 25)]
    res = dict(inputs=dict(L_m=L, rope_radius_m=R, payload_kg=PAYLOAD,
                           distributed_weight_n_per_m=W,
                           current_U=dict(EA_n=1150.19, EI_nm2=0.061),
                           current_M=dict(EA_n=85.07, EI_nm2=0.0046),
                           criteria=dict(max_offset_mm=10, max_tangent_deg=5, max_strain=0.05)),
               results=rows,
               scope='Linear small-deflection estimate; no buckling, contact or 3D check.')
    Path(__file__).with_name('results').joinpath('stiffness_requirement_estimate.json').write_text(
        json.dumps(res, indent=2), encoding='utf-8')
    for r in rows:
        print(f"pitch {r['pitch_deg']} deg  root moment {r['root_gravity_moment_nm']:.3f} N.m")
        for k in ('A_passive', 'B_single', 'C_per_module'):
            d = r[k]
            print(f"  {k:13s} EI>={d['EI_nm2']:8.3f} N.m2  EA>={d['EA_n']:8.0f} N  "
                  f"T={d.get('tendon_n', d.get('tendon_root_n')):7.1f} N")
    print('C EA per module (20 deg):', np.round(rows[1]['C_per_module']['EA_per_module_n']).astype(int))
