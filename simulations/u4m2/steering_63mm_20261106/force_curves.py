"""Actual force continuations, not lines connecting unrelated optimum controls."""
import argparse,json
import numpy as np
from spatial_model import SpatialDatabaseRod,dump,write_csv
from search_steering import OUT
from refine_steering import stationary,score

def run(u,m):
    rows=json.loads((OUT/f'U{u}_M{m}_maximums.json').read_text())
    states=np.load(OUT/f'U{u}_M{m}_selected_states.npz');curves=[]
    for row in rows:
        if row.get('direction') not in ['right','up','down'] or not row.get('qualifies'):continue
        sid=row['state_id'];r=SpatialDatabaseRod(u,m,row['anchors'],sub=4)
        fine=SpatialDatabaseRod(u,m,row['anchors'],sub=8)
        q=(states[sid+'_z']/fine.scale).reshape(-1,4)
        # Sum child rotations and average strain for an initial guess only;
        # all curve points are subsequently solved to force equilibrium.
        qc=q.reshape(r.m,2,4).sum(axis=1);qc[:,3]/=2
        seed=qc.ravel()*r.scale;T=states[sid+'_T']
        for fraction in np.linspace(1,0,11):
            z=stationary(r,T*fraction,seed)
            if z is None:
                curves.append(dict(configuration=r.label,direction=row['direction'],strain_mode=row['strain_mode'],fraction=float(fraction),converged=False));continue
            seed=z;metric,_,_=r.metrics(z,T*fraction,stability=True)
            metric.update(direction=row['direction'],strain_mode=row['strain_mode'],state_id=sid,fraction=float(fraction),converged=True,
                directional_angle_deg=score(metric,row['direction']),curve_scope='Four cells per module; fixed force allocation scaled along one equilibrium branch, not reoptimized at each force')
            curves.append(metric)
        print(r.label,row['direction'],row['strain_mode'],'force continuation completed',flush=True)
        dump(OUT/f'U{u}_M{m}_force_curves.json',curves);write_csv(OUT/f'U{u}_M{m}_force_curves.csv',curves)
    dump(OUT/f'U{u}_M{m}_force_curve_completion.json',dict(completed=True,records=len(curves)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--u',type=int);p.add_argument('--m',type=int);a=p.parse_args();run(a.u,a.m)
