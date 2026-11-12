import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import unittest
import numpy as np
from payload_planar import PayloadPlanarRod
from rope_planar import PlanarRod
from spatial_rod import SpatialRod

class PayloadChecks(unittest.TestCase):
    def test_point_load_energy_and_exact_derivatives(self):
        a=PlanarRod((8,12,4,1),3);b=PayloadPlanarRod((8,12,4,1),3)
        x=np.zeros(a.ndof);x[::2]=np.linspace(0,-1.1,a.m);x[1::2]=.02
        Ea,ga,Ha,da=a.evaluate(x,detail=True);Eb,gb,Hb,db=b.evaluate(x,detail=True)
        self.assertAlmostEqual(Eb-Ea,.5*9.81*da['points'][-1,1],places=12)
        np.testing.assert_allclose(gb-ga,.5*9.81*da['head_jac'][1],atol=1e-11)
        rng=np.random.default_rng(5);v=rng.normal(size=a.ndof);v[1::2]*=.01;h=1e-6
        hv=Hb[0]*v
        for k in range(1,b.bandwidth+1):hv[k:]+=Hb[k,:-k]*v[:-k];hv[:-k]+=Hb[k,:-k]*v[k:]
        np.testing.assert_allclose((b.evaluate(x+h*v)[1]-b.evaluate(x-h*v)[1])/(2*h),hv,rtol=1e-6,atol=5e-6)

    def test_backbone_is_absent_from_every_front_cell(self):
        for f in range(5,9):
            for d in range(1,f):
                r=PayloadPlanarRod((8,12,d,f-d),4,rope_mass=False)
                np.testing.assert_allclose(r.EI[r.b:r.b+d*4],.0035)
                np.testing.assert_allclose(r.EI[r.b+d*4:],.0024)
                np.testing.assert_allclose(r.EA[-4:],43.75)
                expected=(8*5.1+12*3.9+d*4+(f-d)*3.6)/1000+.960*7900*r.area
                self.assertAlmostEqual(r.mass.sum(),expected)
                s=SpatialRod((8,12,d,f-d),2)
                np.testing.assert_allclose(s.vertical[s.b:s.b+d*2],.0035)
                np.testing.assert_allclose(s.sidepos[s.b:s.b+d*2],.0037)
                np.testing.assert_allclose(s.sideneg[s.b:s.b+d*2],.0030)
                np.testing.assert_allclose(s.vertical[-2:],.0024)

    def test_spatial_gradient_all_ropes_gravity_and_twist(self):
        r=SpatialRod((2,3,3,2),2);rng=np.random.default_rng(17)
        z=rng.normal(size=r.ndof)*.03;v=rng.normal(size=r.ndof);v/=np.linalg.norm(v)
        T=np.array([2.4,.7,.2,1.1]);h=2e-6
        E,g,d=r.evaluate(z,T,detail=True)
        self.assertLess(abs((r.evaluate(z+h*v,T)[0]-r.evaluate(z-h*v,T)[0])/(2*h)-g@v),1e-7)
        self.assertEqual(d['guide_points'].shape,(r.n+1,4,3))
        lp=r.evaluate(z+h*v,T,detail=True)[2]['rope_lengths'];lm=r.evaluate(z-h*v,T,detail=True)[2]['rope_lengths']
        np.testing.assert_allclose((lp-lm)/(2*h),d['rope_jac']@v,atol=1e-8)

    def test_spatial_planar_limit_including_loaded_root_stress(self):
        p=PayloadPlanarRod((8,12,4,1),4);r=SpatialRod(p.counts,4)
        x=p.free_equilibrium();self.assertIsNotNone(x);z=r.lift_planar(x)
        E,g,d=r.evaluate(z,[0,0,0,0],detail=True);pe,pg,ph,pd=p.evaluate(x,detail=True)
        self.assertAlmostEqual(E,pe,places=10)
        np.testing.assert_allclose(d['points'][:,:2],pd['points'],atol=1e-12)
        m,_=r.metrics(z,[0,0,0,0]);pm,_,_=p.shape_metrics(x,0.)
        self.assertAlmostEqual(m['max_core_stress_mpa'],pm['max_core_stress_mpa'],places=7)

    def test_original_module_torsion_spring_is_preserved_on_refinement(self):
        for sub in [1,2,4]:
            r=SpatialRod((1,1,1,1),sub,payload_kg=0.)
            q=np.zeros((r.m,4));q[-sub:,0]=.2/sub
            E,_=r.evaluate(q.ravel()*r.scale,gravity=0.)
            self.assertAlmostEqual(E,.5*.059*.2**2,places=12)

    def test_fixed_winch_energy_gradient_with_load(self):
        r=SpatialRod((2,3,3,2),2);rng=np.random.default_rng(21)
        z=rng.normal(size=r.ndof)*.025;_,g,d=r.evaluate(z,detail=True)
        prescribed=np.array([3.,.8,0.,1.2]);rest=d['rope_lengths']/(1+prescribed/r.planar.rope_ea)+np.where(prescribed>0,0.,.001)
        def locked(zz):
            E,gg,dd=r.evaluate(zz,detail=True);extension=np.maximum(dd['rope_lengths']-rest,0.);T=r.planar.rope_ea/rest*extension
            return E+.5*np.sum(T*extension),gg+T@dd['rope_jac']
        v=rng.normal(size=r.ndof);v/=np.linalg.norm(v);h=1e-6
        self.assertLess(abs((locked(z+h*v)[0]-locked(z-h*v)[0])/(2*h)-locked(z)[1]@v),2e-6)

if __name__=='__main__':unittest.main()
