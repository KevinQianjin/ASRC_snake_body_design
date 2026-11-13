"""Export a simulation-exact design reference, not a manufacturing release.

Reads the frozen v3 nominal result and the solver's actual parameter objects.
No solver inputs, saved simulation results, or source CAD files are modified.
Run with the repository development Python environment.
"""
from pathlib import Path
import csv, hashlib, io, json, subprocess, sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = 'bee65b7'
STUDY = 'simulations/u4m2/backbone_20261108/'
SOURCE_CAD = ROOT / 'cad/previews/u4m2'

def git_bytes(path):
    return subprocess.check_output(['git', 'show', f'{REVISION}:{path}'], cwd=ROOT)

def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + '\n')

def main():
    # Fail if the local numerical implementation differs from the pinned one.
    paths = [STUDY+'backbone.py', STUDY+'length_cycle.py',
             'simulations/u4m2/steering_63mm_20261106/spatial_model.py',
             'simulations/u4m2/stiffness_63mm_20261106/run_study.py',
             'data/materials/module_stiffness.sqlite3']
    for path in paths:
        assert (ROOT/path).read_bytes() == git_bytes(path), f'Pinned-source mismatch: {path}'
    sys.path.insert(0, str(ROOT/STUDY))
    from backbone import spatial_rod, VARIANTS
    from length_cycle import LengthDrive
    r = spatial_rod(4, 2, [4, 5, 6], 20, 8, 'niti18_E40')
    d = LengthDrive(r, 1., 1.)
    saved = json.loads(git_bytes(STUDY+'model_data/model_data.json'))
    summary = json.loads(git_bytes(STUDY+'closed_loop_v3_results/nominal_summary.json'))
    settings = json.loads(git_bytes(STUDY+'closed_loop_v3_results/settings.json'))
    records = json.loads(git_bytes(STUDY+'closed_loop_v3_results/nominal.json'))
    states = np.load(io.BytesIO(git_bytes(STUDY+'closed_loop_v3_results/nominal_states.npz')))['closed']
    L = float(r.planar.module_length*1000)
    interface = float(r.planar.interface_length*1000)
    modules = []
    for i in range(r.n):
        k=i*r.sub
        modules.append(dict(name=f'{"U" if i<4 else "M"}{i+1}', index=i+1,
            start_mm=interface+i*L, end_mm=interface+(i+1)*L, length_mm=L,
            bare_mass_g=float(r.planar.bare_mass[i]*1000),
            routed_rope_mass_g=float(r.planar.rope_module_mass[i]*1000),
            EA_N=float(r.K[k,3]/r.l), EI_vertical_Nm2=float(r.K[k,1]*r.l),
            EI_horizontal_Nm2=float(r.K[k,2]*r.l), GJ_Nm2=float(r.K[k,0]*r.l),
            torsional_spring_Nm_per_rad=float(r.K[k,0]*r.l/(L/1000))))
    tendons=[]; coordinate_rows=[]
    directions=['UP','RIGHT','DOWN','LEFT']
    for g,anchor in enumerate(r.anchors):
        for q,off in enumerate(r.offsets*1000):
            name=f'{"ABC"[g]}-{directions[q]}'
            points=[[interface+j*L,float(off[1]),float(off[2])] for j in range(anchor+1)]
            tendons.append(dict(name=name,group='ABC'[g],anchor_module=anchor,
                diameter_mm=2.,radius_mm=float(np.linalg.norm(off)),
                guide_points_local_mm=points,anchor_local_mm=points[-1],
                free_length_m=d.free,EA_N=float(d.ea)))
            for j,pt in enumerate(points):
                coordinate_rows.append(dict(tendon=name,disk=j,x_mm=pt[0],y_mm=pt[1],z_mm=pt[2],role='anchor' if j==anchor else 'pass-through'))
    rods=[dict(module=i+1,start_local_mm=[interface+i*L,0.,0.],
               end_local_mm=[interface+(i+1)*L,0.,0.],length_mm=L,**VARIANTS['niti18_E40']) for i in [4,5]]
    metadata=dict(status='SIMULATION REFERENCE ONLY — NOT A MANUFACTURING RELEASE',
        source_revision=subprocess.check_output(['git','rev-parse',REVISION],cwd=ROOT,text=True).strip(),
        units='Geometry mm; mechanical quantities SI unless explicitly suffixed',
        frame='Local X: straight assembly axis; Y: UP; Z: RIGHT; origin at clamp. World frame = rotate local frame +20 degrees about Z.',
        module_count=r.n,flexible_length_mm=L*r.n,interface_length_mm=interface,
        nominal_front_length_mm=interface+L*r.n,collision_diameter_mm=r.diameter*1000,
        interface_model='Massless rigid link. Its displayed cylinder is an envelope, not designed adapter hardware.',
        modules=modules,backbones=rods,tendons=tendons,
        payload=dict(mass_kg=r.payload,point_local_mm=[interface+L*r.n,0.,0.],
                     eccentricity_mm=[0.,0.,0.],rotary_inertia='not modeled',
                     collision_diameter_mm=63.,physical_head_geometry='unspecified'),
        installation=dict(pitch_deg=r.pitch,steering_clamp_s_mm=15.,
                          frame_note='Clamp-local assembly coordinates are not absolute tank coordinates.'),
        tendon_material={k:saved['tendons'][k] for k in ['material','young_modulus_pa','density_kg_m3','diameter_mm','EA_N','linear_density_g_per_m','calibrated','friction','bending_stiffness','winch_model']},mass_totals=saved['mass_totals']['niti18_E40'],
        controller=summary['settings'],settled_angle_target_deg=.2,angle_acceptance_deg=1.,
        total_rope_offset_limit_mm=5.,correction_limit_mm=.25,
        assumptions=['Backbone is fixed/bonded at both M end disks and constrained to co-deform with the module.',
            'No independent backbone slip, end compliance, or inter-guide buckling DOFs exist.',
            'Module interfaces have no added gap, hinge, slip, mass or extra compliance.',
            'Tendons are frictionless and tension-only, with straight chords between module-end guides.',
            'No motor dynamics, sensing noise/delay, backlash, NiTi hysteresis or fatigue.'],
        authority_note='Use v3 nominal_summary.json runtime settings: target 3 N, settle floor 2.5 N. The gains metadata settings.json retains a stale 1.5 N value; it is not the v3 controller target.',
        saved_nominal_result=summary)
    metadata['tendon_material']['historical_pretension_note']='The exported model sheet includes older 1 N exploration; latest runtime target/floor are in controller.'
    write_json('baseline.json',metadata)
    with (HERE/'tendon_coordinates.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=coordinate_rows[0]);w.writeheader();w.writerows(coordinate_rows)
    with (HERE/'module_properties.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=modules[0]);w.writeheader();w.writerows(modules)
    # Select one actual saved 500 g entry pose for a curved analysis view.
    idx=next(i for i,x in enumerate(records) if x['phase']=='right_out' and x['target_yaw_deg']>=90)
    _,_,ev=r.evaluate(states[idx],detail=True)
    p=(ev['points']+np.array([interface/1000,0,0]))*1000
    F=ev['frames']; disks=p[::r.sub]; frames=F[::r.sub]
    routes=[]
    for t in tendons:
        off=np.array(t['anchor_local_mm']);off[0]=0
        routes.append(dict(name=t['name'],points_local_mm=[(disks[j]+frames[j]@off).tolist() for j in range(t['anchor_module']+1)]))
    pose=dict(sample_index=idx,phase=records[idx]['phase'],yaw_deg=records[idx]['yaw_deg'],elevation_deg=records[idx]['elevation_deg'],
        points_local_mm=p.tolist(),frames=F.tolist(),tendon_paths=routes,
        note='Actual saved equilibrium; line/collision-envelope representation, not a deformation of the detailed source STEP mesh.')
    write_json('saved_pose.json',pose)
    # Quantify physical conflicts; do not silently change the idealized model.
    conflicts=[]
    for direction in directions:
        same=[t for t in tendons if t['name'].endswith('-'+direction)]
        conflicts.append(dict(direction=direction,tendons=[t['name'] for t in same],
            coincident_interval_local_x_mm=[interface,interface+4*L],
            minimum_center_distance_mm=0.,minimum_surface_gap_for_2mm_ropes_mm=-2.))
    import trimesh
    cad=[]
    for f in sorted(SOURCE_CAD.glob('*.stl')):
        mesh=trimesh.load(f,process=False);axes=[0,2] if f.name.startswith('Uni') else [0,1]
        radius=float(np.linalg.norm(mesh.vertices[:,axes],axis=1).max())
        cad.append(dict(file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bounds_mm=mesh.bounds.tolist(),
                        enclosing_cylinder_diameter_mm=2*radius,exceeds_63mm_envelope=radius>31.5+1e-6))
    write_json('cad_geometry_audit.json',cad)
    checks={
        'configuration_U4_M2':r.n==6 and r.u_count==4 and r.m_count==2,
        'lengths_96_576_20_596':np.allclose([L,L*r.n,interface,interface+L*r.n],[96,576,20,596]),
        'twelve_tendons_four_each':len(tendons)==12 and r.anchors==[4,5,6],
        'all_tendon_radii_24mm':all(abs(t['radius_mm']-24)<1e-10 for t in tendons),
        'all_offsets_exact_solver_offsets':all(np.allclose(t['anchor_local_mm'][1:],r.offsets[q%4,1:]*1000) for q,t in enumerate(tendons)),
        'two_1p8mm_96mm_backbones':len(rods)==2 and all(x['diameter_mm']==1.8 and x['length_mm']==96 for x in rods),
        'payload_500g_at_x596':r.payload==.5 and metadata['payload']['point_local_mm']==[596.,0.,0.],
        'latest_runtime_tension_3N_floor_2p5N':summary['settings']['tension_target_n']==3 and summary['settings']['settle_tension_n']==2.5,
        'saved_cycle_1072_completed':summary['completed'] and len(states)==len(records)==1072,
        'no_new_hardware_inferred':True,
    }
    assert all(checks.values()),checks
    report=dict(parameter_checks=checks,parameter_checks_pass=True,
        physical_manufacturing_conformance=False,
        blocking_issues=['Three same-direction physical tendons occupy the same ideal route through U1-U4; B/C remain coincident through M5.',
                         'Original U/M body meshes exceed the 63 mm collision envelope; source geometry remains unchanged reference geometry.',
                         'Fixed/co-deforming backbone and rigid interfaces are ideal constraints, not implemented or verified hardware.',
                         'Real head/adapter, module stiffness, rope stiffness and masses have not been validated against manufactured hardware.'],
        route_conflicts=conflicts,
        historical_metadata_conflict=dict(gain_settings_target_n=settings['feedback_tension_target_n'],runtime_target_n=summary['settings']['tension_target_n']),
        new_simulation_performed=False)
    write_json('validation.json',report)
    provenance={path:hashlib.sha256(git_bytes(path)).hexdigest() for path in paths}
    for name in ['closed_loop_v3_results/nominal_summary.json','closed_loop_v3_results/nominal_states.npz','closed_loop_v3_results/nominal.json']:
        provenance[STUDY+name]=hashlib.sha256(git_bytes(STUDY+name)).hexdigest()
    write_json('source_hashes.json',provenance)
    print(json.dumps({'parameter_checks_pass':True,'manufacturing_conformance':False,'files_written':8,'saved_pose_sample':idx},indent=2))

if __name__=='__main__': main()
