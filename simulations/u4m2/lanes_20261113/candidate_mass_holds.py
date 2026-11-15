"""Re-solve archived 500 g held states at fixed tensions with candidate CAD mass.

This isolates the mass change; guide positions and homogenised stiffness remain
ideal. It is not a full closed-loop replay or a mount/contact structural model.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states
from refine_steering import stationary


def run(archive, baseline_mass, candidate_mass, out, max_seconds):
    start=time.monotonic();out.mkdir(parents=True,exist_ok=True)
    baseline=json.loads(baseline_mass.read_text());candidate=json.loads(candidate_mass.read_text())
    geometry=candidate_mass.parent/'geometry_check.json'
    if geometry.exists() and not json.loads(geometry.read_text())['all_straight_positions_clear']:
        raise ValueError('Candidate geometry is rejected; do not promote its mass model to a new equilibrium study')
    (out/'baseline_mass.json').write_bytes(baseline_mass.read_bytes())
    (out/'candidate_mass.json').write_bytes(candidate_mass.read_bytes())
    lanes.install((21,24,28),24,baseline)
    before=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    lanes.install((21,24,28),24,candidate)
    after=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    saved=[];saved_tensions=[];saved_meta=[];rows=[];states,coverage=load_states(archive)
    result=dict(scope=__doc__,payload_g=500,archive=str(archive),
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        mass_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (baseline_mass,candidate_mass)},
        mass_change_g=(1000*(np.array(candidate['module_mass_kg'])-baseline['module_mass_kg'])).tolist(),
        source_coverage=coverage,rows=rows,completed=False)
    def save():
        result['elapsed_seconds']=time.monotonic()-start
        (out/'summary.json').write_text(json.dumps(result,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x))+'\n')
        np.savez_compressed(out/'mass_holds_states.npz',z=np.asarray(saved),tensions_n=np.asarray(saved_tensions))
        (out/'mass_holds.json').write_text(json.dumps(saved_meta,indent=2)+'\n')
    for label,z,T,meta in states:
        if time.monotonic()-start>=max_seconds:
            result['stop_reason']='study time budget reached';save();return result
        old=before.metrics(z,T,stability=True)[0]
        x=stationary(after,T,z)
        if x is None:
            rows.append(dict(state=label,solved=False));save();continue
        new,_,world=after.metrics(x,T,stability=True)
        old_world=before.metrics(z,T,stability=False)[2]
        row=dict(state=label,solved=True,baseline=old,candidate=new,
            head_change_mm=float(np.linalg.norm(world[-1]-old_world[-1])*1000),
            yaw_change_deg=float(new['yaw_deg']-old['yaw_deg']),
            elevation_change_deg=float(new['world_elevation_deg']-old['world_elevation_deg']))
        rows.append(row);saved.append(x);saved_tensions.append(T)
        saved_meta.append(dict(source_state=label,source_metadata=meta,phase=meta.get('phase','inverse'),tensions_n=T.ravel().tolist()))
        save();print(label,'head change mm',row['head_change_mm'],flush=True)
    result['completed']=True
    result['all_states_solved']=all(r['solved'] for r in rows)
    save();return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('--baseline-mass',type=Path,required=True)
    p.add_argument('--candidate-mass',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-seconds',type=float,default=600)
    a=p.parse_args();run(a.archive,a.baseline_mass,a.candidate_mass,a.out,a.max_seconds)
