"""Full-coverage point-sampled web/guide compatibility screen for rigid V3-style guides.

For every saved equilibrium and every requested guide, dense samples of the
actual module-body surface near the guide are beam-mapped (same exact
constant-strain-cell map as the Boolean audits), expressed in the guide's rigid
station frame and evaluated against the guide, cap and lockwire-envelope
surfaces with a signed distance (negative = body point inside a guide part).

The screen also reports the relative motion of the body at the proposed bond
land with respect to the rigid guide and the implied bond-line shear strain
(axial relative displacement / nominal bond gap). This is a kinematic screen of
the homogenised beam map, not solid FEA, adhesive qualification or a contact
solution. A sampled point set can miss very thin slivers; results are
cross-checked against the existing manifold Boolean audits.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
from scipy.spatial import cKDTree
import lanes
from guide_path_audit import map_cad
from state_archives import load_states

BODY = {'M5': 'M5_lane_anchorB.stl', 'M6': 'M6_lane_anchorC.stl'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SignedDistance:
    """Minimum signed distance over the closed components of a guide assembly, mm."""
    def __init__(self, meshes):
        self.functions = []
        for mesh in meshes:
            for part in mesh.split(only_watertight=False):
                poly = vtk.vtkPolyData(); pts = vtk.vtkPoints()
                pts.SetData(numpy_to_vtk(np.ascontiguousarray(part.vertices, dtype=float), deep=True))
                poly.SetPoints(pts)
                cells = vtk.vtkCellArray()
                cells.SetCells(len(part.faces), numpy_to_vtkIdTypeArray(
                    np.c_[np.full(len(part.faces), 3), part.faces].astype(np.int64).ravel(), deep=True))
                poly.SetPolys(cells)
                f = vtk.vtkImplicitPolyDataDistance(); f.SetInput(poly)
                self.functions.append(f)

    def __call__(self, points):
        out = np.full(len(points), np.inf)
        if not len(points):
            return out
        src = numpy_to_vtk(np.ascontiguousarray(points, dtype=float), deep=True)
        for f in self.functions:
            res = vtk.vtkDoubleArray()
            f.FunctionValue(src, res)
            out = np.minimum(out, vtk_to_numpy(res))
        return out


def station_transform(module, station, rod, details):
    node = module * rod.sub + int(round((station + 48) / (rod.l * 1000)))
    return details['points'][node], details['frames'][node]


def to_station(points_cad, module, station, rod, details):
    origin, frame = station_transform(module, station, rod, details)
    local = (map_cad(points_cad, module, rod, details) - origin) @ frame
    return np.c_[-local[:, 2], local[:, 1], local[:, 0]] * 1000


def sample_patch(body, guide_meshes, station, spacing, window, seed):
    """Dense surface samples of the complete body within `window` mm of the guide."""
    assembly = trimesh.util.concatenate(guide_meshes)
    lo, hi = assembly.bounds
    lo = lo + [0, 0, station] - window; hi = hi + [0, 0, station] + window
    tri = body.vertices[body.faces]
    keep = np.all(tri.max(1) > lo, axis=1) & np.all(tri.min(1) < hi, axis=1)
    patch = trimesh.Trimesh(body.vertices, body.faces[keep], process=False)
    # Pre-sample the guide surface to discard far body samples before dense sampling.
    rng = np.random.default_rng(seed)
    count = int(np.ceil(patch.area / spacing**2))
    points, faces = trimesh.sample.sample_surface(patch, count, seed=rng)
    guide_samples, _ = trimesh.sample.sample_surface(assembly, 400000, seed=rng)
    near, _ = cKDTree(guide_samples).query(points - [0, 0, station], distance_upper_bound=window)
    mask = np.isfinite(near)
    return points[mask], patch.face_normals[faces[mask]]


def run(archive, body_cad, guide_cad, out, tags, spacing, window, max_seconds, labels=None, land=0.5, gap=0.15, seed=7, shard=(0, 1), margin=0.03):
    start = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    lanes.install((21, 24, 28), 24)
    rod = lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8)
    states, coverage = load_states(archive)
    if labels is not None:
        states = [s for s in states if s[0] in set(labels)]
    # Shards partition unique geometries, so duplicate records stay in one shard.
    order = {}
    for st in states:
        order.setdefault(st[1].tobytes(), len(order))
    states = [st for st in states if order[st[1].tobytes()] % shard[1] == shard[0]]
    bodies = {k: trimesh.load_mesh(body_cad / BODY[k]) for k in sorted({t.split('_z')[0] for t in tags})}
    for k, b in bodies.items():
        if not b.is_watertight:
            raise ValueError(f'{k} body is not watertight')
    setup = {}
    for tag in tags:
        kind, st = tag.split('_z'); station = int(st)
        meshes = [trimesh.load_mesh(guide_cad / f'{tag}_{s}.stl') for s in ('guide', 'caps', 'wire_envelope')]
        points, normals = sample_patch(bodies[kind], meshes, station, spacing, window, seed)
        sdf = SignedDistance(meshes)
        straight = sdf(points - [0, 0, station])
        local_z = points[:, 2] - station
        land_mask = (np.abs(local_z) <= land / 2) & (straight < gap + 0.1)
        setup[tag] = dict(kind=kind, module=int(kind[1:]) - 1, station=station, points=points, sdf=sdf,
                          straight=straight, land=land_mask, radius=np.hypot(points[:, 0], points[:, 1]))
        print(tag, 'samples', len(points), 'land samples', int(land_mask.sum()),
              'straight min', float(straight.min()), flush=True)
    result = dict(scope=__doc__, archive=str(archive), archive_sha256=sha(archive), coverage=coverage,
                  body_cad=str(body_cad), guide_cad=str(guide_cad),
                  body_sha256={BODY[k]: sha(body_cad / BODY[k]) for k in bodies},
                  guide_sha256={p.name: sha(p) for p in sorted(guide_cad.glob('*.stl')) if any(p.name.startswith(t + '_') for t in tags)},
                  guide_design=json.loads((guide_cad / 'design.json').read_text()),
                  sampling=dict(spacing_mm=spacing, window_mm=window, seed=seed,
                                note='Random area-weighted samples of complete-body faces near each guide; sliver-depth sensitivity is limited by spacing and the 0.005 mm mesh tolerance used elsewhere.'),
                  shard=dict(index=shard[0], count=shard[1]), query_margin_mm=margin,
                  land_axial_mm=land, nominal_bond_gap_mm=gap, payload_g=500, rod_cells_per_module=8,
                  straight={t: dict(samples=int(len(s['points'])), land_samples=int(s['land'].sum()),
                                    minimum_signed_distance_mm=float(s['straight'].min())) for t, s in setup.items()},
                  rows=[], completed=False)

    def save():
        result['elapsed_seconds'] = time.monotonic() - start
        (out / 'summary.json').write_text(json.dumps(result, indent=1) + '\n')
    save()
    cache = {}
    for label, z, tension, meta in states:
        if time.monotonic() - start > max_seconds:
            result['stop_reason'] = 'study time budget reached'; save(); return result
        key = z.tobytes()
        phase = meta.get('phase') if isinstance(meta, dict) else None
        if key in cache:
            for row in cache[key]:
                result['rows'].append({**row, 'state': label, 'phase': phase, 'reused_geometry_from_state': row['state']})
            continue
        details = rod.evaluate(z, tension, detail=True)[2]
        state_rows = []
        for tag, s in setup.items():
            moved = to_station(s['points'], s['module'], s['station'], rod, details)
            disp = moved - (s['points'] - [0, 0, s['station']])
            dnorm = np.linalg.norm(disp, axis=1)
            # The signed distance is 1-Lipschitz: d(moved) >= d(straight) - |displacement|.
            # Points whose bound exceeds the margin are certified clear without a query.
            bound = s['straight'] - dnorm
            check = bound < margin
            d = bound.copy(); d[check] = s['sdf'](moved[check])
            i = int(np.argmin(d))
            land = s['land']
            axial = np.abs(disp[land, 2]) if land.any() else np.zeros(1)
            cells = slice(s['module'] * rod.sub, (s['module'] + 1) * rod.sub)
            kappa = np.linalg.norm(details['q'][cells, :3], axis=1).max() / (rod.l * 1000)
            row = dict(state=label, phase=phase, part=tag,
                       minimum_signed_distance_mm=float(d[i]),
                       minimum_is_lipschitz_bound=bool(not check[i]),
                       penetrating_samples=int((d < 0).sum()),
                       worst_point_station_mm=moved[i].tolist(),
                       worst_point_undeformed_station_mm=(s['points'][i] - [0, 0, s['station']]).tolist(),
                       worst_point_displacement_mm=disp[i].tolist(),
                       max_relative_displacement_mm=float(dnorm.max()),
                       land_max_relative_displacement_mm=float(dnorm[land].max()) if land.any() else None,
                       land_max_axial_relative_displacement_mm=float(axial.max()),
                       land_implied_shear_strain=float(axial.max() / gap),
                       module_max_curvature_rad_per_mm=float(kappa),
                       distance_queries=int(check.sum()))
            state_rows.append(row); result['rows'].append(row)
        cache[key] = state_rows
        worst = min(state_rows, key=lambda r: r['minimum_signed_distance_mm'])
        print(label, phase, worst['part'], round(worst['minimum_signed_distance_mm'], 5),
              'gamma', round(max(r['land_implied_shear_strain'] for r in state_rows), 3),
              f"{time.monotonic() - start:.0f}s", flush=True)
        save()
    rows = result['rows']
    result['completed'] = True
    result['records'] = len({r['state'] for r in rows})
    result['unique_geometries'] = len(cache)
    result['penetrating_checks'] = sum(r['minimum_signed_distance_mm'] < 0 for r in rows)
    result['penetrating_records'] = len({r['state'] for r in rows if r['minimum_signed_distance_mm'] < 0})
    result['minimum_signed_distance_mm'] = min(r['minimum_signed_distance_mm'] for r in rows)
    result['by_part'] = {t: dict(minimum_signed_distance_mm=min(r['minimum_signed_distance_mm'] for r in rows if r['part'] == t),
                                 penetrating_checks=sum(r['minimum_signed_distance_mm'] < 0 for r in rows if r['part'] == t),
                                 max_land_axial_relative_displacement_mm=max(r['land_max_axial_relative_displacement_mm'] for r in rows if r['part'] == t),
                                 max_land_implied_shear_strain=max(r['land_implied_shear_strain'] for r in rows if r['part'] == t))
                         for t in tags}
    save()
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--body-cad', type=Path, required=True)
    p.add_argument('--guide-cad', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--parts', nargs='+', default=[f'{k}_z{z:+d}' for k in ('M5', 'M6') for z in (-24, -12, 12, 24)])
    p.add_argument('--states', nargs='+')
    p.add_argument('--spacing', type=float, default=0.03)
    p.add_argument('--window', type=float, default=0.6)
    p.add_argument('--land', type=float, default=0.5)
    p.add_argument('--gap', type=float, default=0.15)
    p.add_argument('--max-seconds', type=float, default=1800)
    p.add_argument('--shard', type=int, nargs=2, default=(0, 1), metavar=('INDEX', 'COUNT'))
    p.add_argument('--margin', type=float, default=0.03, help='Query points whose Lipschitz lower bound is below this, mm')
    a = p.parse_args()
    run(a.archive, a.body_cad, a.guide_cad, a.out, a.parts, a.spacing, a.window, a.max_seconds, a.states, a.land, a.gap,
        shard=tuple(a.shard), margin=a.margin)
