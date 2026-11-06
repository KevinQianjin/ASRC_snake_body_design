"""Aggregate equilibria, screen saved CAD sections, and compute rear references."""
from pathlib import Path
import json, sys, hashlib, shutil, math
import numpy as np
from run_study import HERE, OUT, OLD, DB, DATA, PAIRS, DatabaseRod, dump, write_csv
from lightweight_path_check import Obstacles
from rear_beam import solve_beam, segments_for

def inside_cavity(points, profiles, radius=31.5, margin=5):
    xs=profiles['length_mm'];floor=profiles['floor_mm'];roof=profiles['roof_mm']
    x,y=points.T
    return bool(np.all((x>=radius+margin)&(x<=1600-radius-margin)&
        (y>=np.interp(x,xs,floor)+radius+margin)&(y<=np.interp(x,xs,roof)-radius-margin)))

def below_tank(points, profiles, radius=31.5):
    x,y=points.T
    within=(x>=0)&(x<=1600)
    return bool(np.all((~within)|(y+radius<np.interp(x,profiles['length_mm'],profiles['floor_mm']))))

def choose(rows, pitch, mode):
    candidates=[r for r in rows if r.get('fine_converged') and r.get('kind')=='optimized' and abs(r['pitch_deg']-pitch)<1e-6 and r['strain_mode']==mode and r['stable_with_1m_extra_rope'] and (mode!='low_strain' or r['strain_diagnostic_pass']) and not r['nonlocal_capsule_overlap'] and not r['local_radius_curvature_exceeded']]
    if not candidates:return None
    return min(candidates,key=lambda r:r['maximum_axis_deviation_mm']+.5*max(0,r['nominal_front_length_mm']-r['axial_projection_mm']))

def path_check(row, points, obstacles, profiles):
    """Front-only fixed actively tensioned shape, including initial head entry.

    The moving clamp is not restricted to lie in front of the old rear guide.
    No storage tube is invented; crossing that guide is reported as packaging
    unvalidated. Thus even a clear front sweep is not complete installation.
    """
    pitch=row['pitch_deg'];a=np.radians(pitch);v=np.array([np.cos(a),np.sin(a)])
    entry=np.array([449.,np.interp(449.,profiles['length_mm'],profiles['floor_mm'])])
    p=points*1000;start=-row['nominal_front_length_mm']-150
    sgrid=np.arange(start,1000.001,4.)
    gaps=[];ins=[];selected=None
    for s in sgrid:
        moved=p+entry+s*v
        gap=obstacles.clearance(moved)-31.5
        gaps.append(gap);ins.append(inside_cavity(moved,profiles))
        if ins[-1] and gap>=5:
            selected=len(gaps)-1
            break
    gaps=np.asarray(gaps);sgrid=sgrid[:len(gaps)];ins=np.asarray(ins)
    # Recheck the complete front-only path to the first final placement at 2 mm.
    if selected is not None:
        sgrid=np.arange(start,sgrid[selected]+.001,2.)
        gaps=np.array([obstacles.clearance(p+entry+s*v)-31.5 for s in sgrid])
        final_s=float(sgrid[-1])
    else:final_s=None
    initial=p+entry+start*v
    min_gap=float(gaps.min());max_step=float(np.max(np.diff(sgrid)))
    # Distance to a fixed obstacle is 1-Lipschitz under a rigid translation.
    certified_lower=min_gap-max_step/2
    bad=np.flatnonzero(gaps<5)
    result=dict(configuration=row['configuration'],state_id=row['state_id'],architecture=row['architecture'],
        strain_mode=row['strain_mode'],pitch_deg=pitch,anchors=row['anchors'],
        max_abs_axial_strain=row['max_abs_axial_strain'],low_strain_diagnostic_pass=row['strain_diagnostic_pass'],
        start_s_mm=float(start),final_s_mm=final_s,final_fully_inside_sampled_cavity=final_s is not None,
        initial_front_below_or_outside_tank=below_tank(initial,profiles),
        initial_head_below_or_outside_tank=below_tank(initial[-1:],profiles),
        minimum_sampled_envelope_clearance_mm=min_gap,
        conservative_translation_clearance_lower_bound_mm=certified_lower,
        front_only_continuous_translation_screen_pass=bool(final_s is not None and certified_lower>=5),
        first_failed_sample_s_mm=None if not len(bad) else float(sgrid[bad[0]]),
        path_step_mm=max_step,fixed_active_tendon_tensions_n=row['all_tendon_tensions_n'],
        front_width_checked_planes_mm=[628,632,648,664,668],
        required_front_width_span_mm=[616.5,679.5],
        initial_head_feed_geometrically_screened=True,
        rear_guide_and_storage_packaging_validated=False,full_width_and_full_3D_validated=False,
        scope='Front-only sweep through saved 2D sections; translating clamp; no sheath support/contact or rear packaging; fixed actively tensioned equilibrium, not passive sag')
    return result,sgrid,gaps

