"""Base interface, head adapter and a whole-assembly hole check for the lane-routed U4+M2 front.

Run after build_lane_modules.py (it reads the module STLs from this folder):
    python build_lane_modules.py && python build_ends_and_check.py

Writes base_interface.stl, head_adapter.stl, spring_strip.json and assembly_check.json.

Assembly frame: Z axial. Base interface z -20..0 (the simulation's 20 mm clamp), U1 0..96,
U2 96..192, U3 192..288, U4 288..384, M5 384..480, M6 480..576, head adapter 576..582.
"""
import json
from pathlib import Path
import numpy as np
import trimesh
import build_lane_modules as B

HERE = Path(__file__).resolve().parent
R_OUT = 31.45
CBORE_D, CBORE_LEFT = 4.2, 3.        # M2 socket-head counterbore; 3 mm of material left under the head
INSERT_D, INSERT_DEPTH = 4.0, 6.     # M3 heat-set insert (short, 4.0 mm hole)
BASE_L, ADAPTER_T = 20., 6.
MOUNT_R_BASE, MOUNT_R_HEAD, MOUNT_ANGLES = 17., 20., (45., 135., 225., 315.)
ROD_RELIEF_D, ROD_RELIEF_DEPTH = 2.4, 1.
REAR_FLARE_D, REAR_FLARE_DEPTH = 2.9, .5   # rope exit chamfer toward the winches (3 mm lane pitch)
FILES = ['U_lane_pass.stl'] * 3 + ['U4_lane_anchorA.stl', 'M5_lane_anchorB.stl', 'M6_lane_anchorC.stl']


def ring_holes(z0, z1, d, r, angles, sections=24):
    return [B.cyl(d, z0, z1, *B.xy(a, r), sections=sections) for a in angles]


def base_interface():
    """20 mm block between the rear beam and U1: guides all 12 ropes straight into U1."""
    add = [B.cyl(2 * R_OUT, -BASE_L, 0., sections=180)]
    sub = []
    for s, r in B.LANES.items():
        for a in B.RAYS.values():
            x, y = B.xy(a, r)
            sub.append(B.cyl(B.HOLE_D, -BASE_L - 1, 1., x, y))
            sub.append(B.cone(B.HOLE_D + 2 * B.CHAMFER, B.HOLE_D, .01, -B.CHAMFER, x, y))           # front chamfer
            sub.append(B.cone(REAR_FLARE_D, B.HOLE_D, -BASE_L - .01, -BASE_L + REAR_FLARE_DEPTH, x, y))  # rear flare
    sub += ring_holes(-BASE_L - 1, 1., B.BOLT_D, B.BOLT_R, B.SCREW_ANGLES)
    sub += ring_holes(-BASE_L + 2, 1., B.DOWEL_PILOT_D, B.BOLT_R, B.DOWEL_ANGLES)                   # blind dowel holes, 18 mm deep
    sub += ring_holes(-BASE_L - 1, -CBORE_LEFT, CBORE_D, B.BOLT_R, B.SCREW_ANGLES)                # screw-head access from the rear
    sub += ring_holes(-BASE_L - 1, -BASE_L + INSERT_DEPTH, INSERT_D, MOUNT_R_BASE, MOUNT_ANGLES)  # M3 inserts to the rear beam
    return trimesh.boolean.difference([trimesh.boolean.union(add, engine='manifold')] + sub, engine='manifold')


def head_adapter():
    """6 mm plate on the M6 distal face: closes the C anchor grooves, carries the head."""
    add = [B.cyl(2 * R_OUT, 0., ADAPTER_T, sections=180)]
    sub = ring_holes(-1, ADAPTER_T + 1, B.BOLT_D, B.BOLT_R, B.SCREW_ANGLES)
    sub += ring_holes(-1, ADAPTER_T - 1, B.DOWEL_PILOT_D, B.BOLT_R, B.DOWEL_ANGLES)              # blind dowel holes, 5 mm deep
    sub += ring_holes(CBORE_LEFT, ADAPTER_T + 1, CBORE_D, B.BOLT_R, B.SCREW_ANGLES)
    sub += ring_holes(ADAPTER_T - INSERT_DEPTH + 1.5, ADAPTER_T + 1, INSERT_D, MOUNT_R_HEAD, MOUNT_ANGLES)  # 4.5 mm deep
    sub.append(B.cyl(ROD_RELIEF_D, -1, ROD_RELIEF_DEPTH, sections=24))
    return trimesh.boolean.difference([trimesh.boolean.union(add, engine='manifold')] + sub, engine='manifold')


