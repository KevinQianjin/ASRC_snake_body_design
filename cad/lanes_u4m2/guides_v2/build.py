"""Build CAD-matched guide saddles, removable caps and retaining-wire envelopes.

The +/-12 mm stations attach to outer webs; +/-24 mm attach to inner webs.
Sockets follow the actual inclined rectangular CAD webs with a 0.15 mm bond gap.
All non-mounting flexures receive 0.30 mm clearance in the straight CAD model.
"""
import argparse, json, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon, box as rectangle
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import build_lane_modules as B
import build_ends_and_check as E
D=json.loads((HERE/'design.json').read_text())

def boolean(op,meshes):return getattr(trimesh.boolean,op)(meshes,engine='manifold')
def box(size,pos):
    m=trimesh.creation.box(size);m.apply_translation(pos);return m

def cyl(d,h):return trimesh.creation.cylinder(radius=d/2,height=h,sections=64)
def place(m,a):return m.copy().apply_transform(B.rz(a))
def prism(poly,h):
    m=trimesh.creation.extrude_polygon(poly,h);m.apply_translation([0,0,-h/2]);return m

def loft(bounds,zs):
    v=[]
    for (x0,y0,x1,y1),z in zip(bounds,zs):v.extend([[x0,y0,z],[x1,y0,z],[x1,y1,z],[x0,y1,z]])
    f=[[0,2,1],[0,3,2]]
    for k in range(len(zs)-1):
        for j in range(4):
            a=4*k+j;b=4*k+(j+1)%4;c=b+4;d=a+4;f.extend([[a,b,c],[a,c,d]])
    n=len(v);f.extend([[n-4,n-3,n-2],[n-4,n-2,n-1]])
    m=trimesh.Trimesh(v,f,process=True);m.fix_normals();return m

def expand(bounds,g):return bounds+np.array([-g,-g,g,g])

def sections(body,z):
    sec=body.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    return [Polygon(p[:,:2]) for p in sec.discrete]

@lru_cache(None)
def profiles(station):
    body=trimesh.load_mesh(HERE/'M5_lane_anchorB.stl',force='mesh')
    h=D['plate_thickness_mm'];zs=np.linspace(-h/2-.02,h/2+.02,9)
    reference=sections(body,station)
    stack=[sections(body,station+z) for z in zs]
    out=[]
    for poly in reference:
        center=np.array(poly.centroid.coords[0]);radius=np.linalg.norm(center)
        if radius>32 or radius<3:continue
        angle=round(float(np.degrees(np.arctan2(center[1],center[0]))),1);a=np.radians(angle)
        R=np.array([[np.cos(a),np.sin(a)],[-np.sin(a),np.cos(a)]])
        bounds=[]
        for ps in stack:
            chosen=min(ps,key=lambda p:np.linalg.norm(np.array(p.centroid.coords[0])-center))
            P=np.asarray(chosen.exterior.coords)@R.T
            bounds.append(np.round([*P.min(0),*P.max(0)],5))
        out.append(dict(radius=float(radius),angle=float(angle),bounds=np.asarray(bounds),zs=zs))
    return out

def bellmouth():
    h=D['plate_thickness_mm'];throat=D['rope_throat_length_mm']/2
    z=np.linspace(-h/2-.03,h/2+.03,30);u=np.clip((abs(z)-throat)/(h/2-throat),0,1)
    r=D['rope_bore_mm']/2+(D['rope_mouth_mm']-D['rope_bore_mm'])/2*(1-np.sqrt(np.maximum(0,1-u*u)))
    return trimesh.creation.revolve(np.vstack([[0,z[0]],np.c_[r,z],[0,z[-1]]]),sections=64)

