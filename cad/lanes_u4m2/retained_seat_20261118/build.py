"""Build the independent M5 guide station parts and machine only the eight mounted webs."""

import argparse
import json
from pathlib import Path

import manifold3d as md
import numpy as np
import trimesh

import joint as j

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
BODY = BASE / "end_bellmouth_v1/M5_lane_anchorB.stl"
FRAME = BASE / "guides_v3/M5_z+12_guide.stl"
M = md.Manifold
N = 96


def load(path):
    tri = trimesh.load_mesh(path)
    if not tri.is_volume:
        raise ValueError(f"Open input solid: {path}")
    obj = M(
        md.Mesh64(
            np.ascontiguousarray(tri.vertices),
            np.ascontiguousarray(tri.faces, dtype=np.uint64),
        )
    )
    if obj.status() != md.Error.NoError:
        raise ValueError(f"B-rep conversion failed: {path}")
    return obj


def trimesh_of(obj):
    m = obj.to_mesh64()
    return trimesh.Trimesh(m.vert_properties[:, :3], m.tri_verts, process=True)


def export(obj, path):
    if (
        obj.status() != md.Error.NoError
        or len(obj.decompose()) != 1
        or obj.volume() <= 0
    ):
        raise ValueError(
            f"Disconnected or invalid part {path.name}: {len(obj.decompose())} components"
        )
    tri = trimesh_of(obj)
    tri = trimesh.Trimesh(tri.vertices.astype(np.float32), tri.faces, process=True)
    tri.update_faces(tri.unique_faces() & tri.nondegenerate_faces(height=0))
    tri.remove_unreferenced_vertices()
    tri.export(path)
    r = trimesh.load_mesh(path)
    if not r.is_volume or len(r.split(only_watertight=False)) != 1:
        raise ValueError(f"STL round trip failed: {path.name}")
    return dict(volume_mm3=float(r.volume), triangles=len(r.faces), closed=True)


def box(lo, hi):
    lo, hi = np.array(lo), np.array(hi)
    return M.cube(hi - lo).translate(lo)


def cyl(r, low, high, n=N):
    return M.cylinder(high - low, r, r, n).translate((0, 0, low))


def revolve(path):
    return md.CrossSection([np.asarray(path)], md.FillRule.EvenOdd).revolve(N)


def axial_profile(y, r):
    ring = np.column_stack((r, y)).tolist()
    return revolve([[0, y[0]], *ring, [0, y[-1]]])


def yz(obj):
    return obj.rotate((-90, 0, 0)).translate((j.R_PIVOT, 0, 0))


def place(obj, angle, z=0):
    return obj.rotate((0, 0, angle)).translate((0, 0, z))


def union(parts):
    return M.batch_boolean(parts, md.OpType.Add)


def rigid_box(width_lo, width_hi, s):
    x0, y0 = width_lo
    x1, y1 = width_hi
    return np.array([[s, x0, y0], [s, x1, y0], [s, x1, y1], [s, x0, y1]])


def loft(station, profile):
    # Each section is perpendicular to the inclined mounting web.
    ss = [-12.0, -j.LAND / 2, j.LAND / 2, 12.0]
    v = np.vstack([rigid_box(*profile(s), s) for s in ss]) @ j.web_axes(station).T + [
        j.R_PIVOT,
        0,
        0,
    ]
    f = [[0, 2, 1], [0, 3, 2]]
    for k in range(3):
        for i in range(4):
            a, b = 4 * k + i, 4 * k + (i + 1) % 4
            f.extend([[a, b, b + 4], [a, b + 4, a + 4]])
    f.extend([[12, 13, 14], [12, 14, 15]])
    return M(md.Mesh64(v, np.asarray(f, np.uint64)))


def web_cut():
    y = np.unique(np.r_[np.linspace(-1.65, 1.65, 101), 0])
    bore = axial_profile(y, j.hole_radius(y))
    r = np.unique(np.r_[np.linspace(0, j.PATCH, 56), np.linspace(j.PATCH, j.BLEND, 18)])
    surface = revolve(
        [
            [0, 1.72],
            [j.BLEND, 1.72],
            *np.column_stack((r, j.face_height(r)))[::-1].tolist(),
        ]
    )
    return yz(bore + surface + surface.mirror((0, 0, 1)))


def teeth(z, angle, pitch, root, major, phase=0):
    # Truncated 60-degree helical V profile; both mating parts use the same phase.
    x = np.abs(((z / pitch - angle / (2 * np.pi) + phase + 0.5) % 1) - 0.5)
    return np.clip(major - (np.maximum(x - 0.065, 0) * pitch * np.sqrt(3)), root, major)


