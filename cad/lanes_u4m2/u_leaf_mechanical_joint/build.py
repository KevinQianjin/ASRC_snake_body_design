"""Single-leaf mechanical joint coupons. Dimensions in mm, assembly in the published U frame."""
from pathlib import Path
import hashlib
import json
from importlib.metadata import version

import manifold3d as md
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "guides_v2"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
M = md.Manifold
SCREW_X, SCREW_Y = 6.4, 21.12
KEY_Y0, KEY_Y1 = 18.05, 29.85
KEY_LEFT, KEY_RIGHT, KEY_D0, KEY_D1, EDGE_R = 4.97, 8.52, 3.13, 4.55, .25
SHOE_BOXES = [
    (4.44,10.55,19.96,29.17,.08,.88),
    (4.44,4.77,23.18,29.17,.78,2.62),
    (10.23,10.55,23.18,29.17,.78,2.62),
    (3.83,4.77,23.18,29.17,1.60,2.62),
    (10.23,11.35,23.18,29.17,1.60,2.62),
    (10.23,12.80,23.18,27.60,1.60,2.62),
]


def box(x0, x1, y0, y1, z0, z1):
    return M.cube([x1-x0, y1-y0, z1-z0]).translate([x0,y0,z0])


def cyl(x, y, z0, z1, radius, top=None, sides=96):
    return M.cylinder(z1-z0, radius, radius if top is None else top, sides).translate([x,y,z0])


def union(items):
    return M.batch_boolean(items, md.OpType.Add)


def mesh(m):
    a = m.to_mesh()
    return trimesh.Trimesh(vertices=a.vert_properties[:, :3], faces=a.tri_verts, process=True)


def solid(t):
    m = M(md.Mesh(np.asarray(t.vertices, dtype=np.float32), np.asarray(t.faces, dtype=np.uint32)))
    assert m.status() == md.Error.NoError and m.volume() > 0
    return m


def read(name):
    return trimesh.load_mesh(SOURCE / name)


def export(m, name):
    t = mesh(m)
    f = OUT / (name + ".stl")
    t.export(f)
    back = trimesh.load_mesh(f)
    assert back.is_volume and len(back.split(only_watertight=False)) == 1, name
    assert abs(back.volume-m.volume()) < max(.002, m.volume()*1e-5), name


def frame(m, near):
    # Involution between module XYZ and the local end frame (x,y,d). d points inward.
    return m.translate([0,0,48]) if near else m.mirror([0,0,1]).translate([0,0,48])


def world(m, near):
    return m.translate([0,0,-48]) if near else frame(m, False)


def swept(items, travel):
    return union([M.batch_hull([it,it.translate(travel)]) for it in items])


