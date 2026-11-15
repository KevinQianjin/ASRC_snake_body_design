"""Double-precision Manifold transfer for deformed-CAD contact measurements.

The trimesh Manifold adapter in the recorded environment converts vertices to
float32. Keep the beam-mapped vertices in float64, and reject kernel errors
instead of interpreting an invalid/empty solid as a contact-free result.
"""
import numpy as np
import trimesh
from manifold3d import Manifold, Mesh64, Error


def to_manifold(mesh):
    if not mesh.is_volume:
        raise ValueError('Boolean input must be a closed oriented positive-volume mesh')
    result=Manifold(Mesh64(vert_properties=np.ascontiguousarray(mesh.vertices,dtype=np.float64),
                           tri_verts=np.ascontiguousarray(mesh.faces,dtype=np.uint64)))
    if result.status()!=Error.NoError:
        raise ValueError(f'Manifold input error: {result.status()}')
    return result


def to_trimesh(solid):
    if solid.status()!=Error.NoError:
        raise ValueError(f'Manifold operation error: {solid.status()}')
    mesh=solid.to_mesh64()
    return trimesh.Trimesh(vertices=mesh.vert_properties,faces=mesh.tri_verts,process=False)


def intersection64(first,second):
    return to_trimesh(to_manifold(first)^to_manifold(second))
