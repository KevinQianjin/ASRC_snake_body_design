import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,time
from pathlib import Path
import numpy as np
from rope_planar import PlanarRod,HERE
from run_rope_sweep import search_case,jsonable,write_json

def main():
    output=HERE/'reference_validation';output.mkdir(exist_ok=True)
    report=[]
    for front in range(5,12):
        d=round(front*8/11);counts=(8,12,d,front-d)
        rod=PlanarRod(counts,4)
        found,trials=search_case(rod,{})
        for name,(fine,cand) in found.items():
            row=dict(front=front,counts=counts,target=name,found=cand is not None,trials=trials[name])
            if cand is not None:
                x,D,_=cand['solution'];common=cand['common'];met=cand['metrics']
                refined=PlanarRod(counts,16);xx=np.zeros(refined.ndof)
                xx[::2]=np.interp(np.linspace(0,1,refined.m+1)[1:],np.linspace(0,1,fine.m+1),np.r_[0,x[::2]])
                xx[1::2]=np.repeat(x[1::2],2)
                kind='level' if name=='level' else 'arc';sense=-1 if name=='down' else 1
                sol=refined.inverse(kind,sense,common,initial=(xx,D,{}),maxiter=70)
                row['fine_refinement_converged']=sol is not None
                row['metrics_8_cells']=met
                if sol is not None:
                    m,dat,H=refined.shape_metrics(*sol[:2],common)
                    row.update(metrics_16_cells=m,tension_change_n=abs(m['total_tension_n']-met['total_tension_n']),
                        head_position_change_mm=float(np.hypot(m['head_x_mm']-met['head_x_mm'],m['head_y_mm']-met['head_y_mm'])),
                        arc_error_change_mm=abs(m['semicircle_max_error_mm']-met['semicircle_max_error_mm']),
                        core_stress_change_mpa=abs(m['max_core_stress_mpa']-met['max_core_stress_mpa']))
                np.savez_compressed(output/f'F{front:02d}_{name}.npz',state=x,tensions=fine.tensions(D,common),
                                    points=fine.evaluate(x,detail=True)[3]['points'])
            report.append(row)
            print(json.dumps({k:v for k,v in row.items() if not k.startswith('metrics')},default=jsonable),flush=True)
    write_json(output/'reference_cases.json',report)
    good=[r for r in report if r.get('fine_refinement_converged')]
    summary=dict(reference_targets=21,found=sum(r['found'] for r in report),
        refinement_failures=sum(r['found'] and not r.get('fine_refinement_converged',False) for r in report),
        max_tension_change_n=max(r['tension_change_n'] for r in good),
        max_position_change_mm=max(r['head_position_change_mm'] for r in good),
        max_arc_error_change_mm=max(r['arc_error_change_mm'] for r in good),
        max_core_stress_change_mpa=max(r['core_stress_change_mpa'] for r in good))
    summary['passed']=bool(summary['refinement_failures']==0 and summary['max_tension_change_n']<.02
                           and summary['max_position_change_mm']<1. and summary['max_core_stress_change_mpa']<.1)
    write_json(output/'validation_summary.json',summary);print(json.dumps(summary),flush=True)
    return 0 if summary['passed'] else 2

if __name__=='__main__':raise SystemExit(main())
