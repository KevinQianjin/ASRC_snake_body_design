"""Check saved guided-run consistency without treating physical failures as passes."""
import csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
import lanes
from state_archives import load_states
from audit_saved_guided_run import STARTUP,SWEEP
HERE=Path(__file__).resolve().parent;ROOT=HERE/'guided_validation_20261114'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
    cases={}
    for name,radii in [('baseline',(21,24,27)),('candidate',(21,24,28))]:
        root=ROOT/name
        archives=[root/'inverse'/STARTUP,root/'inverse'/SWEEP,root/'reference/nominal_states.npz',root/'closed_loop/nominal_states.npz',root/'closed_loop/nominal_trace_states.npz']
        counts=[];audit=read(root/'path_audit/summary.json')
        for path,coverage in zip(archives,audit['coverage']):
            states,actual=load_states(path)
            assert actual['states']==coverage['states'] and actual['sha256']==coverage['sha256']
            assert actual['unsolved_records_without_states']==0
            counts.append(len(states))
        ref=read(root/'reference/nominal.json');closed=read(root/'closed_loop/nominal.json');trace=read(root/'closed_loop/nominal_trace.json')
        summary=read(root/'closed_loop/nominal_summary.json');settings=read(root/'closed_loop/settings.json')
        assert summary['completed'] and len(ref)==len(closed)==summary['samples']
        assert settings['reference_sha256']==sha(root/'reference/nominal.json')
        assert settings['states_sha256']==sha(root/'reference/nominal_states.npz')
        assert read(root/'reference/nominal_summary.json')['source_sha256']==sha(root/'inverse'/SWEEP)
        assert set(r['phase'] for r in trace)=={'straighten','entry','right_out','right_return','left_out','left_return','exit'}
        assert max(r['target_yaw_deg'] for r in ref)==175 and min(r['target_yaw_deg'] for r in ref)==-175
        assert trace[-1]['phase']=='exit' and trace[-1]['clamp_s_mm']==-750
        with np.load(root/'closed_loop/nominal_trace_states.npz') as saved:
            Z=saved['z'];R=saved['rest_m'];T=saved['tensions_n']
        assert len(Z)==len(R)==len(T)==len(trace)==counts[-1]
        np.testing.assert_allclose(T,np.array([r['tensions_n'] for r in trace]),atol=1e-12,rtol=0)
        lanes.install(radii,24)
        from length_cycle import LengthDrive
        rod=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8);drive=LengthDrive(rod)
        indices=sorted(set(np.linspace(0,len(trace)-1,17,dtype=int).tolist()+[int(np.argmax(T.max(axis=1))),int(np.argmin(T.min(axis=1)))]))
        for i in indices:np.testing.assert_allclose(drive.force(Z[i],R[i]).ravel(),T[i],atol=1e-6,rtol=0)
        assert sum(not r['checks_pass'] for r in closed)==summary['settled']['failed_checks']
        assert sum(not r['checks_pass'] for r in trace if r['kind']!='start')==summary['trace']['failed_checks']
        with gzip.open(root/'closed_loop/nominal_motion.csv.gz','rt') as f:motion_rows=sum(1 for _ in csv.DictReader(f))
        assert motion_rows==len(trace)
        if audit['end_region_penetrating_states']:
            assert read(root/'path_audit/end_region_example.json')['points']
        cases[name]=dict(data_consistency_pass=True,archive_states=counts,motion_states=len(trace),
            sampled_state_command_force_rechecks=len(indices),settled_failed_checks=summary['settled']['failed_checks'],
            motion_failed_checks=summary['trace']['failed_checks'],flexure_failed_records=audit['flexure_screen_failed_states'],
            end_region_penetrating_records=audit['end_region_penetrating_states'])
    cad=HERE.parents[2]/'cad/lanes_u4m2/guides_v2'
    masses=read(cad/'mass_model.json')['module_mass_kg']
    np.testing.assert_array_equal(read(ROOT/'candidate/inverse/lanes.json')['mass_config']['module_mass_kg'],masses)
    geom=read(cad/'geometry_check.json');mount=read(ROOT/'candidate/mount_audit/summary.json')
    assert geom['all_straight_positions_clear'] and geom['all_mounts_on_existing_webs']
    assert not mount['all_selected_poses_clear']
    result=dict(base_commit='64a14a6402790f0d353bf07b110cf32853784cbe',cases=cases,
        unique_numerical_tests_passed=23,test_evidence='logs/: original 14-test suite, initial 7 guide tests, targeted load aggregation and solid/end classification tests, plus archive-reader recheck',
        existing_configurations_validated=11,straight_CAD_mesh_and_intersection_checks_pass=True,
        physical_design_released=False,release_blockers=['Rigid guide/body interference under beam-mapped bending','Rope-centre penetration of finite end-region material','Unvalidated support stiffness, strength, friction, retention and fatigue'])
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    files=[]
    for name in ['baseline','candidate']:files.extend((ROOT/name).rglob('*.npz'))
    files.extend(cad.glob('*.stl'));files.extend(cad.glob('*.json'));files.extend(cad.glob('*.py'))
    files.extend(HERE.glob('*.py'))
    files.extend(HERE.parent/'backbone_20261108'/p for p in ['closed_loop_v2.py','closed_loop_cycle.py','length_cycle.py'])
    repo=HERE.parents[2]
    (ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(repo)}\n' for p in sorted(set(files))))
    print(json.dumps(result,indent=2))
if __name__=='__main__':verify()
