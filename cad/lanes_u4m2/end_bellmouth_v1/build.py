"""Add inboard lane-exit bellmouths to the V2 M5/M6 bodies and check the result.

Evening run 15 November 2026 (EST).  Source bodies: ../guides_v2 (unchanged
lanes, stations, guides, backbone bores, joints, anchors and return holes).
Each listed inboard lane-hole exit gets an axisymmetric convex fillet: tangent
to the Ø2.5 mm bore at depth h_b = R_w sin(theta_d) and sweeping to theta_d at
the inboard face.  Outputs (this folder): M5_lane_anchorB.stl,
M6_lane_anchorC.stl, geometry_check.json.

    python build.py
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'guides_v2'
D = json.loads((HERE / 'design.json').read_text())
HOLE_R = D['hole_diameter_mm'] / 2
SECTIONS = 128


def profile_radius(h, wall, theta_d):
    hb = wall * np.sin(np.radians(theta_d))
    return HOLE_R + wall - np.sqrt(np.maximum(wall**2 - (hb - h)**2, 0.)), hb


def cutter(wall, theta_d):
    """Solid of revolution about +Z; z = depth into material from the inboard face."""
    hb = wall * np.sin(np.radians(theta_d))
    h = np.linspace(0., hb, 61)
    w, _ = profile_radius(h, wall, theta_d)
    w0 = w[0]
    pts = [(0., -0.6), (w0 + 0.6, -0.6), (w0 + 0.6, -1e-3)] + list(zip(w, h)) + [(HOLE_R - .05, hb + 1e-3), (HOLE_R - .05, hb + .06), (0., hb + .06)]
    return trimesh.creation.revolve(np.array(pts), sections=SECTIONS)


def build(module, filename):
    body = trimesh.load_mesh(SRC / filename, force='mesh')
    cutters, placed = [], []
    for key, ex in D['exits'].items():
        if not key.startswith(module):
            continue
        base = cutter(ex['wall_radius_mm'], ex['design_wrap_deg'])
        for lane in ex['lanes']:
            r = D['lane_radii_mm'][lane]
            for ray, (cx, cy) in D['rays_cad_xy'].items():
                c = base.copy()
                if ex['inboard_sign'] > 0:            # material lies toward -Z of the face
                    c.apply_transform(trimesh.transformations.reflection_matrix([0, 0, 0], [0, 0, 1]))
                c.apply_translation([cx * r, cy * r, ex['face_z_mm']])
                cutters.append(c); placed.append(dict(exit=key, lane=lane, ray=ray, x=cx * r, y=cy * r, z=ex['face_z_mm']))
    tool = trimesh.boolean.union(cutters, engine='manifold')
    out = trimesh.boolean.difference([body, tool], engine='manifold')
    return body, out, placed


def hole_loops(mesh, z, rmin=20.):
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    p2, T = s.to_2D(); loops = []
    for poly in p2.discrete:
        P = (np.c_[poly, np.zeros(len(poly)), np.ones(len(poly))] @ T.T)[:, :2]
        c = P.mean(0); rr = np.linalg.norm(P - c, axis=1)
        if rr.max() < 2.6 and np.linalg.norm(c) > rmin:
            loops.append(dict(center=c, radius=float(np.linalg.norm(c)), mean_r=float(rr.mean()), poly=Polygon(P)))
    return loops


def bridges(mesh, z):
    """Minimum B-C (same ray) wall between lane-hole loops in a section, mm."""
    loops = [l for l in hole_loops(mesh, z) if abs(l['radius'] - 24) < .3 or abs(l['radius'] - 28) < .3]
    best = None
    for a in loops:
        for b in loops:
            if a['radius'] < 26 < b['radius'] and np.degrees(abs(np.arctan2(*a['center'][::-1]) - np.arctan2(*b['center'][::-1]))) % 360 < 5:
                d = a['poly'].distance(b['poly']); best = d if best is None else min(best, d)
    return best, [round(2 * l['mean_r'], 3) for l in loops]


def main():
    report = dict(design=D, source={}, parts={})
    for module, filename in [('M5', 'M5_lane_anchorB.stl'), ('M6', 'M6_lane_anchorC.stl')]:
        body, out, placed = build(module, filename)
        out.export(HERE / filename)
        re = trimesh.load_mesh(HERE / filename, force='mesh')
        comps = re.split(only_watertight=False)
        src_comps = body.split(only_watertight=False)
        rep = dict(watertight=bool(re.is_watertight), winding_consistent=bool(re.is_winding_consistent),
                   components=len(comps), source_components=len(src_comps),
                   volume_mm3=float(re.volume), source_volume_mm3=float(body.volume), removed_volume_mm3=float(body.volume - re.volume),
                   bounds=re.bounds.tolist(), source_bounds=body.bounds.tolist(), cutters=len(placed),
                   sha256=hashlib.sha256((HERE / filename).read_bytes()).hexdigest())
        report['source'][filename] = hashlib.sha256((SRC / filename).read_bytes()).hexdigest()
        checks = {}
        for key, ex in D['exits'].items():
            if not key.startswith(module):
                continue
            hb = ex['wall_radius_mm'] * np.sin(np.radians(ex['design_wrap_deg']))
            for h in (0.02, hb / 2, hb + 0.2):
                z = ex['face_z_mm'] - ex['inboard_sign'] * h
                nominal = float(profile_radius(min(h, hb), ex['wall_radius_mm'], ex['design_wrap_deg'])[0]) if h <= hb else HOLE_R
                loops = [l for l in hole_loops(re, z) if any(abs(l['radius'] - D['lane_radii_mm'][s]) < .3 for s in ex['lanes'])]
                b_new, _ = bridges(re, z) if module == 'M5' else (None, None)
                b_old, _ = bridges(body, z) if module == 'M5' else (None, None)
                checks[f'{key}@h={h:.3f}'] = dict(z_mm=z, nominal_hole_d_mm=2 * nominal,
                                                   measured_hole_d_mm=sorted({round(2 * l['mean_r'], 3) for l in loops}),
                                                   lane_holes_found=len(loops), b_c_bridge_mm=b_new, source_b_c_bridge_mm=b_old)
        rep['section_checks'] = checks
        report['parts'][filename] = rep
        print(filename, json.dumps({k: v for k, v in rep.items() if k != 'section_checks'}))
        for k, v in checks.items(): print('  ', k, v)
    report['all_watertight_single_component'] = all(p['watertight'] and p['components'] == p['source_components'] == 1 for p in report['parts'].values())
    bridges_m5 = [c['b_c_bridge_mm'] for c in report['parts']['M5_lane_anchorB.stl']['section_checks'].values() if c['b_c_bridge_mm'] is not None]
    report['minimum_b_c_bridge_mm'] = min(bridges_m5)
    report['minimum_bridge_target_met'] = min(bridges_m5) >= D['minimum_bridge_target_mm']
    report['note'] = ('Bridge is the minimum polygon distance between same-ray B (24 mm) and C (28 mm) hole sections at the listed depths. '
                      'Section diameters are mean distances of the sliced polygon from its centroid (128-sided cutter).  Geometry only: '
                      'no printed tolerance, strength, wear or rope-qualification claim.')
    (HERE / 'geometry_check.json').write_text(json.dumps(report, indent=1, default=float) + '\n')
    print('all watertight single:', report['all_watertight_single_component'], 'min bridge', report['minimum_b_c_bridge_mm'])


if __name__ == '__main__':
    main()