def thread(start, end, pitch, minor, major):
    n = 48
    levels = max(8, int(np.ceil((end - start) / pitch * 20)))
    z = np.linspace(start, end, levels + 1)
    a = np.arange(n) * 2 * np.pi / n
    rr = teeth(z[:, None], a, pitch, minor, major)
    vertices = np.stack(
        (rr * np.cos(a), rr * np.sin(a), np.broadcast_to(z[:, None], rr.shape)), axis=-1
    ).reshape(-1, 3)
    faces = []
    for k in range(levels):
        for i in range(n):
            ia = k * n + i
            ib = k * n + (i + 1) % n
            faces.extend([(ia, ib, ib + n), (ia, ib + n, ia + n)])
    for i in range(1, n - 1):
        faces.extend([(0, i + 1, i), (levels * n, levels * n + i, levels * n + i + 1)])
    return M(md.Mesh64(vertices, np.asarray(faces, np.uint64)))


def pilot_segment(hi, r=0.72):
    centre, tangent = j.thrust_rim()
    angle = np.linspace(np.arctan2(*(tangent - centre)[::-1]), 0, 25)
    radii = np.r_[
        np.linspace(0.26, tangent[0], 36),
        (centre[0] + j.THRUST_FILLET * np.cos(angle))[1:],
    ]
    front = np.column_stack((radii, j.thrust_height(radii))).tolist()
    return revolve([[0, front[0][1]], *front, [r, hi], [0, hi]])


def metal_parts():
    # Shoulder seats on the negative cheek. The screw-on thrust cap captures the sliding gate on the positive cheek.
    negative = pilot_segment(j.CHEEK).mirror((0, 0, 1))
    shaft = cyl(j.PIN, -j.CHEEK, 2.46)
    head = cyl(1.04, -j.CHEEK - 0.42, -j.CHEEK)
    slot = box((-0.14, -1.15, -j.CHEEK - 0.44), (0.14, 1.15, -j.CHEEK - 0.25))
    male = thread(2.42, 3.68, 0.15, 0.206, 0.288)
    pin = yz((negative + head + shaft + male) - slot)
    blank = pilot_segment(j.GATE_TOP + 0.02) + cyl(
        1.04, j.GATE_TOP, j.GATE_TOP + 0.46
    )
    female = thread(2.36, 3.77, 0.15, 0.223, 0.307)
    clearance = cyl(0.316, 0, 2.46)
    cap = yz(
        blank
        - (female + clearance)
        - box((-0.14, -1.1, j.GATE_TOP + 0.28), (0.14, 1.1, j.GATE_TOP + 0.49))
    )
    return pin, cap


def lock_screw():
    male = thread(-1.48, -0.53, 0.25, 0.335, 0.482)
    stem = cyl(0.48, -0.57, 1.64)
    head = cyl(0.80, 1.60, 1.94)
    return (male + stem + head) - box((-0.13, -0.85, 1.79), (0.13, 0.85, 1.99))


def tongue(y):
    return box((8.33, y - 0.91, -0.55), (11.69, y + 0.91, 0.55)) - cyl(
        0.535, -2, 2
    ).translate((j.HUB_FASTENER_X, y, 0))


def hub():
    ring = cyl(j.HUB_R, -1.6, 1.6) - cyl(7.80, -2, 2)
    for a, y in [(k, 0) for k in (0, 90, 180, 270)] + [(k, j.FORK_Y) for k in j.ANGLES]:
        slot = box((8.25, y - 0.955, -0.595), (14, y + 0.955, 0.595))
        hole = cyl(0.54, -0.61, 2.1) + thread(-1.68, -0.54, 0.25, 0.356, 0.506)
        ring = ring - place(slot + hole.translate((j.HUB_FASTENER_X, y, 0)), a)
    return ring


def lap_screw():
    male = thread(-1.44, -0.065, 0.20, 0.264, 0.383)
    stem = cyl(0.37, 0.03, 1.62) + cyl(0.263, -0.10, 0.05)
    head = cyl(0.62, 1.6, 1.88)
    return (male + stem + head) - box((-0.105, -0.68, 1.75), (0.105, 0.68, 1.92))


def sector(halfangle, low, high):
    a = np.deg2rad(halfangle)
    return (
        md.CrossSection(
            [
                [
                    (0, 0),
                    (20 * np.cos(a), -20 * np.sin(a)),
                    (20 * np.cos(a), 20 * np.sin(a)),
                ]
            ]
        )
        .extrude(high - low)
        .translate((0, 0, low))
    )


