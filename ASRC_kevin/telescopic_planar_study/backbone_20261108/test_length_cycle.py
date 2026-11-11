"""Numerical contract checks for position-control energy and tangent stability."""
import unittest
import numpy as np
from length_cycle import LengthDrive, references

class LengthDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r,cls.z,cls.knots=references(10)
        cls.d=LengthDrive(cls.r)
        cls.R=cls.knots[10][3]

    def test_inverse_recovers_reference_tension(self):
        from length_cycle import SOURCE
        T=np.load(SOURCE)['y0_T8']
        np.testing.assert_allclose(self.d.force(self.z,self.R),T,atol=1e-9)

    def test_energy_gradient(self):
        rng=np.random.default_rng(42); v=rng.normal(size=self.r.ndof); v/=np.linalg.norm(v)
        h=1e-6
        fd=(self.d.energy(self.z+h*v,self.R)[0]-self.d.energy(self.z-h*v,self.R)[0])/(2*h)
        self.assertAlmostEqual(fd,float(self.d.energy(self.z,self.R)[1]@v),places=6)

    def test_elastic_hessian_matches_gradient_difference(self):
        T=self.d.force(self.z,self.R); J=self.r.control_jacobian(self.z)
        H=self.r.hessian(self.z,T)+J.T@((self.d.ea/self.R.ravel())[:,None]*J)
        v=np.random.default_rng(4).normal(size=self.r.ndof);v/=np.linalg.norm(v);h=1e-6
        fd=(self.d.energy(self.z+h*v,self.R)[1]-self.d.energy(self.z-h*v,self.R)[1])/(2*h)
        np.testing.assert_allclose(H@v,fd,rtol=1e-4,atol=1e-5)

    def test_forward_equilibrium_and_no_compression_in_slack_rope(self):
        x=self.d.solve(self.z,self.R)
        self.assertIsNotNone(x)
        self.assertLess(self.r.residual(self.d.energy(x,self.R)[1]),2e-6)
        np.testing.assert_array_equal(self.d.force(self.z,self.R+1),np.zeros((3,4)))

class TankQueryTests(unittest.TestCase):
    def test_fast_query_matches_existing_triangle_distance(self):
        from length_cycle import FastTank
        import trimesh
        tank=FastTank()
        points=np.random.default_rng(2).uniform([0,0,500],[1000,700,800],(50,3))
        expected=trimesh.proximity.ProximityQuery(tank.mesh).on_surface(points)[1]
        actual=tank.query.on_surface(points)[1]
        np.testing.assert_allclose(actual,expected,atol=1e-8,rtol=1e-10)

if __name__=='__main__':unittest.main()
