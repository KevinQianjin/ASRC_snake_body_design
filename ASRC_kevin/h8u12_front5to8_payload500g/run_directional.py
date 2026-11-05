"""Search loaded spatial equilibrium branches in all four bend directions.

The maximum is reported ONLY if the 205 MPa/self-contact/stability constraints
are satisfied. An empty searched admissible set is not a zero-degree maximum.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,argparse,time,concurrent.futures,multiprocessing
import numpy as np
from pathlib import Path
from spatial_rod import SpatialRod
from payload_planar import PayloadPlanarRod
from rope_planar import HERE
from run_rope_sweep import write_json

DRIVE=[0.,.25,.5,1.,2.,4.,6.,8.,10.,12.,16.,24.,32.,48.,64.]
SIDE_VERTICAL_BIAS=[-4.,0.,4.,8.,12.,16.]
COMMON=[0.,4.]

def tension(direction,drive,bias=0.,common=0.):
    T=np.ones(4)*common/2
    T[dict(up=0,down=2,right=1,left=3)[direction]]+=drive
    if direction in ['left','right']:
        T[0]+=max(bias,0.);T[2]+=max(-bias,0.)
    else:T[1]+=bias/2;T[3]+=bias/2
    return T

def process(counts):
    out=HERE/'results/directional';out.mkdir(parents=True,exist_ok=True)
    label='-'.join(f'{k}{v}' for k,v in zip('HUDL',counts));file=out/(label+'.json')
    if file.exists():return json.loads(file.read_text())['summary']
    start=time.monotonic();sub=2;r=SpatialRod(counts,sub)
    planar=PayloadPlanarRod(counts,sub);x=planar.free_equilibrium()
    if x is None:raise RuntimeError('Could not establish loaded free-sag seed '+label)
    initial=r.lift_planar(x);rows=[];states=[];boundaries={};attempted=0;converged=0
    for direction in ['up','down','right','left']:
        best=None;closest=None;bestz=None;closez=None
        biases=[0.,4.,16.] if direction in ['up','down'] else SIDE_VERTICAL_BIAS
        for common in COMMON:
            for bias in biases:
                previous=initial
                for drive in DRIVE:
                    T=tension(direction,drive,bias,common);attempted+=1
                    sol=r.solve(T,previous,maxiter=300)
                    if sol is None:continue
                    previous=sol[0];converged+=1
                    metric,data=r.metrics(previous,T)
                    metric.update(combination=label,front_modules=sum(counts[2:]),direction=direction,drive_n=drive,vertical_or_side_bias_n=bias,common_n=common,cells_per_module=sub)
                    metric['axial_strain_exceeds_5_percent']=max(metric['max_axial_compression'],metric['max_axial_extension'])>.05
                    signed=metric['front_up_projected_deg'] if direction in ['up','down'] else metric['front_side_projected_deg']
                    metric['directional_angle_deg']=signed*(1 if direction in ['up','right'] else -1)
                    metric['qualifies']=False
                    geometry_ok=metric['passes_self_envelope_screen']
                    if geometry_ok and (closest is None or metric['max_core_stress_mpa']<closest['max_core_stress_mpa']):closest=metric;closez=previous.copy()
                    if geometry_ok and metric['passes_reference_yield']:
                        checked,_=r.metrics(previous,T,stability=True);metric.update(checked)
                        metric['qualifies']=bool(metric['stable_spatial'])
                        if metric['qualifies'] and (best is None or metric['directional_angle_deg']>best['directional_angle_deg']):best=metric;bestz=previous.copy()
                    rows.append(metric)
        result=dict(direction=direction,maximum_angle_deg=None,tensions_at_max_n=None,status='no_admissible_equilibrium_found_in_documented_search',closest_stress_diagnostic=closest)
        if best is not None:
            result.update(maximum_angle_deg=best['directional_angle_deg'],tensions_at_max_n=best['tensions_n'],status='largest_admissible_angle_found',maximum_state=best)
        boundaries[direction]=result
        if closez is not None:states.append((direction+'_closest_stress',closez,np.array(closest['tensions_n'])))
        if bestz is not None:states.append((direction+'_maximum',bestz,np.array(best['tensions_n'])))
    summary=dict(combination=label,front_modules=sum(counts[2:]),attempted=attempted,converged=converged,admissible=sum(r['qualifies'] for r in rows),minimum_geometry_screened_core_stress_mpa=min((r['max_core_stress_mpa'] for r in rows if r['passes_self_envelope_screen']),default=None),seconds=time.monotonic()-start)
    write_json(file,dict(summary=summary,maximums=boundaries,trials=rows,force_grid_n=DRIVE,side_vertical_bias_n=SIDE_VERTICAL_BIAS,common_grid_n=COMMON,maximum_is_finite_search_not_physical_strength=True))
    arrays={}
    for name,z,T in states:arrays[name+'_z']=z;arrays[name+'_T']=T
    np.savez_compressed(out/(label+'_states.npz'),**arrays)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    jobs=[(8,12,d,f-d) for f in range(5,9) for d in range(1,f)]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(process,c) for c in jobs];summaries=[]
        for future in concurrent.futures.as_completed(futures):
            summary=future.result();summaries.append(summary);print(json.dumps({'done':len(summaries),**summary}),flush=True)
    write_json(HERE/'results/directional_summary.json',summaries)

if __name__=='__main__':main()