def hub_sectors():
    ring = hub()
    hole = cyl(0.421, -0.02, 2.05) + thread(-1.65, 0.06, 0.20, 0.283, 0.405)
    for a in np.arange(22.5, 360, 45):
        ring -= place(hole.translate((9.60, 0, 0)), a)
    full = sector(17.55, -1.61, 1.61)
    upper = sector(27.12, 0.024, 1.61)
    lower = sector(27.12, -1.61, -0.024)
    return ring ^ (full + upper), ring.rotate((0, 0, -45)) ^ (full + lower)


def arm():
    existing = load(FRAME)
    # Clip the arm from the source mesh to preserve both original bellmouth faces exactly.
    finger = existing ^ box((11.31, -3.005, -1.65), (30.65, 3.005, 1.65))
    outline = [
        (11, -1.10),
        (20.8, -1.10),
        (22.50, -3.01),
        (31, -3.01),
        (31, 3.01),
        (22.50, 3.01),
        (20.8, 1.10),
        (11, 1.10),
    ]
    waist = md.CrossSection([outline]).extrude(3.4).translate((0, 0, -1.7))
    return (finger ^ waist) + tongue(0)


def saddle(station, radial_limit=j.FORK_RADIAL_LIMIT):
    h = j.PLATE_HALF
    slab = box((13.6, -5, -h), (31, 5, h))

    def extent(s):
        return j.WEB_WIDTH / 2 + j.profile_gap(s)

    outer = (
        loft(
            station,
            lambda s: ((-(extent(s) + 0.80), -j.CHEEK), (extent(s) + 0.80, j.CHEEK)),
        )
        ^ slab
    )
    inner = loft(
        station,
        lambda s: (
            (-extent(s), -1.50 - j.profile_gap(s)),
            (extent(s), 1.50 + j.profile_gap(s)),
        ),
    )
    # An inboard gate travels tangentially. Its cheek-side tab is positively trapped under the metal cap flange.
    block = outer - inner
    gate_cut = loft(station, lambda s: ((extent(s) - 0.04, -7), (16, 1.62)))
    gate_piece = loft(station, lambda s: ((extent(s) + 0.012, -6), (16, 1.56)))
    gate_wall = block ^ gate_piece
    sideplate = box(
        (j.R_PIVOT - 3.8, j.CHEEK - 0.005, -h), (j.R_PIVOT + 1.25, j.GATE_TOP, h)
    )
    # Follow the socket side rather than extending into adjacent webs.
    sheet = outer.translate((0, 0.40, 0)) ^ sideplate
    key = (gate_wall + sheet) - yz(cyl(0.755, -6, 6))
    # A single off-axis root leaves an unobstructed radial mouth during insertion.
    beam = box((11.32, j.FORK_Y - 1.00, -h), (j.R_PIVOT + 2.6, j.FORK_Y + 0.95, h))
    fork = (
        (block + beam) - inner - gate_cut - yz(cyl(0.75, -6, 6)) - sideplate
    ) + tongue(j.FORK_Y)
    if radial_limit is not None:
        fork = fork.trim_by_plane((-1, 0, 0), -radial_limit)
    return fork, key


def component_records():
    upper, lower = hub_sectors()
    yield "hub_upper_sector", upper, "aluminium"
    yield "hub_lower_sector", lower, "aluminium"
    yield "lap_screw", lap_screw(), "steel"
    yield "rope_arm", arm(), "PA12"
    yield "hub_screw", lock_screw(), "steel"
    pin, cap = metal_parts()
    yield "shoulder_pin", pin, "steel"
    yield "threaded_cap", cap, "steel"
    for z in j.STATIONS:
        fork, key = saddle(z)
        yield f"fork_{z:+d}", fork, "PA12"
        yield f"gate_{z:+d}", key, "PA12"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    data = {}
    for name, obj, material in component_records():
        data[name] = export(obj, out / (name + ".stl")) | dict(material=material)
        print(name, data[name], flush=True)
    cuts = union([place(web_cut(), a, z) for z in j.STATIONS for a in j.ANGLES])
    body = load(BODY)
    # Only the eight real mounting sites are machined.

    actual = body - cuts
    if actual.status() != md.Error.NoError or len(actual.decompose()) != 1:
        raise ValueError("Machining disconnected the M5 body")
    data["machined_body"] = export(
        actual.simplify(0.0001), out / "M5_machined_body.stl"
    ) | dict(material="PA12")
    data["body_machining"] = dict(
        original_volume_mm3=body.volume(),
        remaining_volume_mm3=actual.volume(),
        removed_mm3=body.volume() - actual.volume(),
        sites=8,
        connected=True,
    )
    (out / "parts.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
