"""Build the lane-routed U4+M2 module bodies from the STEP-derived meshes.

Newest design (13 Nov 2026): continuous 96 mm modules U1-U4, M5, M6; three
tendon sets on their own radial lanes (A 21 mm -> ends at U4, B 24 mm -> M5,
C 27 mm -> M6) on the up/right/down/left rays; 1.8 mm NiTi backbone through
M5 and M6.

Assembly frame (all outputs): Z = module axis (proximal -> distal), +Y = up,
+X = left, -X = right (right-handed with the simulation frame X axial, Y up,
Z right). Module body local Z runs -48 (proximal disk) .. +48 (distal disk).

What is changed relative to the source meshes in ../previews/u4m2 (which stay
untouched):
  * Clocking: the spring strips of both bodies lie on the 0/90/180/270 deg rays
    of their STEP frames, exactly where the ropes must run. The U body is
    rotated -45 deg (its leaf-spring diagonal, the stiff direction, then lies
    on +-Y = vertical) and the M body -22.5 deg, which puts every rope lane in
    a straight, strip-free corridor (checked below).
  * Rope pads: the end disks are notched exactly at those corridors, so a
    3 mm pad (radial 18.5-29.5 mm, 7 mm wide) is added in each disk notch on
    every ray, and drilled with 2.5 mm lane holes (2 mm rope + 0.5 mm) with
    0.25 mm entry chamfers.
  * Anchors: the distal disk of the anchor module gets a 7 mm deep anchor
    block per ray (disk + 4 mm into the free space inside the module) with a
    groove on the distal face and a return hole: the rope comes up its lane,
    turns along the groove, goes back down the return hole and is crimped on the
    inside face. B and C loop tangentially (return hole 5 mm beside the lane);
    A loops radially inward (return hole 3.5 mm inside the lane) so the U4 block
    stays clear of the leaf springs. A stop never sits on a lane, which the 3 mm
    lane pitch could not accommodate.
  * Backbone: the 8.4 mm M passage is plugged and bored 1.85 mm for the
    1.8 mm NiTi rod, and a 6 mm OD x 12 mm sleeve inside each M end disk
    gives the rod 15 mm of support per end so it is clamped in rotation.
  * Solid disks: each 3 mm end disk is a full round plate (r 31.45 mm); the STEP
    notches, blind slots (strip-root reliefs, U diagonal slots) and the unused 8.4 mm
    centre hole are filled. The only holes left are lane
    holes, anchor grooves/return holes, the M backbone bore, the joint holes and the U
    leaf-spring pockets.
  * Joints: 4 holes at r 12.5 mm: left/right 1.9 mm pilots for 2 mm dowel pins (ream),
    up/down 2.2 mm for M2 screws + nuts; free inside both bodies.

See BUILD_GUIDE.md for making and assembling the parts; build_ends_and_check.py
adds the base interface and head adapter and checks the whole assembly.

Outputs (this folder): U_lane_pass.stl (U1-U3), U4_lane_anchorA.stl,
M5_lane_anchorB.stl, M6_lane_anchorC.stl, U_leaf_springs.stl (unchanged
springs, re-clocked), lane_design.json (dimensions + checks),
lane_assembly.scad (OpenSCAD viewer), lane_disks.png (end-disk faces).
"""
import json
from pathlib import Path
import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'previews' / 'u4m2'

LANES = dict(A=21., B=24., C=27.)                   # mm, set -> lane radius
ANCHOR_MODULE = dict(A=3, B=4, C=5)                 # 0..5 = U1..U4, M5, M6
RAYS = dict(right=180., up=90., left=0., down=270.)  # deg in the assembly XY plane (+X = left)
ROPE_D, HOLE_D, CHAMFER = 2.0, 2.5, .25   # chamfer to 3.0 mm: keeps a wall at the 3 mm lane pitch
ROD_D, BORE_D, SLEEVE_OD, SLEEVE_L, PLUG_D = 1.8, 1.85, 6., 12., 8.6
PAD_R, PAD_W, DISK_T, HALF = (18.5, 29.5), 7., 3., 48.
ANCHOR_DEPTH, RETURN_OFFSET, GROOVE_W, GROOVE_D = 4., 5., 2.2, 2.2
RETURN_INWARD, RETURN_WALL = 3.5, 2.   # set A: return hole 3.5 mm radially inside its lane (r 17.5)


