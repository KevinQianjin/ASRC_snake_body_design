"""Audit all saved inverse, reference, settled and motion states of a guided run."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
import lanes
from state_archives import NAMES
from guide_path_audit import audit
from guide_load_design import screen
from inspect_end_region import inspect
STARTUP='startup_niti18_E40_p20_pre3_states.npz'
SWEEP='minforce_niti18_E40_p20_a456_pre3_exact_smooth1_fromstartup_tol1_states.npz'

def run(root,radii,cad):
    archives=[root/'inverse'/STARTUP,root/'inverse'/SWEEP,root/'reference/nominal_states.npz',
              root/'closed_loop/nominal_states.npz',root/'closed_loop/nominal_trace_states.npz']
    audit(archives,root/'path_audit',radii,True,cad)
    if tuple(radii)==(21,24,28):screen(root/'path_audit',root/'design_loads.json')
    export_motion(root,radii)
    inspect(root,radii,cad)

def export_motion(root,radii):
    """Export directly inspectable command/path lengths, loads and full head frame."""
    lanes.install(radii,24)
    rod=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    trace=json.loads((root/'closed_loop/nominal_trace.json').read_text())
    with np.load(root/'closed_loop/nominal_trace_states.npz') as saved:
        z=saved['z'];rest=saved['rest_m'];forces=saved['tensions_n']
    if not len(z)==len(rest)==len(forces)==len(trace):raise ValueError('Motion export alignment mismatch')
    with (root/'path_audit/path_checks.csv').open() as f:
        checks=[row for row in csv.DictReader(f) if row['archive'].endswith('nominal_trace_states.npz')]
    if len(checks)!=len(trace):raise ValueError('Motion/clearance count mismatch')
    with gzip.open(root/'closed_loop/nominal_motion.csv.gz','wt',newline='') as f:
        writer=None
        for i,(state,R,T,row,check) in enumerate(zip(z,rest,forces,trace,checks)):
            d=rod.evaluate(state,detail=True)[2]
            out=dict(trace_index=i,reference_index=row['index'],phase=row['phase'],kind=row['kind'],
                yaw_deg=row['yaw_deg'],elevation_deg=row['elevation_deg'],yaw_error_deg=row['yaw_error_deg'],
                elevation_error_deg=row['elevation_error_deg'],tank_clearance_bound_mm=row['clearance_mm']-1.5,
                rope_flexure_clearance_bound_mm=check['flexure_clearance_bound_mm'],
                end_region_centerline_points_inside=check['end_region_centerline_points_inside'],
                maximum_end_region_center_penetration_mm=check['maximum_end_region_center_penetration_mm'],
                minimum_fixed_winch_eigenvalue=row['minimum_eigenvalue'],strain=row['strain'],
                equilibrium_residual=row['residual'],node_move_mm=row['node_move_mm'],checks_pass=row['checks_pass'])
            out.update({f'head_tank_{axis}_mm':value for axis,value in zip('xyz',row['head_tank_mm'])})
            out.update({f'head_frame_base_R{a}{b}':float(d['frames'][-1,a,b]) for a in range(3) for b in range(3)})
            for k,name in enumerate(NAMES):
                out[name+'_command_rest_mm']=float(R.ravel()[k]*1000)
                out[name+'_internal_path_mm']=float(d['rope_lengths'].ravel()[k]*1000)
                out[name+'_tension_n']=float(T.ravel()[k])
            if writer is None:writer=csv.DictWriter(f,list(out));writer.writeheader()
            writer.writerow(out)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    p.add_argument('--radii',nargs=3,type=float,required=True);p.add_argument('--cad',type=Path,required=True)
    a=p.parse_args();run(a.root,a.radii,a.cad)
