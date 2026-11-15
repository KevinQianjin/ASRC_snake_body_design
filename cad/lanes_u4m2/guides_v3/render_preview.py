"""Render the actual V3 STL assembly; no synthetic replacement geometry."""
from pathlib import Path
from math import radians,cos,sin
import bpy
from mathutils import Vector

P=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=24
s.cycles.use_denoising=False;s.render.threads_mode='FIXED';s.render.threads=2
s.render.resolution_x=900;s.render.resolution_y=1000;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.world.use_nodes=True
s.world.node_tree.nodes['Background'].inputs[0].default_value=(.85,.88,.92,1)
s.world.node_tree.nodes['Background'].inputs[1].default_value=.5
s.view_settings.view_transform='AgX'

def mat(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.5
    return m

frame=mat('V3 guide frame',(.95,.45,.03));cap=mat('Inward cap',(.98,.7,.2))
wire=mat('Lockwire',(.25,.28,.3));body=mat('Cutaway M5 body',(.62,.68,.73))
blue=mat('NiTi backbone',(.02,.18,.8));green=mat('B ropes',(.02,.55,.18));red=mat('C ropes',(.8,.03,.07))

def mesh(filename,material,z=0):
    bpy.ops.wm.stl_import(filepath=str(P/filename));o=bpy.context.object
    o.scale=(.01,)*3;o.location.z=z*.01;o.data.materials.append(material);return o

objects=[mesh('../guides_v2/M5_preview_cutaway.stl',body)]
for z in (-24,-12,12,24):
    for suffix,material in [('guide',frame),('caps',cap),('wire_envelope',wire)]:
        objects.append(mesh(f'M5_z{z:+d}_{suffix}.stl',material,z))

def cylinder(x,y,r,material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r*.01,depth=.96,location=(x*.01,y*.01,0))
    o=bpy.context.object;o.data.materials.append(material);return o

objects.append(cylinder(0,0,.9,blue))
for r,material in [(24,green),(28,red)]:
    for a in (0,90,180,270):objects.append(cylinder(r*cos(radians(a)),r*sin(radians(a)),1,material))
for position,power in [((2,-3,4),350),((-3,-2,2),180),((1,3,3),230)]:
    bpy.ops.object.light_add(type='AREA',location=position);light=bpy.context.object
    light.data.energy=power;light.data.size=3
    light.rotation_euler=(Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();camera=bpy.context.object;s.camera=camera;camera.data.type='ORTHO'

def render(filename,position,scale):
    camera.location=position
    camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=scale;s.render.filepath=str(P/filename);bpy.ops.render.render(write_still=True)

render('M5_assembly_preview.png',(1.45,-2.4,1.5),1.34)
for o in objects:o.hide_render=True
for suffix,material in [('guide',frame),('caps',cap),('wire_envelope',wire)]:mesh(f'M5_z-12_{suffix}.stl',material)
render('M5_outer_station_preview.png',(0,-.55,2),.72)
