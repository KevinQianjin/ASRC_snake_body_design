import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import unittest,sys
from pathlib import Path
import numpy as np
from rope_planar import PlanarRod,HERE
sys.path.insert(0,str(HERE/'inputs'))
import snake_model_rear_backbone as R

class MechanicsChecks(unittest.TestCase):
    def test_energy_gradient_hessian_and_head_jacobian_at_bent_shape(self):
        r=PlanarRod((2,3,3,2),3)
        rng=np.random.default_rng(17)
        x=np.zeros(r.ndof);x[::2]=np.linspace(0,-1.5,r.m)+.02*rng.normal(size=r.m)
        x[1::2]=-.01+.001*rng.normal(size=r.m)
        v=rng.normal(size=r.ndof);v[1::2]*=.05
        T=[1.8,.2,.1,.2];h=2e-6
        E,g,H,d=r.evaluate(x,T,detail=True)
        ep,gp,_,dp=r.evaluate(x+h*v,T,detail=True)
        em,gm,_,dm=r.evaluate(x-h*v,T,detail=True)
        hv=H[0]*v
        for k in range(1,r.bandwidth+1):
            hv[k:]+=H[k,:-k]*v[:-k];hv[:-k]+=H[k,:-k]*v[k:]
        self.assertLess(abs((ep-em)/(2*h)-g@v),2e-7)
        self.assertLess(np.max(abs((gp-gm)/(2*h)-hv)),2e-6)
        np.testing.assert_allclose((dp['points'][-1]-dm['points'][-1])/(2*h),d['head_jac']@v,atol=1e-8)

    def test_guide_count_and_rope_virtual_work(self):
        for sub in [2,4,8]:
            r=PlanarRod((2,3,3,2),sub)
            x=np.zeros(r.ndof);x[::2]=np.linspace(0,1.,r.m)
            _,g0,_,d=r.evaluate(x,gravity=0,detail=True)
            _,g1,_,_=r.evaluate(x,[1,0,0,0],gravity=0,detail=True)
            self.assertEqual(len(d['guide_points']),r.n+1)
            np.testing.assert_allclose(g1-g0,d['rope_jac'][0],atol=1e-12)
            v=np.ones(r.ndof);v[1::2]=0;h=1e-6
            lp=r.evaluate(x+h*v,gravity=0,detail=True)[3]['rope_lengths']
            lm=r.evaluate(x-h*v,gravity=0,detail=True)[3]['rope_lengths']
            np.testing.assert_allclose((lp-lm)/(2*h),d['rope_jac']@v,atol=1e-8)

    def test_zero_rope_limit_against_original_fine_solver(self):
        counts=(8,12,4,1);r=PlanarRod(counts,8,rope_mass=False,extensible=False)
        x=r.free_equilibrium();self.assertIsNotNone(x)
        new=r.evaluate(x,detail=True)[3]['points'][-1]*1000
        cfg,mat,_=R.read_inputs(HERE/'inputs/rear_backbone_config.json',HERE/'inputs/rope_materials.json')
        cfg['front']['modules']=5
        old=R.case_rows(R.solve_counts(counts,cfg,mat,cells=32),cfg)[0]
        self.assertLess(abs(new[0]-old['tip_x_mm']),.05)
        self.assertLess(abs(new[1]+old['tip_drop_mm']),.05)

    def test_length_control_recovers_the_prescribed_tensions(self):
        r=PlanarRod((8,12,4,1),4)
        sol=r.load_inverse('level');self.assertIsNotNone(sol)
        x,D0,_=sol;T=r.tensions(D0)
        _,g,H,d=r.evaluate(x,T,detail=True)
        rest=d['rope_lengths']/(1+T/r.rope_ea)+np.where(T>1e-7,0.,.001)
        recovered=r.rope_ea/rest*np.maximum(d['rope_lengths']-rest,0)
        np.testing.assert_allclose(recovered,T,rtol=0,atol=1e-10)
        self.assertGreater(r.stability(H,d,T),0.)

    def test_rear_only_core_mass_and_original_properties(self):
        r=PlanarRod((8,12,4,1),4,rope_mass=False)
        self.assertAlmostEqual(r.mass.sum(),(8*5.1+12*3.9+4*4.+1*3.6)/1000+
            .960*7900*np.pi*.0042**2/4)
        np.testing.assert_allclose(r.EI[r.b:][:16],.0035)
        np.testing.assert_allclose(r.EI[-4:],.0024)
        np.testing.assert_allclose(r.EA[-4:],43.75)

if __name__=='__main__':unittest.main()
