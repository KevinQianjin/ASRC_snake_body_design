import unittest
import numpy as np
from closed_loop_cycle import *

class FeedbackTests(unittest.TestCase):
    def test_nominal_sensitivity_matches_forward_perturbations(self):
        rows=json.loads((REF/'nominal.json').read_text());z=np.load(REF/'nominal_states.npz')['z'][350]
        r=spatial_rod(4,2,[4,5,6],20,8);d=LengthDrive(r)
        R=np.array([rows[350][n+'_rest_mm'] for n in NAMES]).reshape(3,4)/1000
        B=gains(r,d,z,R)
        for k in [1,8,9]:
            delta=np.zeros((3,4));delta.ravel()[k]=.01/1000
            zp=d.solve(z,R+delta);zm=d.solve(z,R-delta)
            self.assertIsNotNone(zp);self.assertIsNotNone(zm)
            fd=np.r_[error(angles(r,zp),angles(r,zm)),(d.force(zp,R+delta)-d.force(zm,R-delta)).ravel()]/.02
            np.testing.assert_allclose(B[:,k],fd,rtol=.025,atol=.02)

    def test_qp_respects_increment_and_total_offset_bounds(self):
        B=np.zeros((14,12));B[0,0]=2;B[1,1]=2;B[2:]=-np.eye(12)
        off=np.zeros(12);off[0]=4.9
        dx,ok=correction(B,np.array([5.,-5.]),np.ones(12)*3,off)
        self.assertTrue(ok);self.assertLessEqual(abs(dx).max(),.250001)
        self.assertLessEqual(abs(off+dx).max(),5.000001)
        self.assertTrue(np.all(3+B[2:]@dx>=1.5-1e-8))

    def test_newton_matches_original_forward_solver(self):
        data=np.load(OUT/'nominal_gains.npz');z=np.load(REF/'nominal_states.npz')['z'][350]
        r=spatial_rod(4,2,[4,5,6],20,8);r.payload=.55
        old=LengthDrive(r);new=FeedbackDrive(r);R=data['R'][350].copy();R[2,1]+=.0001
        new.stability(z,R,new.force(z,R))
        a=old.solve(z,R);b=new.solve(z,R)
        self.assertIsNotNone(a);self.assertIsNotNone(b)
        np.testing.assert_allclose(angles(r,a),angles(r,b),atol=1e-4)
        np.testing.assert_allclose(old.force(a,R),new.force(b,R),atol=1e-3)

    def test_damping_uses_observed_error_growth(self):
        self.assertEqual(adapt_scale(None,3.,1.),1.)
        self.assertEqual(adapt_scale(1.,1.1,1.),.5)
        self.assertEqual(adapt_scale(.1,.15,1.),1.)
        self.assertEqual(adapt_scale(2.,1.,.25),.25)
        self.assertEqual(adapt_scale(1.,2.,.0625),.0625)

    def test_yaw_wrap(self):
        np.testing.assert_allclose(error([179.,20.],np.array([-179.,21.])),[-2.,-1.])

if __name__=='__main__':unittest.main()
