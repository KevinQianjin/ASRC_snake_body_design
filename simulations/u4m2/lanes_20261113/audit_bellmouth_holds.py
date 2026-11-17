"""Audit re-solved rope curves against the actual rigid M5/M6 end CAD.

Checks both complete curve endpoint closure and the finite 2 mm rope envelope
in the end regions |CAD z| >= 38 mm. Intended bore/fillet bearing is allowed
within the declared 0.005 mm mesh tolerance. This is sampled clearance, not a
contact-force FEA or a tolerance/strength qualification. Guide loads are ideal
point-guide reactions with simultaneous station resultants.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth,inspect_routing
from bellmouth_cad_check import Body
from state_archives import load_states

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def table(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def audit(archive,mass_file,out,max_seconds=1200.):
    start=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    design_path=ROOT/'cad/lanes_u4m2/end_bellmouth_v1/design.json'
    design=json.loads(design_path.read_text());mass=json.loads(mass_file.read_text())
    lanes.install((21,24,28),24,mass)
    rod=apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,8),design)
    states,coverage=load_states(archive)
    bodies={name:Body(design_path.parent/file) for name,file in [('M5','M5_lane_anchorB.stl'),('M6','M6_lane_anchorC.stl')]}
    exits_all=[];guides_all=[];stations=[];cache={}
    summary=dict(scope=__doc__,coverage=coverage,completed=False,sample_step_mm=.02,tolerance_mm=.005,
        cad_sha256={n:hashlib.sha256((design_path.parent/(f'{n}_lane_anchor'+('B.stl' if n=='M5' else 'C.stl'))).read_bytes()).hexdigest() for n in bodies})
    def save():
        if not exits_all:return
        fails=[r for r in exits_all if r['envelope_clearance_mm']<-.005]
        summary.update(elapsed_seconds=time.monotonic()-start,records=len(set(r['state'] for r in exits_all)),
            rope_exit_checks=len(exits_all),unique_geometry_states=len(cache),
            envelope_failing_checks=len(fails),envelope_failing_records=len(set(r['state'] for r in fails)),
            min_envelope_clearance_mm=min(r['envelope_clearance_mm'] for r in exits_all),
            max_endpoint_error_mm=max(r['endpoint_error_mm'] for r in exits_all),
            max_exit_angle_deg=max(r['exit_angle_deg'] for r in exits_all),
            min_design_margin_deg=min(r['design_margin_deg'] for r in exits_all),
            wrap_failing_checks=sum(not r['margin_pass'] for r in exits_all),
            max_fillet_resultant_n=max(r['fillet_resultant_n'] for r in exits_all),
            max_guide_hole_force_n=max(r['hole_force_n'] for r in guides_all),
            max_station_force_n=max(r['force_n'] for r in stations),
            max_station_moment_nmm=max(r['moment_nmm'] for r in stations))
        summary['worst_envelope']=min(exits_all,key=lambda r:r['envelope_clearance_mm'])
        summary['minimum_wrap_margin']=min(exits_all,key=lambda r:r['design_margin_deg'])
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        table(out/'rope_exits.csv',exits_all);table(out/'guide_holes.csv',guides_all);table(out/'guide_stations.csv',stations)
    for label,z,T,meta in states:
        if time.monotonic()-start>=max_seconds:
            summary['stop_reason']='audit time budget reached';save();return summary
        exits,guides=inspect_routing(rod,z,T,sample=True)
        key=z.tobytes()
        if key not in cache:
            records=[]
            for r in exits:
                pts=r['curve_cad_mm'];selected=pts[np.abs(pts[:,2])>=38.-1e-10]
                if len(selected)==0:raise ValueError('No end-region curve samples')
                sd=bodies[r['module']].signed(selected)
                idx=int(np.argmin(sd))
                records.append(dict(envelope_clearance_mm=float(sd[idx]-1.),
                    worst_cad_z_mm=float(selected[idx,2]),samples=len(selected)))
            cache[key]=records
        for r,cad in zip(exits,cache[key]):
            r={k:v for k,v in r.items() if not k.startswith('curve_')}
            exits_all.append(dict(state=label,source_state=meta.get('source_state',label),**r,**cad))
        for g in guides:guides_all.append(dict(state=label,**g))
        for module in ('M5','M6'):
            for station in (-24.,-12.,12.,24.):
                group=[g for g in guides if g['module']==module and g['station_z_mm']==station]
                force=np.sum([g['force_base_n'] for g in group],axis=0)
                moment=np.sum([g['moment_base_nmm'] for g in group],axis=0)
                stations.append(dict(state=label,module=module,station_z_mm=station,
                    force_n=float(np.linalg.norm(force)),moment_nmm=float(np.linalg.norm(moment)),
                    force_base_n=force.tolist(),moment_base_nmm=moment.tolist()))
        save();print(label,'minimum_envelope_mm',round(min(x['envelope_clearance_mm'] for x in cache[key]),7),flush=True)
    summary['completed']=True;save();return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path)
    p.add_argument('--mass',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-seconds',type=float,default=1200.)
    a=p.parse_args();audit(a.archive,a.mass,a.out,a.max_seconds)
