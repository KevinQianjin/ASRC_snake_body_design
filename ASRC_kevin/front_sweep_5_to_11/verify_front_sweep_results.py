import csv,json,sys,copy,argparse
from pathlib import Path
root=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'inputs'))
import snake_model_front_sweep as W
import snake_model_rear_backbone as R
p=argparse.ArgumentParser()
p.add_argument('--output-dir',type=Path,default=root/'front_sweep_results')
out=p.parse_args().output_dir
data=json.loads((out/'run_summary.json').read_text())
swept=list(csv.DictReader((out/'all_rear_sweep_combinations.csv').open()))
fixed=list(csv.DictReader((out/'all_fixed_N31_combinations.csv').open()))
base,material,_=R.read_inputs(root/'inputs/rear_backbone_config.json',root/'inputs/rope_materials.json')
checks=[]
for front in range(5,12):
    a=min((r for r in swept if int(r['front_modules'])==front),key=lambda r:abs(float(r['capsule_vertical_span_mm'])-300))
    b=min((r for r in fixed if int(r['front_modules'])==front),key=lambda r:abs(float(r['core_reference_yield_ratio'])-1))
    cfg=copy.deepcopy(base);cfg['front']['modules']=front
    for kind,row in [('height',a),('yield',b)]:
        counts=[int(row[k]) for k in ['n_high','n_uni','n_directional','n_low']]
        sol,fine=W.solve_group(R,counts,cfg,material,[1600,830,300],64)
        fine=fine[0]
        check=dict(front_modules=front,criterion=kind,combination=row['combination'],
                   base_cells=16,refined_cells=64,
                   base_vertical_span_mm=float(row['capsule_vertical_span_mm']),refined_vertical_span_mm=fine['capsule_vertical_span_mm'],
                   base_yield_ratio=float(row['core_reference_yield_ratio']),refined_yield_ratio=fine['core_reference_yield_ratio'],
                   height_screen_unchanged=(row['passes_empty_box_envelope_screen']=='True')==fine['passes_empty_box_envelope_screen'],
                   yield_screen_unchanged=(row['passes_reference_yield_screen']=='True')==fine['passes_reference_yield_screen'],
                   refined_converged=fine['converged'])
        checks.append(check)
    s=next(s for s in data['fronts'] if s['front_modules']==front)
    best=s['max_reach_combined_candidate']
    print(front,'max rear',s['maximum_rear_count_with_combined_pass'],'best reach',None if best is None else (best['combination'],best['tip_x_mm']))
    candidates=[r for r in swept if int(r['front_modules'])==front]
    closest=min(candidates,key=lambda r:float(r['capsule_vertical_span_mm']))
    print('minimum vertical span',closest['combination'],float(closest['capsule_vertical_span_mm']))
old_path=root/'inputs/prior_study_reference.csv'
if not old_path.exists():old_path=root.parent/'tank_front_assessment/sensitivity_cases.csv'
old=list(csv.DictReader(old_path.open())) if old_path.exists() else []
key=lambda r:(r['combination'],r['front_modules'])
newmap={key(r):r for r in swept+fixed}
diffs=[]
for row in old:
    if int(row['front_modules']) in range(5,12):
        newer=newmap[key(row)]
        diffs.extend(abs(float(newer[k])-float(row[k])) for k in ['tip_drop_mm','tip_x_mm','front_compliance_gravity_deg_per_nmm','core_reference_yield_ratio'])
result=dict(closest_boundary_checks=checks,all_boundary_classifications_unchanged=all(c['height_screen_unchanged'] and c['yield_screen_unchanged'] and c['refined_converged'] for c in checks),
            prior_study_comparison_available=bool(old),
            prior_study_max_numeric_difference=max(diffs) if diffs else None,prior_study_metrics_compared=len(diffs),
            maximum_reference_fine_drop_change_mm=max(c['fine_drop_change_mm'] for c in data['validation']['per_front']),
            maximum_independent_continuum_drop_error_mm=max(c['independent_continuum_drop_error_mm'] for c in data['validation']['per_front']))
W.write_json(out/'boundary_and_prior_result_checks.json',result)
print(json.dumps(result,indent=2))
if not result['all_boundary_classifications_unchanged'] or (diffs and max(diffs)>1e-7):
    raise SystemExit(2)
