import unittest
import numpy as np
import trimesh
from cad_surface_refinement import refine_axial, axial_span


class SurfaceRefinementTests(unittest.TestCase):
    def test_closed_surface_volume_winding_and_original_vertices_are_preserved(self):
        original = trimesh.creation.box([3, 5, 24])
        original.apply_transform(trimesh.transformations.rotation_matrix(.37, [0, 1, 0]))
        refined = refine_axial(original, .75)
        self.assertTrue(refined.is_watertight)
        self.assertTrue(refined.is_winding_consistent)
        self.assertEqual(refined.euler_number, original.euler_number)
        self.assertAlmostEqual(refined.volume, original.volume, places=9)
        self.assertAlmostEqual(refined.area, original.area, places=9)
        np.testing.assert_array_equal(refined.vertices[:len(original.vertices)], original.vertices)
        self.assertLessEqual(axial_span(refined), .75 * (1 + 1e-12))

    def test_curved_surface_chord_error_decreases_with_refinement(self):
        # Analytical constant-curvature bending, independent of the rod solver.
        original = trimesh.creation.box([2, 3, 24])
        def bend(v):
            angle = v[:, 2] / 100
            return np.c_[(100 + v[:, 0]) * np.cos(angle) - 100,
                         v[:, 1], (100 + v[:, 0]) * np.sin(angle)]
        def error(mesh):
            corners = mesh.vertices[mesh.faces]
            actual = bend(corners.mean(axis=1))
            chords = bend(mesh.vertices)[mesh.faces].mean(axis=1)
            return np.linalg.norm(actual - chords, axis=1).max()
        coarse, fine = error(original), error(refine_axial(original, .5))
        self.assertGreater(coarse, .5)
        self.assertLess(fine, .005)
        self.assertLess(fine, coarse / 100)

    def test_refines_actual_cad_without_open_edges(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[3] / 'cad/lanes_u4m2/guides_v2/M5_lane_anchorB.stl'
        original = trimesh.load_mesh(path)
        refined = refine_axial(original, 2)
        self.assertTrue(refined.is_watertight)
        self.assertTrue(refined.is_winding_consistent)
        self.assertEqual(refined.euler_number, original.euler_number)
        self.assertAlmostEqual(refined.volume, original.volume, places=7)
        self.assertLessEqual(axial_span(refined), 2 * (1 + 1e-12))

    def test_invalid_resolution_is_rejected(self):
        mesh = trimesh.creation.box()
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                refine_axial(mesh, value)

    def test_rigid_frame_invariance_of_actual_bent_intersection(self):
        from pathlib import Path
        import lanes
        from mount_refinement_study import in_station_frame
        from mesh_boolean64 import intersection64,to_manifold,to_trimesh
        from state_archives import load_states
        here=Path(__file__).resolve().parent
        cad=here.parents[2]/'cad/lanes_u4m2/guides_v2'
        archive=here/'guided_validation_20261114/candidate/inverse/minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'
        _,z,T,_=next(s for s in load_states(archive)[0] if s[0]=='y175_z8')
        lanes.install((21,24,28),24)
        rod=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
        d=rod.evaluate(z,T,detail=True)[2]
        body=refine_axial(trimesh.load_mesh(cad/'M5_lane_anchorB.stl'),1.)
        body.vertices=in_station_frame(body.vertices,4,-12,rod,d)
        assembly=trimesh.util.concatenate([trimesh.load_mesh(cad/f'M5_z-12_{s}.stl') for s in ('guide','caps','wire_envelope')])
        a=intersection64(body,assembly).volume
        node=35
        rotation=d['frames'][node]@np.array([[0,0,1],[0,1,0],[-1,0,0]])
        translation=d['points'][node]*1000
        transform=np.c_[rotation,translation]
        first=to_manifold(body).transform(transform)
        second=to_manifold(assembly).transform(transform)
        b=to_trimesh(first^second).volume
        self.assertGreater(a,5.)
        # The Boolean kernel retriangulates near-degenerate CAD intersections
        # under transforms (~0.001 mm^3 here). Require 0.1% volume agreement;
        # this is a numerical regression tolerance, not allowed physical contact.
        self.assertAlmostEqual(a,b,delta=1e-3*max(a,b))

    def test_boolean_known_volume_and_invalid_input(self):
        from mesh_boolean64 import intersection64,to_manifold
        a=trimesh.creation.box([2,2,2]);b=a.copy();b.apply_translation([1,0,0])
        self.assertAlmostEqual(intersection64(a,b).volume,4.,places=10)
        opened=trimesh.Trimesh(vertices=a.vertices,faces=a.faces[:-1],process=False)
        with self.assertRaises(ValueError):to_manifold(opened)

    def test_rejected_cad_cannot_start_mass_equilibrium_study(self):
        import json,tempfile
        from pathlib import Path
        from candidate_mass_holds import run
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            mass=p/'mass_model.json';mass.write_text(json.dumps({'module_mass_kg':[.04]*6}))
            (p/'geometry_check.json').write_text(json.dumps({'all_straight_positions_clear':False}))
            with self.assertRaisesRegex(ValueError,'Candidate geometry is rejected'):
                run(p/'must_not_be_read.npz',mass,mass,p/'output',1)


if __name__ == '__main__':
    unittest.main()
