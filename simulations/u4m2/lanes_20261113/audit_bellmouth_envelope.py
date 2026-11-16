"""Selected-state tank envelope, tension and strain checks after end routing.

Use recorded clamp depth where available. Startup holds are explicitly placed
at -750 mm and inverse steering holds at +15 mm, following the existing study.
The 63 mm head/front envelope and 1.5 mm sampling/mesh allowance are retained.
This is not a full command replay, a continuous collision proof or actual head CAD.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth
from length_cycle import FastTank
from tank3d_screen import to_tank
from state_archives import load_states


def find_recorded_depth(meta):
    if isinstance(meta,dict):
        if 'clamp_s_mm' in meta:return float(meta['clamp_s_mm'])
        for value in meta.values():
            result=find_recorded_depth(value)
            if result is not None:return result
    return None


def audit(folder,out):
    out.mkdir(parents=True,exist_ok=False)
    mass=json.loads((folder/'mass_model.json').read_text());design=json.loads((folder/'design.json').read_text())
    lanes.install((21,24,28),24,mass)
    rod=apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,8),design)
    states,coverage=load_states(folder/'equilibria_states.npz');tank=FastTank();rows=[]
    for label,z,T,meta in states:
        phase=meta['phase'];depth=find_recorded_depth(meta)
        placement='recorded clamp_s_mm'
        if depth is None:
            if phase=='startup':depth=-750.;placement='explicit startup-hold placement'
            elif phase=='inverse':depth=15.;placement='explicit inverse-hold placement'
            else:raise ValueError('No known clamp placement for '+label)
        metric,detail,world=rod.metrics(z,T)
        points=to_tank(world*1000.,rod.pitch,depth,tank.entry_h)
        gap,critical,fraction=tank.clearance(points)
        rows.append(dict(state=label,source_state=meta['source_state'],phase=phase,clamp_s_mm=depth,placement=placement,
            clearance_mm=gap,allowance_adjusted_clearance_mm=gap-1.5,clearance_pass=bool(gap-1.5>=5.),
            minimum_tension_n=float(T.min()),maximum_tension_n=float(T.max()),
            tension_2p5_to_250_n_pass=bool(T.min()>=2.5 and T.max()<=250.),
            maximum_axial_strain=metric['max_abs_axial_strain'],strain_pass=metric['strain_5percent_pass'],
            geometry_pass=metric['geometry_pass'],head_tank_mm=points[-1].tolist(),
            critical_tank_point_mm=critical.tolist(),critical_arclength_fraction=fraction))
    summary=dict(scope=__doc__,coverage=coverage,tank_sha256=tank.sha,records=len(rows),
        phase_counts=dict(Counter(r['phase'] for r in rows)),
        recorded_depth_records=sum(r['placement']=='recorded clamp_s_mm' for r in rows),
        minimum_clearance_mm=min(r['clearance_mm'] for r in rows),
        minimum_allowance_adjusted_clearance_mm=min(r['allowance_adjusted_clearance_mm'] for r in rows),
        clearance_failures=sum(not r['clearance_pass'] for r in rows),
        minimum_tension_n=min(r['minimum_tension_n'] for r in rows),
        maximum_tension_n=max(r['maximum_tension_n'] for r in rows),
        tension_failures=sum(not r['tension_2p5_to_250_n_pass'] for r in rows),
        maximum_axial_strain=max(r['maximum_axial_strain'] for r in rows),
        strain_failures=sum(not r['strain_pass'] for r in rows),geometry_failures=sum(not r['geometry_pass'] for r in rows),
        rows=rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('scope','rows')},indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();audit(a.folder,a.out)