def return_step(s):
    """(radial, tangential) offset of a set's return hole from its lane hole, mm."""
    return (-RETURN_INWARD, 0.) if s == 'A' else (0., RETURN_OFFSET)
BOLT_R, BOLT_D, BOLT_ANGLES = 12.5, 2.2, (0., 90., 180., 270.)
DOWEL_ANGLES, SCREW_ANGLES, DOWEL_PILOT_D = (0., 180.), (90., 270.), 1.9   # pilot: ream to 2.00 (press) / 2.02 (slip)


def joint_hole_d(a):
    return DOWEL_PILOT_D if a in DOWEL_ANGLES else BOLT_D
CLOCK = dict(U=-45., M=-22.5)
KINDS = ['U', 'U', 'U', 'U', 'M', 'M']


def rz(deg):
    return rotation_matrix(np.radians(deg), [0, 0, 1])


def source(kind):
    if kind == 'U':
        rx = rotation_matrix(np.pi / 2, [1, 0, 0])   # U STEP is long on Y
        body = trimesh.load(SRC / 'UniDirectional_96_part_01.stl'); body.apply_transform(rx)
        springs = trimesh.util.concatenate([trimesh.load(SRC / f'UniDirectional_96_part_0{i}.stl') for i in range(2, 6)])
        springs.apply_transform(rx); springs.apply_transform(rz(CLOCK['U']))
    else:
        body = trimesh.load(SRC / 'Medium_Stiffness_96.stl'); springs = None
    body.apply_transform(rz(CLOCK[kind]))
    return body, springs


def on_ray(ray_deg, r, t, z0, z1, dr, dt):
    """Box of size dr x dt x (z1-z0) centred at radius r, tangential offset t on a ray."""
    box = trimesh.creation.box([dr, dt, z1 - z0])
    box.apply_translation([r, t, (z0 + z1) / 2])
    box.apply_transform(rz(ray_deg))
    return box


def cyl(d, z0, z1, x=0., y=0., sections=48):
    c = trimesh.creation.cylinder(radius=d / 2, height=z1 - z0, sections=sections)
    c.apply_translation([x, y, (z0 + z1) / 2])
    return c


def cone(d0, d1, z0, z1, x, y):
    """Truncated cone from diameter d0 at z0 to d1 at z1 (entry chamfer)."""
    n = 32; a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = lambda d, z: np.c_[x + d / 2 * np.cos(a), y + d / 2 * np.sin(a), np.full(n, z)]
    return trimesh.convex.convex_hull(np.vstack([ring(d0, z0), ring(d1, z1)]))


def xy(ray_deg, r, t=0.):
    a = np.radians(ray_deg)
    return r * np.cos(a) - t * np.sin(a), r * np.sin(a) + t * np.cos(a)


def disk_fill(body, r=31.45):
    """Solid round end disks: every STEP notch, blind slot (strip-root reliefs, U diagonal slots)
    and the 8.4 mm centre hole in the 3 mm disk layer is filled with a full Ø62.9 mm plate; only
    the functional holes are cut again afterwards. The strips stay at r ~ 10 mm next to the disk,
    so the plate does not reach into their path."""
    return [cyl(2 * r, z0, z0 + DISK_T, sections=180) for z0 in (-HALF, HALF - DISK_T)]


SPRING_CLEARANCE = .1


