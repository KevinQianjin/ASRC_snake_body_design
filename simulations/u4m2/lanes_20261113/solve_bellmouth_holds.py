"""Re-solve saved force or reconstructed winch holds with bellmouth paths.

This is selected-state equilibrium coverage, not a new closed-loop replay.
Checkpoint after every state; an existing output folder is never overwritten.
"""
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth, mass_with_bellmouth, inspect_routing, angle_difference_deg
from state_archives import load_states
from spatial_model import refine_seed
from length_cycle import LengthDrive

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def damped_stationary(rod,tensions,seed,max_seconds=30.,drive=None,rest=None):
    """Newton equilibrium with residual backtracking and domain-safe trials.

    Force-controlled equilibria can be saddles of the potential, so decrease
    the gradient norm rather than requiring an energy minimum. Reject, rather
    than extrapolate, trial configurations outside the fillet tangent domain.
    """
    start=time.monotonic();x=seed.copy();trace=[]
    for iteration in range(60):
        if time.monotonic()-start>max_seconds:return None,trace,'state time budget reached'
        try:
            if drive is None:
                _,g=rod.evaluate(x,tensions);current_t=tensions
            else:
                _,g=drive.energy(x,rest);current_t=drive.force(x,rest)
            res=rod.residual(g);norm=float(np.linalg.norm(g))
        except ValueError:return None,trace,'initial or accepted state outside tangent domain'
        trace.append(dict(iteration=iteration,residual=res,gradient_norm=norm))
        q=(x/rod.scale).reshape(-1,4)
        if res<2e-8 and np.max(np.abs(q[:,3]))<.6 and np.max(np.abs(q[:,:3]))<1.5:
            return x,trace,'converged'
        try:
            hessian=rod.hessian(x,current_t)
            if drive is not None:
                jac=rod.control_jacobian(x);active=current_t.ravel()>1e-8
                hessian+=jac[active].T@((drive.ea/rest.ravel()[active])[:,None]*jac[active])
            step=np.linalg.solve(hessian,-g)
        except np.linalg.LinAlgError:return None,trace,'singular force tangent'
        accepted=False
        for factor in 0.5**np.arange(18):
            trial=x+factor*step
            try:ng=rod.evaluate(trial,tensions)[1] if drive is None else drive.energy(trial,rest)[1]
            except ValueError:continue
            if np.linalg.norm(ng)<norm*(1.-1e-4*factor):
                x=trial;trace[-1]['step_factor']=float(factor);accepted=True;break
        if not accepted:return None,trace,'no residual-decreasing Newton step'
    return None,trace,'iteration budget reached'


