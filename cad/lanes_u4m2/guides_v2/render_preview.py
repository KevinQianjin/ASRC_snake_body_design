"""Render the actual V2 STL parts using Blender (blender -b --python render_preview.py)."""
import bpy
from pathlib import Path
from math import radians,cos,sin
from mathutils import Vector
P=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=40;s.cycles.use_denoising=False
s.render.resolution_x=1000;s.render.resolution_y=1100;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.world.use_nodes=True
s.world.node_tree.nodes['Background'].inputs[0].default_value=(.94,.96,.98,1)
s.world.node_tree.nodes['Background'].inputs[1].default_value=.6;s.view_settings.view_transform='Standard'
def mat(name,c):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
 m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*c,1)
 m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.4;return m
orange=mat('Guide frame',(.95,.5,.07));yellow=mat('Caps',(.98,.72,.18));steel=mat('Retaining wire',(.3,.35,.4))
gray=mat('Cutaway M5 body',(.55,.65,.72));blue=mat('NiTi',(.03,.2,.7));green=mat('B ropes',(.02,.45,.16));red=mat('C ropes',(.75,.03,.05))
def mesh(name,m,z=0):
 bpy.ops.wm.stl_import(filepath=str(P/name));o=bpy.context.object;o.scale=(.01,)*3;o.location.z=z*.01;o.data.materials.append(m);return o
objects=[mesh('M5_preview_cutaway.stl',gray)]
for z in [-24,-12,12,24]:
 for suffix,m in [('guide',orange),('caps',yellow),('wire_envelope',steel)]:objects.append(mesh(f'M5_z{z:+d}_{suffix}.stl',m,z))
def cylinder(x,y,r,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.01,depth=.96,location=(x*.01,y*.01,0))
 o=bpy.context.object;o.data.materials.append(m);return o
objects.append(cylinder(0,0,.9,blue))
for r,m in [(24,green),(28,red)]:
 for a in [0,90,180,270]:objects.append(cylinder(r*cos(radians(a)),r*sin(radians(a)),1,m))
for pos,power,size in [((2,-3,4),420,3),((-3,-2,2),220,3),((1,3,3),300,2)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size
 o.rotation_euler=(Vector((0,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO'
def render(name,pos,scale):
 cam.location=pos;cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 s.render.filepath=str(P/name);bpy.ops.render.render(write_still=True)
render('M5_assembly_preview.png',(1.45,-2.4,1.5),1.34)
for o in objects:o.hide_render=True
parts=[mesh(f'M5_z-12_{suffix}.stl',m) for suffix,m in [('guide',orange),('caps',yellow),('wire_envelope',steel)]]
render('M5_outer_station_preview.png',(0,-.4,2),.72)