def spring_pockets(springs):
    """Leaf-spring pockets: the spring section + 0.1 mm per side. Proximal pocket goes through the
    disk (the spring slides in from the proximal face); distal pocket is blind, 2 mm deep. The
    spring (94 mm) then sits from the distal pocket bottom (z = +47) to 1 mm inside the proximal face
    and is bonded at both ends; the next module or the base interface closes the opening."""
    from shapely.geometry import Polygon
    out = []
    for sp in springs.split(only_watertight=False):
        top = sp.bounds[1, 2]
        sec = sp.section(plane_origin=[0, 0, top - 1.], plane_normal=[0, 0, 1])
        poly = Polygon(max(sec.discrete, key=len)[:, :2]).buffer(SPRING_CLEARANCE, join_style=2)
        for z0, z1 in ((-HALF - 1, -HALF + DISK_T + .01), (HALF - DISK_T - .01, top)):
            pr = trimesh.creation.extrude_polygon(poly, z1 - z0); pr.apply_translation([0, 0, z0]); out.append(pr)
    return out


def module_sets(i):
    """Lane sets passing through module i, and the set anchored at its distal disk (or None)."""
    sets = [s for s, m in ANCHOR_MODULE.items() if m >= i]
    anchor = next((s for s, m in ANCHOR_MODULE.items() if m == i), None)
    return sets, anchor


def build(i):
    kind = KINDS[i]
    body, springs = source(kind)
    sets, anchor = module_sets(i)
    add, sub = disk_fill(body), []
    if springs is not None:
        sub += spring_pockets(springs)
    for ray in RAYS.values():
        for z0, z1 in ((-HALF, -HALF + DISK_T), (HALF - DISK_T, HALF)):
            add.append(on_ray(ray, sum(PAD_R) / 2, 0., z0, z1, PAD_R[1] - PAD_R[0], PAD_W))
        if anchor:
            ra = LANES[anchor]
            dr, dt = return_step(anchor)
            if dt:   # tangential loop (B, C): block widened sideways to hold the return hole
                add.append(on_ray(ray, sum(PAD_R) / 2, dt / 2, HALF - DISK_T - ANCHOR_DEPTH, HALF, PAD_R[1] - PAD_R[0], PAD_W + dt))
                sub.append(on_ray(ray, ra, dt / 2, HALF - GROOVE_D, HALF + 1, GROOVE_W, dt))
            else:    # radial loop (A, innermost): block extended inward, stays 7 mm wide (clear of the U leaf springs)
                r0 = ra + dr - RETURN_WALL
                add.append(on_ray(ray, (r0 + PAD_R[1]) / 2, 0., HALF - DISK_T - ANCHOR_DEPTH, HALF, PAD_R[1] - r0, PAD_W))
                sub.append(on_ray(ray, ra + dr / 2, 0., HALF - GROOVE_D, HALF + 1, -dr, GROOVE_W))
            x, y = xy(ray, ra + dr, dt)
            sub.append(cyl(HOLE_D, HALF - DISK_T - ANCHOR_DEPTH - 1, HALF + 1, x, y))
        for s in sets:
            x, y = xy(ray, LANES[s])
            sub.append(cyl(HOLE_D, -HALF - 1, HALF + 1, x, y))
            faces = [(-HALF, 1), (-HALF + DISK_T, -1), (HALF, -1)]
            faces.append((HALF - DISK_T - (ANCHOR_DEPTH if anchor else 0), 1))
            for zf, sgn in faces:   # chamfer every face the rope crosses (sgn: direction into the material)
                sub.append(cone(HOLE_D + 2 * CHAMFER, HOLE_D, zf - sgn * .01, zf + sgn * CHAMFER, x, y))
    for a in BOLT_ANGLES:
        x, y = xy(a, BOLT_R)
        sub.append(cyl(joint_hole_d(a), -HALF - 1, HALF + 1, x, y, 24))
    if kind == 'M':
        for sgn in (-1, 1):
            z_out, z_in = sgn * HALF, sgn * (HALF - DISK_T - SLEEVE_L)
            add.append(cyl(PLUG_D, min(z_out, sgn * (HALF - DISK_T)), max(z_out, sgn * (HALF - DISK_T))))
            add.append(cyl(SLEEVE_OD, min(z_out, z_in), max(z_out, z_in)))
        sub.append(cyl(BORE_D, -HALF - 1, HALF + 1, sections=32))
    # Only remove material inside the pads/blocks/plugs/bolt holes; bolt holes must not cut the springs pockets.
    out = trimesh.boolean.union([body] + add, engine='manifold')
    out = trimesh.boolean.difference([out] + sub, engine='manifold')
    return out, springs, sets, anchor


