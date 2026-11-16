"""Rigid-end, exit-pivot rope geometry and bellmouth sizing for M5/M6 (evening 15 Nov 2026 EST).

Physical assumption replacing the ideal interface pivot: the bolted end
regions (proximal disk z -48..-45 mm; distal anchor block + disk z +41..+48 mm)
are rigid and keep the orientation of the rod frame at the module interface
node.  Lane bores are only 0.25 mm larger than the Ø2 mm rope in radius, so the
rope follows the bore axis across the joint and turns where it leaves the
*inboard* face.  The proposed CAD change is a convex fillet (bellmouth) of wall
radius ``R_w`` on each inboard lane-hole exit, swept to a design wrap angle
``theta_d``; a rope deflected by theta <= theta_d bends over the fillet with
centreline radius R_w + 1 mm instead of over a 0.25 mm chamfer edge.

For every saved equilibrium (fixed saved tensions, no re-solution):
* deflection theta at each inboard exit relative to the rigid bore axis, with
  radial/tangential components;  pass if theta <= theta_d - margin;
* length change of the exit-pivot path relative to the solver's interface-pivot
  chord (straight bore + fillet arc + tangent span vs one straight chord);
* the same deflection measured against the cell-mapped (bent) bore, for
  comparison with the CAD beam-map screen.

Not modelled: friction/capstan losses on the fillet, rope bending stiffness
and flattening, wear, printing tolerance, U4 distal exits (outside M scope).
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states
from guide_path_audit import RAYS
from rope_guide_study import _guide_spans

ROPE_R, HOLE_R = 1.0, 1.25
DEPTH = {'proximal': 3.0, 'distal': 7.0}   # interface face -> inboard face, V2 M CAD (mm)


def fillet_path_length(theta, rc, d):
    """Exit-pivot length from the interface to the tangent point equivalent.

    Rope centreline: straight along the bore for (d - rc*sin(theta)), then an arc
    of radius rc through theta.  Returns (length, endpoint offset along axis,
    endpoint lateral offset) measured from the interface on the bore axis line
    (rope centre assumed 0.25 mm off-axis toward the bend side, which shifts the
    path laterally but not its length)."""
    s = max(d - rc * np.sin(theta), 0.)
    return s + rc * theta, s + rc * np.sin(theta), rc * (1 - np.cos(theta))


def run(archive, out, radii, design, margin_deg):
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
                    for ray in range(4):
                        off = rod.offsets3[k, ray] * 1000.
                        P = (p[nodes] + np.einsum('nij,j->ni', F[nodes], rod.offsets3[k, ray])) * 1000.
                        for end in ('proximal', 'distal'):
                            n, i_face, i_guide, sgn = (nodes[0], 0, 1, 1.) if end == 'proximal' else (nodes[-1], -1, -2, -1.)
                            Fi = F[n]; a = sgn * Fi[:, 0]
                            rhat = Fi @ (off / np.linalg.norm(off)); that = np.cross(a, rhat)
                            face, g = P[i_face], P[i_guide]
                            depth = DEPTH[end]
                            ex = design['exits'][f'M{j+1}/{end}']; rc = ex['wall_radius_mm'] + ROPE_R; theta_d_deg = ex['design_wrap_deg']
                            # deflection relative to the rigid bore: chord from the inboard exit to the guide
                            exit_ = face + depth * a
                            c = g - exit_; L = np.linalg.norm(c); c /= L
                            theta = float(np.arccos(np.clip(c @ a, -1, 1)))
                            # exit-pivot path length (straight + arc + tangent) vs ideal chord
                            s, ax, lat = fillet_path_length(theta, rc, depth)
                            nvec = c - (c @ a) * a; nvec = nvec / max(np.linalg.norm(nvec), 1e-12)
                            tangent_pt = face + ax * a + lat * nvec
                            exit_len = s + np.linalg.norm(g - tangent_pt)
                            ideal_len = np.linalg.norm(g - face)
                            # interface-pivot chord angle against rigid axis (what a straight flare would need)
                            ci = (g - face) / ideal_len
                            res.append(dict(module=f'M{j+1}', set='ABC'[k], ray=RAYS[ray], end=end, tension_n=float(T[k, ray]),
                                            exit_deflection_deg=float(np.degrees(theta)),
                                            exit_deflection_radial_deg=float(np.degrees(np.arctan2(c @ rhat, c @ a))),
                                            exit_deflection_tangential_deg=float(np.degrees(np.arctan2(c @ that, c @ a))),
                                            interface_chord_angle_deg=float(np.degrees(np.arccos(np.clip(ci @ a, -1, 1)))),
                                            straight_flare_halfwidth_needed_mm=float(depth * np.tan(np.arccos(np.clip(ci @ a, -1, 1))) + ROPE_R),
                                            length_change_mm=float(exit_len - ideal_len),
                                            wrap_within_fillet=bool(np.degrees(theta) <= theta_d_deg - margin_deg),
                                            fillet_axial_extent_mm=float(rc * np.sin(theta)),
                                            design_wrap_deg=theta_d_deg, wall_radius_mm=ex['wall_radius_mm']))
            cache[key] = res
        rows.extend(dict(state=label, phase=meta.get('phase', 'inverse'), **r) for r in cache[key])
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'exit_pivot.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    groups = {}
    for r in rows:
        g = groups.setdefault(f"{r['module']}/{r['end']}", dict(checks=0, fail=0, max_deflection_deg=0., max_radial_deg=0., max_tangential_deg=0.,
                                                              max_interface_chord_deg=0., max_straight_flare_mm=0., max_abs_length_change_mm=0., worst=None))
        g['checks'] += 1; g['fail'] += int(not r['wrap_within_fillet'])
        if r['exit_deflection_deg'] > g['max_deflection_deg']: g['max_deflection_deg'] = r['exit_deflection_deg']; g['worst'] = r
        g['max_radial_deg'] = max(g['max_radial_deg'], abs(r['exit_deflection_radial_deg']))
        g['max_tangential_deg'] = max(g['max_tangential_deg'], abs(r['exit_deflection_tangential_deg']))
        g['max_interface_chord_deg'] = max(g['max_interface_chord_deg'], r['interface_chord_angle_deg'])
        g['max_straight_flare_mm'] = max(g['max_straight_flare_mm'], r['straight_flare_halfwidth_needed_mm'])
        g['max_abs_length_change_mm'] = max(g['max_abs_length_change_mm'], abs(r['length_change_mm']))
    per_rope = {}
    for r in rows:
        per_rope[(r['state'], r['set'], r['ray'])] = per_rope.get((r['state'], r['set'], r['ray']), 0.) + r['length_change_mm']
    v = np.array(list(per_rope.values()))
    s = dict(scope=__doc__, archive=str(archive), coverage=coverage, radii_mm=list(radii), rigid_end_depth_mm=DEPTH,
             design_exits=design['exits'], margin_deg=margin_deg,
             records=len({r['state'] for r in rows}), rope_end_checks=len(rows),
             exits_beyond_design_wrap=sum(not r['wrap_within_fillet'] for r in rows),
             records_beyond_design_wrap=len({r['state'] for r in rows if not r['wrap_within_fillet']}),
             max_exit_deflection_deg=max(r['exit_deflection_deg'] for r in rows),
             per_rope_m5_m6_length_change_mm=dict(min=float(v.min()), max=float(v.max()), mean=float(v.mean())),
             groups=groups)
    (out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: (val if k != 'groups' else {g: {kk: vv for kk, vv in gg.items() if kk != 'worst'} for g, gg in val.items()})
                      for k, val in s.items() if k not in ('scope', 'coverage')}, indent=1))
    return s


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--radii', type=float, nargs=3, default=(21., 24., 28.))
    ap.add_argument('--design', type=Path, required=True, help='end_bellmouth design.json')
    ap.add_argument('--margin-deg', type=float, default=1.0)
    a = ap.parse_args()
    run(a.archive, a.out, a.radii, json.loads(a.design.read_text()), a.margin_deg)
