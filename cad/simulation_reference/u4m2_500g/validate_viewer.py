"""Inspect the saved Blender geometry against the extracted solver inputs."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
p=Path(__file__).resolve().parent
b=json.loads((p/'baseline.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(p/'simulation_reference.blend'))
s=bpy.data.scenes['01 Exact nominal simulation reference']
def near(a,b,tol=1e-4):return all(abs(float(x)-float(y))<=tol for x,y in zip(a,b))
def world_dimensions(o):
    pts=[o.matrix_world@Vector(v) for v in o.bound_box]
    return tuple(max(p[k] for p in pts)-min(p[k] for p in pts) for k in range(3))
checks={}
for t in b['tendons']:
 o=s.objects[t['name']+' - coincident ideal route']
 actual=[tuple(x.co[:3]) for x in o.data.splines[0].points]
 checks[t['name']+'_coordinates']=len(actual)==len(t['guide_points_local_mm']) and all(near(x,y) for x,y in zip(actual,t['guide_points_local_mm']))
 checks[t['name']+'_diameter']=abs(o.data.bevel_depth*2-t['diameter_mm'])<1e-6
for r in b['backbones']:
 o=s.objects['M'+str(r['module'])+' NiTi rod - ideal co-deformation']
 checks['M'+str(r['module'])+'_rod_dimensions']=near(world_dimensions(o),(96,1.8,1.8))
 checks['M'+str(r['module'])+'_rod_center']=near(o.location,[(r['start_local_mm'][i]+r['end_local_mm'][i])/2 for i in range(3)])
for m in b['modules']:
 o=s.objects[m['name']+' analytical collision ENVELOPE']
 checks[m['name']+'_envelope']=near(world_dimensions(o),(96,63,63))
 for k in ['EA_N','EI_vertical_Nm2','EI_horizontal_Nm2','GJ_Nm2','bare_mass_g']:
  checks[m['name']+'_'+k]=abs(o[k]-m[k])<1e-10
checks['payload_position']=near(s.objects['500 g point load DISPLAY MARKER'].location,[596,0,0])
checks['rigid_interface_dimensions']=near(world_dimensions(s.objects['20 mm MASSLESS rigid interface ENVELOPE']),[20,63,63])
checks['millimeter_units']=abs(s.unit_settings.scale_length-.001)<1e-9
checks['no_invented_fixture_objects']=not any(any(x in o.name.lower() for x in ['ferrule','screw','bushing','support spoke']) for o in s.objects)
result=dict(checks=checks,all_pass=all(checks.values()),dimension_tolerance_mm=0.0001,scope='Saved viewer geometry and properties versus solver-exported baseline, not manufacturing performance.')
(p/'viewer_validation.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['all_pass'],[k for k,v in checks.items() if not v]
print(json.dumps({'viewer_checks':len(checks),'all_pass':result['all_pass']}))
