"""Compare rigid-guide contact using axially refined beam-mapped CAD surfaces.

Uses saved 500 g equilibria; does not re-solve contact, mounting stiffness or
control. An axial surface resolution is distinct from the eight-cell rod mesh.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import trimesh
import lanes
from cad_surface_refinement import refine_axial, axial_span
from guide_path_audit import map_cad
from state_archives import load_states
from mesh_boolean64 import to_manifold,to_trimesh


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def in_station_frame(vertices, module, station, rod, details):
    node = module * rod.sub + int(round((station + 48) / (rod.l * 1000)))
    local = (map_cad(vertices, module, rod, details) - details['points'][node]) @ details['frames'][node]
    return np.c_[-local[:, 2], local[:, 1], local[:, 0]] * 1000


def run(archive, cad, out, resolutions, labels, tags, max_seconds, guide_cad=None, export_geometry=False, legacy_float32=False):
    start = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    lanes.install((21, 24, 28), 24)
    rod = lanes.backbone.spatial_rod(4, 2, [4, 5, 6], 20, 8)
    states, coverage = load_states(archive)
    labels = [s[0] for s in states] if labels is None else labels
    selected = {s[0]: s for s in states if s[0] in labels}
    if len(selected) != len(set(labels)):
        raise ValueError('Missing selected states')
    body_names = {'M5': 'M5_lane_anchorB.stl', 'M6': 'M6_lane_anchorC.stl'}
    needed_bodies = sorted({tag.split('_z')[0] for tag in tags})
    if not needed_bodies or not set(needed_bodies).issubset(body_names):
        raise ValueError('Select guide parts belonging to M5 or M6')
    # Retain each complete body, but do not load/refine unrelated modules for
    # a targeted part check. This bounds memory without cropping the solid.
    bodies = {kind: trimesh.load_mesh(cad / body_names[kind]) for kind in needed_bodies}
    guide_cad = cad if guide_cad is None else guide_cad
    assemblies = {tag: trimesh.util.concatenate([trimesh.load_mesh(guide_cad / f'{tag}_{suffix}.stl')
                  for suffix in ('guide', 'caps', 'wire_envelope')]) for tag in tags}
    native_guides = {} if legacy_float32 else {tag:to_manifold(m) for tag,m in assemblies.items()}
    result = dict(scope=__doc__, archive=str(archive), archive_sha256=sha(archive),
        guide_design=json.loads((guide_cad/'design.json').read_text()),
        cad_sha256={p.name: sha(p) for p in sorted(cad.glob('*.stl')) if
                    p.name in [body_names[k] for k in needed_bodies] or
                    any(p.name.startswith(tag + '_') for tag in tags)},
        guide_cad_sha256={p.name:sha(p) for p in sorted(guide_cad.glob('*.stl')) if any(p.name.startswith(tag + '_') for tag in tags)},
        coverage=coverage, selected_states=labels, selected_parts=tags,
        requested_axial_resolutions_mm=resolutions, rod_cells_per_module=8,
        payload_g=500, boolean_transfer_precision='float32' if legacy_float32 else 'float64',
        body_scope='complete deformed body; no cropping', loaded_body_modules=needed_bodies,
        surface_meshes=[], rows=[], completed=False)
    def save():
        result['elapsed_seconds'] = time.monotonic() - start
        (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    save()
    for resolution in resolutions:
        geometry_cache={}
        meshes = {k: refine_axial(v, resolution) if resolution else v.copy() for k, v in bodies.items()}
        for kind, mesh in meshes.items():
            if not mesh.is_watertight or not mesh.is_winding_consistent:
                raise ValueError('Refinement opened the source CAD')
            result['surface_meshes'].append(dict(module=kind, resolution_mm=resolution,
                vertices=len(mesh.vertices), faces=len(mesh.faces), maximum_axial_span_mm=axial_span(mesh),
                undeformed_volume_mm3=float(mesh.volume), watertight=bool(mesh.is_watertight)))
        for label in labels:
            _, z, tension, _ = selected[label]
            details = rod.evaluate(z, tension, detail=True)[2]
            key=z.tobytes()
            if key in geometry_cache:
                for original in geometry_cache[key]:
                    result['rows'].append({**original,'state':label,'reused_geometry_from_state':original['state']})
                save();continue
            native_bodies={}
            if not legacy_float32:
                for kind,mesh in meshes.items():
                    body=mesh.copy();body.vertices=map_cad(body.vertices,int(kind[1:])-1,rod,details)*1000
                    native_bodies[kind]=to_manifold(body)
            state_rows=[]
            for tag in tags:
                if time.monotonic() - start >= max_seconds:
                    result['stop_reason'] = 'study time budget reached'; save(); return result
                kind, station_text = tag.split('_z')
                module, station = int(kind[1:]) - 1, int(station_text)
                if legacy_float32:
                    body = meshes[kind].copy()
                    body.vertices = in_station_frame(body.vertices, module, station, rod, details)
                    overlap = trimesh.boolean.intersection([body, assemblies[tag]], engine='manifold')
                else:
                    node=module*rod.sub+int(round((station+48)/(rod.l*1000)))
                    rotation=details['frames'][node]@np.array([[0,0,1],[0,1,0],[-1,0,0]])
                    translation=details['points'][node]*1000
                    guide=native_guides[tag].transform(np.c_[rotation,translation])
                    solid=native_bodies[kind]^guide
                    overlap=to_trimesh(solid.transform(np.c_[rotation.T,-rotation.T@translation]))
                volume = 0. if overlap.is_empty else float(overlap.volume)
                pieces = []
                if not overlap.is_empty:
                    for piece in overlap.split(only_watertight=False):
                        if abs(piece.volume) > 1e-5:
                            pieces.append(dict(volume_mm3=float(piece.volume),
                                center_station_cad_mm=piece.center_mass.tolist(), bounds_mm=piece.bounds.tolist()))
                row = dict(resolution_mm=resolution, state=label, part=tag,
                    overlap_mm3=volume, pass_interference=volume < 1e-6,
                    overlap_components=pieces)
                result['rows'].append(row);state_rows.append(row); save()
                print({k:v for k,v in row.items() if k != 'overlap_components'}, flush=True)
                if export_geometry and label == 'y175_z8' and tag == 'M5_z-12' and resolution == resolutions[-1]:
                    body=meshes[kind].copy();body.vertices=in_station_frame(body.vertices,module,station,rod,details)
                    suffix = f'{resolution:g}mm' if resolution else 'original'
                    body.export(out / f'M5_body_{suffix}.stl')
                    assemblies[tag].export(out / 'M5_z-12_assembly.stl')
                    if not overlap.is_empty: overlap.export(out / f'M5_z-12_overlap_{suffix}.stl')
            geometry_cache[key]=state_rows
    result['completed'] = True
    result['all_selected_poses_clear'] = all(r['pass_interference'] for r in result['rows'])
    save()
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--cad', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--guide-cad', type=Path, help='Separate guide folder; module bodies remain in --cad')
    p.add_argument('--export-geometry', action='store_true', help='Export one final-resolution diagnostic STL set')
    p.add_argument('--legacy-float32',action='store_true',help='Reproduce the original trimesh Boolean adapter in each station frame')
    p.add_argument('--resolutions', nargs='+', type=float, default=[0, 2, 1, .5])
    p.add_argument('--states', nargs='+', default=['y0_z8', 'y90_z8', 'y175_z8'])
    p.add_argument('--all-states', action='store_true')
    p.add_argument('--parts', nargs='+', default=[f'{k}_z{z:+d}' for k in ('M5', 'M6') for z in (-24, -12, 12, 24)])
    p.add_argument('--max-seconds', type=float, default=900)
    a = p.parse_args()
    run(a.archive, a.cad, a.out, a.resolutions, None if a.all_states else a.states, a.parts, a.max_seconds, a.guide_cad, a.export_geometry, a.legacy_float32)