def straight_clearance(mesh, x, y, z0=-HALF + DISK_T + .1, z1=HALF - DISK_T - .1):
    """Smallest gap (mm) between a straight 2 mm rope running disk to disk and the body between the
    disks (the disk layers themselves are drilled, so they are excluded); negative = the rope axis
    passes through material."""
    inner = mesh.slice_plane([0, 0, z0 - .05], [0, 0, 1]).slice_plane([0, 0, z1 + .05], [0, 0, -1])
    zs = np.linspace(z0, z1, 400)
    P = np.c_[np.full_like(zs, x), np.full_like(zs, y), zs]
    _, d, _ = trimesh.proximity.closest_point(inner, P)
    hit = inner.ray.intersects_any([[x, y, z0 - .05]], [[0, 0, 1.]])[0]
    return float(-d.min() if hit else d.min() - ROPE_D / 2)


def main():
    report = dict(frame='Z axial (proximal -> distal), +Y up, +X left, -X right; module local Z -48..48',
                  lanes_mm=LANES, anchor_module={s: ['U1', 'U2', 'U3', 'U4', 'M5', 'M6'][m] for s, m in ANCHOR_MODULE.items()},
                  rays_deg=RAYS, body_clocking_deg=CLOCK, rope_d=ROPE_D, lane_hole_d=HOLE_D, chamfer=CHAMFER,
                  lane_pitch_mm=3., wall_between_lane_holes_mm=3. - HOLE_D, rod_d=ROD_D, rod_bore_d=BORE_D,
                  rod_support_length_per_end_mm=DISK_T + SLEEVE_L, sleeve_od=SLEEVE_OD, pad=dict(radial=PAD_R, width=PAD_W, thickness=DISK_T),
                  anchor=dict(block_depth=DISK_T + ANCHOR_DEPTH, return_offset_B_C_tangential=RETURN_OFFSET, return_offset_A_radial_inward=RETURN_INWARD, groove_w=GROOVE_W, groove_d=GROOVE_D),
                  joint=dict(radius=BOLT_R, dowel_angles=DOWEL_ANGLES, dowel_pilot_d=DOWEL_PILOT_D, screw_angles=SCREW_ANGLES, screw_hole_d=BOLT_D), modules={})
    names = {0: 'U_lane_pass', 3: 'U4_lane_anchorA', 4: 'M5_lane_anchorB', 5: 'M6_lane_anchorC'}
    # straight-corridor clearance of every lane in the *unmodified* re-clocked bodies (ropes between the disks)
    for kind in 'UM':
        body, springs = source(kind)
        full = body if springs is None else trimesh.util.concatenate([body, springs])
        report[f'{kind}_lane_clearance_mm'] = {f'{s}@{ray}': round(straight_clearance(full, *xy(a, LANES[s])), 2)
                                               for s in LANES for ray, a in RAYS.items()}
        report[f'{kind}_lane_clearance_without_reclocking_mm'] = {
            s: round(straight_clearance(full.copy().apply_transform(rz(-CLOCK[kind])), *xy(0., LANES[s])), 2) for s in LANES}
    for i, name in names.items():
        mesh, springs, sets, anchor = build(i)
        mesh.export(HERE / f'{name}.stl')
        if springs is not None and i == 0:
            springs.export(HERE / 'U_leaf_springs.stl')
        r = np.hypot(mesh.vertices[:, 0], mesh.vertices[:, 1]).max()
        report['modules'][name] = dict(used_for=['U1, U2, U3', '', '', 'U4', 'M5', 'M6'][i], lanes=sets, anchored_set=anchor,
                                       watertight=bool(mesh.is_watertight), volume_mm3=round(float(mesh.volume), 1),
                                       max_radius_mm=round(float(r), 2), bounds=np.round(mesh.bounds, 2).tolist())
        print(name, report['modules'][name])
    (HERE / 'lane_design.json').write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if 'clearance' in k}, indent=1))


if __name__ == '__main__':
    main()
