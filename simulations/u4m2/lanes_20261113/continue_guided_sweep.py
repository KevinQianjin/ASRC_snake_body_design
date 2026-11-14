"""Fine-mesh one-degree continuation near a failed large-yaw coarse seed."""
import argparse,json
from pathlib import Path
import numpy as np
import lanes

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--start',type=int,required=True);ap.add_argument('--end',type=int,default=175);ap.add_argument('--radii',nargs=3,type=float,default=(21,24,27));a=ap.parse_args()
    lanes.install(a.radii,24.)
    from min_force_sweep import min_force,accept
    r=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    p=a.folder/'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'
    with np.load(p) as data:states={k:data[k].copy() for k in data.files}
    z=states[f'y{a.start}_z8'];T=states[f'y{a.start}_T8'];records=[]
    for yaw in range(a.start+1,a.end+1):
        z,T,info=min_force(r,z,T,yaw,20,maxiter=120,pretension=3,exact=True,smooth=1.,Cprev=T)
        ok,m=accept(r,z,T,yaw,20,1.)
        records.append(dict(yaw_target_deg=yaw,accepted=bool(ok),metrics=m,optimisation=info,tensions_n=T.tolist()))
        (a.folder/'fine_continuation.json').write_text(json.dumps(records,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else float(x)))
        print(yaw,'accepted',ok,'peak',float(T.max()),'residual',m['equilibrium_residual'],flush=True)
        if not ok:raise SystemExit(f'No accepted fine equilibrium at yaw {yaw}')
        states[f'y{yaw}_z8']=z;states[f'y{yaw}_T8']=T;np.savez_compressed(p,**states)