def guide(kind,station):
    h=D['plate_thickness_mm'];tip=D['arm_tip_radius_mm'];ri=7.8;ro=10.2
    ring=boolean('difference',[cyl(2*ro,h),cyl(2*ri,h+2)])
    solids=[ring];cuts=[];caps=[];wires=[];mounts=[];cap_cuts=[]
    for a in (0,90,180,270):
        v=np.array([[ri,-2,-h/2],[ri,2,-h/2],[14,-3,-h/2],[14,3,-h/2],[tip,-3,-h/2],[tip,3,-h/2],
                    [ri,-2,h/2],[ri,2,h/2],[14,-3,h/2],[14,3,h/2],[tip,-3,h/2],[tip,3,h/2]])
        solids.append(place(trimesh.convex.convex_hull(v),a))
        for r in ((24.,28.) if kind=='M5' else (28.,)):
            hole=bellmouth();hole.apply_translation([r,0,0]);cuts.append(place(hole,a))
    expected=6.896 if abs(station)==24 else 19.229
    for p in profiles(station):
        angle=p['angle'];selected=abs(p['radius']-expected)<.2 and any(abs((angle-a+180)%360-180)<.2 for a in D['web_angles_deg'])
        gap=.15 if selected else .30
        inner=expand(p['bounds'],gap)
        bore=place(loft(inner,p['zs']),angle);cuts.append(bore)
        if not selected:continue
        # The four keyed saddles follow each web's actual slope through the plate.
        outer=expand(inner,.85)
        solid=place(loft(outer,p['zs']),angle);solids.append(solid)
        # Inward cap closes a radial assembly opening; lockwire holds it after bonding.
        cb=outer.copy();cb[:,1]=inner[:,1];cb[:,2]=inner[:,0];cb[:,3]=inner[:,3]
        cap=place(loft(cb,p['zs']),angle)
        caps.append(cap);cap_cuts.append(place(loft(expand(cb,.03),p['zs']*1.02),angle))
        if abs(station)==12:
            # Forks connect the remote outer-web saddles to the central frame.
            far=float(outer[:,2].max())
            for sign in (-1,1):
                solids.append(place(box([far-9.,2.,h],[(far+9.)/2,sign*2.65,0]),angle))
        mid=outer[len(outer)//2]
        rounding=.2
        outer_poly=rectangle(mid[0]+rounding,mid[1]+rounding,mid[2]-rounding,mid[3]-rounding).buffer(rounding)
        wire_outer=outer_poly.buffer(-.025);wire_inner=wire_outer.buffer(-D['retaining_wire_d_mm'])
        wire=place(prism(wire_outer.difference(wire_inner),D['retaining_wire_d_mm']),angle)
        groove=place(prism(wire_outer.buffer(.05).difference(wire_inner.buffer(-.05)),D['wire_groove_d_mm']),angle)
        wires.append(wire);cuts.append(groove)
        caps[-1]=boolean('difference',[caps[-1],groove])
        mounts.append(dict(angle_deg=angle,web_center_radius_mm=p['radius'],bond_gap_mm=gap,section_bounds_radial_tangential_mm=p['bounds'][4].tolist(),
                           station_z_mm=station,web_section_count=len(p['zs']),bond_area_estimate_mm2=float(2*((p['bounds'][4,2]-p['bounds'][4,0])+(p['bounds'][4,3]-p['bounds'][4,1]))*h)))
    if len(mounts)!=4:raise RuntimeError(f'{station}: four real web mounts required, found {len(mounts)}')
    main=boolean('difference',[boolean('union',solids)]+cuts+cap_cuts)
    parts=[c for c in main.split(only_watertight=False) if abs(c.volume)>1e-4]
    main=trimesh.util.concatenate(parts)
    return main,caps,wires,mounts

def build_bodies():
    B.HERE=HERE;E.HERE=HERE;B.LANES=D['lane_radii_mm'];B.PAD_R=(18.5,30.5)
    B.main();E.main()
    p=HERE/'lane_design.json';d=json.loads(p.read_text());d['lane_pitch_mm']={'A_B':3.,'B_C':4.};d['wall_between_lane_holes_mm']={'A_B':.5,'B_C':1.5};p.write_text(json.dumps(d,indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--guides-only',action='store_true');a=p.parse_args()
    if not a.guides_only:build_bodies()
    report=dict(design=D,parts={},all_straight_positions_clear=True,all_mounts_on_existing_webs=True)
    for kind,bodyfile in [('M5','M5_lane_anchorB.stl'),('M6','M6_lane_anchorC.stl')]:
        body=trimesh.load_mesh(HERE/bodyfile,force='mesh')
        for z in D['stations_z_mm']:
            part,caps,wires,mounts=guide(kind,z);tag=f'{kind}_z{z:+d}'
            part.export(HERE/f'{tag}_guide.stl')
            trimesh.util.concatenate(caps).export(HERE/f'{tag}_caps.stl')
            trimesh.util.concatenate(wires).export(HERE/f'{tag}_wire_envelope.stl')
            exported={s:trimesh.load_mesh(HERE/f'{tag}_{s}.stl') for s in ('guide','caps','wire_envelope')}
            export_checks={s:dict(watertight=bool(mesh.is_watertight),components=len(mesh.split())) for s,mesh in exported.items()}
            assembly=trimesh.util.concatenate([part]+caps+wires);assembly.apply_translation([0,0,z])
            overlap=boolean('intersection',[body,assembly]);volume=0. if overlap.is_empty else float(overlap.volume)
            good=volume<1e-6 and all(v['watertight'] and v['components']==(1 if k=='guide' else 4) for k,v in export_checks.items())
            report['all_straight_positions_clear'] &= bool(good)
            report['parts'][tag]=dict(watertight=bool(part.is_watertight),components=len(part.split()),frame_volume_mm3=float(part.volume),
                cap_volume_mm3=sum(float(c.volume) for c in caps),wire_envelope_volume_mm3=sum(float(w.volume) for w in wires),
                body_overlap_mm3=volume,pass_geometry=bool(good),mounts=mounts,export_checks=export_checks)
            print(tag,'overlap',volume,'components',len(part.split()),flush=True)
    report.update(minimum_bore_bridge_mm=4-D['rope_bore_mm'],minimum_mouth_bridge_mm=4-D['rope_mouth_mm'],outer_mouth_wall_mm=D['arm_tip_radius_mm']-28-D['rope_mouth_mm']/2)
    (HERE/'geometry_check.json').write_text(json.dumps(report,indent=2))
    if not report['all_straight_positions_clear']:raise SystemExit('Revise geometry: intersection or disconnected frame')
if __name__=='__main__':main()
