"""Geometry of rope exits from the rigid M5/M6 end bores (evening study, 15 Nov 2026 EST).

The rod model routes each rope as a frictionless polyline whose end vertex is
the lane-hole centre on the module *interface* face (local z = -48 / +48 mm).
The real end region is a rigid bore (proximal disk 3 mm: z -48..-45; distal
anchor block + disk 7 mm: z +41..+48) only 0.25 mm larger than the Ø2 mm rope
in radius, so the rope must follow the bore axis there and bend where it leaves
the bore at the *inboard* face.

For every saved equilibrium this script evaluates, without re-solving:

* the deflection angle the rope needs at each inboard bore exit (between the
  bore axis and the straight span to the first/last guide station),
  decomposed into radial and tangential components;
* the change in routed rope length between the ideal interface-pivot polyline
  and the exit-pivot path (bore axis + span from the exit), per rope and summed
  per rope over M5+M6;
* the half-width an interface-pivot conical flare would need at the inboard
  face to keep the full Ø2 mm rope envelope clear (the alternative design).

Points are mapped with the same constant-strain cell kinematics as the CAD
screen.  This is a geometric study at fixed saved tensions, not an equilibrium
re-solution and not a contact/friction model.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states
from guide_path_audit import map_cad, RAYS
from rope_guide_study import _guide_spans

HOLE_R, ROPE_R = 1.25, 1.0
EXIT_Z = {'proximal': -45.0, 'distal': 41.0}      # inboard faces of the rigid end regions, mm (V2 CAD)
FACE_Z = {'proximal': -48.0, 'distal': 48.0}
CAD_XY = {'up': (0., 1.), 'right': (-1., 0.), 'down': (0., -1.), 'left': (1., 0.)}  # CAD X is left


def run(archive, out, radii):
    lanes.install(tuple(radii), 24.)
    rod = lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8)
    states, coverage = load_states(archive, rod.ndof)
    rows, cache = [], {}
    for label, z, T, meta in states:
        key = z.tobytes()
        if key not in cache:
            d = rod.evaluate(z, T, detail=True)[2]
            p, F = d['points'], d['frames']
            res = []
            for j in (4, 5):
                spans = _guide_spans(j * rod.sub, (j + 1) * rod.sub, 2)
                nodes = [spans[0][0]] + [b for a, b in spans]
                for k in ((1, 2) if j == 4 else (2,)):
                    r = radii[k]
                    for ray in range(4):
                        P = p[nodes] + np.einsum('nij,j->ni', F[nodes], rod.offsets3[k, ray])
                        cx, cy = CAD_XY[RAYS[ray]]
                        for end in ('proximal', 'distal'):
                            g = P[1] if end == 'proximal' else P[-2]
                            face_ideal = P[0] if end == 'proximal' else P[-1]
                            ze, zf = EXIT_Z[end], FACE_Z[end]
                            cadpts = np.array([[cx * r, cy * r, zf], [cx * r, cy * r, ze],
                                               [cx * r, cy * r, ze + (0.5 if end == 'proximal' else -0.5)],
                                               [cx * (r + 1), cy * (r + 1), ze]])
                            m = map_cad(cadpts, j, rod, d) * 1000.
                            face, exit_, ahead, outward = m
                            axis = (ahead - exit_) / np.linalg.norm(ahead - exit_)      # inboard bore axis
                            rhat = outward - exit_; rhat -= (rhat @ axis) * axis; rhat /= np.linalg.norm(rhat)
                            that = np.cross(axis, rhat)
                            span = g * 1000. - exit_; ls = np.linalg.norm(span); c = span / ls
                            ideal = np.linalg.norm(g * 1000. - face_ideal * 1000.)
                            exit_path = np.linalg.norm(exit_ - face) + ls
                            # interface-pivot chord: required flare half-width at the inboard face
                            ci = (g * 1000. - face_ideal * 1000.); ci /= np.linalg.norm(ci)
                            depth = abs(zf - ze)
                            lat = ci * depth / max(ci @ axis, 1e-9) - depth * axis
                            res.append(dict(module=f'M{j+1}', set='ABC'[k], ray=RAYS[ray], end=end, tension_n=float(T[k, ray]),
                                            exit_deflection_deg=float(np.degrees(np.arccos(np.clip(c @ axis, -1, 1)))),
                                            exit_deflection_radial_deg=float(np.degrees(np.arctan2(c @ rhat, c @ axis))),
                                            exit_deflection_tangential_deg=float(np.degrees(np.arctan2(c @ that, c @ axis))),
                                            length_change_mm=float(exit_path - ideal),
                                            interface_face_offset_mm=float(np.linalg.norm(face - face_ideal * 1000.)),
                                            flare_needed_radial_mm=float(abs(lat @ rhat) + ROPE_R),
                                            flare_needed_tangential_mm=float(abs(lat @ that) + ROPE_R),
                                            flare_side_radial=int(np.sign(lat @ rhat))))
            cache[key] = res
        rows.extend(dict(state=label, phase=meta.get('phase', 'inverse'), **r) for r in cache[key])
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'exit_routing.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    return rows, coverage


def summarise(rows, coverage, out, args):
    groups = {}
    for r in rows:
        k = f"{r['module']}/{r['end']}"
        g = groups.setdefault(k, dict(checks=0, max_exit_deflection_deg=0., max_radial_deflection_deg=0., max_tangential_deflection_deg=0.,
                                      max_abs_length_change_mm=0., max_interface_offset_mm=0., max_flare_radial_mm=0., max_flare_tangential_mm=0.))
        g['checks'] += 1
        g['max_exit_deflection_deg'] = max(g['max_exit_deflection_deg'], r['exit_deflection_deg'])
        g['max_radial_deflection_deg'] = max(g['max_radial_deflection_deg'], abs(r['exit_deflection_radial_deg']))
        g['max_tangential_deflection_deg'] = max(g['max_tangential_deflection_deg'], abs(r['exit_deflection_tangential_deg']))
        g['max_abs_length_change_mm'] = max(g['max_abs_length_change_mm'], abs(r['length_change_mm']))
        g['max_interface_offset_mm'] = max(g['max_interface_offset_mm'], r['interface_face_offset_mm'])
        g['max_flare_radial_mm'] = max(g['max_flare_radial_mm'], r['flare_needed_radial_mm'])
        g['max_flare_tangential_mm'] = max(g['max_flare_tangential_mm'], r['flare_needed_tangential_mm'])
    # per-rope total length change through M5+M6 for each state
    per_rope = {}
    for r in rows:
        per_rope.setdefault((r['state'], r['set'], r['ray']), 0.)
        per_rope[(r['state'], r['set'], r['ray'])] += r['length_change_mm']
    vals = np.array(list(per_rope.values()))
    s = dict(scope=__doc__, archive=str(args.archive), coverage=coverage, radii_mm=list(args.radii),
             hole_radius_mm=HOLE_R, rope_radius_mm=ROPE_R, inboard_exit_z_mm=EXIT_Z, interface_z_mm=FACE_Z,
             records=len({r['state'] for r in rows}), rope_end_checks=len(rows), groups=groups,
             per_rope_m5_m6_length_change_mm=dict(min=float(vals.min()), max=float(vals.max()), mean=float(vals.mean())),
             b_c_radial_pitch_mm=4.0,
             note='flare_needed_* is the half-width from the hole axis, at the inboard face, that a cone with its throat at the interface face would need for the full rope radius. Two facing radial flares on one ray (B 24 mm, C 28 mm) overlap when their sum exceeds 4 mm.')
    (out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: v for k, v in s.items() if k not in ('scope', 'coverage')}, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--radii', type=float, nargs=3, default=(21., 24., 28.))
    a = ap.parse_args()
    rows, cov = run(a.archive, a.out, a.radii)
    summarise(rows, cov, a.out, a)
