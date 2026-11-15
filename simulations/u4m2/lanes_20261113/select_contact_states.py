"""Reproducible targeted contact subset of the saved V2 500 g trajectory.

Includes all startup/inverse holds, each phase's endpoints and angle-range
samples, and recorded motion extrema. This does not certify unsampled motion.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from state_archives import load_states


def select(root, out, extra_motion_samples=0, seed=20261115):
    out.mkdir(parents=True,exist_ok=True)
    chosen={};coverage=[]
    def add(path,state,reason):
        label,z,T,meta=state
        key=(str(path),label)
        if key in chosen: chosen[key]['selection_reasons'].append(reason);return
        chosen[key]=dict(archive=str(path),source_state=label,z=z,T=T,
            phase=meta.get('phase','inverse' if label.startswith('y') else 'startup'),
            source_metadata=meta,selection_reasons=[reason])
    for filename in ('startup_niti18_E40_p20_pre3_states.npz',
                     'minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'):
        p=root/'inverse'/filename;states,c=load_states(p);coverage.append(c)
        for state in states:add(p,state,'all saved startup or inverse holds')
    for filename in ('nominal_states.npz','nominal_trace_states.npz'):
        p=root/'closed_loop'/filename;states,c=load_states(p);coverage.append(c)
        phases=sorted({s[3]['phase'] for s in states})
        for phase in phases:
            group=[s for s in states if s[3]['phase']==phase]
            add(p,group[0],'phase start');add(p,group[-1],'phase end')
            if filename=='nominal_states.npz':
                lo=min(s[3]['yaw_deg'] for s in group);hi=max(s[3]['yaw_deg'] for s in group)
                for target in np.arange(np.ceil(lo/15)*15,hi+.001,15):
                    add(p,min(group,key=lambda s:abs(s[3]['yaw_deg']-target)),f'nearest {target:g} deg yaw within phase')
        if filename=='nominal_trace_states.npz':
            for field,mode in [('peak_tension_n','max'),('minimum_tension_n','min'),('clearance_mm','min'),
                               ('minimum_eigenvalue','min'),('strain','max'),('node_move_mm','max')]:
                fn=max if mode=='max' else min
                add(p,fn(states,key=lambda s:s[3][field]),f'{mode} {field} in recorded motion')
            for field in ('yaw_error_deg','elevation_error_deg'):
                add(p,max(states,key=lambda s:abs(s[3][field])),f'max absolute {field} in recorded motion')
            # Rod scaling is constant per component, so state extrema identify
            # the same locations as strain/rotation extrema within each DOF.
            Z=np.array([s[1] for s in states])
            for component in range(32*4,48*4):
                for index in (np.argmin(Z[:,component]),np.argmax(Z[:,component])):
                    add(p,states[int(index)],f'M-cell DOF {component} extremum')
    if extra_motion_samples:
        existing={r['z'].tobytes() for r in chosen.values()}
        pool=[]
        # At this point states/p refer to the motion-trace archive. Select
        # geometries unseen by the initial targeted set, before new CAD checks.
        for state in states:
            key=state[1].tobytes()
            if key not in existing:
                pool.append(state);existing.add(key)
        if len(pool)<extra_motion_samples: raise ValueError('Insufficient independent motion geometries')
        for index in sorted(np.random.default_rng(seed).choice(len(pool),extra_motion_samples,replace=False)):
            add(p,pool[int(index)],f'additional deterministic unseen motion sample; seed {seed}')
    rows=list(chosen.values())
    # Keep provenance for distinct archive records, even when geometries repeat.
    np.savez_compressed(out/'selected_states.npz',z=np.array([r['z'] for r in rows]),tensions_n=np.array([r['T'] for r in rows]))
    metadata=[{k:v for k,v in r.items() if k not in ('z','T')} for r in rows]
    (out/'selected.json').write_text(json.dumps(metadata,indent=2)+'\n')
    result=dict(scope=__doc__,source_coverage=coverage,selected_records=len(rows),extra_motion_samples=extra_motion_samples,extra_sample_seed=seed,
                unique_geometries=len({r['z'].tobytes() for r in rows}),
                phase_counts={p:sum(r['phase']==p for r in rows) for p in sorted({r['phase'] for r in rows})})
    (out/'selection_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--extra-motion-samples',type=int,default=0);p.add_argument('--seed',type=int,default=20261115)
    a=p.parse_args();select(a.root,a.out,a.extra_motion_samples,a.seed)