def run():
    assert hashlib.sha256(DB.read_bytes()).hexdigest()==DATA['database_sha256'], 'Database changed during the run'
    completions=[];allrows=[];baselines=[];states={}
    for u,m in PAIRS:
        c=json.loads((OUT/f'U{u}_M{m}_completion.json').read_text());assert c['completed'];completions.append(c)
        assert c['database_sha256']==DATA['database_sha256']
        allrows.extend(json.loads((OUT/f'U{u}_M{m}_best.json').read_text()))
        baselines.extend(json.loads((OUT/f'U{u}_M{m}_baseline.json').read_text()))
        states[f'U{u}-M{m}']=np.load(OUT/f'U{u}_M{m}_states.npz')
    write_csv(OUT/'all_equilibria.csv',baselines+allrows)
    dump(OUT/'all_equilibria.json',baselines+allrows)
    representatives=[]
    for u,m in PAIRS:
        rows=[r for r in allrows if r['configuration']==f'U{u}-M{m}']
        for pitch in [15,20,25]:
            for mode in ['shape_only','low_strain']:
                row=choose(rows,pitch,mode)
                if row:representatives.append(row)
    dump(OUT/'representatives.json',representatives);write_csv(OUT/'representatives.csv',representatives)
    # Conservatively project all five previously retained section polygons.
    cad=json.loads((OLD/'results/cad_sections.json').read_text())
    obstacles=Obstacles(cad['sections']);profiles=np.load(OLD/'results/cavity_profiles.npz')
    # Reproduce the earlier known clearance on its original three planes.
    reference=Obstacles([s for s in cad['sections'] if s['width_mm'] in [632,648,664]])
    old=np.load(OLD/'results/front_refined_states.npz');a=np.radians(20)
    entry=np.array([449.,np.interp(449.,profiles['length_mm'],profiles['floor_mm'])])
    old_distance=reference.clearance(old['r004_points_m']*1000+entry+884*np.array([np.cos(a),np.sin(a)]))
    assert abs(old_distance-21.091794349950874)<1e-6
    paths=[];curves={}
    for row in representatives:
        p=states[row['configuration']][row['state_id']+'_points_m']
        result,s,gap=path_check(row,p,obstacles,profiles);paths.append(result)
        key=row['configuration']+'_'+row['state_id']
        curves[key+'_s_mm']=s;curves[key+'_gap_mm']=gap
        print('PATH',row['configuration'],row['pitch_deg'],row['strain_mode'],row['architecture'],
              'clearance',round(result['minimum_sampled_envelope_clearance_mm'],2),
              'end',result['final_s_mm'],'pass',result['front_only_continuous_translation_screen_pass'],flush=True)
        dump(OUT/'front_only_path_screen.json',paths)
    np.savez_compressed(OUT/'front_only_path_curves.npz',**curves)
    # Reference only: original 40/30 mm tubes are supporting beams, not a tube
    # through which the new 63 mm modules can pass. Gravity reactions only.
    rear=[]
    for row in representatives:
        if abs(row['pitch_deg']-20)>1e-6:continue
        for exposure in [.6,1.]:
            for layout in ['stepped_40_30','single_30']:
                q=solve_beam(segments_for(layout,exposure),np.radians(row['pitch_deg']),
                    row['vertical_gravity_reaction_n'],row['gravity_moment_about_interface_nm'],numerical_check=True)
                for key in ['nominal_yield_screen_ratio','nominal_yield_factor','passes_nominal_section_yield_screen']:q.pop(key,None)
                q.update(configuration=row['configuration'],state_id=row['state_id'],strain_mode=row['strain_mode'],layout=layout,
                    scope='Gravity-only ideal original tube reference; NOT a 63mm storage sheath; tendon/actuator reactions, joints and overlap omitted')
                rear.append(q)
    dump(OUT/'rear_reference.json',rear);write_csv(OUT/'rear_reference.csv',rear)
    fine=[r for r in allrows if r.get('fine_converged')]
    critical=[]
    for u,m in PAIRS:
        r=DatabaseRod(u,m,[u+m])
        # Characteristic force needed to oppose the straight M segment root
        # moment, excluding internal bending resistance and rope weight.
        length=m*.096
        moment=9.81*np.cos(np.radians(20))*(.5*length+r.bare_mass[-m:].sum()*length/2)
        critical.append(dict(configuration=r.label,M_length_mm=length*1000,
            straight_M_root_head_and_module_moment_nm=float(moment),
            characteristic_tendon_force_n=float(moment/.024),
            M_5percent_axial_force_n=166.694*.05,
            scope='Straight-state moment balance scale, not a solved equilibrium or failure limit'))
    summary=dict(database_sha256=DATA['database_sha256'],diameter_mm=63,guide_radius_mm=24,
        configuration_pairs=PAIRS,pitches_deg=[15,20,25],
        natural_baselines=len(baselines),single_sweep_attempts=sum(q['sweep_attempts'] for q in completions),
        single_sweep_equilibria=sum(q['sweep_equilibria'] for q in completions),
        local_optimizer_attempts=sum(q['optimizer_attempts'] for q in completions),
        fine_best_records=len(fine),optimized_fine_records=sum(r['kind']=='optimized' for r in fine),
        straight_geometry_records=sum(r['provisional_straight_geometry'] for r in fine),
        all_straight_diagnostics_pass_records=sum(r['all_straight_diagnostics_pass'] for r in fine),
        maximum_mesh_tip_change_mm=max(r.get('mesh_tip_change_mm',0) for r in fine),
        low_strain_optimized_records=sum(r['kind']=='optimized' and r['strain_mode']=='low_strain' and r['strain_diagnostic_pass'] for r in fine),
        path_screen_records=len(paths),front_only_path_pass_records=sum(r['front_only_continuous_translation_screen_pass'] for r in paths),
        low_strain_front_only_path_pass_records=sum(r['front_only_continuous_translation_screen_pass'] and r['low_strain_diagnostic_pass'] for r in paths),
        full_installation_validated=False,clearance_reference_abs_error_mm=abs(old_distance-21.091794349950874),
        characteristic_M_loads=critical,
        scope='Finite local planar searches with active insertion tension; no global impossibility or material safety claim')
    dump(OUT/'summary.json',summary)
    shutil.copy2(DB,HERE/'module_stiffness_input.sqlite3')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':run()
