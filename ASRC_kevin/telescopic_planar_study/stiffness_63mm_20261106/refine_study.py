"""Targeted 8 to 16 cells per module checks at unchanged tendon tensions."""
import json
import numpy as np
from run_study import HERE,OUT,PAIRS,DatabaseRod,dump,write_csv
from refine_front import finer_seed
from postprocess import path_check
from lightweight_path_check import Obstacles

def run():
    allrows=json.loads((OUT/'all_equilibria.json').read_text())
    reps=json.loads((OUT/'representatives.json').read_text())
    selected={(r['configuration'],r['state_id']):r for r in reps}
    for r in sorted(allrows,key=lambda q:q.get('mesh_tip_change_mm',0),reverse=True)[:8]:
        selected[r['configuration'],r['state_id']]=r
    checks=[];refined=[];arrays={}
    for (name,sid),row in selected.items():
        u,m=row['n_uni'],row['n_medium'];z=np.load(OUT/f'U{u}_M{m}_states.npz')
        old=DatabaseRod(u,m,row['anchors'],row['pitch_deg'],sub=8,common=row['common_per_rope_n'])
        fine=DatabaseRod(u,m,row['anchors'],row['pitch_deg'],sub=16,common=row['common_per_rope_n'])
        T=np.array(row['top_extra_tensions_n']);x=fine.solve(T,finer_seed(z[sid+'_x'],old,fine))
        check=dict(configuration=name,state_id=sid,refined_converged=x is not None)
        if x is not None:
            metric,p,d=fine.metrics(x,T,geometry=True)
            err=float(np.linalg.norm(p[-1]-z[sid+'_points_m'][-1])*1000)
            check.update(tip_change_mm=err,coarse_strain=row['max_abs_axial_strain'],fine_strain=metric['max_abs_axial_strain'],fine_equilibrium_residual=metric['equilibrium_residual'],low_strain_classification_unchanged=metric['strain_diagnostic_pass']==row['strain_diagnostic_pass'],straight_geometry_classification_unchanged=metric['provisional_straight_geometry']==row['provisional_straight_geometry'])
            metric.update(state_id=sid,architecture=row['architecture'],strain_mode=row['strain_mode'],kind=row['kind'],fine_converged=True,mesh_8_to_16_tip_change_mm=err)
            refined.append(metric)
            key=name+'_'+sid
            arrays[key+'_points_m']=p;arrays[key+'_x']=x;arrays[key+'_strain']=d['eps'];arrays[key+'_theta_rad']=d['theta']
        checks.append(check)
        print(name,sid,'16-cell tip change',check.get('tip_change_mm'),flush=True)
    dump(OUT/'mesh_8_to_16_checks.json',checks);write_csv(OUT/'mesh_8_to_16_checks.csv',checks)
    dump(OUT/'refined_equilibria.json',refined);np.savez_compressed(OUT/'refined_states.npz',**arrays)
    # Recheck the passing front sweeps on the more finely resolved centreline.
    paths=json.loads((OUT/'front_only_path_screen.json').read_text())
    passes=[r for r in paths if r['front_only_continuous_translation_screen_pass']]
    from run_study import OLD
    cad=json.loads((OLD/'results/cad_sections.json').read_text());obs=Obstacles(cad['sections']);prof=np.load(OLD/'results/cavity_profiles.npz')
    curves={};path_checks=[]
    for oldpath in passes:
        row=next(r for r in refined if r['configuration']==oldpath['configuration'] and r['state_id']==oldpath['state_id'])
        key=row['configuration']+'_'+row['state_id'];path,s,gap=path_check(row,arrays[key+'_points_m'],obs,prof)
        path.update(cells_per_module=16,previous_8cell_minimum_clearance_mm=oldpath['minimum_sampled_envelope_clearance_mm'])
        path_checks.append(path);curves[key+'_s_mm']=s;curves[key+'_gap_mm']=gap
        print('REFINED PATH',key,path['front_only_continuous_translation_screen_pass'],path['minimum_sampled_envelope_clearance_mm'],flush=True)
    dump(OUT/'refined_passing_path_checks.json',path_checks);np.savez_compressed(OUT/'refined_path_curves.npz',**curves)
    summary=json.loads((OUT/'summary.json').read_text())
    summary.update(mesh_8_to_16_checked=len(checks),mesh_8_to_16_converged=sum(r['refined_converged'] for r in checks),
        mesh_8_to_16_maximum_tip_change_mm=max(r.get('tip_change_mm',0) for r in checks),
        refined_front_only_path_pass_records=sum(r['front_only_continuous_translation_screen_pass'] for r in path_checks))
    dump(OUT/'summary.json',summary)

if __name__=='__main__':run()
