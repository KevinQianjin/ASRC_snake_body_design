"""Per-hole loads and sampled deformed-CAD flexure clearance along saved paths.

This maps the supplied M CAD to the rod's material frames, not a solid FEA.
Ropes are 2 mm diameter; sample spacing <=1 mm yields a 0.5 mm distance bound.
End disks/anchors are excluded from the flexure screen (|local Z| <=40 mm).
Guide mounts and intended rope/eyelet contact need separate physical validation.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
import trimesh
import lanes
from state_archives import load_states
from rope_guide_study import _guide_spans

HERE = Path(__file__).resolve().parent
CAD = HERE.parents[2] / 'cad' / 'lanes_u4m2'
RAYS = ('up', 'right', 'down', 'left')


def guide_loads(points, tension):
    """Force exerted by one frictionless rope on each internal guide, N."""
    segments = np.diff(points, axis=0)
    lengths = np.linalg.norm(segments, axis=1)
    if (lengths <= 1e-12).any():
        raise ValueError('zero-length rope span')
    tangents = segments / lengths[:, None]
    return tension * (tangents[1:] - tangents[:-1])


def map_cad(vertices, module, rod, details):
    """Exact constant-strain-cell kinematics, CAD (X left,Y up,Z axial) -> rod frame, m."""
    s = np.clip((vertices[:, 2] + 48.) / 1000., 0., .096)
    cells = np.minimum((s / rod.l).astype(int), rod.sub - 1)
    u = s / rod.l - cells
    idx = module * rod.sub + cells
    q = details['q'][idx]
    phi = np.c_[q[:, 0], -q[:, 2], q[:, 1]]
    theta = np.linalg.norm(phi, axis=1)
    safe = np.where(theta < 1e-9, 1., theta)
    a = np.where(theta < 1e-9, u, np.sin(theta * u) / safe)
    b = np.where(theta < 1e-9, .5 * u**2, (1 - np.cos(theta * u)) / safe**2)
    c = np.where(theta < 1e-9, u**3 / 6., (theta * u - np.sin(theta * u)) / safe**3)
    ex = np.tile([1., 0., 0.], (len(vertices), 1))
    cross = np.cross(phi, ex)
    center = rod.l * (1 + q[:, 3, None]) * (u[:, None] * ex + b[:, None] * cross + c[:, None] * np.cross(phi, cross))
    off = np.c_[np.zeros(len(vertices)), vertices[:, 1], -vertices[:, 0]] / 1000.
    rotated = off + a[:, None] * np.cross(phi, off) + b[:, None] * np.cross(phi, np.cross(phi, off))
    return details['points'][idx] + np.einsum('nij,nj->ni', details['frames'][idx], center + rotated)


class FlexureDistance:
    def __init__(self, path):
        self.mesh = trimesh.load_mesh(path, force='mesh')
        self.faces = self.mesh.faces[np.max(abs(self.mesh.vertices[self.mesh.faces, 2]), axis=1) <= 40.0001]
        self.poly = vtk.vtkPolyData()
        cells = vtk.vtkCellArray()
        cells.SetCells(len(self.faces), numpy_to_vtkIdTypeArray(np.c_[np.full(len(self.faces), 3), self.faces].astype(np.int64).ravel(), deep=True))
        self.poly.SetPolys(cells)
        self.solid = vtk.vtkPolyData()
        full_cells = vtk.vtkCellArray()
        full_cells.SetCells(len(self.mesh.faces), numpy_to_vtkIdTypeArray(np.c_[np.full(len(self.mesh.faces), 3), self.mesh.faces].astype(np.int64).ravel(), deep=True))
        self.solid.SetPolys(full_cells)

    def update(self, vertices_m):
        points = vtk.vtkPoints(); points.SetData(numpy_to_vtk(vertices_m * 1000, deep=True))
        self.poly.SetPoints(points)
        self.solid.SetPoints(points)
        self.locator = vtk.vtkStaticCellLocator(); self.locator.SetDataSet(self.poly); self.locator.BuildLocator()

    def distances(self, points_m):
        cp = [0., 0., 0.]; cid = vtk.reference(0); sub = vtk.reference(0); d2 = vtk.reference(0.)
        out = []
        for p in points_m * 1000:
            self.locator.FindClosestPoint(p, cp, cid, sub, d2)
            out.append(float(d2)**.5)
        sample_points = vtk.vtkPoints(); sample_points.SetData(numpy_to_vtk(points_m * 1000, deep=True))
        samples = vtk.vtkPolyData(); samples.SetPoints(sample_points)
        enclosed = vtk.vtkSelectEnclosedPoints(); enclosed.SetInputData(samples); enclosed.SetSurfaceData(self.solid)
        enclosed.SetTolerance(1e-7); enclosed.Update()
        inside = vtk_to_numpy(enclosed.GetOutput().GetPointData().GetArray('SelectedPoints')).astype(bool)
        # End disks / anchor blocks are outside the flexure-only distance scope.
        # Classify their real penetrations separately, rather than assigning the
        # distance to a distant flexure surface as their penetration depth.
        signed = np.asarray(out)
        self.last_inside_end_points = 0
        self.last_max_end_penetration_mm = 0.
        self.last_end_details = []
        if inside.any():
            full_locator = vtk.vtkStaticCellLocator(); full_locator.SetDataSet(self.solid); full_locator.BuildLocator()
            for i in np.where(inside)[0]:
                full_locator.FindClosestPoint(points_m[i] * 1000, cp, cid, sub, d2)
                face = self.mesh.faces[int(cid)]
                if np.max(abs(self.mesh.vertices[face, 2])) <= 40.0001:
                    signed[i] = -signed[i]
                else:
                    self.last_inside_end_points += 1
                    self.last_max_end_penetration_mm = max(self.last_max_end_penetration_mm, float(d2)**.5)
                    self.last_end_details.append(dict(sample_index=int(i),center_penetration_mm=float(d2)**.5,
                        nearest_face_centroid_cad_mm=self.mesh.vertices[face].mean(axis=0).tolist(),
                        nearest_face_cad_z_range_mm=[float(self.mesh.vertices[face,2].min()),float(self.mesh.vertices[face,2].max())]))
        return signed


def audit(archives, output, radii=(21., 24., 27.), geometry=True, cad=CAD):
    lanes.install(radii, 24.)
    rod = lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8)
    bodies = {j: FlexureDistance(cad / name) for j, name in [(4, 'M5_lane_anchorB.stl'), (5, 'M6_lane_anchorC.stl')]} if geometry else {}
    output.mkdir(parents=True, exist_ok=True)
    summary = dict(scope=__doc__, radii_mm=list(radii), coverage=[], maximum_hole_force_n=0., maximum_station_force_n=0.,
                   maximum_station_moment_nmm=0., per_hole={}, per_station={}, minimum_flexure_clearance_bound_mm=None,
                   end_region_penetrating_states=0, maximum_end_region_center_penetration_mm=0.,
                   flexure_screen_failed_states=0, geometry_checked=geometry, unique_geometry_states=0,
                   cad_sha256={name: hashlib.sha256((cad / name).read_bytes()).hexdigest() for name in ['M5_lane_anchorB.stl', 'M6_lane_anchorC.stl']})
    cache = {}
    with gzip.open(output / 'hole_loads.csv.gz', 'wt', newline='') as lf, (output / 'path_checks.csv').open('w', newline='') as pf:
        fields = ['archive', 'state', 'phase', 'module', 'station_z_mm', 'set', 'ray', 'tension_n', 'fx_n', 'fy_n', 'fz_n', 'force_n']
        loads = csv.DictWriter(lf, fields); loads.writeheader()
        checks = csv.DictWriter(pf, ['archive', 'state', 'phase', 'maximum_hole_force_n', 'maximum_station_force_n', 'flexure_clearance_bound_mm', 'flexure_screen_pass', 'end_region_centerline_points_inside', 'maximum_end_region_center_penetration_mm'])
        checks.writeheader()
        for archive in archives:
            states, coverage = load_states(archive, rod.ndof); summary['coverage'].append(coverage)
            for state_index, (label, z, T, meta) in enumerate(states):
                d = rod.evaluate(z, T, detail=True)[2]
                p, F = d['points'], d['frames']
                worst_hole = worst_station = 0.; rope_points = {}; station_rows = []
                location = dict(archive=str(archive), state=label, phase=meta.get('phase', 'inverse'))
                for j in (4, 5):
                    spans = _guide_spans(j * rod.sub, (j + 1) * rod.sub, 2)
                    nodes = [spans[0][0]] + [b for a, b in spans]
                    forces = np.zeros((4, 3)); moments = np.zeros((4, 3)); samples = []
                    for k in ((1, 2) if j == 4 else (2,)):
                        for ray in range(4):
                            off = rod.offsets3[k, ray]
                            P = p[nodes] + np.einsum('nij,j->ni', F[nodes], off)
                            force = guide_loads(P, T[k, ray])
                            for g, f in enumerate(force):
                                local = F[nodes[g + 1]].T @ f
                                magnitude = float(np.linalg.norm(f)); worst_hole = max(worst_hole, magnitude)
                                forces[g] += local; moments[g] += np.cross(off * 1000, local)
                                row = dict(**location, module=f'M{j+1}', station_z_mm=(-24, -12, 12, 24)[g], set=('A','B','C')[k], ray=RAYS[ray], tension_n=float(T[k,ray]), fx_n=float(local[0]), fy_n=float(local[1]), fz_n=float(local[2]), force_n=magnitude)
                                loads.writerow(row)
                                key = f'M{j+1}/z{row["station_z_mm"]}/{row["set"]}/{row["ray"]}'
                                if magnitude > summary['per_hole'].get(key, {}).get('force_n', -1): summary['per_hole'][key] = row
                            for a, b in zip(P[:-1], P[1:]):
                                n = max(1, int(np.ceil(np.linalg.norm(b-a) * 1000)))
                                samples.append(a + np.linspace(0,1,n+1)[:,None] * (b-a))
                    rope_points[j] = np.vstack(samples)
                    for g, (force, moment) in enumerate(zip(forces, moments)):
                        norm = float(np.linalg.norm(force)); torque = float(np.linalg.norm(moment)); worst_station = max(worst_station, norm)
                        key = f'M{j+1}/z{(-24,-12,12,24)[g]}'
                        if norm > summary['per_station'].get(key, {}).get('force_n', -1):
                            summary['per_station'][key] = dict(**location, force_n=norm, force_local_n=force.tolist(), moment_local_nmm=moment.tolist(), moment_nmm=torque)
                        if torque > summary['maximum_station_moment_nmm']:
                            summary['maximum_station_moment_nmm'] = torque
                            summary['peak_station_moment'] = dict(**location, module=f'M{j+1}', station_z_mm=(-24,-12,12,24)[g],
                                force_local_n=force.tolist(), moment_local_nmm=moment.tolist(), moment_nmm=torque)
                summary['maximum_hole_force_n'] = max(summary['maximum_hole_force_n'], worst_hole)
                summary['maximum_station_force_n'] = max(summary['maximum_station_force_n'], worst_station)
                gap = None; end_inside = 0; end_depth = 0.
                if geometry:
                    key = z.tobytes()
                    if key not in cache:
                        minimum = float('inf')
                        for j, body in bodies.items():
                            body.update(map_cad(body.mesh.vertices, j, rod, d))
                            minimum = min(minimum, float(body.distances(rope_points[j]).min()) - 1.0 - 0.5)
                            end_inside += body.last_inside_end_points
                            end_depth = max(end_depth, body.last_max_end_penetration_mm)
                        cache[key] = (minimum, end_inside, end_depth); summary['unique_geometry_states'] += 1
                    gap, end_inside, end_depth = cache[key]
                    if summary['minimum_flexure_clearance_bound_mm'] is None or gap < summary['minimum_flexure_clearance_bound_mm']:
                        summary['minimum_flexure_clearance_bound_mm'] = gap; summary['worst_clearance_state'] = location
                    summary['flexure_screen_failed_states'] += int(gap < 0)
                    summary['end_region_penetrating_states'] += int(end_inside > 0)
                    if end_depth > summary['maximum_end_region_center_penetration_mm']:
                        summary['maximum_end_region_center_penetration_mm'] = end_depth
                        summary['worst_end_region_penetration_state'] = location
                checks.writerow(dict(**location, maximum_hole_force_n=worst_hole, maximum_station_force_n=worst_station, flexure_clearance_bound_mm=gap, flexure_screen_pass=None if gap is None else gap >= 0,
                    end_region_centerline_points_inside=end_inside,maximum_end_region_center_penetration_mm=end_depth))
                if state_index % 100 == 0: print(Path(archive).name, state_index, 'hole N', round(worst_hole,3), 'gap mm', gap, flush=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('per_hole','per_station')}, indent=2))
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archives', nargs='+', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--radii', nargs=3, type=float, default=(21.,24.,27.))
    ap.add_argument('--loads-only', action='store_true')
    ap.add_argument('--cad', type=Path, default=CAD)
    args = ap.parse_args()
    audit(args.archives, args.out, args.radii, not args.loads_only, args.cad)