def joint(near):
    # Side key sits across the one-sided shoulder of the positive-X, positive-Y blade.
    radius_limit = cyl(0,0,-1,10,31.42,sides=360)
    rail = box(4.15,12.25,17.05,31.4,2.76,6.28)
    pedestal = box(4.15,11.6,18.95,23.04,2.76,8.55)
    boss = (rail + pedestal) ^ radius_limit
    blade_pass = box(4.86,10.14,23.26,29.55,2.75,9)
    # Rounded working edge where the key approaches the thin flexible span.
    cx,cz=KEY_RIGHT-EDGE_R,KEY_D0+EDGE_R
    profile=[(KEY_LEFT,KEY_D0),(cx,KEY_D0)]
    for angle in np.linspace(-np.pi/2,0,13)[1:]:
        profile.append((cx+EDGE_R*np.cos(angle),cz+EDGE_R*np.sin(angle)))
    profile.extend([(KEY_RIGHT,KEY_D1),(KEY_LEFT,KEY_D1)])
    key_blank=md.CrossSection([np.array(profile)]).extrude(KEY_Y1-KEY_Y0).rotate([90,0,0]).translate([0,KEY_Y1,0])
    key_blocks = [key_blank]
    key_slot = box(4.85,8.64,17.93,43,3.01,4.67)
    # Low bridge behind the proximal blade heel. Deeper side flanges engage independent grooves.
    shoe_blocks = [box(*bounds) for bounds in SHOE_BOXES]
    shoe_slot = union([box(4.32,10.67,19.84,43,-.03,1.00),
                       box(4.32,4.95,23.06,43,.66,2.74),
                       box(10.05,10.67,23.06,43,.66,2.74),
                       box(3.71,4.95,23.06,43,1.48,2.74),
                       box(10.05,12.92,23.06,43,1.48,2.74)])
    hole = cyl(SCREW_X,SCREW_Y,-1,10,.90)
    countersink = cyl(SCREW_X,SCREW_Y,-.02,.93,1.85,.90)
    fastener_cut = hole + countersink
    key = union(key_blocks) - hole
    shoe = union(shoe_blocks) - fastener_cut
    # Square nut and flat-head screw are dimensional envelopes, not thread specifications.
    nut_blank = box(SCREW_X-1.6,SCREW_X+1.6,SCREW_Y-1.6,SCREW_Y+1.6,6.30,7.60)
    nut = nut_blank - cyl(SCREW_X,SCREW_Y,6.2,7.7,.82)
    nut_slot = box(SCREW_X-1.73,44,SCREW_Y-1.73,SCREW_Y+1.73,6.17,7.73)
    screw_pieces=[cyl(SCREW_X,SCREW_Y,.23,1.03,1.60,.80),cyl(SCREW_X,SCREW_Y,1.03,8.23,.80)]
    screw = union(screw_pieces)
    cuts = union([blade_pass,key_slot,fastener_cut,nut_slot]+([shoe_slot] if near else []))
    parts = {"shoulder_key":key,"screw_envelope":screw,"nut_envelope":nut}
    sweeps = {"shoulder_key":swept(key_blocks,[0,18,0]),"nut":swept([nut_blank],[32,0,0]),
              "screw":swept(screw_pieces,[0,0,-15]),"driver":cyl(SCREW_X,SCREW_Y,-25,0,2.2)}
    if near:
        parts["backstop"] = shoe
        sweeps["backstop"] = swept(shoe_blocks,[0,18,0])
    return boss,cuts,parts,sweeps


def positive_volume(m):
    return max(0.,m.volume())


def check(m, other):
    v = positive_volume(m ^ other)
    return dict(overlap_mm3=round(v,7), gap_mm=round(m.min_gap(other,50),5))


def protected():
    # Over-bound the as-designed return, groove and block with a solid prism on each ray.
    data = json.loads((SOURCE/'lane_design.json').read_text())
    anchor=data['anchor']
    low=data['lanes_mm']['A']-anchor['return_offset_A_radial_inward']-2
    hi=data['pad']['radial'][1]
    half=data['pad']['width']/2
    block=box(-half,half,low,hi,0,anchor['block_depth'])
    bores=[cyl(0,r,-1,12,1.50) for r in data['lanes_mm'].values()]
    ropes=[cyl(0,r,-1,12,1.0) for r in data['lanes_mm'].values()]
    def around(m):
        return union([m.rotate([0,0,a]) for a in (0,90,180,270)])
    return {"anchor_block":around(block),"A_tail_sleeve":around(cyl(0,17.5,7,13,1.75)),
            "bore_mouths":around(union(bores)),
            "rope_2mm":around(union(ropes))}


def key_metrics(body,parts,leaf,near):
    # Use cross sections immediately inside the two faces to get projected areas in XY.
    def section(m,z):
        return m.slice(z)
    def overlap_area(a,b):
        return (a ^ b).area()
    area=overlap_area(section(leaf,2.98),section(parts['shoulder_key'],3.1301))
    lip=overlap_area(section(parts['shoulder_key'],4.54),section(body,4.68))
    def chord(a,b,n=0):
        hits=body.ray_cast(a,b)
        return round(float(np.linalg.norm(np.subtract(hits[n+1].position,hits[n].position))),5)
    values=dict(shoulder_overlap_mm2=round(area,4),key_inner_rail_bearing_mm2=round(lip,4),
                shoulder_to_key_axial_gap_mm=0.13,
                key_slot_side_wall_mm=chord([3.7,25,4],[16,25,4]),
                inner_rail_roof_mm=chord([7,18.55,4],[7,18.55,9]),
                key_to_nut_slot_web_mm=chord([5.8,22.2,4],[5.8,22.2,9]),
                nut_slot_roof_mm=chord([5.8,22.2,7],[5.8,22.2,10]))
    if near:
        values.update(backstop_outer_lip_mm=chord([11,26,-1],[11,26,10]),
                      heel_to_backstop_gap_mm=.12,
                      heel_backstop_bearing_mm2=round(overlap_area(section(leaf,1.01),section(parts['backstop'],.87)),4),
                      backstop_flange_bearing_mm2=round(overlap_area(section(parts['backstop'],1.61),section(body,1.47)),4))
    else:
        values.update(original_blind_floor_mm=chord([6,26,-1],[6,26,9]))
    return values


