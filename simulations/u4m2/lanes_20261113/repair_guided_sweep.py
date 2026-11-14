"""Recover missing fine-mesh yaw knots using neighbouring accepted fine states.

Records every optimisation attempt; never fills a missing state by interpolation.
The four-cell seed has different guide stations, so it can land on a poor branch.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import lanes

def run(folder,radii,yaws=None):
    lanes.install(radii,24.)
    from min_force_sweep import min_force, accept
    r=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    file=folder/'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'
    with np.load(file) as data:states={k:data[k].copy() for k in data.files}
    attempts=[]
    for yaw in (range(0,176,5) if yaws is None else yaws):
        if f'y{yaw}_z8' in states:continue
        neighbours=sorted([int(k[1:-3]) for k in states if k.endswith('_z8')],key=lambda y:abs(y-yaw))
        passed=False
        for seed in neighbours[:4]:
            z0=states[f'y{seed}_z8'];T0=states[f'y{seed}_T8']
            z,T,info=min_force(r,z0,T0,yaw,20,maxiter=300,pretension=3,exact=True,smooth=1,Cprev=T0)
            ok,m=accept(r,z,T,yaw,20,1.)
            attempts.append(dict(target_yaw_deg=yaw,seed_yaw_deg=seed,accepted=bool(ok),optimisation=info,metrics=m))
            (folder/'sweep_repairs.json').write_text(json.dumps(attempts,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x)))
            print('repair',yaw,'seed',seed,'accepted',ok,'peak',float(T.max()),flush=True)
            if ok:
                states[f'y{yaw}_z8']=z;states[f'y{yaw}_T8']=T
                np.savez_compressed(file,**states);passed=True;break
        (folder/'sweep_repairs.json').write_text(json.dumps(attempts,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x)))
        if not passed:raise RuntimeError(f'No accepted equilibrium at {yaw} degrees')
    print('Requested missing fine-mesh yaw states recovered',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--radii',type=float,nargs=3,default=(21,24,27))
    ap.add_argument('--yaw',type=int,nargs='+',help='only recover these missing yaw knots')
    a=ap.parse_args();run(a.folder,a.radii,a.yaw)
