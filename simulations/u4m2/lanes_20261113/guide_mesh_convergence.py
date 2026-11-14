"""Refine selected guided equilibria from 8 to 16 cells per module at equal tensions."""
import argparse,json
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states

def run(archive,mass,out):
    lanes.install((21,24,28),24,json.loads(mass.read_text()))
    from spatial_model import refine_seed
    from refine_steering import stationary
    coarse=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    fine=lanes.backbone.spatial_rod(4,2,[4,5,6],20,16)
    rows=[]
    for label,z,T,meta in load_states(archive)[0]:
        if label not in ['y0_z8','y90_z8','y175_z8']:continue
        x=stationary(fine,T,refine_seed(z,coarse,fine))
        if x is None:
            rows.append(dict(state=label,solved=False));continue
        m8,d8,w8=coarse.metrics(z,T,stability=True);m16,d16,w16=fine.metrics(x,T,stability=True)
        row=dict(state=label,solved=True,coarse=m8,fine=m16,head_difference_mm=float(np.linalg.norm(w16[-1]-w8[-1])*1000),
            yaw_difference_deg=float(m16['yaw_deg']-m8['yaw_deg']),elevation_difference_deg=float(m16['world_elevation_deg']-m8['world_elevation_deg']))
        rows.append(row);print(label,row['head_difference_mm'],row['yaw_difference_deg'],row['elevation_difference_deg'],flush=True)
    if len(rows)!=3:raise ValueError('Three requested states required')
    result=dict(scope='Same 500 g payload, CAD mass, lane radii and four guide stations; fixed tendon tensions, free-space stationary solves. Selected holds only; no full 16-cell closed-loop run.',rows=rows)
    out.write_text(json.dumps(result,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x))+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--mass',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.archive,a.mass,a.out)