def write_json(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run(archive, out, max_seconds, indices=None, sub=8, mode='force', reuse=None):
    start=time.monotonic()
    out.mkdir(parents=True,exist_ok=False)
    design_path=ROOT/'cad/lanes_u4m2/end_bellmouth_v1/design.json'
    geometry_path=design_path.with_name('geometry_check.json')
    mass_path=ROOT/'cad/lanes_u4m2/guides_v3/mass_model.json'
    design=json.loads(design_path.read_text()); chk=json.loads(geometry_path.read_text())
    if not chk['all_watertight_single_component'] or not chk['minimum_bridge_target_met']:
        raise ValueError('Published CAD has not passed its straight geometry checks')
    for name,part in chk['parts'].items():
        assert hashlib.sha256((design_path.parent/name).read_bytes()).hexdigest()==part['sha256']
    base_mass=json.loads(mass_path.read_text()); mass=mass_with_bellmouth(base_mass,chk)
    write_json(out/'mass_model.json',mass);write_json(out/'design.json',design)
    lanes.install((21,24,28),24,base_mass)
    before=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    lanes.install((21,24,28),24,mass)
    after=apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,sub),design)
    old_drive=LengthDrive(before);new_drive=LengthDrive(after)
    states,coverage=load_states(archive)
    if indices is not None:states=[states[i] for i in indices]
    started=datetime.now(timezone.utc)
    result=dict(scope=__doc__,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        started_et=started.astimezone(ZoneInfo('America/New_York')).isoformat(),
        started_utc=started.isoformat(),payload_g=500,cells_per_module=sub,
        input_coverage=coverage,selected_indices=indices,requested_records=len(states),
        inputs_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [archive.resolve(),design_path,geometry_path,mass_path]},
        versions={n:importlib.metadata.version(n) for n in ('numpy','scipy','numba','trimesh','vtk')},
        mass_change_g=mass['bellmouth_mass_change_g'],mode=mode,free_rope_length_m=1.,
        command_scope='Reconstructed rest lengths of the saved V3 equilibria; not original archived controller commands',
        completed=False,rows=[])
    saved=[];tensions=[];metadata=[];cache={};reused_labels=[]
    if reuse is not None:
        previous=json.loads((reuse/'summary.json').read_text())
        if previous.get('mode')!=mode or previous['cells_per_module']!=sub or previous['inputs_sha256']!=result['inputs_sha256']:
            raise ValueError('Checkpoint does not match mode, mesh and source hashes')
        source_by_label={label:(z,T) for label,z,T,_ in states}
        checkpoints=np.load(reuse/'equilibria_states.npz',allow_pickle=False)
        previous_meta=json.loads((reuse/'equilibria.json').read_text())
        for x,meta in zip(checkpoints['z'],previous_meta):
            label=meta['source_state']
            if label not in source_by_label:continue
            z,T=source_by_label[label];seed=z if sub==8 else refine_seed(z,before,after)
            rest=old_drive.inverse(z,T)
            gradient=after.evaluate(x,T)[1] if mode=='force' else new_drive.energy(x,rest)[1]
            if after.residual(gradient)>=2e-8:raise ValueError('Checkpoint equilibrium does not pass residual check')
            cache[seed.tobytes()+T.tobytes()]=x.copy();reused_labels.append(label)
        result['reused_checkpoint']=str(reuse);result['reused_checkpoint_states']=reused_labels
    initial_cache_count=len(cache)
    def save():
        result['elapsed_seconds']=time.monotonic()-start
        good=[r for r in result['rows'] if r['solved']]
        if good:
            result['aggregate']=dict(solved_records=len(good),failed_records=len(result['rows'])-len(good),
                max_head_change_mm=max(r['head_change_mm'] for r in good),
                max_abs_yaw_change_deg=max(abs(r['yaw_change_deg']) for r in good),
                max_abs_elevation_change_deg=max(abs(r['elevation_change_deg']) for r in good),
                max_residual=max(r['candidate']['equilibrium_residual'] for r in good),
                minimum_fixed_winch_eigenvalue=min(r['candidate']['minimum_fixed_winch_eigenvalue'] for r in good),
                nonpositive_fixed_winch_records=sum(r['candidate']['minimum_fixed_winch_eigenvalue']<=0 for r in good),
                max_exit_angle_deg=max(r['max_exit_angle_deg'] for r in good),
                min_design_margin_deg=min(r['min_design_margin_deg'] for r in good),
                wrap_failing_records=sum(r['wrap_failures']>0 for r in good),
                wrap_failing_exits=sum(r['wrap_failures'] for r in good),
                max_fillet_resultant_n=max(r['max_fillet_resultant_n'] for r in good),
                max_guide_hole_force_n=max(r['max_guide_hole_force_n'] for r in good))
        write_json(out/'summary.json',result)
        np.savez_compressed(out/'equilibria_states.npz',z=np.asarray(saved),tensions_n=np.asarray(tensions))
        write_json(out/'equilibria.json',metadata)
    for label,z,T,meta in states:
        if time.monotonic()-start>=max_seconds:
            result['stop_reason']='study time budget reached';save();return result
        old,od,oldworld=before.metrics(z,T,stability=False)
        rest=old_drive.inverse(z,T)
        seed=z if sub==8 else refine_seed(z,before,after)
        key=seed.tobytes()+T.tobytes()
        if key in cache:
            x=cache[key].copy();cached=True
        else:
            x,trace,reason=damped_stationary(after,T,seed,drive=new_drive if mode=='rest' else None,rest=rest);cached=False
            if x is not None:cache[key]=x.copy()
        if x is None:
            result['rows'].append(dict(state=label,solved=False,solver_reason=reason,solver_trace=trace));save()
            print(label,'FAILED',reason,flush=True);continue
        candidate_t=new_drive.force(x,rest) if mode=='rest' else T
        new,nd,world=after.metrics(x,candidate_t,stability=False)
        candidate_rest=rest if mode=='rest' else new_drive.inverse(x,candidate_t)
        eig=new_drive.stability(x,candidate_rest,candidate_t)
        new['minimum_fixed_winch_eigenvalue']=eig;new['stable_fixed_winch']=bool(eig>0.)
        exits,guides=inspect_routing(after,x,candidate_t)
        result['rows'].append(dict(state=label,source_metadata=meta,solved=True,reused_identical_equilibrium=cached,
            solver_trace=[] if cached else trace,baseline=old,candidate=new,head_change_mm=float(np.linalg.norm(world[-1]-oldworld[-1])*1000.),
            yaw_change_deg=angle_difference_deg(new['yaw_deg'],old['yaw_deg']),
            elevation_change_deg=float(new['world_elevation_deg']-old['world_elevation_deg']),
            baseline_rope_lengths_mm=(od['rope_lengths']*1000.).tolist(),
            candidate_rope_lengths_mm=(nd['rope_lengths']*1000.).tolist(),
            reconstructed_rest_lengths_mm=(rest*1000.).tolist(),candidate_rest_lengths_mm=(candidate_rest*1000.).tolist(),
            max_tension_change_n=float(np.max(np.abs(candidate_t-T))),
            head_frame_base=nd['frames'][-1].tolist(),
            max_exit_angle_deg=max(r['exit_angle_deg'] for r in exits),
            min_design_margin_deg=min(r['design_margin_deg'] for r in exits),
            wrap_failures=sum(not r['margin_pass'] for r in exits),
            max_fillet_resultant_n=max(r['fillet_resultant_n'] for r in exits),
            max_guide_hole_force_n=max(r['hole_force_n'] for r in guides)))
        saved.append(x);tensions.append(candidate_t)
        metadata.append(dict(source_state=label,source_metadata=meta,phase=meta.get('phase','inverse'),
            status='solved',tensions_n=candidate_t.tolist()))
        save()
        print(label,'head_change_mm',round(result['rows'][-1]['head_change_mm'],6),
              'margin_deg',round(result['rows'][-1]['min_design_margin_deg'],4),
              'winch_eigenvalue',round(new['minimum_fixed_winch_eigenvalue'],6),flush=True)
    result['completed']=True;result['unique_solves']=len(cache)-initial_cache_count;save()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-seconds',type=float,default=1200.)
    p.add_argument('--indices',type=int,nargs='+');p.add_argument('--sub',type=int,default=8)
    p.add_argument('--mode',choices=['force','rest'],default='force')
    p.add_argument('--reuse',type=Path)
    a=p.parse_args();run(a.archive,a.out,a.max_seconds,a.indices,a.sub,a.mode,a.reuse)
