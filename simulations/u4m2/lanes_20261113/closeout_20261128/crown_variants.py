"""Build native circular-radius and deeper-section changes at all sixteen M6 rib arches."""

import json
import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
import trimesh

from crown_mesh import BS, HERE

ROOT = HERE.parents[3]
SOURCE = ROOT / "cad/modules/Medium_Stiffness_96.step"
OUT = HERE / "results" / "crown_cad"
ORIGINAL_RIB_ANGLE = -112.5


def transverse_frame(angle_deg):
    angle = np.radians(angle_deg)
    return np.array([np.cos(angle), np.sin(angle)]), np.array([-np.sin(angle), np.cos(angle)])


def crown_section(native):
    """Read the positive crown's 1.5 mm cylinder and three vertices from native B-Rep."""
    radial, tangent = transverse_frame(ORIGINAL_RIB_ANGLE)
    ends = []
    centers = []
    for face in native.Faces():
        if face.geomType() != "CYLINDER":
            continue
        surface = BRepAdaptor_Surface(face.wrapped).Cylinder()
        center = np.asarray(cq.Vector(surface.Location()).toTuple())
        if (abs(surface.Radius() - 1.5) > 1e-6 or abs(center[2] - 21.57057) > 0.002
                or abs(center[:2] @ radial - 8.7523) > 0.01 or abs(center[:2] @ tangent) > 0.001):
            continue
        xyz = np.asarray([v.Center().toTuple() for v in face.Vertices()])
        section = np.c_[xyz[:, :2] @ radial, xyz[:, 2]]
        ends.extend(section)
        centers.append([center[:2] @ radial, center[2]])
    assert len(centers) == 2
    endpoints = np.unique(np.round(np.asarray(ends), 8), axis=0)
    assert endpoints.shape == (3, 2)
    origin = np.mean(centers, axis=0)
    normals = (endpoints - origin) / np.linalg.norm(endpoints - origin, axis=1)[:, None]
    return origin, normals


def rib_patch(center, normals, sign, *, radius=None, extra_depth=None):
    base_radius = 1.5
    point = lambda x: cq.Vector(x[0], -1.5, sign * x[1])
    if radius is not None:
        virtual_corner = center + np.linalg.solve(normals[[0, 2]], np.full(2, base_radius))
        shifted_center = virtual_corner + (center - virtual_corner) * radius / base_radius
        front = shifted_center + radius * normals
        edge = cq.Edge.makeThreePointArc(*(point(p) for p in front))
    else:
        angles = np.unwrap(np.arctan2(normals[:, 1], normals[:, 0]))
        fraction = np.linspace(0, 1, 17)
        theta = angles[0] + (angles[-1] - angles[0]) * fraction
        depth = extra_depth * np.sin(np.pi * fraction) ** 2
        profile = center + (base_radius - depth[:, None]) * np.c_[np.cos(theta), np.sin(theta)]
        tangents = [cq.Vector(-np.sin(a), 0, sign * np.cos(a)) for a in angles[[0, 2]]]
        edge = cq.Edge.makeSpline([point(p) for p in profile], tangents=tuple(tangents))
        front = profile[[0, 8, 16]]
    back = center + 1.58 * normals
    a, _, b = [point(p) for p in front]
    c, m, d = [point(p) for p in back[::-1]]
    wire = cq.Wire.assembleEdges([edge, cq.Edge.makeLine(b, c),
        cq.Edge.makeThreePointArc(c, m, d), cq.Edge.makeLine(d, a)])
    return cq.Solid.extrudeLinear(wire, [], cq.Vector(0, 3, 0))


