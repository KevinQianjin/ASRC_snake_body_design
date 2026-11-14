"""Boolean interference screen of rigid guides against beam-mapped M-body CAD.

Selected equilibrium poses only, not solid FEA or a complete contact path proof.
Any positive overlap rejects this rigid mounting candidate. Contact forces and
changes in module stiffness are not calculated by this kinematic screen.
"""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import trimesh
import lanes
from guide_path_audit import map_cad
from state_archives import load_states


def audit(archive,cad,out,labels):
    lanes.install((21,24,28),24)
    rod=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    states,coverage=load_states(archive)
    selected=[s for s in states if s[0] in labels]
    if len(selected)!=len(set(labels)):raise ValueError('Missing requested audit poses')
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for label,z,T,meta in selected:
        details=rod.evaluate(z,T,detail=True)[2]
        for j,kind in [(4,'M5'),(5,'M6')]:
            body=trimesh.load_mesh(cad/('M5_lane_anchorB.stl' if j==4 else 'M6_lane_anchorC.stl'))
            body.vertices=map_cad(body.vertices,j,rod,details)*1000
            for station in [-24,-12,12,24]:
                tag=f'{kind}_z{station:+d}'
                assembly=trimesh.util.concatenate([trimesh.load_mesh(cad/f'{tag}_{s}.stl') for s in ['guide','caps','wire_envelope']])
                node=j*8+(station+48)//12
                v=assembly.vertices
                assembly.vertices=(details['points'][node]+np.c_[v[:,2],v[:,1],-v[:,0]]/1000@details['frames'][node].T)*1000
                overlap=trimesh.boolean.intersection([body,assembly],engine='manifold')
                volume=0. if overlap.is_empty else float(overlap.volume)
                row=dict(state=label,part=tag,overlap_mm3=volume,pass_interference=volume<1e-6)
                rows.append(row);print(row,flush=True)
                # One inspectable failure geometry, in solver coordinates (mm).
                if label=='y90_z8' and tag=='M5_z-12':
                    body.export(out/'bent_M5_body.stl');assembly.export(out/'bent_M5_z-12_guide.stl')
                    if not overlap.is_empty:overlap.export(out/'bent_M5_z-12_overlap.stl')
    result=dict(scope=__doc__,archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        coverage=coverage,selected_states=labels,rows=rows,all_selected_poses_clear=all(r['pass_interference'] for r in rows),
        maximum_overlap_mm3=max(r['overlap_mm3'] for r in rows),
        decision='Do not release rigid saddle mounting for manufacture. Resolve motion interference and mount-induced stiffness before hardware tests.')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path)
    p.add_argument('--cad',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--states',nargs='+',default=['y0_z8','y90_z8','y175_z8'])
    a=p.parse_args();audit(a.archive,a.cad,a.out,a.states)
