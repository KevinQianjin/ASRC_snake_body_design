"""Render the exported simulation geometry; retain original CAD as a separate scene."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
P=Path(__file__).resolve().parent;ROOT=P.parents[2]
b=json.loads((P/'baseline.json').read_text());pose=json.loads((P/'saved_pose.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def material(name,col,alpha=1,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,alpha);m.use_nodes=True
 n=m.node_tree.nodes;links=m.node_tree.links;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.45
 if alpha<1:
  t=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=alpha;links.new(t.outputs[0],mix.inputs[1]);links.new(p.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],n.get('Material Output').inputs['Surface'])
 return m
blue=material('U envelope - NOT solid material',(.04,.30,.65),.12)
orange=material('M envelope - NOT solid material',(.95,.32,.04),.12)
silver=material('NiTi rod display',(.40,.47,.55),1,.7)
gray=material('Rigid interface envelope',(.35,.40,.46),.12)
wire=material('Envelope boundary',(.14,.25,.38))
red=material('Mathematical 500g point',(.8,.03,.04));head=material('Provisional head collision envelope',(.8,.1,.1),.06)
rope_mats=[material('A exact coincident route',(.95,.55,.02)),material('B exact coincident route',(.02,.6,.18)),material('C exact coincident route',(.75,.02,.35))]
refmat=material('Unmodified CAD reference',(.48,.56,.64))
def new_scene(name):
 s=bpy.data.scenes.new(name);bpy.context.window.scene=s
 s.unit_settings.system='METRIC';s.unit_settings.scale_length=.001;s.unit_settings.length_unit='MILLIMETERS'
 s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=False;s.render.film_transparent=True
 s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX'
 s.world=bpy.data.worlds.new(name+' world');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.92,.95,1,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.7
 return s
def line(name,pts,r,mat):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=2
 sp=c.splines.new('POLY');sp.points.add(len(pts)-1)
 for q,v in zip(sp.points,pts):q.co=(*v,1)
 o=bpy.data.objects.new(name,c);bpy.context.scene.collection.objects.link(o);o.data.materials.append(mat);return o
def cyl(name,a,z,r,mat):
 v=Vector(z)-Vector(a);bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=v.length,location=(Vector(a)+Vector(z))/2)
 o=bpy.context.object;o.name=name;o.rotation_euler=v.to_track_quat('Z','Y').to_euler();o.data.materials.append(mat);return o
def sphere(name,p,r,mat):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=r,location=p);o=bpy.context.object;o.name=name;o.data.materials.append(mat);return o
def ring(name,center,frame=None):
 F=Matrix.Identity(3) if frame is None else Matrix(frame)
 pts=[Vector(center)+F@Vector((0,31.5*math.cos(2*math.pi*j/80),31.5*math.sin(2*math.pi*j/80))) for j in range(81)]
 return line(name,[list(x) for x in pts],.30,wire)
def stage(s,target,scale,wide=True):
 target=Vector(target);bpy.ops.object.camera_add(location=target+Vector((100,-1100,650)));cam=bpy.context.object;cam.name='Reference camera';cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.clip_end=10000;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();s.camera=cam
 for off,power,size in [((0,400,600),7500000,600),((100,-450,350),5000000,450)]:
  bpy.ops.object.light_add(type='AREA',location=target+Vector(off));o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
 s.render.resolution_x=1800 if wide else 880;s.render.resolution_y=550 if wide else 680
 bpy.context.view_layer.update();return cam
s=new_scene('01 Exact nominal simulation reference')
# All input values are taken from baseline.json; units are mm.
cyl('20 mm MASSLESS rigid interface ENVELOPE',(0,0,0),(b['interface_length_mm'],0,0),31.5,gray)
for i,m in enumerate(b['modules']):
 o=cyl(m['name']+' analytical collision ENVELOPE',(m['start_mm'],0,0),(m['end_mm'],0,0),31.5,blue if i<4 else orange)
 for k in ['EA_N','EI_vertical_Nm2','EI_horizontal_Nm2','GJ_Nm2','bare_mass_g']:o[k]=m[k]
for x in [0,20]+[m['end_mm'] for m in b['modules']]:ring('Envelope station '+str(x),(x,0,0))
for r in b['backbones']:cyl('M'+str(r['module'])+' NiTi rod - ideal co-deformation',r['start_local_mm'],r['end_local_mm'],r['diameter_mm']/2,silver)
for t in b['tendons']:
 o=line(t['name']+' - coincident ideal route',t['guide_points_local_mm'],t['diameter_mm']/2,rope_mats['ABC'.index(t['group'])]);o['radius_mm']=t['radius_mm'];o['anchor_module']=t['anchor_module'];o['EA_N']=t['EA_N'];o['free_length_m']=t['free_length_m']
 # Default render shows the longest coincident paths once to avoid coplanar artifacts.
 o.hide_render=t['group']!='C'
sphere('500 g point load DISPLAY MARKER',b['payload']['point_local_mm'],2.5,red)
sphere('63 mm provisional head ENVELOPE',b['payload']['point_local_mm'],31.5,head)
cam=stage(s,(300,0,0),700)
(P/'projection.json').write_text(json.dumps({str(i):list(world_to_camera_view(s,cam,Vector(((m['start_mm']+m['end_mm'])/2,0,0)))) for i,m in enumerate(b['modules'])}))
s.render.filepath=str(P/'nominal_reference.png')
bpy.ops.render.render(write_still=True)
nominal_scene=s
s=new_scene('02 Saved nominal equilibrium - no new simulation')
points=pose['points_local_mm'];frames=pose['frames']
cyl('Massless interface',(0,0,0),(20,0,0),31.5,gray)
for i in range(48):cyl('Cell envelope '+str(i),points[i],points[i+1],31.5,blue if i<32 else orange)
for j in range(0,49,8):ring('Module end '+str(j//8),points[j],frames[j])
for i in [4,5]:line('M backbone co-deformation assumption '+str(i+1),points[i*8:(i+1)*8+1],.9,silver)
for t in pose['tendon_paths']:
 o=line(t['name'],t['points_local_mm'],1,rope_mats['ABC'.index(t['name'][0])]);o.hide_render=t['name'][0]!='C'
sphere('500 g point load',points[-1],2.5,red)
sphere('Head ENVELOPE',points[-1],31.5,head)
mins=Vector(tuple(min(p[k] for p in points) for k in range(3)));maxs=Vector(tuple(max(p[k] for p in points) for k in range(3)))
stage(s,(mins+maxs)/2,650,False);s.render.filepath=str(P/'saved_equilibrium.png');bpy.ops.render.render(write_still=True)
s=new_scene('03 Original CAD reference - NOT conformed')
for i,m in enumerate(b['modules']):
 fs=[f'UniDirectional_96_part_0{j}.stl' for j in range(1,6)] if i<4 else ['Medium_Stiffness_96.stl']
 for f in fs:
  bpy.ops.wm.stl_import(filepath=str(ROOT/'cad/previews/u4m2'/f));o=bpy.context.object;o.name=m['name']+' ORIGINAL '+f
  rot=Matrix.Rotation(math.pi/2,4,'Y')
  if i<4:rot=rot@Matrix.Rotation(math.pi/2,4,'X')
  o.matrix_world=Matrix.Translation(((m['start_mm']+m['end_mm'])/2,0,0))@rot;o.data.materials.append(refmat)
for t in b['tendons']:
 o=line(t['name']+' exact ideal route',t['guide_points_local_mm'],1,rope_mats['ABC'.index(t['group'])]);o.hide_render=t['group']!='C'
for r in b['backbones']:cyl('NiTi reference '+str(r['module']),r['start_local_mm'],r['end_local_mm'],.9,silver)
stage(s,(300,0,0),700,True);s.render.filepath=str(P/'original_cad_reference.png');bpy.ops.render.render(write_still=True)
bpy.context.window.scene=nominal_scene
bpy.ops.wm.save_as_mainfile(filepath=str(P/'simulation_reference.blend'))