def triangles(shape, deflection=0.008):
    v, f = shape.tessellate(deflection, 0.18)
    mesh = trimesh.Trimesh(vertices=np.asarray([a.toTuple() for a in v]), faces=f, process=False)
    mesh.merge_vertices(digits_vertex=7)
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-8) & mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def write_lattice(native, output):
    """Crop the native solid to the same master planes as the archived FE lattice."""
    trim = cq.Solid.makeBox(90, 90, BS.Z_HI - BS.Z_LO, cq.Vector(-45, -45, BS.Z_LO))
    solid = max(native.intersect(trim).Solids(), key=lambda part: part.Volume())
    mesh = triangles(solid)
    coords = np.asarray(mesh.vertices, float).copy()
    for z in (BS.Z_LO, BS.Z_HI):
        coords[abs(coords[:, 2] - z) < 1e-4, 2] = z
    trimesh.Trimesh(vertices=coords, faces=mesh.faces, process=False).export(output)
    loaded = trimesh.load_mesh(output)
    assert loaded.is_volume and loaded.body_count == 1
    return loaded


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    native = cq.importers.importStep(str(SOURCE)).val().rotate((0, 0, 0), (0, 0, 1), -22.5)
    center, normals = crown_section(native)
    base = BS.lattice()[0]
    native_control = write_lattice(native, OUT / "native_control_lattice.stl")
    native_offset = trimesh.proximity.closest_point(native_control, base.vertices)[1]
    assert native_offset.max() < 0.012 and abs(native_control.volume - base.volume) < 2.0
    summary = {"original_radius_mm": 1.5, "center_radial_axial_mm": center.tolist(), "variants": {}}
    summary["matched_control"] = dict(surface_offset_max_mm=float(native_offset.max()),
                                      volume_delta_mm3=float(native_control.volume - base.volume))
    for name, kwargs in (("radius_2p0", {"radius": 2.0}), ("depth_0p42", {"extra_depth": 0.42})):
        try:
            patches = [
                rib_patch(center, normals, sign, **kwargs).rotate((0, 0, 0), (0, 0, 1), angle)
                for angle in BS.RIBS for sign in (-1, 1)
            ]
            assert all(p.isValid() and p.Volume() > 0 for p in patches)
            candidate = native.fuse(*patches, tol=1e-6).clean()
            assert candidate.isValid() and len(candidate.Solids()) == 1
            gain = candidate.Volume() - native.Volume()
            assert gain > 0.1
            vertices = [v.Center().toTuple() for patch in patches for v in patch.Vertices()]
            assert np.hypot(np.asarray(vertices)[:, 0], np.asarray(vertices)[:, 1]).min() > 6.5
            assert min(min(abs(b.zmin), abs(b.zmax)) for b in
                       (patch.BoundingBox() for patch in patches)) > 19.970314
            dest = OUT / (name + ".step")
            cq.exporters.export(candidate, str(dest))
            lines = dest.read_text(encoding="ascii").splitlines()
            dest.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="ascii")
            loaded = cq.importers.importStep(str(dest)).val()
            assert loaded.isValid() and len(loaded.Solids()) == 1
            lattice = write_lattice(loaded, OUT / (name + "_lattice.stl"))
            assert abs(lattice.volume - native_control.volume - gain) < 1.5
            r = np.hypot(*native_control.vertices[:, :2].T)
            z = np.abs(native_control.vertices[:, 2])
            away = (r < 6.5) | (r > 14) | (z < 19.97) | (z > 29)
            distance = trimesh.proximity.closest_point(lattice, native_control.vertices[away])[1]
            assert distance.max() < 0.012
            summary["variants"][name] = dict(
                valid=True, volume_added_mm3=gain, PA12_added_g=0.00101 * gain,
                interpolated_mesh_delta_mm3=lattice.volume - native_control.volume,
                maximum_far_vertex_change_mm=float(distance.max()),
                stage="Native rib candidate with matched B-Rep tessellation and FE cut planes",
                parameters_mm=kwargs,
            )
            print(name, summary["variants"][name], flush=True)
        except (RuntimeError, ValueError, AssertionError) as error:
            summary["variants"][name] = dict(valid=False, error=repr(error))
            print(name, repr(error), flush=True)
    (OUT / "geometry.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    build()
