"""Geometric, virtual-work and regression checks for constrained end routing."""
import json
from pathlib import Path
import unittest
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth, sample_span, mass_with_bellmouth, inspect_routing, angle_difference_deg
from end_bellmouth_kernel import span_geometry, span_end_loads
from spatial_model import rotation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGN = json.loads((ROOT/'cad/lanes_u4m2/end_bellmouth_v1/design.json').read_text())
MASS = json.loads((ROOT/'cad/lanes_u4m2/guides_v3/mass_model.json').read_text())


def model(sub=8):
    lanes.install((21,24,28),24,MASS)
    return apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,sub),DESIGN)


class BellmouthTests(unittest.TestCase):
    def test_heading_comparison_is_periodic(self):
        self.assertAlmostEqual(angle_difference_deg(-194.7,165.),.3)
        self.assertAlmostEqual(angle_difference_deg(194.7,-165.),-.3)
        self.assertAlmostEqual(angle_difference_deg(179.,-179.),-2.)

    def test_straight_preserves_original_lengths_energy_gradient(self):
        r=model(); z=np.zeros(r.ndof); T=np.arange(12.).reshape(3,4)+1.
        a=r.evaluate(z,T,detail=True)
        del r.bellmouth_profiles
        b=r.evaluate(z,T,detail=True)
        self.assertAlmostEqual(a[0],b[0],places=12)
        np.testing.assert_allclose(a[1],b[1],atol=1e-11)
        np.testing.assert_allclose(a[2]['rope_lengths'],b[2]['rope_lengths'],atol=1e-14)

    def test_contact_curve_reaches_guide_and_is_tangent(self):
        r=model()
        for ei,sgn in [(0,1.),(1,-1.)]:
            pr=r.bellmouth_profiles[0,ei]
            d=np.array([sgn*.020,.008,.003])
            length,grad,ti,to,contact=span_geometry(d,sgn,pr)
            self.assertTrue(contact)
            p=sample_span(d,sgn,pr,max_step=1e-6)
            np.testing.assert_allclose(p[[0,-1]],np.array([np.zeros(3),d]),atol=1e-14)
            self.assertLess(abs(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()-length),2e-9)
            axis=np.array([sgn,0.,0.]); n=np.r_[0.,d[1:]/np.linalg.norm(d[1:])]
            centre=(pr[0]-pr[1]*np.sin(pr[2]))*axis+(pr[1]+pr[3])*n
            rc=pr[1]+pr[4]
            pin=centre+rc*(np.sin(ti)*axis-np.cos(ti)*n)
            pout=centre+rc*(np.sin(to)*axis-np.cos(to)*n)
            self.assertLess(abs(np.dot(pin,pin-centre)),1e-14)
            self.assertLess(abs(np.dot(d-pout,pout-centre)),1e-14)
            np.testing.assert_allclose((d-pout)/np.linalg.norm(d-pout),grad,atol=1e-12)

    def test_endpoint_derivative_and_rigid_frame_virtual_work(self):
        pr=model().bellmouth_profiles[0,1]
        F=rotation(np.array([.2,-.1,.3]))[0]; p=np.array([.1,.04,-.02]); off=np.array([0.,.024,0.])
        g=p+F@(off+np.array([-.020,.008,.003]))
        length,dg,df=span_end_loads(p,F,g,off,-1.,pr)
        h=1e-7
        for k in range(3):
            e=np.eye(3)[k]*h
            fd=(span_end_loads(p,F,g+e,off,-1.,pr)[0]-span_end_loads(p,F,g-e,off,-1.,pr)[0])/(2*h)
            self.assertLess(abs(fd-dg[k]),1e-7)
            Fp=rotation(e)[0]@F; Fm=rotation(-e)[0]@F
            fd=(span_end_loads(p,Fp,g,off,-1.,pr)[0]-span_end_loads(p,Fm,g,off,-1.,pr)[0])/(2*h)
            self.assertLess(abs(fd-np.sum(df*(Fp-Fm)/(2*h))),1e-8)

    def test_contact_transition_is_continuous_with_continuous_gradient(self):
        pr=model().bellmouth_profiles[0,1]
        s0=pr[0]-pr[1]*np.sin(pr[2]); rc=pr[1]+pr[4]; cy=pr[1]+pr[3]
        ti=np.arccos(rc/np.hypot(s0,cy))-np.arctan2(s0,cy)
        values=[]
        for eps in [-1e-8,1e-8]:
            d=np.array([-.02,.02*np.tan(ti+eps),0.])
            values.append(span_geometry(d,-1.,pr))
        self.assertFalse(values[0][-1]); self.assertTrue(values[1][-1])
        self.assertLess(abs(values[0][0]-values[1][0]),1e-9)
        np.testing.assert_allclose(values[0][1],values[1][1],atol=3e-8)

    def test_saved_state_energy_and_rope_length_derivatives(self):
        r=model(); rng=np.random.default_rng(1611)
        archive=HERE/'guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz'
        data=np.load(archive,allow_pickle=False)
        for i in [0,64,146,216]:
            z=data['z'][i]; T=data['tensions_n'][i].reshape(3,4)
            E,g=r.evaluate(z,T)
            for _ in range(3):
                v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
                fd=(r.evaluate(z+h*v,T)[0]-r.evaluate(z-h*v,T)[0])/(2*h)
                self.assertLess(abs(fd-g@v),2e-7)
            J=r.control_jacobian(z)
            dplus=r.evaluate(z+h*v,detail=True)[2]['rope_lengths']
            dminus=r.evaluate(z-h*v,detail=True)[2]['rope_lengths']
            np.testing.assert_allclose((dplus-dminus).ravel()/(2*h),J@v,atol=3e-8)

    def test_actual_stations_required_and_refinement_supported(self):
        r=model(16)
        self.assertEqual(r.bellmouth_profiles.shape,(2,2,5))
        lanes.install((21,24,28),24,MASS)
        with self.assertRaises(ValueError):apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,4),DESIGN)

    def test_mass_delta_uses_cad_removed_volume(self):
        chk=json.loads((ROOT/'cad/lanes_u4m2/end_bellmouth_v1/geometry_check.json').read_text())
        new=mass_with_bellmouth(MASS,chk)
        expected=-sum(p['removed_volume_mm3'] for p in chk['parts'].values())*MASS['densities_kg_per_mm3']['PA12']
        self.assertAlmostEqual(sum(new['module_mass_kg'])-sum(MASS['module_mass_kg']),expected,places=14)
        self.assertEqual(new['module_mass_kg'][:4],MASS['module_mass_kg'][:4])

    def test_fixed_winch_energy_and_tangent_match_finite_differences(self):
        from length_cycle import LengthDrive
        r=model();drive=LengthDrive(r)
        data=np.load(HERE/'guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz',allow_pickle=False)
        z=data['z'][146];T=data['tensions_n'][146].reshape(3,4)
        rest=drive.inverse(z,T);h=1e-6
        v=np.random.default_rng(28).normal(size=r.ndof);v/=np.linalg.norm(v)
        E,g=drive.energy(z,rest)
        fd=(drive.energy(z+h*v,rest)[0]-drive.energy(z-h*v,rest)[0])/(2*h)
        self.assertLess(abs(fd-g@v),2e-7)
        J=r.control_jacobian(z)
        H=r.hessian(z,T)+J.T@((drive.ea/rest.ravel())[:,None]*J)
        fdg=(drive.energy(z+h*v,rest)[1]-drive.energy(z-h*v,rest)[1])/(2*h)
        np.testing.assert_allclose(H@v,fdg,atol=2e-5,rtol=2e-6)

    def test_exit_and_guide_loads_balance_force_and_moment(self):
        r=model()
        data=np.load(HERE/'guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz',allow_pickle=False)
        z=data['z'][146];T=data['tensions_n'][146].reshape(3,4)
        exits,guides=inspect_routing(r,z,T)
        points=r.evaluate(z,T,detail=True)[2]['points']
        for j in (4,5):
            force=np.zeros(3);moment=np.zeros(3)
            for rec in exits:
                if rec['module']!=f'M{j+1}':continue
                node=j*r.sub if rec['end']=='proximal' else (j+1)*r.sub
                f=np.array(rec['end_resultant_base_n']);force+=f
                moment+=np.cross(points[node]*1000.,f)+rec['end_moment_base_nmm']
            for rec in guides:
                if rec['module']!=f'M{j+1}':continue
                node=j*r.sub+int(round((rec['station_z_mm']+48.)/(r.l*1000.)))
                f=np.array(rec['force_base_n']);force+=f
                moment+=np.cross(points[node]*1000.,f)+rec['moment_base_nmm']
            np.testing.assert_allclose(force,0.,atol=1e-12)
            np.testing.assert_allclose(moment,0.,atol=1e-10)


if __name__=='__main__':unittest.main()
