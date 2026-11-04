"""Sweep flexible fronts of 5--11 modules using the existing original-data solver.

Rear: high -> uni-d, with a 4.2 mm solid SS304 core. Front: directional -> low,
without a core. Each type is present. Compare both a rear-length sweep and a
fixed total count; do not conflate their lengths. No ropes, tip payload, contact,
plasticity or 3D motion. The empty-box screen is a conservative capsule envelope,
not a CAD collision test or a guarantee of task feasibility.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/asrc_front_sweep_mpl')
import numpy as np

HERE = Path(__file__).resolve().parent
BLUE, ORANGE, GRAY = '#34678f', '#bc6c2d', '#777777'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_csv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else ['combination', 'front_modules']
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def interval(rows, field):
    if not rows:
        return None
    return [min(r[field] for r in rows), max(r[field] for r in rows)]


def add_envelope(solution, rows, inspection, diameter):
    length, phi = solution['length'], solution['phi']
    x = np.cumsum(length * np.cos(phi), axis=1) * 1000
    y = np.cumsum(length * np.sin(phi), axis=1) * 1000
    xmin, xmax = np.minimum(0, x.min(axis=1)), np.maximum(0, x.max(axis=1))
    ymin, ymax = np.minimum(0, y.min(axis=1)), np.maximum(0, y.max(axis=1))
    for i, row in enumerate(rows):
        row['front_drop_mm'] = row['tip_drop_mm'] - row['rear_drop_mm']
        row['capsule_horizontal_span_mm'] = float(xmax[i] - xmin[i] + diameter)
        row['capsule_vertical_span_mm'] = float(ymax[i] - ymin[i] + diameter)
        row['capsule_width_mm'] = float(diameter)
        row['passes_empty_box_envelope_screen'] = bool(
            row['capsule_horizontal_span_mm'] <= inspection[0]
            and row['capsule_width_mm'] <= inspection[1]
            and row['capsule_vertical_span_mm'] <= inspection[2])
        row['passes_combined_reference_screen'] = bool(row['converged']
            and row['passes_reference_yield_screen'] and row['passes_empty_box_envelope_screen'])
        row['elastic_shape_within_reference_yield'] = bool(row['converged'] and row['passes_reference_yield_screen'])
    return rows


def solve_group(R, counts, cfg, material, inspection, cells):
    sol = R.solve_counts(counts, cfg, material, cells=cells)
    rows = add_envelope(sol, R.case_rows(sol, cfg), inspection, cfg['module_diameter_mm'])
    return sol, rows


def validate_front(R, base_cfg, material, cfg, spec, counts, reference, snapshot):
    coarse = R.case_rows(R.solve_counts(counts, cfg, material, cells=8), cfg)[0]
    fine = R.case_rows(R.solve_counts(counts, cfg, material, cells=32), cfg)[0]
    stepped = R.case_rows(R.solve_counts(counts, cfg, material, cells=16,
                                       steps=cfg['solver']['gravity_steps'] * 2), cfg)[0]
    zero_cfg = copy.deepcopy(cfg)
    zero_cfg['gravity_m_s2'] = 0.
    zero = R.case_rows(R.solve_counts(counts, zero_cfg, material, cells=16), zero_cfg)[0]
    props = R.S.properties(cfg)
    expected = sum(n * p['length_mm'] / 1000 / p['EI_down_nm2']
                   for n, p in zip(counts[2:], props[2:])) * R.DEG_PER_NMM
    body = R.build_cells(counts, cfg, material, cells=16)
    b = body['rear_cells']
    core = body['core']
    expected_core_mass = (counts[0]+counts[1]) * cfg['module_length_mm'] / 1000 * core['linear_mass_kg_m']
    checks = dict(front_modules=cfg['front']['modules'], reference_combination=reference['combination'],
                  cells=[8,16,32], drops_mm=[coarse['tip_drop_mm'],reference['tip_drop_mm'],fine['tip_drop_mm']],
                  fine_drop_change_mm=abs(fine['tip_drop_mm']-reference['tip_drop_mm']),
                  fine_reach_change_mm=abs(fine['tip_x_mm']-reference['tip_x_mm']),
                  fine_compliance_change_deg_per_nmm=abs(fine['front_compliance_gravity_deg_per_nmm']-reference['front_compliance_gravity_deg_per_nmm']),
                  doubled_gravity_steps_drop_change_mm=abs(stepped['tip_drop_mm']-reference['tip_drop_mm']),
                  zero_g_compliance_error=abs(zero['front_compliance_gravity_deg_per_nmm']-expected),
                  zero_g_drop_mm=zero['tip_drop_mm'],
                  no_core_mass_in_front=bool(np.all(body['core_mass'][:,b:] == 0)),
                  original_front_EI=bool(np.array_equal(body['EI_effective'][:,b:],body['EI_module'][:,b:])),
                  core_mass_error_kg=abs(float(body['core_mass'].sum())-expected_core_mass),
                  all_reference_solves_converged=bool(coarse['converged'] and fine['converged'] and stepped['converged'] and zero['converged']))
    if spec['independent_bvp_validation']:
        # Independent continuous force/moment balance, with its own ODE and BC.
        from test_snake_model_rear_backbone import independent_continuum
        continuous_cfg = copy.deepcopy(cfg)
        continuous_cfg['reference_counts'] = list(counts)
        continuous = independent_continuum(continuous_cfg, material)
        checks['independent_continuum_drop_error_mm'] = abs(fine['tip_drop_mm'] + continuous.y[-1,-1]*1000)
        checks['independent_continuum_reach_error_mm'] = abs(fine['tip_x_mm'] - continuous.y[-2,-1]*1000)
    checks['passed'] = bool(checks['all_reference_solves_converged']
        and checks['fine_drop_change_mm'] < .15 and checks['fine_reach_change_mm'] < .15
        and checks['doubled_gravity_steps_drop_change_mm'] < 1e-4
        and checks['zero_g_compliance_error'] < 1e-7 and abs(checks['zero_g_drop_mm']) < 1e-9
        and checks['core_mass_error_kg'] < 1e-12 and checks['no_core_mass_in_front'] and checks['original_front_EI']
        and checks.get('independent_continuum_drop_error_mm',0) < .03
        and checks.get('independent_continuum_reach_error_mm',0) < .03)
    return checks


def plotting():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
                         'axes.spines.top':False, 'axes.spines.right':False})
    return plt


def plot_front(folder, front, swept, fixed, frontier, reference_counts, core_shape, no_core_shape, height):
    plt = plotting()
    fig, ax = plt.subplots(2,2,figsize=(14,10),layout='constrained')
    rear_counts = sorted({r['rear_modules'] for r in swept})
    for rear in rear_counts:
        group = [r for r in swept if r['rear_modules']==rear]
        bounds = interval(group,'tip_drop_mm')
        ax[0,0].plot([rear,rear],bounds,color=BLUE,lw=2)
    ax[0,0].plot(rear_counts,[min(r['tip_drop_mm'] for r in swept if r['rear_modules']==n) for n in rear_counts],
                 color=BLUE,lw=1,marker='o',ms=3,label='Min/max across all H/U and D/L splits')
    ax[0,0].axhline(height-32,color=GRAY,ls='--',label=f'{height:g} mm height minus 32 mm diameter')
    ax[0,0].set(xlabel='Rear module count (48 mm each)',ylabel='Head drop (mm)',title='Rear length sweep',
                 ylim=(0,None),xticks=rear_counts[::2])
    ax[0,0].legend(frameon=False,fontsize=8)
    grid = np.full((front-1, fixed[0]['rear_modules']-1),np.nan)
    for r in fixed: grid[r['n_low']-1,r['n_high']-1] = r['core_reference_yield_ratio']
    m = ax[0,1].imshow(grid,origin='lower',aspect='auto',cmap='cividis',vmin=.6,vmax=1.3,
                      extent=(.5,grid.shape[1]+.5,.5,grid.shape[0]+.5))
    if grid.min()<1<grid.max():
        ax[0,1].contour(np.arange(1,grid.shape[1]+1),np.arange(1,front),grid,levels=[1],colors='white',linewidths=1.5)
    ax[0,1].set(xlabel='high count (uni-d = rear count - high)',ylabel=f'low count (directional = {front} - low)',
                 title=f'N=31: core stress / reference yield (1 = 205 MPa)',yticks=range(1,front),
                 xticks=sorted(set([1,grid.shape[1]]+list(range(1,grid.shape[1]+1,max(1,(grid.shape[1]+5)//6))))))
    fig.colorbar(m,ax=ax[0,1],label='Stress / reference yield',shrink=.85)
    for passed,color,marker,label in [(False,GRAY,'x','Above reference yield: elastic extrapolation'),
                                      (True,BLUE,'o','Within reference yield')]:
        group=[r for r in fixed if r['passes_reference_yield_screen']==passed]
        if group: ax[1,0].scatter([r['tip_x_mm'] for r in group],
            [r['front_compliance_gravity_deg_per_nmm'] for r in group],color=color,marker=marker,s=20,alpha=.65,label=label)
    if frontier:
        ax[1,0].plot([r['tip_x_mm'] for r in frontier],[r['front_compliance_gravity_deg_per_nmm'] for r in frontier],
                      color=ORANGE,marker='o',ms=4,lw=1.5,label='Yield-only Pareto; tank screen not applied')
    passing=sum(r['passes_combined_reference_screen'] for r in fixed)
    ax[1,0].set(xlabel='Horizontal reach (mm)',ylabel='Front compliance (deg / N mm)',
                 title=f'N=31: reach / small-moment compliance; box + yield pass {passing}/{len(fixed)}')
    ax[1,0].legend(frameon=False,fontsize=8)
    ax[1,1].axhspan(-(height-32),0,color='#e8edf0',label='300 mm height, 32 mm diameter')
    for xy,b,style,color,label in [(core_shape[0],core_shape[1],'-',BLUE,'Rear backbone'),
                                  (no_core_shape[0],no_core_shape[1],'--',GRAY,'Same modules, no backbone')]:
        ax[1,1].plot(xy[:,0],xy[:,1],style,color=color,lw=1.6,label=label)
        if style=='-':
            ax[1,1].plot(xy[b:,0],xy[b:,1],color=ORANGE,lw=2,label='Flexible front')
            ax[1,1].plot(*xy[b],'s',color=BLUE,ms=4)
        ax[1,1].plot(*xy[-1],'o',color=color,ms=4)
    ax[1,1].set(xlabel='Horizontal distance from clamp (mm)',ylabel='Height relative to clamp (mm)',
                 title='Reference '+' / '.join(f'{x}{n}' for x,n in zip('HUDL',reference_counts)))
    ax[1,1].set_aspect('equal',adjustable='box');ax[1,1].legend(frameon=False,fontsize=8,loc='lower right')
    for a in ax.flat:a.grid(alpha=.13)
    fig.suptitle(f'Flexible front: {front} modules = {front*48} mm',fontsize=17)
    fig.supxlabel('Original CRAFT module EI/masses | 4.2 mm SS304 core in rear only | self weight only\n'
                  'No tendons, tip payload or contact. Above-yield shapes are not valid elastic designs.\n'
                  'The empty-box envelope screen does not test entrance, obstacles, tool pose or 3D manoeuvring.',fontsize=9)
    fig.savefig(folder/'simulation_summary.png',dpi=180);plt.close(fig)


def overview(output, summaries, references, fixed_rows, spec):
    plt = plotting()
    fronts=spec['front_module_counts']
    fig,ax=plt.subplots(2,2,figsize=(13.5,9.5),layout='constrained')
    fields=['tip_drop_mm','tip_x_mm','front_compliance_gravity_deg_per_nmm']
    positions=[ax[0,0],ax[0,1],ax[1,0]]
    labels=['Head drop (mm)','Horizontal reach (mm)','Front compliance (deg / N mm)']
    for field,a,ylabel in zip(fields,positions,labels):
        for front in fronts:
            group=[r for r in references if r['front_modules']==front]
            y=[r[field] for r in group]
            a.vlines(front,min(y),max(y),color=BLUE,lw=2)
            a.scatter([front]*len(y),y,s=24,color=BLUE,alpha=.6)
        a.set(xlabel='Flexible front modules (48 mm each)',ylabel=ylabel,
              title='Rear fixed at H8 + U12 (960 mm)',xticks=fronts,xlim=(min(fronts)-.5,max(fronts)+.5))
    height=spec['effective_inspection_dimensions_mm'][2]
    ax[0,0].axhline(height,color=GRAY,ls=':',label=f'Effective height: {height:g} mm')
    ax[0,0].axhline(height-32,color=GRAY,ls='--',label=f'{height-32:g} mm + 32 mm diameter = {height:g} mm')
    ax[0,0].set_ylim(0,650);ax[0,0].legend(frameon=False,fontsize=9)
    for front in fronts:
        group=[r for r in fixed_rows if r['front_modules']==front]
        y=[r['core_reference_yield_ratio'] for r in group]
        ax[1,1].plot([front,front],[min(y),max(y)],color=ORANGE,lw=2,marker='o',ms=4)
        count=sum(r['passes_reference_yield_screen'] for r in group)
        ax[1,1].text(front,max(y)+.018,f'{count}/{len(group)}',ha='center',fontsize=9)
    ax[1,1].axhline(1,color=GRAY,ls='--',label='Reference yield: 205 MPa')
    ax[1,1].set(xlabel='Flexible front modules (rear = 31 - front)',ylabel='Core stress / reference yield',
                title='Total fixed at 31 modules (1488 mm)',xticks=fronts,ylim=(.78,1.31))
    ax[1,1].legend(frameon=False,fontsize=9,loc='lower left')
    for a in ax.flat:a.grid(axis='y',alpha=.15)
    fig.suptitle('Fronts of 5–11 modules: gravity deformation and reference strength screen',fontsize=16)
    fig.supxlabel('Ranges are composition min/max, not uncertainty bounds. The first three panels vary total length.\n'
                  'The last panel varies rear length to hold total length fixed; labels show cases within reference yield.\n'
                  'Original module data | rear-only 4.2 mm SS304 | no tendons, payload or contact',fontsize=9)
    fig.savefig(output/'front_5_to_11_overview.png',dpi=180);plt.close(fig)
    # Complete enumeration, including zero-pass cells; rates are not probabilities.
    rear=range(spec['rear_modules_min'],spec['rear_modules_max']+1)
    grid=np.array([[next(s for s in summaries if s['front_modules']==f)['rear_groups'][str(n)]['combined_pass_fraction']
                    for n in rear] for f in fronts])
    fig,a=plt.subplots(figsize=(15,6),layout='constrained')
    im=a.imshow(grid,origin='lower',aspect='auto',vmin=0,vmax=1,cmap='cividis',
                 extent=(min(rear)-.5,max(rear)+.5,min(fronts)-.5,max(fronts)+.5))
    for f in fronts:
        data=next(s for s in summaries if s['front_modules']==f)['rear_groups']
        for n in rear:
            z=data[str(n)]
            a.text(n,f,f"{z['combined_pass_count']}/{z['cases']}",ha='center',va='center',fontsize=7,
                   color='white' if z['combined_pass_fraction']<.45 else '#222222')
    a.set(xlabel='Rear module count (48 mm each, with SS304 backbone)',ylabel='Flexible front module count',
          title='Empty 1600 × 830 × 300 mm envelope + reference-yield screen',xticks=list(rear),yticks=fronts)
    cb=fig.colorbar(im,ax=a,pad=.02);cb.set_label('Fraction passing the combined screen')
    from matplotlib.ticker import PercentFormatter
    cb.ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.supxlabel('Cell labels: passing / enumerated H/U and D/L combinations. Capsule diameter: 32 mm.\n'
                  'Best vertical placement in an empty box is assumed; entrance, obstacles, tool load and actuation are not tested.',fontsize=9)
    fig.savefig(output/'rear_front_envelope_screen.png',dpi=180);plt.close(fig)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=HERE/'front_sweep_config.json')
    parser.add_argument('--project',type=Path,default=HERE/'inputs' if (HERE/'inputs').is_dir() else HERE)
    parser.add_argument('--output-dir',type=Path,default=HERE/'front_sweep_results')
    args=parser.parse_args(argv)
    spec=json.loads(args.config.read_text())
    if spec['front_module_counts'] != list(range(5,12)):
        raise ValueError('This study requires every front count from 5 through 11.')
    if spec['cells_per_module'] != 16:
        raise ValueError('This reviewed study uses 16 cells/module.')
    sys.path.insert(0,str(args.project.resolve()))
    import snake_model_rear_backbone as R
    base_cfg,material,catalog=R.read_inputs(args.project/'rear_backbone_config.json',args.project/'rope_materials.json')
    if base_cfg['backbone']['diameter_mm'] != 4.2 or base_cfg['backbone']['material'] != 'ss304_annealed':
        raise ValueError('The authorised core is a solid 4.2 mm SS304 rod.')
    if base_cfg['data_mode'] != 'paper_original':
        raise ValueError('Module data must remain the unscaled original paper data.')
    sources=[args.project/n for n in ['craft_data.py','snake_model_pla_sag.py','snake_model_rear_backbone.py',
             'test_snake_model_rear_backbone.py','rear_backbone_config.json','rope_materials.json']]
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    write_json(out/'run_config.json',dict(study=spec,base_model=base_cfg))
    write_csv(out/'module_properties.csv',R.S.properties(base_cfg))
    write_json(out/'backbone_properties.json',dict(properties=R.backbone_properties(material,4.2),
               material=material,sources=catalog.get('sources')))
    all_rows,all_fixed,all_ref,summaries,checks,reference_rows=[],[],[],[],[],[]
    counts_seen=set()
    for front in spec['front_module_counts']:
        cfg=copy.deepcopy(base_cfg);cfg['front']['modules']=front
        folder=out/f'front_{front:02d}';folder.mkdir(parents=True,exist_ok=True)
        swept=[]
        for rear in range(spec['rear_modules_min'],spec['rear_modules_max']+1):
            counts=list(R.count_combinations(rear,front))
            assert len(counts)==(rear-1)*(front-1) and len(counts)==len(set(counts))
            _,rows=solve_group(R,counts,cfg,material,spec['effective_inspection_dimensions_mm'],spec['cells_per_module'])
            swept.extend(rows)
        fixed_rear=spec['focus_total_modules']-front
        fixed=[r for r in swept if r['total_modules']==spec['focus_total_modules']]
        if not fixed:
            _,fixed=solve_group(R,list(R.count_combinations(fixed_rear,front)),cfg,material,
                                spec['effective_inspection_dimensions_mm'],spec['cells_per_module'])
        reference_all=[r for r in swept if [r['n_high'],r['n_uni']]==spec['reference_rear_counts']]
        d=max(1,min(front-1,round(front*spec['reference_directional_fraction'])))
        counts=(*spec['reference_rear_counts'],d,front-d)
        ref_sol,ref_list=solve_group(R,counts,cfg,material,spec['effective_inspection_dimensions_mm'],16)
        reference=ref_list[0];reference_rows.append(reference)
        baseline_sol,baseline_rows=solve_group(R,counts,cfg,None,spec['effective_inspection_dimensions_mm'],16)
        core_shape=R.shape(ref_sol);no_core_shape=R.shape(baseline_sol)
        for name,solution in [('reference_with_backbone',ref_sol),('reference_without_backbone',baseline_sol)]:
            xy=R.shape(solution)['points_mm']
            shape_rows=[dict(s_mm=float(s),x_mm=float(x),y_mm=float(y),zone='rear' if i<=solution['rear_cells'] else 'front')
                        for i,(s,(x,y)) in enumerate(zip(np.r_[0,np.cumsum(solution['length'][0])*1000],xy))]
            write_csv(folder/f'{name}_shape.csv',shape_rows)
        frontier=R.pareto_rows(fixed)
        combined=[r for r in swept if r['passes_combined_reference_screen']]
        combined_pareto=R.pareto_rows(combined)
        for name,rows in [('combinations',swept),('fixed_N31',fixed),('fixed_rear_H8_U12',reference_all),
                          ('pareto_N31_reference_yield_only',frontier),('empty_box_and_reference_yield_candidates',combined),
                          ('pareto_empty_box_and_reference_yield',combined_pareto)]:
            write_csv(folder/f'{name}.csv',rows,list(swept[0]))
        write_json(folder/'reference_comparison.json',dict(with_backbone=reference,without_backbone=baseline_rows[0]))
        rear_groups={}
        for n in range(spec['rear_modules_min'],spec['rear_modules_max']+1):
            group=[r for r in swept if r['rear_modules']==n]
            passed=[r for r in group if r['passes_combined_reference_screen']]
            rear_groups[str(n)]=dict(cases=len(group),combined_pass_count=len(passed),combined_pass_fraction=len(passed)/len(group),
                                     drop_range_mm=interval(group,'tip_drop_mm'),reach_range_mm=interval(group,'tip_x_mm'))
        summary=dict(front_modules=front,front_length_mm=front*48,swept_cases=len(swept),fixed_total_cases=len(fixed),
             fixed_rear_reference_drop_range_mm=interval(reference_all,'tip_drop_mm'),
             fixed_rear_reference_reach_range_mm=interval(reference_all,'tip_x_mm'),
             fixed_rear_reference_compliance_range_deg_per_nmm=interval(reference_all,'front_compliance_gravity_deg_per_nmm'),
             fixed_rear_reference_front_drop_range_mm=interval(reference_all,'front_drop_mm'),
             fixed_total_reference_yield_ratio_range=interval(fixed,'core_reference_yield_ratio'),
             fixed_total_reference_yield_pass_count=sum(r['passes_reference_yield_screen'] for r in fixed),
             fixed_total_combined_pass_count=sum(r['passes_combined_reference_screen'] for r in fixed),
             swept_combined_pass_count=len(combined),
             maximum_rear_count_with_combined_pass=max((r['rear_modules'] for r in combined),default=None),
             max_reach_combined_candidate=max(combined,key=lambda r:r['tip_x_mm']) if combined else None,
             rear_groups=rear_groups,reference=reference)
        write_json(folder/'summary.json',summary);summaries.append(summary)
        checks.append(validate_front(R,base_cfg,material,cfg,spec,counts,reference,args.project))
        plot_front(folder,front,swept,fixed,frontier,counts,
                   (core_shape['points_mm'],core_shape['rear_cells']),
                   (no_core_shape['points_mm'],no_core_shape['rear_cells']),spec['effective_inspection_dimensions_mm'][2])
        all_rows.extend(swept);all_fixed.extend(fixed);all_ref.extend(reference_all)
        counts_seen.update((r['n_high'],r['n_uni'],r['n_directional'],r['n_low']) for r in swept+fixed)
        print(json.dumps({k:summary[k] for k in ['front_modules','swept_cases','fixed_total_cases','swept_combined_pass_count',
              'maximum_rear_count_with_combined_pass','fixed_rear_reference_drop_range_mm','fixed_total_reference_yield_pass_count']},ensure_ascii=False),flush=True)
    write_csv(out/'all_rear_sweep_combinations.csv',all_rows)
    write_csv(out/'all_fixed_N31_combinations.csv',all_fixed)
    write_csv(out/'reference_H8_U12_all_front_splits.csv',all_ref)
    write_csv(out/'reference_configurations.csv',reference_rows)
    compact=[]
    for s in summaries:
        row={k:v for k,v in s.items() if k not in ['rear_groups','reference','max_reach_combined_candidate']}
        row['max_combined_candidate_reach_mm']=s['max_reach_combined_candidate']['tip_x_mm'] if s['max_reach_combined_candidate'] else None
        row['max_combined_candidate']=s['max_reach_combined_candidate']['combination'] if s['max_reach_combined_candidate'] else None
        row={k:(json.dumps(v) if isinstance(v,list) else v) for k,v in row.items()}
        compact.append(row)
    write_csv(out/'front_count_summary.csv',compact)
    overview(out,summaries,all_ref,all_fixed,spec)
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    expected_swept=sum(n-1 for n in range(spec['rear_modules_min'],spec['rear_modules_max']+1))*sum(n-1 for n in spec['front_module_counts'])
    expected_fixed=sum((spec['focus_total_modules']-f-1)*(f-1) for f in spec['front_module_counts'])
    validation=dict(per_front=checks,all_cases_converged=all(r['converged'] for r in all_rows+all_fixed),
         maximum_moment_residual_nm=max(r['residual_nm'] for r in all_rows+all_fixed),
         swept_count=len(all_rows),expected_swept_count=expected_swept,fixed_total_count=len(all_fixed),expected_fixed_total_count=expected_fixed,
         unique_configurations=len(counts_seen),inputs_unchanged=unchanged,
         source_sha256=hashes,front_count_coverage=sorted({r['front_modules'] for r in all_rows}),
         all_reference_checks_passed=all(c['passed'] for c in checks))
    validation['passed']=bool(validation['all_cases_converged'] and unchanged and validation['all_reference_checks_passed']
                               and len(all_rows)==expected_swept and len(all_fixed)==expected_fixed)
    write_json(out/'validation.json',validation)
    write_json(out/'run_summary.json',dict(config=spec,fronts=summaries,validation=validation,
        scope='Original module EI and masses; rear-only 4.2 mm SS304; horizontal clamp; self weight only. '
              'No tendons, tip payload, contact, shear, torsion, plasticity or 3D path. Empty-box capsule screen is not CAD collision validation. '
              '205 MPa is a catalogue reference, not a measured rod strength. Above-yield shapes are elastic extrapolations only.'))
    print(json.dumps(dict(output=str(out.resolve()),validation_passed=validation['passed'],swept_cases=len(all_rows),
                          fixed_total_cases=len(all_fixed),unique_configurations=len(counts_seen)),ensure_ascii=False),flush=True)
    return 0 if validation['passed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
