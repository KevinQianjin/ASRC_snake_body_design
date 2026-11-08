"""Central NiTi backbone added to each M module: shared properties and rod classes.

The rod is assumed central, bonded to the M module end disks, laterally guided
and bending with the module, so its EA, EI and torsion add in parallel to the
supplied M properties. Its mass is added to each M module. Module-end fittings,
guides and adhesive are not included. Values are calculated, not measured.
"""
import sys, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(STUDY / 'm_axial_sweep_20261108'))
sys.path.insert(0, str(STUDY / 'steering_63mm_20261106'))
sys.path.insert(0, str(STUDY / 'stiffness_63mm_20261106'))
sys.path.insert(0, str(STUDY))

MODULE_LENGTH = .096
DENSITY = 6450.  # kg/m^3, NiTi
POISSON = .33

def rod_properties(d_mm=1.8, E=40e9):
    d = d_mm / 1000
    A = math.pi * d * d / 4
    I = math.pi * d ** 4 / 64
    G = E / (2 * (1 + POISSON))
    return dict(diameter_mm=d_mm, E_pa=E, EA_n=E * A, EI_nm2=E * I,
                torsion_module_nm_per_rad=G * 2 * I / MODULE_LENGTH,
                mass_per_module_kg=DENSITY * A * MODULE_LENGTH)

# Lower-bound (martensite-like) and upper (austenite-like) moduli.
VARIANTS = {'none': None, 'niti18_E40': rod_properties(1.8, 40e9), 'niti18_E75': rod_properties(1.8, 75e9)}


def planar_rod(u, m, anchors, pitch=20, sub=4, variant='niti18_E40', common=0):
    """Planar DatabaseRod with the backbone added to M modules."""
    from run_sweep import ScaledRod
    r = ScaledRod(u, m, anchors, pitch, sub, common)
    rod = VARIANTS[variant]
    r.variant = variant
    if rod is None:
        return r
    r.module_EA[u:] += rod['EA_n']
    r.module_EI[u:] += rod['EI_nm2']
    r.EA = np.repeat(r.module_EA, sub)
    r.EI = np.repeat(r.module_EI, sub)
    r.bare_mass = r.bare_mass.copy()
    r.bare_mass[u:] += rod['mass_per_module_kg']
    r.mass = np.repeat((r.bare_mass + r.rope_module_mass) / sub, sub)
    r.weight_after = np.cumsum(r.mass[::-1])[::-1] - r.mass + r.payload_kg
    return r


def spatial_rod(u, m, anchors, pitch=20, sub=2, variant='niti18_E40'):
    """SpatialDatabaseRod with the backbone added to M modules (EA, both EI, torsion, mass)."""
    from spatial_model import SpatialDatabaseRod
    r = SpatialDatabaseRod(u, m, anchors, pitch, sub)
    rod = VARIANTS[variant]
    r.variant = variant
    if rod is None:
        return r
    p = planar_rod(u, m, anchors, pitch, sub, variant)
    r.planar = p
    r.mass = p.mass
    Mcells = slice(u * sub, None)
    K = r.K.copy()
    K[Mcells, 0] += rod['torsion_module_nm_per_rad'] * MODULE_LENGTH / r.l
    K[Mcells, 1] += rod['EI_nm2'] / r.l
    K[Mcells, 2] += rod['EI_nm2'] / r.l
    K[Mcells, 3] += rod['EA_n'] * r.l
    r.K = K
    r.scale = np.sqrt(K).ravel()
    return r


if __name__ == '__main__':
    for k, v in VARIANTS.items():
        print(k, v)
