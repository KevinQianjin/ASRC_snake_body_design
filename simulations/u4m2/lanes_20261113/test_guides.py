import json
import csv
import gzip
from pathlib import Path
import tempfile
import unittest
import numpy as np
from state_archives import load_states, NAMES
from guide_path_audit import guide_loads, map_cad, FlexureDistance
from rope_guide_study import _guide_spans
import lanes
from guide_load_design import screen


class ArchiveTests(unittest.TestCase):
    def test_all_published_formats_and_force_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            np.savez(p/'inverse.npz', k0_z8=np.zeros(192), k0_T8=np.ones((3,4))*3)
            self.assertEqual(load_states(p/'inverse.npz')[1]['states'], 1)
            for key in ('z', 'closed'):
                f=p/f'{key}_states.npz'; np.savez(f, **{key:np.zeros((2,192))})
                rows = [{n+'_tension_n':float(i+3) for n in NAMES} for i in range(2)] if key == 'z' else [{'tensions_n':[i+3.]*12} for i in range(2)]
                (p/f'{key}.json').write_text(json.dumps(rows))
                states, report = load_states(f)
                self.assertEqual(report['states'],2)
                self.assertEqual(states[1][2][0,0],4.)
                rows.insert(1,dict(status='solve_failed'))
                (p/f'{key}.json').write_text(json.dumps(rows))
                self.assertEqual(load_states(f)[1]['unsolved_records_without_states'],1)
            np.savez(p/'motion_trace_states.npz',z=np.zeros((3,192)),tensions_n=np.ones((3,12)))
            self.assertEqual(load_states(p/'motion_trace_states.npz')[1]['states'],3)

    def test_unsupported_empty_and_misaligned_archives_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad_states.npz'
            for payload in ({'other':np.zeros(192)}, {'z':np.zeros((0,192)),'tensions_n':np.zeros((0,12))}, {'z':np.zeros((2,192)),'tensions_n':np.ones((1,12))}):
                np.savez(p,**payload)
                with self.assertRaises(ValueError): load_states(p)


class GeometryTests(unittest.TestCase):
    def test_rope_center_inside_solid_is_not_positive_clearance(self):
        import trimesh
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cube.stl'
            central=trimesh.creation.box([4,4,4])
            end=trimesh.creation.box([4,4,4]);end.apply_translation([0,0,45])
            trimesh.util.concatenate([central,end]).export(path)
            query=FlexureDistance(path);query.update(query.mesh.vertices/1000)
            distances=query.distances(np.array([[0.,0,0],[.004,0,0],[0,0,.045]]))
            self.assertLess(distances[0],0)
            self.assertAlmostEqual(distances[1],2.)
            self.assertGreater(distances[2],0)
            self.assertEqual(query.last_inside_end_points,1)
            self.assertAlmostEqual(query.last_max_end_penetration_mm,2.)

    def test_interleaved_hole_loads_are_combined_per_station(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'summary.json').write_text(json.dumps(dict(radii_mm=[21,24,28],maximum_hole_force_n=4,
                maximum_station_force_n=7,maximum_station_moment_nmm=0)))
            rows=[dict(archive='a',state='0',module='M5',station_z_mm=str(station),set=rope,ray='up',
                fx_n=0,fy_n=force,fz_n=0,force_n=force) for station,rope,force in [(-24,'B',3),(24,'B',1),(-24,'C',4)]]
            with gzip.open(p/'hole_loads.csv.gz','wt') as f:
                writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
            result=screen(p,p/'loads.json')
            self.assertEqual(result['scaled_design_requirements']['station_sum_absolute_hole_forces_n'],21)
            self.assertAlmostEqual(result['scaled_design_requirements']['nominal_arm_normal_stress_mpa'],21/(4*3.2))

    def test_cad_mass_updates_all_cells_without_changing_stiffness(self):
        masses=np.array([.04,.041,.042,.043,.044,.045])
        nominal=lanes._original_spatial_rod(4,2,[4,5,6],20,8)
        try:
            factory=lanes.install((21,24,28),24,{'module_mass_kg':masses.tolist()})
            r=factory(4,2,[4,5,6],20,8)
            np.testing.assert_allclose(r.mass.reshape(6,8).sum(axis=1),masses+r.planar.rope_module_mass)
            np.testing.assert_array_equal(r.scale,nominal.scale)
            bad=lanes.install((21,24,28),24,{'module_mass_kg':[float('nan')]*6})
            with self.assertRaises(ValueError):bad(4,2,[4,5,6],20,8)
        finally:lanes.install()

    def test_station_positions_survive_mesh_refinement(self):
        for sub in (8,16,24):
            spans=_guide_spans(4*sub,5*sub,sub//4)
            positions=[(b-4*sub)*96/sub-48 for a,b in spans[:-1]]
            self.assertEqual(positions,[-24,-12,12,24])

    def test_force_balance_and_rotation_covariance(self):
        P=np.array([[0.,0,0],[1,0,0],[1,1,0],[2,1,0]])
        f=guide_loads(P,10.)
        np.testing.assert_allclose(f.sum(axis=0),[0,0,0])
        self.assertAlmostEqual(np.linalg.norm(f[0]),np.sqrt(200))
        R=lanes.rotation(np.array([.3,.5,-.2]))[0]
        np.testing.assert_allclose(guide_loads(P@R.T,10),f@R.T)

    def test_cad_mapping_matches_rod_nodes(self):
        r=lanes.apply_lanes(lanes._original_spatial_rod(4,2,[4,5,6],20,8),(21,24,27),24)
        z=np.random.default_rng(42).normal(size=r.ndof)*.01
        d=r.evaluate(z,detail=True)[2]
        V=np.c_[np.zeros(9),np.zeros(9),np.linspace(-48,48,9)]
        np.testing.assert_allclose(map_cad(V,4,r,d),d['points'][32:41],atol=1e-10)
        straight=r.evaluate(np.zeros(r.ndof),detail=True)[2]
        np.testing.assert_allclose(map_cad(np.array([[27.,0,0]]),4,r,straight),[[.432,0,-.027]],atol=1e-12)

    def test_actual_eight_and_sixteen_cell_guided_gradients(self):
        rng=np.random.default_rng(4)
        for sub in (8,16):
            r=lanes.apply_lanes(lanes._original_spatial_rod(4,2,[4,5,6],20,sub),(21,24,27),24)
            z=rng.normal(size=r.ndof)*.01; T=rng.uniform(3,20,(3,4))
            v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
            g=r.evaluate(z,T)[1]
            fd=(r.evaluate(z+h*v,T)[0]-r.evaluate(z-h*v,T)[0])/(2*h)
            self.assertAlmostEqual(fd,float(g@v),delta=1e-6)


if __name__=='__main__': unittest.main()
