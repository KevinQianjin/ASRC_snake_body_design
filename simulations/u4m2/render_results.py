"""English-only standalone engineering figures from saved planar calculations."""
from pathlib import Path
import json,csv,math,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon
from matplotlib.text import Text
from planar_clearance import load_geometry,HERE
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union

OUT=HERE/'results'
BLUE='#246b9d';ORANGE='#c86431';GREY='#596570';GREEN='#587b52'
plt.rcParams.update({'font.family':'DejaVu Sans','axes.unicode_minus':False,'font.size':12,'axes.titlesize':13,
 'axes.labelsize':12,'legend.fontsize':10,'figure.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})

def paint(ax,g,color,alpha=1.,z=2):
 if g.is_empty:return
 if g.geom_type=='Polygon':
  ax.add_patch(PatchPolygon(np.asarray(g.exterior.coords),facecolor=color,edgecolor=color,linewidth=.6,alpha=alpha,zorder=z))
  for ring in g.interiors:ax.add_patch(PatchPolygon(np.asarray(ring.coords),facecolor='white',edgecolor=color,linewidth=.6,zorder=z+.01))
 elif hasattr(g,'geoms'):
  for a in g.geoms:paint(ax,a,color,alpha,z)

def save(fig,name):
 # Enforce the user's English-only requirement on every visible text object.
 for t in fig.findobj(Text):
  if any(ord(c)>127 for c in t.get_text()):raise ValueError('Non-ASCII figure text: '+t.get_text())
 fig.savefig(OUT/name,dpi=180,bbox_inches='tight');plt.close(fig)

def run():
 _,obs,cavity,xs,floor,roof=load_geometry();center=obs[648.]
 fits=json.loads((OUT/'adaptive_static_fits.json').read_text());fit=next(r for r in fits if r['fine_mesh'])
 z=np.load(OUT/'front_refined_states.npz')
 entry=np.array([449.,np.interp(449.,xs,floor)])
 def context(ax):
  paint(ax,center,GREY)
  ax.set(xlim=(-130,1660),ylim=(-145,510),xlabel='Tank length coordinate (mm)',ylabel='Height (mm)')
  ax.set_aspect('equal');ax.grid(alpha=.13,zorder=0)
  ax.annotate('Access A: 500 x 200 mm in opening plane',xy=entry,xytext=(575,-105),
    arrowprops={'arrowstyle':'->','lw':.8,'color':GREY},fontsize=10,ha='center')
 def rear(ax,angle,s):
  a=math.radians(angle);v=np.array([math.cos(a),math.sin(a)]);guide=entry-200*v;root=entry+s*v
  paint(ax,LineString([guide-260*v,guide]).buffer(25,cap_style='flat'),GREY,alpha=.35,z=3)
  paint(ax,LineString([guide,root]).buffer(20,cap_style='flat'),BLUE,alpha=.65,z=4)
  ax.plot(*guide,'ks',ms=5,zorder=6)
  ax.annotate('External guide',xy=guide,xytext=(35,-55),fontsize=10,
    arrowprops={'arrowstyle':'->','lw':.8,'color':GREY},ha='center')
  return root,v
 fig,axs=plt.subplots(2,1,figsize=(11,8.7))
 for ax in axs:context(ax)
 root,v=rear(axs[0],15,400)
 ideal=np.array([root,root+500*v]);paint(axs[0],LineString(ideal).buffer(16),ORANGE,.72,5)
 axs[0].plot(*ideal[-1],'o',mfc='white',mec=ORANGE,ms=7,zorder=6)
 axs[0].set_title('A. Imposed straight geometry: 15 deg, insertion s = 400 mm\nClear of the sampled CAD sections; this is NOT a 500 g equilibrium',loc='left',pad=12)
 axs[0].annotate('500 mm front',xy=ideal.mean(0),xytext=(1000,165),fontsize=11,
   arrowprops={'arrowstyle':'->','lw':.8,'color':ORANGE},ha='center')
 root,v=rear(axs[1],20,884)
 p=z['r004_points_m']*1000+root
 paint(axs[1],LineString(p).buffer(16),ORANGE,.72,5);axs[1].plot(*p[-1],'o',mfc='white',mec=ORANGE,ms=7,zorder=6)
 axs[1].set_title('B. Loaded equilibrium: U3-M7, 20 deg, top tendon 8 N, head 500 g\nNarrow STATIC fit only; rear idealized rigid, front strain 4.55%',loc='left',pad=12)
 axs[1].annotate('Front hangs down\nabout 350 mm',xy=p[len(p)//2],xytext=(1040,165),fontsize=11,
   arrowprops={'arrowstyle':'->','lw':.8,'color':ORANGE},ha='center')
 axs[1].annotate('Head',xy=p[-1],xytext=(1550,160),fontsize=10,
   arrowprops={'arrowstyle':'->','lw':.8,'color':ORANGE},ha='center')
 fig.tight_layout(rect=(0,.055,1,1));fig.text(.5,.012,'CAD plane: width 648 mm. Flank planes also screened. Front/head envelope: 32 mm; required clearance: 5 mm.\nGeometry window: s = 883.45-884.28 mm. Exposed rear length = s + 200 mm. No deployment or 3D approval.',ha='center',fontsize=10)
 save(fig,'planar_installation.png')

 fig,axs=plt.subplots(1,2,figsize=(12,5.3),gridspec_kw={'width_ratios':[1,1.15]})
 colors=[BLUE,ORANGE,GREEN]
 for rid,cfg,c in zip(['r004','r010','r016'],['U3-M7','U5-M5','U7-M3'],colors):
  p=z[rid+'_points_m']*1000;axs[0].plot(p[:,0],p[:,1],color=c,lw=2,label=cfg)
  axs[0].plot(*p[-1],'o',color=c,ms=5)
 axs[0].plot(0,0,'ks',ms=5);axs[0].axhline(0,color=GREY,lw=.8)
 axs[0].set(xlabel='Forward displacement (mm)',ylabel='Vertical displacement (mm)',title='Loaded front shapes at 20 deg\nTop tendon 8 N; head 500 g')
 axs[0].set_aspect('equal');axs[0].grid(alpha=.15);axs[0].legend(loc='lower left')
 rows=list(csv.DictReader((OUT/'geometry_axis_windows.csv').open()))
 for i,a in enumerate([10,15,20,25,30]):
  row=next(r for r in rows if r['port']=='A' and r['direction']=='1' and int(r['pitch_deg'])==a)
  for dy,prefix,c,label in [(-.16,'rear',BLUE,'Rear only'),(.16,'straight_front',ORANGE,'With imposed straight front')]:
   lo=float(row['minimum_'+prefix+'_insertion_mm']);hi=float(row['maximum_'+prefix+'_insertion_mm'])
   axs[1].barh(i+dy,hi-lo,left=lo,height=.25,color=c,label=label if i==0 else None)
   axs[1].text(hi+13,i+dy,f'{hi:.0f}',va='center',fontsize=10)
 axs[1].set(yticks=range(5),yticklabels=[f'{a} deg' for a in [10,15,20,25,30]],xlabel='Insertion from access opening, s (mm)',xlim=(0,1120),title='Access A, forward axis: geometric windows\n40 mm rear, 32 mm front, 5 mm clearance')
 axs[1].invert_yaxis();axs[1].grid(axis='x',alpha=.15);axs[1].legend(loc='lower right')
 fig.tight_layout(rect=(0,.08,1,1));fig.text(.5,.014,'Left: fine mesh equilibria, not straight-front commands. Right: imposed geometry only; 10 mm insertion grid.\nTube length, guide setback, front deformation, and insertion travel are distinct quantities.',ha='center',fontsize=10)
 save(fig,'front_and_geometry_limits.png')

 sys.path.insert(0,str(HERE));from rear_beam import calculate_case
 fig,axs=plt.subplots(1,2,figsize=(11,4.8))
 for layout,name,c in [('stepped_40_30','40/30 mm stepped tubes',BLUE),('single_30','Single 30 mm tube',ORANGE)]:
  ls=np.linspace(.2,1.2,31);rr=[calculate_case(layout,float(l),15,'horizontal') for l in ls]
  axs[0].plot(ls,[r['interface_vertical_deflection_down_mm'] for r in rr],color=c,label=name,lw=2)
  axs[1].plot(ls,[r['maximum_nominal_normal_stress_mpa'] for r in rr],color=c,label=name,lw=2)
 axs[0].axhline(5,color=GREY,ls='--',lw=1,label='Proposed 5 mm deflection target')
 axs[0].set(ylabel='Interface downward deflection (mm)',title='Nominal beam deflection',ylim=(0,5.5))
 axs[1].set(ylabel='Maximum nominal normal stress (MPa)',title='Nominal tube section stress',ylim=(0,None))
 for ax in axs:ax.set_xlabel('Exposed length from front guide (m)');ax.grid(alpha=.15)
 axs[0].legend(loc='upper left',fontsize=9);axs[1].legend(loc='upper left',fontsize=9)
 fig.suptitle('Rear support screening: ideal joints, 15 deg, horizontal 500 mm front',fontsize=14)
 fig.tight_layout(rect=(0,.075,1,.95));fig.text(.5,.012,'Aluminum assumptions: E = 69 GPa; density = 2700 kg/m3; wall = 2 mm. Includes tube self-weight and front end moment.\nJoint compliance, overlap mass, tendon forces, motor loads, local bearing contact, and base anchoring are not included.',ha='center',fontsize=9)
 save(fig,'rear_beam_screen.png')
 fig,axs=plt.subplots(2,1,figsize=(11,8),gridspec_kw={'height_ratios':[1.5,1]})
 context(axs[0]);rear(axs[0],20,884)
 rel=z['r004_points_m']*1000
 for s,c,style in [(200,GREY,'--'),(550,GREEN,'-.'),(884,ORANGE,'-')]:
  points=entry+s*np.array([math.cos(math.radians(20)),math.sin(math.radians(20))])+rel
  axs[0].plot(points[:,0],points[:,1],color=c,ls=style,lw=2,label=f's = {s} mm')
 axs[0].set_ylim(-260,510);axs[0].set_title('Frozen-shape deployment check: same loaded front translated along the rear axis',loc='left',pad=12)
 axs[0].legend(loc='upper left',fontsize=10)
 fo=unary_union([obs[k] for k in [632.,648.,664.]])
 sgrid=np.arange(-550.,885.,2.);v=np.array([math.cos(math.radians(20)),math.sin(math.radians(20))])
 gap=np.array([LineString(entry+s*v+rel).distance(fo)-16 for s in sgrid])
 axs[1].plot(sgrid,gap,color=BLUE,lw=1.7,label='Front envelope clearance to CAD solids')
 axs[1].axhline(5,color=GREY,ls='--',lw=1,label='Required 5 mm margin')
 axs[1].axhline(0,color=GREY,lw=.8)
 axs[1].fill_between(sgrid,gap,0,where=gap<0,color=ORANGE,alpha=.22,label='Envelope overlaps a CAD solid')
 axs[1].set(xlabel='Front-interface insertion coordinate, s (mm)',ylabel='Envelope clearance (mm)',ylim=(-20,60))
 axs[1].grid(alpha=.15);axs[1].legend(loc='upper right',fontsize=9)
 fig.tight_layout(rect=(0,.07,1,1));fig.text(.5,.015,'A clear final pose does not establish a clear insertion path. This frozen-shape path has collisions.\nChanging-shape deployment, contact-guided insertion, and installation fixtures have not been solved.',ha='center',fontsize=10)
 save(fig,'deployment_path.png')
 print('Saved four English-only figures.')

if __name__=='__main__':run()
