"""Finite-diameter rope screen of the M5/M6 end disks and anchor blocks.

Evening study, 15 November 2026 (EST).  The 15 November morning audit counted
only rope *centre* points inside end-region material.  A Ø2 mm rope interferes
whenever its centreline comes within 1 mm (its radius) of any body surface, so
this script reports the signed centreline-to-surface distance minus the rope
radius ("envelope clearance") along the ideal rope chords near both module
ends, and classifies where the minimum occurs.

Kinematics: the same constant-strain beam mapping of the refined CAD as
``guide_path_audit.py``; rope centrelines are the frictionless polyline through
the end-hole centres and the four guide stations of the rod model.  This is a
geometric screen of the ideal path; it is not a contact-force or wrap solution
and does not model rope flattening, friction or printed tolerances.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy
import lanes
from state_archives import load_states
from guide_path_audit import FlexureDistance, map_cad, RAYS
from rope_guide_study import _guide_spans

ROPE_RADIUS_MM = 1.0
END_WINDOW_MM = 36.0     # screen samples with |local axial station| >= this
STEP_MM = 0.05


def signed_distance(body, points_mm):
    """Signed distance (mm) of points to the full mapped CAD surface, positive outside."""
    loc = vtk.vtkStaticCellLocator(); loc.SetDataSet(body.solid); loc.BuildLocator()
    cp = [0., 0., 0.]; cid = vtk.reference(0); sub = vtk.reference(0); d2 = vtk.reference(0.)
    dist = np.empty(len(points_mm)); faces = np.empty(len(points_mm), int)
    for i, p in enumerate(points_mm):
        loc.FindClosestPoint(p, cp, cid, sub, d2)
        dist[i] = float(d2) ** .5; faces[i] = int(cid)
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(points_mm, deep=True))
    poly = vtk.vtkPolyData(); poly.SetPoints(pts)
    enc = vtk.vtkSelectEnclosedPoints(); enc.SetInputData(poly); enc.SetSurfaceData(body.solid)
    enc.SetTolerance(1e-7); enc.Update()
    inside = vtk_to_numpy(enc.GetOutput().GetPointData().GetArray('SelectedPoints')).astype(bool)
    return np.where(inside, -dist, dist), faces


def rope_samples(P, nodes_local_z):
    """Samples (m) and local axial station (mm) of the end spans of one rope polyline."""
    out, axial = [], []
    for span in (0, len(P) - 2):
        a, b = P[span], P[span + 1]
        za, zb = nodes_local_z[span], nodes_local_z[span + 1]
        n = max(1, int(np.ceil(abs(zb - za) / STEP_MM)))
        t = np.linspace(0, 1, n + 1)
        z = za + t * (zb - za); keep = abs(z) >= END_WINDOW_MM
        out.append(a + t[keep, None] * (b - a)); axial.append(z[keep])
    return np.vstack(out), np.concatenate(axial)


def run(archive, cad, out, span_mm, radii):
    lanes.install(tuple(radii), 24.)
    rod = lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8)
    names = {4: 'M5_lane_anchorB.stl', 5: 'M6_lane_anchorC.stl'}
    bodies = {j: FlexureDistance(cad / n, span_mm) for j, n in names.items()}
    states, coverage = load_states(archive, rod.ndof)
    out.mkdir(parents=True, exist_ok=True)
    rows, cache = [], {}
    for label, z, T, meta in states:
        key = z.tobytes()
        if key not in cache:
            d = rod.evaluate(z, T, detail=True)[2]
            p, F = d['points'], d['frames']
            res = []
            for j, body in bodies.items():
                body.update(map_cad(body.mesh.vertices, j, rod, d))
                spans = _guide_spans(j * rod.sub, (j + 1) * rod.sub, 2)
                nodes = [spans[0][0]] + [b for a, b in spans]
                local_z = [(n - j * rod.sub) * 12. - 48. for n in nodes]
                batch, meta_r = [], []
                for k in ((1, 2) if j == 4 else (2,)):
                    for ray in range(4):
                        P = p[nodes] + np.einsum('nij,j->ni', F[nodes], rod.offsets3[k, ray])
                        S, ax = rope_samples(P, local_z)
                        ang = []
                        off = rod.offsets3[k, ray]; rhat = off / np.linalg.norm(off); that = np.cross([1., 0., 0.], rhat)
                        for n0, n1 in ((0, 1), (len(P) - 1, len(P) - 2)):
                            c = P[n1] - P[n0]; c /= np.linalg.norm(c); loc = F[nodes[n0]].T @ c
                            ang.append((float(np.degrees(np.arccos(np.clip(abs(loc[0]), -1, 1)))),
                                        float(np.degrees(np.arctan2(loc @ rhat, abs(loc[0])))),
                                        float(np.degrees(np.arctan2(loc @ that, abs(loc[0]))))))
                        batch.append(S * 1000); meta_r.append((k, ray, ax, ang))
                sd_all, faces_all = signed_distance(body, np.vstack(batch))
                o = 0
                for S, (k, ray, ax, ang) in zip(batch, meta_r):
                    sd, faces = sd_all[o:o + len(S)], faces_all[o:o + len(S)]; o += len(S)
                    for end, sel in (('proximal', ax < 0), ('distal', ax > 0)):
                        i = np.argmin(np.where(sel, sd, np.inf))
                        fv = body.mesh.vertices[body.mesh.faces[faces[i]]].mean(axis=0)
                        res.append(dict(module=f'M{j+1}', set='ABC'[k], ray=RAYS[ray], end=end,
                                        tension_n=float(T[k, ray]),
                                        min_center_signed_distance_mm=float(sd[i]),
                                        envelope_clearance_mm=float(sd[i] - ROPE_RADIUS_MM),
                                        at_local_axial_mm=float(ax[i]),
                                        nearest_face_cad_xyz_mm=[round(float(v), 3) for v in fv],
                                        nearest_face_radius_mm=float(np.hypot(fv[0], fv[1])),
                                        chord_angle_to_axis_deg=ang[0 if end == 'proximal' else 1][0],
                                        chord_tilt_radial_outward_deg=ang[0 if end == 'proximal' else 1][1],
                                        chord_tilt_tangential_deg=ang[0 if end == 'proximal' else 1][2]))
            cache[key] = res
        for r in cache[key]:
            rows.append(dict(state=label, phase=meta.get('phase', 'inverse'), **r))
        if len(cache) % 20 == 1 and len(rows) == len(cache) * 24: print('state', label, 'unique', len(cache), flush=True)
    with (out / 'end_envelope.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n'); w.writeheader()
        for r in rows: w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})
    return rows, coverage, {n: hashlib.sha256((cad / n).read_bytes()).hexdigest() for n in names.values()}


def summarise(rows, coverage, cad_hash, out, args):
    groups = {}
    for r in rows:
        g = groups.setdefault(f"{r['module']}/{r['set']}/{r['ray']}/{r['end']}", dict(n=0, fail=0, min=np.inf, worst=None, max_angle=0.))
        g['n'] += 1; g['fail'] += int(r['envelope_clearance_mm'] < 0)
        g['max_angle'] = max(g['max_angle'], r['chord_angle_to_axis_deg'])
        if r['envelope_clearance_mm'] < g['min']: g['min'] = r['envelope_clearance_mm']; g['worst'] = r
    states = sorted({r['state'] for r in rows}, key=lambda s: int(s) if s.isdigit() else s)
    failing = sorted({r['state'] for r in rows if r['envelope_clearance_mm'] < 0})
    centre = sorted({r['state'] for r in rows if r['min_center_signed_distance_mm'] < 0})
    s = dict(scope=__doc__, archive=str(args.archive), coverage=coverage, cad=str(args.cad), cad_sha256=cad_hash,
             cad_max_axial_span_mm=args.cad_max_axial_span_mm, radii_mm=args.radii, rope_radius_mm=ROPE_RADIUS_MM,
             end_window_abs_local_axial_mm=END_WINDOW_MM, sample_step_mm=STEP_MM,
             records=len(states), rope_end_checks=len(rows),
             records_with_centre_penetration=len(centre), records_with_envelope_interference=len(failing),
             min_envelope_clearance_mm=float(min(r['envelope_clearance_mm'] for r in rows)),
             max_centre_penetration_mm=float(max(0., -min(r['min_center_signed_distance_mm'] for r in rows))),
             max_chord_angle_to_axis_deg=float(max(r['chord_angle_to_axis_deg'] for r in rows)),
             groups={k: dict(checks=v['n'], envelope_failures=v['fail'], min_envelope_clearance_mm=float(v['min']),
                             max_chord_angle_deg=v['max_angle'], worst=v['worst']) for k, v in sorted(groups.items())})
    (out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: v for k, v in s.items() if k not in ('groups', 'scope', 'coverage')}, indent=1))
    for k, v in s['groups'].items():
        print(k, v['checks'], v['envelope_failures'], round(v['min_envelope_clearance_mm'], 4), round(v['max_chord_angle_deg'], 2),
              v['worst']['at_local_axial_mm'], v['worst']['nearest_face_cad_xyz_mm'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive', type=Path)
    ap.add_argument('--cad', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--radii', type=float, nargs=3, default=(21., 24., 28.))
    ap.add_argument('--cad-max-axial-span-mm', type=float, default=.5)
    a = ap.parse_args()
    rows, cov, h = run(a.archive, a.cad, a.out, a.cad_max_axial_span_mm, a.radii)
    summarise(rows, cov, h, a.out, a)
