"""Compare endpoint closure on saved V3 poses and plot the re-solved changes.

The previous CAD check built an outgoing ray from an estimated angle without
enforcing its intersection with the prescribed guide centre. This comparison
measures that geometric mismatch; it is not a new physical guide-contact test.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth,sample_span
from end_bellmouth_kernel import span_geometry
from state_archives import load_states

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def compare(archive,solved_folder,out):
    out.mkdir(parents=True,exist_ok=False)
    design=json.loads((ROOT/'cad/lanes_u4m2/end_bellmouth_v1/design.json').read_text())
    mass=json.loads((solved_folder/'mass_model.json').read_text())
    lanes.install((21,24,28),24,mass)
    rod=apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,8),design)
    states,coverage=load_states(archive);rows=[];worst=None;per_rope={}
    for label,z,T,meta in states:
        d=rod.evaluate(z,T,detail=True)[2];p,F=d['points'],d['frames']
        for j in (4,5):
            for k in ((1,2) if j==4 else (2,)):
                for ray in range(4):
                    off=rod.offsets3[k,ray]
                    for ei,end in enumerate(('proximal','distal')):
                        node=j*rod.sub if ei==0 else (j+1)*rod.sub
                        guide=node+rod.sub//4 if ei==0 else node-rod.sub//4
                        sign=1. if ei==0 else -1.
                        G=p[guide]+F[guide]@off
                        local=F[node].T@(G-p[node])-off
                        x,rho=sign*local[0],np.linalg.norm(local[1:])
                        pr=rod.bellmouth_profiles[j-4,ei];depth,wall,td,hole,rope=pr
                        theta=np.arctan2(rho,x-depth)
                        s0=depth-wall*np.sin(td);rc=wall+rope;cy=wall+hole
                        tip=np.array([s0+rc*np.sin(theta),cy-rc*np.cos(theta)])
                        direction=np.array([np.cos(theta),np.sin(theta)])
                        delta=np.array([x,rho])-tip
                        miss=abs(delta[0]*direction[1]-delta[1]*direction[0])*1000.
                        length,_,ti,to,contact=span_geometry(local,sign,pr)
                        rec=dict(state=label,module=f'M{j+1}',end=end,set='ABC'[k],
                            ray=('up','right','down','left')[ray],previous_ray_to_guide_miss_mm=float(miss),
                            previous_exit_angle_deg=float(np.degrees(theta)),connected_exit_angle_deg=float(np.degrees(to)),
                            connected_span_length_increase_mm=float((length-np.linalg.norm(local))*1000.))
                        rows.append(rec)
                        key=(label,k,ray);per_rope[key]=per_rope.get(key,0.)+rec['connected_span_length_increase_mm']
                        if worst is None or miss>worst['record']['previous_ray_to_guide_miss_mm']:
                            worst=dict(record=rec,local=local.tolist(),profile=pr.tolist(),sign=sign,
                                previous_tip=tip.tolist(),previous_direction=direction.tolist())
    with (out/'endpoint_comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    summary=dict(scope=__doc__,coverage=coverage,checks=len(rows),
        maximum_previous_ray_to_guide_miss_mm=max(r['previous_ray_to_guide_miss_mm'] for r in rows),
        rays_missing_guide_centre_by_over_0p3_mm=sum(r['previous_ray_to_guide_miss_mm']>.3 for r in rows),
        per_rope_length_increase_at_saved_geometry_mm=dict(min=min(per_rope.values()),max=max(per_rope.values())),
        worst=worst)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot(worst,solved_folder,out)
    return summary


def plot(worst,solved_folder,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.fonttype':'none','font.family':'DejaVu Sans','axes.unicode_minus':False})
    local=np.array(worst['local']);pr=np.array(worst['profile']);sign=worst['sign']
    depth,wall,td,hole,rope=pr;s0=depth-wall*np.sin(td)
    curve=sample_span(local,sign,pr)
    x=sign*curve[:,0]*1000.;y=np.linalg.norm(curve[:,1:],axis=1)*1000.
    wx=np.linspace(0.,depth,400);wy=np.where(wx<=s0,hole,hole+wall-np.sqrt(np.maximum(0.,wall**2-(wx-s0)**2)))
    fig,ax=plt.subplots(figsize=(9,4.8),layout='constrained')
    ax.plot(wx*1000.,wy*1000.,color='#c58a22',lw=3,label='Fillet wall (published CAD parameters)')
    ax.plot(x,y,color='#15824a',lw=2,label='Connected tangent / arc path')
    ax.plot([0.,x[-1]],[0.,y[-1]],':',color='#888888',label='Original interface chord')
    tip=np.array(worst['previous_tip'])*1000.;v=np.array(worst['previous_direction'])
    end=tip+(x[-1]-tip[0])/v[0]*v
    ax.plot([tip[0],end[0]],[tip[1],end[1]],'--',color='#b34235',label='Previous CAD-check outgoing ray')
    ax.scatter([0.,x[-1]],[0.,y[-1]],s=35,color='#1a5b9e',zorder=5)
    ax.annotate('Interface centre',(0.,0.),xytext=(18,16),textcoords='offset points')
    ax.annotate('Actual guide centre',(x[-1],y[-1]),xytext=(-130,12),textcoords='offset points')
    ax.set(xlabel='Distance into module from interface (mm)',ylabel='Radial displacement from bore axis (mm)',
        title=f"Endpoint closure: state {worst['record']['state']}, {worst['record']['module']} {worst['record']['end']}")
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(out/'endpoint_closure.svg',metadata={'Date':None,'Description':'Rope centreline comparison; the rope radius is 1 mm.'})
    fig.savefig('/tmp/asrc_endpoint_closure.png',dpi=140);plt.close(fig)
    data=json.loads((solved_folder/'summary.json').read_text());rows=[r for r in data['rows'] if r['solved']]
    yaw=np.array([r['baseline']['yaw_deg'] for r in rows]);yaw=(yaw+180.)%360.-180.
    fig,axs=plt.subplots(3,1,figsize=(9,8),sharex=True,layout='constrained')
    for ax,key,label in zip(axs,('head_change_mm','yaw_change_deg','elevation_change_deg'),
                            ('Head displacement (mm)','Yaw change (deg)','Elevation change (deg)')):
        ax.scatter(yaw,[r[key] for r in rows],s=13,alpha=.65,color='#2064a0');ax.set_ylabel(label);ax.grid(alpha=.2)
    axs[0].set_title('500 g head: 217 selected fixed-winch equilibria\nReconstructed V3 rest lengths; constrained bellmouth routing')
    axs[-1].set_xlabel('Baseline head yaw (deg)')
    fig.savefig(out/'pose_changes.svg',metadata={'Date':None,'Description':'Selected-state comparison, not a full controller replay.'})
    fig.savefig('/tmp/asrc_pose_changes.png',dpi=120);plt.close(fig)
    # Matplotlib emits trailing spaces in SVG path attributes. Keep equivalent
    # XML geometry while making generated artifacts pass the Git whitespace gate.
    for path in out.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path)
    p.add_argument('--solved',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(compare(a.archive,a.solved,a.out),indent=2))
