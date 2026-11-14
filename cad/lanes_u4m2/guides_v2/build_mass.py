"""Reproduce the CAD-volume mass estimate used in the guided V2 simulation."""
import json
from pathlib import Path
from math import pi
HERE=Path(__file__).resolve().parent

def build():
    lane=json.loads((HERE/'lane_design.json').read_text())
    geom=json.loads((HERE/'geometry_check.json').read_text())
    spring=json.loads((HERE/'spring_strip.json').read_text())
    density=dict(PA12=.93e-6,NiTi=6.45e-6,steel=7.9e-6)
    rows=[]
    for i,name in enumerate(['U_lane_pass']*3+['U4_lane_anchorA','M5_lane_anchorB','M6_lane_anchorC']):
        module=('U' if i<4 else 'M')+str(i+1)
        guide=[v for k,v in geom['parts'].items() if k.startswith(module+'_')]
        rows.append(dict(module=module,body_kg=lane['modules'][name]['volume_mm3']*density['PA12'],
            elastic_insert_kg=(spring['count_per_U']*spring['volume_mm3'] if i<4 else pi*.9**2*96)*density['NiTi'],
            guide_and_caps_kg=sum(v['frame_volume_mm3']+v['cap_volume_mm3'] for v in guide)*density['PA12'],
            wire_envelope_kg=sum(v['wire_envelope_volume_mm3'] for v in guide)*density['steel'],joint_allocation_kg=.0013))
    result=dict(scope='CAD volume estimates, not measured mass. Each module total is distributed uniformly over rod cells. Nominal homogenised module stiffness retained. Adhesive/closure tails excluded; wire square envelope is conservative. 500 g head includes its adapter. Base mass is supported at the clamp.',
        densities_kg_per_mm3=density,components=rows,module_mass_kg=[sum(v for k,v in r.items() if k.endswith('_kg')) for r in rows])
    (HERE/'mass_model.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':print(json.dumps(build(),indent=2))
