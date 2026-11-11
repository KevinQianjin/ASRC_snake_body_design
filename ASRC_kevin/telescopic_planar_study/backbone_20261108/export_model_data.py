"""Export the full input data of the U4+M2 NiTi-backbone model from the model objects themselves.

Writes model_data/model_data.json and model_data/module_properties.csv. Every
number is read from the classes and files used by the studies (run_study.py,
spatial_model.py, backbone.py, side_pull.py, tank3d_screen.py, rope catalogue,
module_stiffness.sqlite3), so the sheet matches what was simulated.
"""
import json, csv, sqlite3, hashlib
from pathlib import Path
import numpy as np
from backbone import HERE, STUDY, VARIANTS, planar_rod, spatial_rod, MODULE_LENGTH, DENSITY, POISSON

OUT = HERE / 'model_data'
OUT.mkdir(exist_ok=True)
ROOT = STUDY.parent
DB = ROOT / 'module_stiffness.sqlite3'
ROPES = ROOT / 'h8u12_front5to8_payload500g' / 'inputs' / 'rope_materials.json'
ANCH = [4, 5, 6]


def r6(x):
    return float(f'{float(x):.6g}')


def main():
    con = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    db_rows = [dict(r) for r in con.execute('select * from rigidity')]
    db_modules = [dict(r) for r in con.execute('select * from modules')]
    rope_mat = next(m for m in json.loads(ROPES.read_text())['materials'] if m['id'] == 'nylon_pa6_reference')

    data = dict(
        title='U4+M2 flexible front with 1.8 mm NiTi backbone: model input data',
        sources=dict(stiffness_database=str(DB.relative_to(ROOT.parent)), stiffness_database_sha256=hashlib.sha256(DB.read_bytes()).hexdigest(),
                     rope_catalogue=str(ROPES.relative_to(ROOT.parent)), tank_step=str((STUDY / 'inputs' / 'tank-v2.step').relative_to(ROOT.parent))),
        units='SI unless the key says mm, g or deg',
        database_modules=db_modules, database_rigidities=db_rows)

    # Geometry and chain
    p = planar_rod(4, 2, ANCH, 20, 8, 'none')
    data['geometry'] = dict(
        configuration='U4+M2: modules 1-4 = U (PA12+NiTi), modules 5-6 = M (PA12), numbered from the base',
        module_length_mm=r6(p.module_length * 1000), module_count=6, flexible_length_mm=r6(p.flexible_length * 1000),
        interface_length_mm=r6(p.interface_length * 1000), interface_mass='massless rigid link between clamp and module 1',
        nominal_front_length_mm=r6(p.nominal_length * 1000), outer_diameter_mm=r6(p.diameter * 1000),
        tendon_guide_radius_mm=r6(p.r * 1000), joints='continuous 96 mm modules; no separate pin joint or gap is modelled',
        tendon_positions_local='up (+Y), right (+Z), down (-Y), left (-Z), each at 24 mm from the axis; world Y is up, X forward, Z right',
        rope_guides='rope passes through every module end disk up to its anchor; straight chord between consecutive disks')

    # Rod (backbone) properties
    data['niti_backbone_rod'] = dict(
        layout='one central rod per M module, running the full 96 mm module length, bonded to both M module end disks, laterally guided, bending with the module (stiffnesses add in parallel)',
        density_kg_m3=DENSITY, poisson=POISSON,
        variants={k: ({kk: r6(vv) for kk, vv in v.items()} if v else None) for k, v in VARIANTS.items()},
        torsion_formula='G J / L with G = E / (2 (1 + nu)), J = pi d^4 / 32, L = 96 mm',
        not_included='end fittings, guides, adhesive mass; NiTi phase transformation and hysteresis')

    # Per-module properties for each variant (what the solver uses)
    rows = []
    for v in ['none', 'niti18_E40', 'niti18_E75']:
        pr = planar_rod(4, 2, ANCH, 20, 8, v)
        sr = spatial_rod(4, 2, ANCH, 20, 8, v)
        sub = sr.sub; l = sr.l
        for k in range(6):
            c = k * sub
            rows.append(dict(variant=v, module=k + 1, type='U' if k < 4 else 'M', length_mm=96,
                             mass_bare_g=r6(pr.bare_mass[k] * 1000), rope_mass_g=r6(pr.rope_module_mass[k] * 1000),
                             mass_total_g=r6((pr.bare_mass[k] + pr.rope_module_mass[k]) * 1000),
                             EA_N=r6(pr.module_EA[k]),
                             EI_vertical_Nm2=r6(sr.K[c, 1] * l), EI_horizontal_Nm2=r6(sr.K[c, 2] * l),
                             torsion_module_Nm_per_rad=r6(sr.K[c, 0] * l / MODULE_LENGTH),
                             GJ_rod_coefficient_Nm2=r6(sr.K[c, 0] * l),
                             ropes_passing=int(pr.routes[:, k].sum() * 4)))
    with open(OUT / 'module_properties.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    data['module_properties'] = rows
    data['module_properties_note'] = ('Database values are structural rigidities of a whole module, not material moduli. '
                                      'Torsion: the database GJ column is the whole-module spring T/theta; the rod coefficient is T/theta x 0.096 m. '
                                      'M EI is the same in all directions; U vertical (against gravity) and horizontal EI differ. '
                                      'Rope mass counts 4 ropes per anchor set routed through that module.')
    tot = {v: dict(modules_g=r6(sum(q['mass_bare_g'] for q in rows if q['variant'] == v)),
                   ropes_in_front_g=r6(sum(q['rope_mass_g'] for q in rows if q['variant'] == v)),
                   front_total_g=r6(sum(q['mass_total_g'] for q in rows if q['variant'] == v))) for v in ['none', 'niti18_E40', 'niti18_E75']}
    data['mass_totals'] = tot

    # Payload
    data['payload'] = dict(head_mass_kg=p.payload_kg, model='point mass at the tip of module 6, no eccentric moment, no rotary inertia',
                           collision_envelope='63 mm diameter sphere/capsule (provisional; real head CAD not available)', gravity_m_s2=9.81)

    # Tendons
    data['tendons'] = dict(
        material=rope_mat['label'], young_modulus_pa=rope_mat['young_modulus_pa'], density_kg_m3=rope_mat['density_kg_m3'],
        diameter_mm=2.0, EA_N=r6(p.rope_ea), linear_density_g_per_m=r6(p.rope_density * 1000), calibrated=rope_mat['calibrated'],
        anchor_sets=dict(lead_layout=ANCH, meaning='each set = 4 ropes (up, right, down, left) anchored at the end disk of that module; module numbers counted from the base',
                         other_layouts_compared=dict(single=[6], two=[4, 6], three_U=[2, 4, 6], three_M=[4, 5, 6])),
        friction='none (frictionless guides)', bending_stiffness='none',
        pretension_N=1.0, pretension_rule='minimum 1 N on every rope (needed for 3D lateral stability)',
        numerical_bounds_N=[1.0, 250.0],
        winch_model=dict(model='fixed winch: linear elastic, tension-only rope; T = EA max(0, L + L_free - R) / R',
                         L_free_m=1.0, meaning='L = routed length inside the front, R = unstretched length set by the winch',
                         effective_stiffness_N_per_mm_at_1p6m=r6(p.rope_ea / 1.6 / 1000)))

    # Installation and tank
    from tank3d_screen import PLANE_WIDTH, R_ENV
    prof = np.load(STUDY / 'results' / 'cavity_profiles.npz')
    data['installation_and_tank'] = dict(
        installation_pitch_deg_studied=[15, 20, 25], recommended_pitch_deg=20,
        insertion_point_length_mm=449.0, insertion_point_height_mm=r6(np.interp(449., prof['length_mm'], prof['floor_mm'])),
        insertion_plane_width_mm=PLANE_WIDTH, clamp_position='s = distance of the base clamp along the axis past the insertion point',
        recommended_steering_clamp_s_mm=[0, 30], envelope_radius_mm=R_ENV,
        tank_model='all 362 solids of the named tank subtree in tank-v2.step, 461,524 triangles at 0.5 mm deflection',
        tank_coordinates='length = -oldX, height = oldY, width = -oldZ (mm)')

    # Numerical model
    data['numerics'] = dict(
        rod_model='extensible rod; planar (2 dof per cell: angle, axial strain) and spatial finite-rotation Kirchhoff rod (4 dof per cell: twist, 2 bending, axial strain)',
        cells_per_module=dict(search=[2, 4], reported=8, mesh_checks=16), quadrature='4-point Gauss-Legendre per cell for gravity and shape',
        gravity_and_tendons='all ropes and gravity act together; distal ropes compress proximal modules',
        stability='minimum eigenvalue of the energy Hessian including fixed-winch rope stiffness (1 m free rope); must be >= 0',
        strain_diagnostic=0.05, coarse_strain_bounds=dict(low_strain=0.0475, planar_low_strain=0.0485, exploratory=[-0.30, 0.15]),
        geometry_checks='local bend radius >= 31.5 mm (with 0.98 margin); nonlocal 63 mm capsule self-clearance for segments >= 126 mm apart',
        straightness_criteria='offset <= 10 mm, tangent error <= 5 deg, axial projection >= 95 %, strain <= 5 %, stable',
        held_elevation='world head elevation = installation pitch (+/- 5 deg band, or exact)',
        angle_search_cap_deg=180)
    (OUT / 'model_data.json').write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print('wrote', OUT / 'model_data.json', 'and module_properties.csv')
    for q in rows:
        print(q)
    print(tot)


if __name__ == '__main__':
    main()
