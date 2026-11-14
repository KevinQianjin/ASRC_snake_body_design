"""Save inspectable rope-centre penetration points at a run's worst end-region state."""
import argparse,json
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states
from guide_path_audit import FlexureDistance,map_cad,RAYS

def inspect(root,radii,cad):
    summary=json.loads((root/'path_audit/summary.json').read_text())
    loc=summary.get('worst_end_region_penetration_state')
    if loc is None:return
    states,coverage=load_states(Path(loc['archive']))
    label,z,T,meta=next(s for s in states if s[0]==loc['state'])
    lanes.install(radii,24);r=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    d=r.evaluate(z,T,detail=True)[2];records=[]
    for j,filename in [(4,'M5_lane_anchorB.stl'),(5,'M6_lane_anchorC.stl')]:
        body=FlexureDistance(cad/filename);body.update(map_cad(body.mesh.vertices,j,r,d))
        nodes=np.array([0,2,3,5,6,8])+j*8
        for k in ([1,2] if j==4 else [2]):
            for ray in range(4):
                P=d['points'][nodes]+np.einsum('nij,j->ni',d['frames'][nodes],r.offsets3[k,ray])
                samples=[];axial=[]
                for span,(a,b) in enumerate(zip(P[:-1],P[1:])):
                    n=max(1,int(np.ceil(np.linalg.norm(b-a)*1000)));t=np.linspace(0,1,n+1)
                    samples.extend(a+t[:,None]*(b-a))
                    axial.extend((nodes[span]-j*8)*12-48+t*(nodes[span+1]-nodes[span])*12)
                samples=np.array(samples);body.distances(samples)
                for point in body.last_end_details:
                    i=point['sample_index']
                    records.append(dict(module=f'M{j+1}',set=('A','B','C')[k],ray=RAYS[ray],tension_n=float(T[k,ray]),
                        center_base_mm=(samples[i]*1000).tolist(),approximate_axial_station_mm=float(axial[i]),**point))
    result=dict(scope='Sampled rope-centre points inside the closed beam-mapped end region. Positive depth is to the nearest full body surface. No finite-rope contact force or swept contact solution is calculated.',
        source=loc,archive_coverage=coverage,points=records)
    (root/'path_audit/end_region_example.json').write_text(json.dumps(result,indent=2)+'\n')
    print('End-region example points:',len(records))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--radii',type=float,nargs=3,required=True);p.add_argument('--cad',type=Path,required=True)
    a=p.parse_args();inspect(a.root,a.radii,a.cad)
