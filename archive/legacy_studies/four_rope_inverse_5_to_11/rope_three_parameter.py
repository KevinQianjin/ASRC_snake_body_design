"""Full symmetric planar tension allocation, including opposing-pair preload.

Real disk chords do not, in general, satisfy Lt+Lb=2*Lside when curvature
varies inside a module. Therefore the symmetric planar control has THREE
parameters: signed top/bottom difference D, antagonistic top/bottom sum A,
and symmetric side sum S. No equivalence of those two common modes is assumed.
"""
import numpy as np
from rope_planar import PlanarRod

class ThreeParameterRod(PlanarRod):
    def __init__(self,counts,sub=8,*,antagonistic_common=0.,**kwargs):
        super().__init__(counts,sub,**kwargs)
        self.antagonistic_common=float(antagonistic_common)
        if self.antagonistic_common<0:raise ValueError('nonnegative antagonistic common tension required')

    def tensions(self,D,common=0):
        a=self.antagonistic_common
        return np.array([max(D,0)+a/2,common/2,max(-D,0)+a/2,common/2])
