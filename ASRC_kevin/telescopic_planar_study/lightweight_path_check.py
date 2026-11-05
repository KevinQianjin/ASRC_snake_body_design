"""Saved-CAD polygon clearance with NumPy only: no CAD runtime installation."""
import json,math
import numpy as np
from matplotlib.path import Path as MplPath
from front_solver import HERE

def cross(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]

class Obstacles:
 def __init__(self,sections):
  self.polys=[p for s in sections for p in s['union_polygons']]
  edges=[]
  for p in self.polys:
   for ring in [p['outer']]+p['holes']:
    a=np.asarray(ring)
    if not np.array_equal(a[0],a[-1]):a=np.vstack((a,a[0]))
    edges.extend(zip(a[:-1],a[1:]))
  self.a=np.array([x for x,y in edges]);self.b=np.array([y for x,y in edges])
 def clearance(self,p):
  p=np.asarray(p);a=p[:-1,None,:];b=p[1:,None,:];c=self.a[None,:,:];d=self.b[None,:,:]
  u=b-a;v=d-c;w=c-a;den=cross(u,v);valid=abs(den)>1e-14
  tt=np.divide(cross(w,v),den,out=np.full_like(den,-1),where=valid)
  ss=np.divide(cross(w,u),den,out=np.full_like(den,-1),where=valid)
  if np.any(valid&(tt>=0)&(tt<=1)&(ss>=0)&(ss<=1)):return 0.
  for poly in self.polys:
   inside=MplPath(poly['outer']).contains_points(p)
   for hole in poly['holes']:inside &= ~MplPath(hole).contains_points(p)
   if inside.any():return 0.
  def dist(point,start,end):
   vec=end-start;den=np.sum(vec*vec,axis=-1);t=np.sum((point-start)*vec,axis=-1)/np.maximum(den,1e-30)
   return np.sum((point-start-np.clip(t,0,1)[...,None]*vec)**2,axis=-1)
  return float(np.sqrt(min(np.min(dist(a,c,d)),np.min(dist(b,c,d)),np.min(dist(c,a,b)),np.min(dist(d,a,b)))))

def run():
 out=HERE/'results';j=json.loads((out/'cad_sections.json').read_text());secs={s['width_mm']:s for s in j['sections']}
 fo=Obstacles([secs[k] for k in [632.,648.,664.]]);ro=Obstacles([secs[k] for k in [628.,648.,668.]])
 prof=np.load(out/'cavity_profiles.npz');xs=prof['length_mm'];floor=prof['floor_mm'];roof=prof['roof_mm']
 entry=np.array([449.,np.interp(449,xs,floor)]);angle=np.radians(20);v=np.array([np.cos(angle),np.sin(angle)]);guide=entry-200*v
 old=np.load(out/'front_refined_states.npz');reference=fo.clearance(old['r004_points_m']*1000+entry+884*v)
 assert abs(reference-21.091794349950874)<1e-6
 states=np.load(out/'segmented_tendon_states.npz');rows=[];curves={}
 # Keep the front interface ahead of the front guide. The head is already
 # inside at this starting pose; initial feed-in is a separate unsolved step.
 sgrid=np.arange(-180.,400.001,2.)
 for u in [8,9]:
  p=states[f'per_module_u{u}_points_m']*1000
  distance=np.array([fo.clearance(p+entry+s*v)-16 for s in sgrid])
  final=p+entry+400*v
  lower=final[:,1]-np.interp(final[:,0],xs,floor)-21
  upper=np.interp(final[:,0],xs,roof)-final[:,1]-21
  inside=bool(min(lower.min(),upper.min(),final[:,0].min()-21,1600-final[:,0].max()-21)>=0)
  rear_clear=ro.clearance(np.array([guide,entry+400*v]))-20
  housing_clear=ro.clearance(np.array([guide-300*v,guide]))-25
  rows.append(dict(configuration=f'U{u}-M{10-u}',architecture='per_module',pitch_deg=20,
    path_start_insertion_mm=-180,path_end_insertion_mm=400,path_step_mm=2,
    initial_head_feed_validated=False,front_housing_packaging_validated=False,
    minimum_front_envelope_clearance_mm=float(distance.min()),final_front_inside_envelope=inside,
    final_rear_clearance_mm=rear_clear,fixed_housing_clearance_mm=housing_clear,
    sampled_geometric_path_pass=bool(distance.min()>=5 and inside and rear_clear>=5 and housing_clear>=5),
    scope='High-strain elastic diagnostic; NOT material, hardware, coupled-structure, or full 3D validation'))
  curves[u]=(p,distance)
 (out/'segmented_path_check.json').write_text(json.dumps(dict(rows=rows,clearance_reference_check_abs_error_mm=abs(reference-21.091794349950874)),indent=2))
 np.savez_compressed(out/'segmented_path_clearance.npz',s_mm=sgrid,**{f'u{u}_gap_mm':curves[u][1] for u in curves})
 render(secs[648.],entry,v,guide,sgrid,curves,out)
 print(json.dumps(rows,indent=2))

def render(section,entry,v,guide,sgrid,curves,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.text import Text
 from matplotlib.patches import Polygon
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.unicode_minus':False})
 fig,axs=plt.subplots(2,1,figsize=(11,7.5))
 for p in section['union_polygons']:
  axs[0].add_patch(Polygon(p['outer'],facecolor='#596570',edgecolor='#596570',lw=.5))
  for h in p['holes']:axs[0].add_patch(Polygon(h,facecolor='white',edgecolor='#596570',lw=.5))
 p=curves[9][0]
 for s,c,ls in [(0,'#596570','--'),(200,'#587b52','-.'),(400,'#c86431','-')]:
  q=p+entry+s*v;axs[0].plot(q[:,0],q[:,1],color=c,ls=ls,lw=2,label=f's = {s} mm')
 axs[0].plot([guide[0],entry[0]+400*v[0]],[guide[1],entry[1]+400*v[1]],color='#246b9d',lw=4)
 axs[0].set(xlim=(0,1650),ylim=(-80,480),xlabel='Tank length coordinate (mm)',ylabel='Height (mm)',title='U9-M1 with 10 anchor sets: partial insertion after initial head entry\nHigh-strain diagnostic only: maximum axial strain about 14%')
 axs[0].set_aspect('equal');axs[0].legend(fontsize=9);axs[0].grid(alpha=.15)
 for u,c in [(8,'#246b9d'),(9,'#c86431')]:axs[1].plot(sgrid,curves[u][1],color=c,label=f'U{u}-M{10-u}',lw=1.7)
 axs[1].axhline(5,color='#596570',ls='--',lw=1,label='Required 5 mm clearance')
 axs[1].set(xlabel='Front interface insertion coordinate, s (mm)',ylabel='Front envelope clearance (mm)',ylim=(0,None));axs[1].legend(fontsize=9);axs[1].grid(alpha=.15)
 fig.tight_layout(rect=(0,.07,1,1));fig.text(.5,.015,'Saved CAD sections; 32 mm front/head, 40 mm rear, 50 mm housing; fixed 20 deg axis.\nInitial head feed-in, mechanism packaging, large-strain material behavior and full 3D deployment are NOT validated.',ha='center',fontsize=9)
 for t in fig.findobj(Text):assert all(ord(c)<128 for c in t.get_text())
 fig.savefig(out/'segmented_insertion_path.png',dpi=170,bbox_inches='tight');plt.close(fig)

if __name__=='__main__':run()
