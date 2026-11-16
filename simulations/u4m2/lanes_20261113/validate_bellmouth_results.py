"""Validate the saved morning evidence without repeating expensive CAD studies.

Checks all selected equilibrium residuals, reconstructed winch commands,
archive alignment, saved load tables, source CAD hashes and summary counts.
This validates evidence integrity, not hardware or manufacturing readiness.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import lanes
from bellmouth_model import apply_bellmouth, angle_difference_deg
from length_cycle import LengthDrive
from state_archives import load_states

ROOT=Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text())


def validate(folder):
    selected=folder/'fixed_winch_holds'
    summary=read(selected/'summary.json')
    assert summary['completed'] and summary['mode']=='rest'
    assert summary['payload_g']==500 and summary['cells_per_module']==8
    for name,digest in summary['inputs_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
    source=ROOT/'simulations/u4m2/lanes_20261113/guided_refinement_20261115/v3_final_mass_holds/mass_holds_states.npz'
    old_states,_=load_states(source)
    states,_=load_states(selected/'equilibria_states.npz')
    rows=summary['rows']
    assert len(old_states)==len(states)==len(rows)==217
    lanes.install((21,24,28),24,read(ROOT/'cad/lanes_u4m2/guides_v3/mass_model.json'))
    before=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    old_drive=LengthDrive(before)
    lanes.install((21,24,28),24,read(selected/'mass_model.json'))
    after=apply_bellmouth(lanes.backbone.spatial_rod(4,2,[4,5,6],20,8),read(selected/'design.json'))
    drive=LengthDrive(after)
    residuals=[]
    for (old_label,old_z,old_t,_),(label,z,t,meta),row in zip(old_states,states,rows):
        assert old_label==row['state']==meta['source_state']
        assert np.isfinite(z).all() and np.isfinite(t).all() and row['solved']
        rest=old_drive.inverse(old_z,old_t)
        np.testing.assert_allclose(rest*1000,row['reconstructed_rest_lengths_mm'],atol=1e-10)
        np.testing.assert_allclose(drive.force(z,rest),t,atol=1e-10)
        residual=after.residual(drive.energy(z,rest)[1])
        assert residual<2e-8
        residuals.append(residual)
        assert abs(row['yaw_change_deg']-angle_difference_deg(row['candidate']['yaw_deg'],row['baseline']['yaw_deg']))<1e-10
    unique=len({z.tobytes() for _,z,_,_ in states})
    assert unique==199
    end=read(folder/'rigid_end_audit/summary.json')
    table_counts={}
    for name,count in [('rope_exits',5208),('guide_holes',10416),('guide_stations',1736)]:
        with (folder/f'rigid_end_audit/{name}.csv').open() as stream:
            data=list(csv.DictReader(stream))
        assert len(data)==count,(name,len(data),count)
        assert len({r['state'] for r in data})==217
        table_counts[name]=count
        if name=='rope_exits':
            assert sum(float(r['envelope_clearance_mm'])<-.005 for r in data)==end['envelope_failing_checks']==0
            assert max(float(r['endpoint_error_mm']) for r in data)==0.
    assert end['completed'] and end['unique_geometry_states']==unique
    for module,digest in end['cad_sha256'].items():
        name=module+'_lane_anchor'+('B.stl' if module=='M5' else 'C.stl')
        assert hashlib.sha256((ROOT/'cad/lanes_u4m2/end_bellmouth_v1'/name).read_bytes()).hexdigest()==digest
    tank=read(folder/'tank_envelope/summary.json')
    assert tank['records']==sum(tank['phase_counts'].values())==217
    assert all(tank[k]==0 for k in ('clearance_failures','tension_failures','strain_failures','geometry_failures'))
    fine=read(folder/'refined_16_cell/summary.json')
    assert fine['completed'] and fine['cells_per_module']==16 and len(fine['rows'])==5
    assert all(r['solved'] and r['candidate']['minimum_fixed_winch_eigenvalue']>0 for r in fine['rows'])
    coarse_mount=read(folder/'mount_selected_0p5mm/summary.json')
    fine_mount=read(folder/'mount_targeted_0p25mm/summary.json')
    assert coarse_mount['completed'] and len(coarse_mount['rows'])==48
    assert fine_mount['completed'] and len(fine_mount['rows'])==6
    assert fine_mount['loaded_body_modules']==['M5']
    assert not fine_mount['all_selected_poses_clear']
    for name,count in [('geometry_regression_tests',31),('control_regression_tests',14)]:
        log=(folder/f'logs/{name}.log').read_text()
        assert f'Ran {count} tests' in log and log.rstrip().endswith('OK')
    return dict(passed=True,scope=__doc__,records=217,unique_geometries=unique,
        maximum_rechecked_residual=max(residuals),table_rows=table_counts,
        regression_tests=45,rod_refinement_records=5,coarse_mount_checks=48,
        fine_mount_checks=6,manufacturing_ready=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=validate(args.folder)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
