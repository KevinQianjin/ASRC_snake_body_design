"""Check exit-pivot rope envelopes against actual end-region CAD (evening 15 Nov 2026 EST).

Uses the per-exit deflections written by ``end_bellmouth_study.py``.  Because the
end regions are treated as rigid, each rope centreline can be built directly in
the undeformed CAD frame: along the lane bore (centre 0.25 mm toward the bend
side), around an arc of radius R_w + 1 mm concentric with the fillet, then
straight at the measured deflection until |local z| = 38 mm.  The signed
distance of these samples to the CAD surface minus the 1 mm rope radius is the
finite-rope clearance.  Intended bearing on the bore/fillet gives ~0; the
acceptance tolerance only covers the 128-sided cutter faceting.

Running the same paths against the V2 bodies shows what the unchanged sharp
(0.25 mm chamfer) exits would do under the same rigid-end assumption.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy

ROPE_R, HOLE_R, STEP = 1.0, 1.25, 0.02
FACE = {'proximal': -48.0, 'distal': 48.0}
INBOARD = {'proximal': 1.0, 'distal': -1.0}
EXIT_FACE = {'proximal': -45.0, 'distal': 41.0}
STOP_Z = 38.0
TOL_MM = 0.005


class Body:
    def __init__(self, path):
        m = trimesh.load_mesh(path, force='mesh')
        pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.asarray(m.vertices, float), deep=True))
        cells = vtk.vtkCellArray()
        cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(np.c_[np.full(len(m.faces), 3), m.faces].astype(np.int64).ravel(), deep=True))
        self.poly = vtk.vtkPolyData(); self.poly.SetPoints(pts); self.poly.SetPolys(cells)
        self.loc = vtk.vtkStaticCellLocator(); self.loc.SetDataSet(self.poly); self.loc.BuildLocator()

    def signed(self, P):
        cp = [0., 0., 0.]; cid = vtk.reference(0); sub = vtk.reference(0); d2 = vtk.reference(0.)
        d = np.empty(len(P))
        for i, p in enumerate(P):
            self.loc.FindClosestPoint(p, cp, cid, sub, d2); d[i] = float(d2) ** .5
        sp = vtk.vtkPoints(); sp.SetData(numpy_to_vtk(np.asarray(P, float), deep=True))
        q = vtk.vtkPolyData(); q.SetPoints(sp)
        enc = vtk.vtkSelectEnclosedPoints(); enc.SetInputData(q); enc.SetSurfaceData(self.poly); enc.SetTolerance(1e-8); enc.Update()
        inside = vtk_to_numpy(enc.GetOutput().GetPointData().GetArray('SelectedPoints')).astype(bool)
        return np.where(inside, -d, d)


def build_path(end, lane_xy, n_hat, theta, wall, theta_d):
    a = np.array([0., 0., INBOARD[end]])
    hb = wall * np.sin(np.radians(theta_d))          # arc start depth from the inboard face
    rc = wall + ROPE_R
    face_z, exit_z = FACE[end], EXIT_FACE[end]
    base = np.array([lane_xy[0], lane_xy[1], 0.]) + (HOLE_R - ROPE_R) * n_hat
    start_s = abs(exit_z - face_z) - hb               # distance from interface to arc start
    pts = [base + np.array([0, 0, face_z]) + s * a for s in np.arange(0., start_s, STEP)]
    origin = base + np.array([0, 0, face_z]) + start_s * a
    centre = origin + rc * n_hat
    for phi in np.arange(0., theta, STEP / rc):
        pts.append(centre - rc * np.cos(phi) * n_hat + rc * np.sin(phi) * a)
    tip = centre - rc * np.cos(theta) * n_hat + rc * np.sin(theta) * a
    d = np.cos(theta) * a + np.sin(theta) * n_hat
    while abs(tip[2]) > STOP_Z:
        pts.append(tip.copy()); tip = tip + STEP * d
    return np.array(pts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('exit_csv', type=Path)
    ap.add_argument('--design', type=Path, required=True)
    ap.add_argument('--cad', type=Path, required=True, help='folder with M5_lane_anchorB.stl / M6_lane_anchorC.stl')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--every', type=int, default=1, help='use every n-th unique geometry (1 = all)')
    a = ap.parse_args()
    design = json.loads(a.design.read_text())
    bodies = {'M5': Body(a.cad / 'M5_lane_anchorB.stl'), 'M6': Body(a.cad / 'M6_lane_anchorC.stl')}
    rows = list(csv.DictReader(a.exit_csv.open()))
    states = sorted({r['state'] for r in rows}, key=int)[::a.every]
    keep = set(states)
    out_rows = []
    for r in rows:
        if r['state'] not in keep:
            continue
        end = r['end']; ex = design['exits'][f"{r['module']}/{end}"]
        cx, cy = design['rays_cad_xy'][r['ray']]; lr = design['lane_radii_mm'][r['set']]
        rhat = np.array([cx, cy, 0.]); that = np.cross([0., 0., INBOARD[end]], rhat)
        th = np.radians(float(r['exit_deflection_deg']))
        tr, tt = np.tan(np.radians(float(r['exit_deflection_radial_deg']))), np.tan(np.radians(float(r['exit_deflection_tangential_deg'])))
        n = tr * rhat + tt * that; nn = np.linalg.norm(n); n = rhat if nn < 1e-12 else n / nn
        P = build_path(end, (cx * lr, cy * lr), n, th, ex['wall_radius_mm'], ex['design_wrap_deg'])
        sd = bodies[r['module']].signed(P)
        i = int(np.argmin(sd))
        out_rows.append(dict(state=r['state'], phase=r['phase'], module=r['module'], set=r['set'], ray=r['ray'], end=end,
                             exit_deflection_deg=float(r['exit_deflection_deg']), envelope_clearance_mm=float(sd[i] - ROPE_R),
                             at_z_mm=float(P[i, 2]), samples=len(P)))
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / 'cad_envelope.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(out_rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(out_rows)
    fails = [r for r in out_rows if r['envelope_clearance_mm'] < -TOL_MM]
    worst = min(out_rows, key=lambda r: r['envelope_clearance_mm'])
    s = dict(scope=__doc__, exit_csv=str(a.exit_csv), design=str(a.design), cad=str(a.cad), every=a.every,
             cad_sha256={k: __import__('hashlib').sha256((a.cad / f).read_bytes()).hexdigest() for k, f in (('M5', 'M5_lane_anchorB.stl'), ('M6', 'M6_lane_anchorC.stl'))},
             records=len(states), rope_exit_checks=len(out_rows), tolerance_mm=TOL_MM,
             failing_checks=len(fails), failing_records=len({r['state'] for r in fails}),
             min_envelope_clearance_mm=worst['envelope_clearance_mm'], worst=worst)
    (a.out / 'summary.json').write_text(json.dumps(s, indent=1) + '\n')
    print(json.dumps({k: v for k, v in s.items() if k != 'scope'}, indent=1))


if __name__ == '__main__':
    main()
