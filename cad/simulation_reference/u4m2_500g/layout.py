from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json
p=Path(__file__).resolve().parent
b=json.loads((p/'baseline.json').read_text());pose=json.loads((p/'saved_pose.json').read_text())
im=Image.new('RGB',(1800,1740),'white');d=ImageDraw.Draw(im)
def f(n,bold=False):return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',n)
def text(x,y,s,n=24,col='#344454',bold=False):d.text((x,y),s,font=f(n,bold),fill=col)
def center(x,y,s,n=24,col='#344454',bold=False):d.text((x,y),s,font=f(n,bold),fill=col,anchor='mt')
def paste(name,x,y,size=None):
 a=Image.open(p/name)
 if size:a=a.resize(size,Image.Resampling.LANCZOS)
 im.paste(a,(x,y),a.getchannel('A'))
text(55,28,'U4 + M2 | Exact simulation reference',49,'#132d46',True)
text(58,94,'500 g nominal v3 · source revision bee65b7 · model coordinates, not a manufacturing release',25)
paste('nominal_reference.png',0,150)
proj=json.loads((p/'projection.json').read_text())
for i,m in enumerate(b['modules']):
 x,y,_=proj[str(i)];x*=1800;y=150+(1-y)*550
 center(x,174,m['name'],28,'#1262a4' if i<4 else '#b85413',True)
 center(x,212,'96 mm',20)
 d.line((x,245,x,y-100),fill='#a8b5bf',width=2)
center(900,606,'20 mm rigid interface + 576 mm flexible front = 596 mm clamp-to-head',28,bold=True)
center(900,650,'All tendon centers: radius 24 mm. Same-direction A/B/C routes coincide; visible paths show C.',22)
d.line((55,701,1745,701),fill='#d6dee5',width=2)
text(55,723,'Saved 500 g equilibrium',31,'#132d46',True)
text(55,766,f"Sample {pose['sample_index']} · yaw {pose['yaw_deg']:.2f}° · elevation {pose['elevation_deg']:.2f}°",23)
paste('saved_equilibrium.png',0,805)
text(950,723,'Original CAD reference',31,'#132d46',True)
text(950,766,'Original meshes retained unchanged; not conformed.',22)
paste('original_cad_reference.png',900,825,(880,269))
text(950,1125,'Required model dimensions',28,'#132d46',True)
for y,label,value in [(1176,'Backbone (each M)','Ø1.8 × 96 mm'),(1220,'Anchors from clamp','404 / 500 / 596 mm'),(1264,'Head load','500 g point at X=596 mm'),(1308,'Tendon model','12 × Ø2 mm; 1 m free rope'),(1352,'Latest tension control','3 N target / 2.5 N floor')]:
 text(950,y,label,22);text(1325,y,value,22,'#132d46',True)
d.line((55,1480,1745,1480),fill='#d6dee5',width=2)
text(55,1500,'PARAMETERS MATCH THE SOLVER. PHYSICAL CONFORMANCE IS NOT ESTABLISHED.',27,'#9a4426',True)
text(55,1550,'1. Three finite-diameter ropes cannot occupy the same route through the U section.',24)
text(55,1590,'2. Original mesh cylindrical envelope ≈ Ø63.311 mm; simulation envelope = Ø63 mm.',24)
text(55,1630,'3. Backbone restraint and module continuity are ideal constraints; no extra fixtures are implied.',24)
text(55,1685,'Envelope surfaces are analytical visualization. Source CAD is not silently scaled; stored results are not rerun.',21)
im.save(p/'simulation_reference.png');im.save(p/'simulation_reference.pdf',resolution=180)