def spring_info():
    _, springs = B.source('U')
    parts = springs.split(only_watertight=False)
    sp = parts[0]
    secs = {}
    for z in (-46., -30., 0., 30., 46.):
        s = sp.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1]); P = max(s.discrete, key=len)[:, :2]
        Q = P - P.mean(0); _, _, vt = np.linalg.svd(Q, full_matrices=False); d = np.ptp(np.asarray(Q @ vt.T), axis=0)
        secs[f'{z:+.0f}'] = dict(width=round(float(d[0]), 2), thickness=round(float(d[1]), 2),
                                 area=round(float(trimesh.path.polygons.Polygon(P).area), 2))
    centres = [dict(radius=round(float(np.hypot(*p.centroid[:2])), 2), angle_deg=round(float(np.degrees(np.arctan2(p.centroid[1], p.centroid[0]))), 1)) for p in parts]
    return dict(count_per_U=len(parts), total=4 * len(parts), length_mm=round(float(sp.bounds[1, 2] - sp.bounds[0, 2]), 2),
                volume_mm3=round(float(sp.volume), 1), sections=secs, positions=centres,
                note='Exact shape: UniDirectional_96.step (solids 2-5) or U_leaf_springs.stl; material NiTi per project intent.')


def open_at(mesh, x, y, zs):
    return not bool(mesh.contains(np.array([[x, y, z] for z in zs])).any())


def assembly_check(base, head):
    mods = [trimesh.load(HERE / f) for f in FILES]
    rep = dict(joints=[], ropes={}, rod={}, envelope_mm={})
    names = ['base'] + ['U1', 'U2', 'U3', 'U4', 'M5', 'M6'] + ['head']
    # every joint: the four joint holes are open on both mating faces
    faces = [(base, -.5)] + [(m, None) for m in mods] + [(head, .5)]
    for k in range(len(names) - 1):
        lo, hi = names[k], names[k + 1]
        a = base if k == 0 else mods[k - 1]; za = -.5 if k == 0 else B.HALF - .5
        b = head if k == 6 else mods[k]; zb = .5 if k == 6 else -B.HALF + .5
        ok = all(open_at(a, *B.xy(t, B.BOLT_R), [za]) and open_at(b, *B.xy(t, B.BOLT_R), [zb]) for t in B.BOLT_ANGLES)
        rep['joints'].append(dict(joint=f'{lo}-{hi}', joint_holes_open_and_aligned=ok))
    # every rope: a clear straight path through every disk up to its anchor disk; return hole present there
    for s, r in B.LANES.items():
        m_anchor = B.ANCHOR_MODULE[s]
        for ray, ang in B.RAYS.items():
            x, y = B.xy(ang, r)
            path = open_at(base, x, y, np.linspace(-BASE_L + .1, -.1, 40))
            for i in range(m_anchor + 1):
                path &= open_at(mods[i], x, y, np.r_[np.linspace(-B.HALF + .1, -B.HALF + B.DISK_T, 8), np.linspace(B.HALF - B.DISK_T - B.ANCHOR_DEPTH * (i == m_anchor), B.HALF - .1, 10)])
            dr, dt = B.return_step(s)
            xr, yr = B.xy(ang, r + dr, dt)
            anchor = mods[m_anchor]
            ret = open_at(anchor, xr, yr, np.linspace(B.HALF - B.DISK_T - B.ANCHOR_DEPTH + .1, B.HALF - .1, 10))
            groove = open_at(anchor, *B.xy(ang, r + dr / 2, dt / 2), [B.HALF - .5, B.HALF - 1.5])
            closed_after = (m_anchor == 5) or not open_at(mods[m_anchor + 1], x, y, [-B.HALF + 1.5])
            rep['ropes'][f'{s}_{ray}'] = dict(clear_path_base_to_anchor=bool(path), groove=bool(groove), return_hole=bool(ret),
                                              no_hole_beyond_anchor=bool(closed_after))
    # rod: bore open through M5 and M6, U4 distal centre solid, adapter relief
    zs = np.linspace(-B.HALF + .1, B.HALF - B.DISK_T - B.SLEEVE_L + 3, 1)
    rep['rod'] = dict(M5_bore_open=open_at(mods[4], 0, 0, np.linspace(-B.HALF + .1, B.HALF - .1, 50)),
                      M6_bore_open=open_at(mods[5], 0, 0, np.linspace(-B.HALF + .1, B.HALF - .1, 50)),
                      M_bore_wall_at_0p9mm=bool(mods[4].contains([[1.0, 0, -46.5], [1.0, 0, 40.]]).all()),
                      U4_distal_centre_solid=bool(mods[3].contains([[0, 0, B.HALF - .5]])[0]),
                      rod_length_mm=2 * 2 * B.HALF)
    for n, m in zip(names, [base] + mods + [head]):
        rep['envelope_mm'][n] = round(float(np.hypot(m.vertices[:, 0], m.vertices[:, 1]).max()), 2)
    flat = [v for d in rep['joints'] for v in d.values() if isinstance(v, bool)]
    flat += [v for d in rep['ropes'].values() for v in d.values()] + [v for v in rep['rod'].values() if isinstance(v, bool)]
    rep['all_pass'] = all(flat)
    return rep