def coupon(body):
    # A test-only gripping flange ends before the added joint boss starts at y=18.95.
    grip=box(-1.9,14.6,9.5,15.0,0,5.8)
    grip-=cyl(1.2,12.5,-1,7,1.6)+cyl(11.5,12.5,-1,7,1.6)
    return (body ^ box(-1.9,14.6,14.0,34,-.02,9.0))+grip


def metal_steps(parts):
    """Analytic key and stepped shoe for prototype quoting; validate STEP round trips."""
    import cadquery as cq
    v=cq.Vector
    cx,cz=KEY_RIGHT-EDGE_R,KEY_D0+EDGE_R
    mid=EDGE_R/np.sqrt(2)
    key=(cq.Workplane('XZ',origin=(0,KEY_Y1,0)).moveTo(KEY_LEFT,KEY_D0)
         .lineTo(cx,KEY_D0).threePointArc((cx+mid,cz-mid),(KEY_RIGHT,cz))
         .lineTo(KEY_RIGHT,KEY_D1).lineTo(KEY_LEFT,KEY_D1).close().extrude(KEY_Y1-KEY_Y0).val())
    boxes=[cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,v(x0,y0,z0))
           for x0,x1,y0,y1,z0,z1 in SHOE_BOXES]
    bore=cq.Solid.makeCylinder(.90,11,v(SCREW_X,SCREW_Y,-1))
    seat=cq.Solid.makeCone(1.85,.90,.95,v(SCREW_X,SCREW_Y,-.02))
    shoe=boxes[0].fuse(*boxes[1:]).cut(bore,seat).clean()
    volumes={}
    for name,shape in [('shoulder_key',key.cut(bore)),('backstop',shoe)]:
        dest = OUT / (name + '.step')
        cq.exporters.export(shape, str(dest))
        # Keep the STEP exchange file free of exporter-added trailing padding.
        dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines()) + '\n')
        loaded = cq.importers.importStep(str(dest)).val()
        assert loaded.isValid() and len(loaded.Solids())==1,name
        difference=abs(loaded.Volume()-parts[name].volume())
        assert difference<.025,(name,difference)
        volumes[name]={'analytic_mm3':round(loaded.Volume(),6),'mesh_delta_mm3':round(difference,6)}
    return volumes


