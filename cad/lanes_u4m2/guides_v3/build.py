"""Build flared outer-web saddle candidates using the actual V2 module bodies.

The central 0.5 mm axial land retains the 0.15 mm nominal bond gap. Relief
increases toward each socket mouth. This is a geometric candidate, not a
validated bonded joint, compliance model, or manufacturing release.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import trimesh

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'guides_v2'
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('guide_v2_builder', SOURCE / 'build.py')
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)


def build(out, slope, explicit_land=True):
    out.mkdir(parents=True, exist_ok=True)
    V.D = {**json.loads((SOURCE/'design.json').read_text()),
        'status': 'socket-relief engineering candidate; not released for manufacture',
        'socket_flare_slope': slope, 'socket_land_axial_mm': .5,
        'socket_explicit_land_breakpoints': explicit_land,
        'axial_retention': 'Outer-web stations: only the central 0.5 mm land is a proposed bond zone; flared mouths are unbonded relief. Inner-web stations retain the V2 socket. Bond strength and retention are unvalidated.',
        'mounting_stiffness': 'Four webs remain connected by a rigid frame. No claim that relief decouples their motion or preserves homogenised stiffness.',
        'body_source': '../guides_v2; unchanged module bodies, disks, anchors and 21/24/28 mm lanes'}
    V.profiles.cache_clear()
    report = dict(design=V.D, parts={}, all_straight_positions_clear=True,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                      [SOURCE/'build.py', SOURCE/'design.json', SOURCE/'M5_lane_anchorB.stl', SOURCE/'M6_lane_anchorC.stl']})
    for kind, filename in [('M5','M5_lane_anchorB.stl'), ('M6','M6_lane_anchorC.stl')]:
        body = trimesh.load_mesh(SOURCE/filename)
        for z in V.D['stations_z_mm']:
            frame, caps, wires, mounts = V.guide(kind,z)
            if abs(z)==12:
                for mount in mounts:
                    mount['full_depth_reference_bond_area_mm2'] = mount['bond_area_estimate_mm2']
                    mount['bond_area_estimate_mm2'] *= V.D['socket_land_axial_mm']/V.D['plate_thickness_mm']
                    mount['proposed_bond_land_axial_mm'] = V.D['socket_land_axial_mm']
            tag = f'{kind}_z{z:+d}'
            components = dict(guide=frame,caps=trimesh.util.concatenate(caps),wire_envelope=trimesh.util.concatenate(wires))
            checks = {}
            for suffix, mesh in components.items():
                mesh.export(out/f'{tag}_{suffix}.stl')
                loaded = trimesh.load_mesh(out/f'{tag}_{suffix}.stl')
                checks[suffix] = dict(watertight=bool(loaded.is_watertight), components=len(loaded.split()),volume_mm3=float(loaded.volume))
            assembly = trimesh.util.concatenate(list(components.values())); assembly.apply_translation([0,0,z])
            overlap = V.boolean('intersection',[body,assembly])
            volume = 0. if overlap.is_empty else float(overlap.volume)
            ok = volume < 1e-6 and all(c['watertight'] and c['components']==(1 if s=='guide' else 4) for s,c in checks.items())
            report['parts'][tag] = dict(body_overlap_mm3=volume, pass_geometry=ok, mounts=mounts, export_checks=checks)
            report['all_straight_positions_clear'] &= ok
            print(tag,'straight overlap',volume,'valid',ok,flush=True)
    mass = json.loads((SOURCE/'mass_model.json').read_text())
    for row in mass['components']:
        if row['module'] not in ('M5','M6'): continue
        guides = [p for tag,p in report['parts'].items() if tag.startswith(row['module']+'_')]
        row['guide_and_caps_kg'] = sum(p['export_checks'][s]['volume_mm3'] for p in guides for s in ('guide','caps')) * mass['densities_kg_per_mm3']['PA12']
        row['wire_envelope_kg'] = sum(p['export_checks']['wire_envelope']['volume_mm3'] for p in guides) * mass['densities_kg_per_mm3']['steel']
    mass['module_mass_kg'] = [sum(v for k,v in row.items() if k.endswith('_kg')) for row in mass['components']]
    mass['scope'] += ' V3 replaces only guide/cap/wire volumes; unchanged V2 body volumes and stiffness. Socket-mouth relief is not an adhesive/compliance model.'
    (out/'design.json').write_text(json.dumps(V.D,indent=2)+'\n')
    (out/'geometry_check.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'mass_model.json').write_text(json.dumps(mass,indent=2)+'\n')
    if not report['all_straight_positions_clear']: raise RuntimeError('Candidate fails straight assembly')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=HERE)
    p.add_argument('--slope',type=float,default=1.5)
    p.add_argument('--legacy-nine-sections',action='store_true',help='Reproduce rejected early variants without explicit land breakpoints')
    a=p.parse_args()
    if not 0<=a.slope<=2: raise ValueError('slope must be between 0 and 2')
    build(a.out,a.slope,not a.legacy_nine_sections)