def clearance_checks():
    """Leaf springs vs U bodies (springs shifted 1.5 mm in 8 directions, between the disks) and
    M2 nuts (4.8 mm across corners x 1.6 mm) on the inner face of every joint hole; volumes in mm3."""
    _, spr = B.source('U')
    box = trimesh.creation.box([80, 80, 2 * (B.HALF - B.DISK_T) - .2])
    out = {}
    for f in ('U_lane_pass.stl', 'U4_lane_anchorA.stl'):
        m = trimesh.load(HERE / f); worst = 0.
        for t in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            s2 = spr.copy(); s2.apply_translation([1.5 * np.cos(t), 1.5 * np.sin(t), 0])
            j = trimesh.boolean.intersection([m, trimesh.boolean.intersection([s2, box], engine='manifold')], engine='manifold')
            worst = max(worst, float(j.volume) if len(j.faces) else 0.)
        out[f'{f}: spring_overlap_with_1p5mm_shift'] = round(worst, 3)
    nut = trimesh.creation.cylinder(radius=2.4, height=1.6, sections=6)
    for f in sorted(set(FILES)):
        m = trimesh.load(HERE / f); worst = 0.
        for a in B.BOLT_ANGLES:
            for zc in (B.HALF - B.DISK_T - .85, -B.HALF + B.DISK_T + .85):
                n2 = nut.copy(); n2.apply_translation([*B.xy(a, B.BOLT_R), zc])
                j = trimesh.boolean.intersection([m, n2], engine='manifold'); worst = max(worst, float(j.volume) if len(j.faces) else 0.)
        out[f'{f}: M2_nut_overlap'] = round(worst, 3)
    return out


def main():
    base, head = base_interface(), head_adapter()
    base.export(HERE / 'base_interface.stl'); head.export(HERE / 'head_adapter.stl')
    for n, m in (('base_interface', base), ('head_adapter', head)):
        print(n, 'watertight', m.is_watertight, 'volume mm3', round(m.volume, 1), 'bounds', np.round(m.bounds, 2).tolist())
    info = spring_info(); (HERE / 'spring_strip.json').write_text(json.dumps(info, indent=1)); print(json.dumps(info))
    rep = assembly_check(base, head)
    rep['clearance_mm3'] = clearance_checks()
    rep['all_pass'] = rep['all_pass'] and all(v == 0 for v in rep['clearance_mm3'].values())
    rep['parts'] = {n: dict(watertight=bool(m.is_watertight), volume_mm3=round(float(m.volume), 1)) for n, m in
                    [('base_interface', base), ('head_adapter', head)] + [(f, trimesh.load(HERE / f)) for f in sorted(set(FILES))]}
    (HERE / 'assembly_check.json').write_text(json.dumps(rep, indent=1))
    bad = {k: v for k, v in rep['ropes'].items() if not all(v.values())}
    print('joints', rep['joints']); print('rod', rep['rod']); print('rope failures', bad); print('envelope', rep['envelope_mm']); print('clearance', rep['clearance_mm3']); print('ALL PASS', rep['all_pass'])


if __name__ == '__main__':
    main()