def build():
    files=['U_lane_pass.stl','U4_lane_anchorA.stl','U_leaf_springs.stl','lane_design.json']
    hashes={f:hashlib.sha256((SOURCE/f).read_bytes()).hexdigest() for f in files}
    springs=read(files[2]).split()
    leaf=solid(next(s for s in springs if all(s.centroid[:2]>0)))
    all_leaves=union([solid(s) for s in springs])
    reserve=protected()
    report={"units":"mm, mm2, mm3", "source_sha256":hashes,
            "source_revision":"8ef0fe02d19fe0358ddea9709e895a1b0dc63b4a",
            "versions":{p:version(p) for p in ('manifold3d','trimesh','numpy','matplotlib','cadquery')},
            "ends":{},"assembly":{}}
    for kind,file in zip(('U1','U4'),files[:2]):
        original=solid(read(file))
        module=original
        for near in (True,False):
            tag=kind+('_proximal' if near else '_distal')
            base=frame(original,near)
            boss,cuts,parts,sweeps=joint(near)
            body=(base+boss)-cuts
            added=body-base
            removed=base-body
            local_leaf=frame(leaf,near)
            metrics=key_metrics(body,parts,local_leaf,near)
            # Virtual over-travel witnesses: positive volume distinguishes engagement
            # of the stops from a loose but collision-free assembly. No contact solve.
            capture={
                'blade_pulls_key':positive_volume(local_leaf.translate([0,0,.18]) ^ parts['shoulder_key']),
                'key_hits_rail':positive_volume(parts['shoulder_key'].translate([0,0,.18]) ^ body),
            }
            if near:
                capture['heel_pushes_shoe']=positive_volume(local_leaf.translate([0,0,-.18]) ^ parts['backstop'])
                capture['shoe_hits_lip']=positive_volume(parts['backstop'].translate([0,0,-.18]) ^ body)
            else:
                capture['heel_hits_blind_floor']=positive_volume(local_leaf.translate([0,0,-.05]) ^ body)
            assert min(capture.values())>.001,(tag,capture)
            checks={"mounted":{},"insertion":{},"protected":{}}
            for name,part in parts.items():
                checks["mounted"][name+"_body"]=check(part,body)
                checks["mounted"][name+"_leaves"]=check(part,frame(all_leaves,near))
            # The pin travels with its axis guided through predrilled retention holes.
            for name,sweep in sweeps.items():
                checks["insertion"][name+"_vs_body"]=check(sweep,body)
                checks["insertion"][name+"_vs_leaves"]=check(sweep,frame(all_leaves,near))
            checks["mounted"]["screw_vs_key"]=check(parts['screw_envelope'],parts['shoulder_key'])
            checks["mounted"]["screw_vs_nut_envelopes"]=check(parts['screw_envelope'],parts['nut_envelope'])
            if near:
                checks['mounted']['screw_vs_backstop']=check(parts['screw_envelope'],parts['backstop'])
                checks['insertion']['backstop_vs_key']=check(sweeps['backstop'],parts['shoulder_key'])
            for name in ('shoulder_key','nut_envelope')+(('backstop',) if near else ()):
                checks['insertion']['screw_vs_'+name]=check(sweeps['screw'],parts[name])
            checks['insertion']['nut_vs_key']=check(sweeps['nut'],parts['shoulder_key'])
            if near:
                checks['insertion']['nut_vs_backstop']=check(sweeps['nut'],parts['backstop'])
            # Check every modification AND swept access against envelopes, including all four A anchors.
            change=union([added,removed,*parts.values()])
            access=union(list(sweeps.values()))
            for name,obj in reserve.items():
                if name in ('A_tail_sleeve','anchor_block') and (near or kind!='U4'):continue
                checks['protected'][name+'_change']=check(change,obj)
                checks['protected'][name+'_access']=check(access,obj)
            metrics['added_PA12_mm3']=round(added.volume(),4)
            metrics['removed_PA12_mm3']=round(removed.volume(),4)
            metrics['body_connected']=len(body.decompose())==1
            interior=box(-40,40,-40,40,3.001,16)
            metrics['boss_overlap_original_inboard_mm3']=round(positive_volume((boss ^ base) ^ interior),6)
            metrics['removed_original_inboard_mm3']=round(positive_volume(removed ^ interior),6)
            report['ends'][tag]={'dimensions':metrics,'capture_witness_mm3':capture,**checks}
            module=(module+world(boss,near))-world(cuts,near)
            if kind=='U1':
                export(coupon(body),tag+'_coupon')
                if near:
                    for name in ('shoulder_key','backstop'):export(parts[name],name)
                    report['STEP_reimport']=metal_steps(parts)
                # A separate NiTi end reference helps locate the shoulder on a physical test blade.
                export(local_leaf ^ box(0,16,18,32,0,13),tag+'_leaf_reference')
                plot_section(coupon(body),parts,local_leaf,tag)
            if tag=='U4_distal':
                plot_anchor(base,boss,parts,local_leaf,reserve,checks['protected'])
        # Both keys and the shoe out, feed a full 94 mm leaf straight in from the proximal end.
        envelope=swept([leaf],[0,0,-100])
        report['assembly'][kind+'_blade_feed']=check(envelope,module)
        report['assembly'][kind+'_blade_seated']=check(leaf,module)
    others=union([solid(s) for s in springs if not all(s.centroid[:2]>0)])
    report['assembly']['blade_feed_other_three_leaves']=check(envelope,others)
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    for group in report['ends'].values():
        for category in ('mounted','insertion','protected'):
            for label,result in group[category].items():
                assert result['overlap_mm3']<=1e-5,(label,result)
        assert group['dimensions']['body_connected']
        assert group['dimensions']['shoulder_overlap_mm2']>0
        assert group['dimensions']['key_inner_rail_bearing_mm2']>0
        assert group['dimensions']['boss_overlap_original_inboard_mm3']<=1e-5
        assert group['dimensions']['removed_original_inboard_mm3']<=1e-5
    for label,result in report['assembly'].items():
        assert result['overlap_mm3']<=1e-5,(label,result)


def plot_section(body,parts,leaf,tag):
    from matplotlib import pyplot as plt
    from matplotlib.patches import Patch
    fig,axs=plt.subplots(1,2,figsize=(11,5.8),layout='constrained')
    palette={'PA12':'#cbd6d8','NiTi':'#68438e','shoulder_key':'#df953a','backstop':'#188775',
             'screw_envelope':'#424e5e','nut_envelope':'#727781'}
    solids={'PA12':body,'NiTi':leaf,**parts}
    for ax,y,title in zip(axs,[26.4,SCREW_Y],['Through the NiTi shoulder','Through the retainer screw']):
        for label,m in solids.items():
            # +90 deg about X maps the original Y to new Z, original depth to negative new Y.
            plane=m.rotate([90,0,0]).slice(y)
            for poly in plane.to_polygons():
                xy=np.asarray(poly)
                signed=np.sum(xy[:,0]*np.roll(xy[:,1],-1)-xy[:,1]*np.roll(xy[:,0],-1))
                ax.fill(xy[:,0],-xy[:,1],color=palette[label] if signed>0 else 'white',ec='#39494c',lw=.6)
        ax.set(xlim=(2.8,12.9),ylim=(9,-.7),aspect='equal',xlabel='Module x (mm)',title=title)
        ax.set_ylabel('Depth from mating face (mm)')
        ax.grid(alpha=.13)
    fig.suptitle(tag.replace('_',' ')+'  |  actual end-disk section')
    fig.legend(handles=[Patch(facecolor=palette[n],label=n.replace('_envelope','').replace('_',' ')) for n in solids],
               loc='outside lower center',ncols=3)
    fig.savefig(OUT/(tag+'_sections.png'),dpi=165)
    plt.close(fig)


def plot_anchor(base,boss,parts,leaf,reserve,checks):
    from matplotlib import pyplot as plt
    from matplotlib.patches import Patch
    fig,ax=plt.subplots(figsize=(8,6.4),layout='constrained')
    def shade(section,color,alpha=1):
        for polygon in section.to_polygons():
            xy=np.asarray(polygon)
            winding=np.sum(xy[:,0]*np.roll(xy[:,1],-1)-xy[:,1]*np.roll(xy[:,0],-1))
            ax.fill(*xy.T,color=color if winding>0 else 'white',ec='#37494a',lw=.55,alpha=alpha)
    shade(base.slice(1.5),'#e1e7e8')
    shade(reserve['anchor_block'].slice(1.5),'#e9b9a7',.65)
    shade(base.slice(5.8),'#a8babc',.68)
    shade(boss.slice(4),'#a1c8bb')
    shade(leaf.slice(2),'#68438e')
    shade(parts['shoulder_key'].slice(4),'#df953a',.89)
    shade(parts['nut_envelope'].slice(7),'#64737f')
    ax.annotate('Key enters from +Y',xy=(6.7,30),xytext=(8.2,33.3),ha='center',
                arrowprops=dict(arrowstyle='->',color='#495954'))
    ax.annotate('Nut enters from +X',xy=(8.1,21.1),xytext=(14.5,19.4),ha='center',
                arrowprops=dict(arrowstyle='->',color='#495954'))
    ax.plot([3.5,4.15],[25,25],color='#212c31',lw=2)
    gap=checks['anchor_block_change']['gap_mm']
    ax.annotate(f'{gap:.2f} mm to reserved block',xy=(3.82,25),xytext=(9.4,15.8),
                arrowprops=dict(arrowstyle='->',color='#495954'))
    ax.set(xlim=(-4.8,19),ylim=(14.8,34.4),aspect='equal',xlabel='Module x (mm)',ylabel='Module y (mm)',
           title='U4 distal end  |  +Y anchor and the selected +X leaf')
    ax.grid(alpha=.14)
    ax.legend(handles=[Patch(color=c,label=l) for c,l in [('#e1e7e8','Original disk, d = 1.5 mm'),
        ('#e9b9a7','Reserved A anchor footprint'),('#a1c8bb','New joint boss, d = 4 mm'),
        ('#68438e','NiTi end, d = 2 mm'),('#df953a','Shoulder key, d = 4 mm'),
        ('#64737f','Square nut, d = 7 mm')]],loc='upper center',bbox_to_anchor=(.5,-.13),ncols=2)
    fig.savefig(OUT/'U4_anchor_access.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':
    build()
