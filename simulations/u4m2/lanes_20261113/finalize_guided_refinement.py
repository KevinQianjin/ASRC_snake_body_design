"""Validate and publish the dated 15 November guide-refinement study outputs."""
import csv,gzip,hashlib,json,re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import lanes
from state_archives import load_states,NAMES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'guided_refinement_20261115'
CAD=ROOT/'cad/lanes_u4m2/guides_v3'


def load(name):return json.loads((OUT/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    mass=load('v3_final_mass_holds/summary.json')
    contact=load('v3_final_contact/summary.json')
    path=load('v3_final_path/summary.json')
    selection=load('contact_subset_final/selection_summary.json')
    provenance=load('contact_subset_final/selected.json')
    convergence=load('mount_convergence_float64/summary.json')
    original_contact=load('v3_contact/summary.json')
    geometry=json.loads((CAD/'geometry_check.json').read_text())
    snapshot=OUT/'v3_final_mass_holds/candidate_mass.json'
    archive=OUT/'v3_final_mass_holds/mass_holds_states.npz'
    states,coverage=load_states(archive)
    n=len(states)
    assert mass['completed'] and mass['all_states_solved'] and len(mass['rows'])==n==selection['selected_records']==217
    assert contact['completed'] and len(contact['rows'])==n*8
    assert len({(r['state'],r['part'],r['resolution_mm']) for r in contact['rows']})==n*8
    assert contact['archive_sha256']==sha(archive)==path['coverage'][0]['sha256']
    assert sha(snapshot)==sha(CAD/'mass_model.json')
    assert geometry['all_straight_positions_clear']
    assert load('socket_gap_verification.json')['all_samples_pass']
    for filename,expected in contact['guide_cad_sha256'].items():assert sha(CAD/filename)==expected
    assert load('v2_reproduction.json')['all_identical'] and load('v2_reproduction.json')['count']==24
    bad=[r for r in contact['rows'] if not r['pass_interference']]
    bad_states={r['state'] for r in bad}
    max_overlap=max(r['overlap_mm3'] for r in contact['rows'])
    rows=mass['rows']
    summary=dict(selected_records=n,unique_geometries=path['unique_geometry_states'],guide_part_checks=n*8,
        failed_guide_part_checks=len(bad),records_with_guide_contact=len(bad_states),maximum_guide_overlap_mm3=max_overlap,
        largest_head_change_mm=max(r['head_change_mm'] for r in rows),
        largest_yaw_change_deg=max(abs(r['yaw_change_deg']) for r in rows),
        largest_elevation_change_deg=max(abs(r['elevation_change_deg']) for r in rows),
        mass_change_g=mass['mass_change_g'],total_mass_change_g=sum(mass['mass_change_g']),
        minimum_fixed_winch_eigenvalue=min(r['candidate']['minimum_fixed_winch_eigenvalue'] for r in rows),
        maximum_equilibrium_residual=max(r['candidate']['equilibrium_residual'] for r in rows),
        all_rod_geometry_checks_pass=all(r['candidate']['geometry_pass'] for r in rows),
        all_fixed_winch_tangents_positive=all(r['candidate']['stable_fixed_winch'] for r in rows),
        minimum_tension_n=float(min(np.min(r['candidate']['tensions_n']) for r in rows)),
        maximum_tension_n=float(max(np.max(r['candidate']['tensions_n']) for r in rows)),
        rope_flexure_clearance_mm=path['minimum_flexure_clearance_bound_mm'],
        end_region_penetrating_records=path['end_region_penetrating_states'],
        maximum_end_region_center_penetration_mm=path['maximum_end_region_center_penetration_mm'],
        cad_axial_resolution_mm=0.5,finer_025mm_check_completed=False,
        contact_checkpoint_recovery=contact.get('checkpoint_recovery'),
        full_closed_loop_replayed=False,manufacturing_release=False,
        limitations=['selected-state geometric screen, not all motion','remaining joint/contact incompatibility',
                     'short bond land and mount-induced stiffness unvalidated','finite end routing fails',
                     'no friction/dynamics/hardware validation',
                     'finer 0.25 mm check incomplete after memory-limit termination'])
    (OUT/'validated_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'v3_final_path/path_checks.csv').open() as f:checks=list(csv.DictReader(f))
    assert len(checks)==n and [r['state'] for r in checks]==[str(i) for i in range(n)]
    lanes.install((21,24,28),24,json.loads(snapshot.read_text()))
    rod=lanes.backbone.spatial_rod(4,2,[4,5,6],20,8)
    with gzip.open(OUT/'selected_pose_metrics.csv.gz','wt',newline='') as f:
        writer=None
        for i,(_,z,T,_) in enumerate(states):
            m=rows[i]['candidate'];d=rod.evaluate(z,T,detail=True)[2]
            pr=provenance[i];check=checks[i]
            c=[r for r in contact['rows'] if r['state']==str(i)]
            row=dict(selected_record=i,source_archive=pr['archive'],source_state=pr['source_state'],phase=pr['phase'],
                yaw_deg=m['yaw_deg'],world_elevation_deg=m['world_elevation_deg'],
                head_change_mm=rows[i]['head_change_mm'],equilibrium_residual=m['equilibrium_residual'],
                minimum_fixed_winch_eigenvalue=m['minimum_fixed_winch_eigenvalue'],
                maximum_guide_body_overlap_mm3=max(r['overlap_mm3'] for r in c),
                rope_flexure_clearance_bound_mm=check['flexure_clearance_bound_mm'],
                end_region_centerline_points_inside=check['end_region_centerline_points_inside'],
                maximum_end_region_center_penetration_mm=check['maximum_end_region_center_penetration_mm'])
            row.update({f'head_world_{axis}_mm':v for axis,v in zip('xyz',m['head_world_mm'])})
            row.update({f'head_frame_base_R{a}{b}':float(d['frames'][-1,a,b]) for a in range(3) for b in range(3)})
            for k,name in enumerate(NAMES):
                row[name+'_internal_path_mm']=float(d['rope_lengths'].ravel()[k]*1000)
                row[name+'_tension_n']=float(T.ravel()[k])
            if writer is None:writer=csv.DictWriter(f,list(row));writer.writeheader()
            writer.writerow(row)

    fig,axes=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
    resolutions=[0,2,1,.5]
    for state,label in [('y0_z8','0° hold'),('y90_z8','90° hold'),('y175_z8','175° hold')]:
        values=[max(r['overlap_mm3'] for r in convergence['rows'] if r['state']==state and r['resolution_mm']==h) for h in resolutions]
        axes[0].plot(range(4),values,'o-',label=label)
    axes[0].set(xticks=range(4),xticklabels=['Original\n≤24.6 mm','≤2 mm','≤1 mm','≤0.5 mm'],yscale='log',
        ylabel='Largest V2 guide/body overlap (mm³)',title='Correct the CAD surface approximation first')
    axes[0].legend();axes[0].grid(alpha=.25)
    angles=[r['candidate']['yaw_deg'] for r in rows]
    overlap=[max(r['overlap_mm3'] for r in contact['rows'] if r['state']==str(i)) for i in range(n)]
    axes[1].scatter(angles,overlap,s=16,c=['#bd4c32' if x>1e-6 else '#246b87' for x in overlap],alpha=.7)
    axes[1].set(xlabel='Re-solved head yaw (degrees)',ylabel='Largest guide/body overlap per record (mm³)',
        title=f'Final V3 candidate: {n} selected records')
    axes[1].grid(alpha=.25)
    fig.suptitle('500 g payload — geometric screening, not manufacturing approval',fontsize=12)
    fig.savefig(OUT/'comparison.png',dpi=180);plt.close(fig)

    report=ROOT/'reports/daily/Morning_Report_2026_11_15.md';text=report.read_text()
    outcome=(f'The corrected final candidate has **{len(bad)} failing guide-part checks out of {n*8}**, '
             f'across **{len(bad_states)} of {n} selected equilibrium records**. Its largest returned overlap is '
             f'**{max_overlap:.6f} mm³**. The remaining contact is concentrated near the short fixed land; '
             'mouth relief alone does not establish mounting compatibility.')
    text=text.replace('**CONTACT_SUMMARY_PENDING**',outcome)
    paired=[]
    for source_state,yaw in [('y0_z8',0),('y90_z8',90),('y175_z8',175)]:
        i=next(i for i,p in enumerate(provenance) if p['source_state']==source_state)
        before=[r for r in convergence['rows'] if r['state']==source_state and r['resolution_mm']==.5]
        after=[r for r in contact['rows'] if r['state']==str(i)]
        paired.append(f"| {yaw}° | {max(r['overlap_mm3'] for r in before):.6f} | {max(r['overlap_mm3'] for r in after):.6f} | {rows[i]['head_change_mm']:.6f} |")
    paired_table='\n'.join(paired)
    section2=f'''## 2. V3 outer-saddle relief and a corrected CAD land

The retained engineering candidate has a nominal **0.15 mm gap**, an explicit
**0.5 mm axial land**, and a **1.5:1 radial/tangential relief slope** outside
that land. Its gap law is `0.15 + 1.5 × max(abs(z) − 0.25, 0)` mm, reaching
**2.205 mm** at the ±1.62 mm socket faces. The socket wall remains 0.85 mm.
Inner-web saddles, rope lanes, eyelets and guide stations retain their V2 sizes.

This run preserved the rejected variants rather than promoting a three-pose
pass to a full design pass:

| Candidate | Evidence | Decision |
|---|---|---|
| V2, no relief | Refined 175° maximum 5.9655 mm³ | Contact remains |
| Early V3 slopes 0.3 / 0.6 | Three-pose maxima about 1.882 / 0.720 mm³ | Reject |
| Early V3 slope 1.0 | Zero in three screening poses, but **17/181** expanded records fail; maximum **0.079759 mm³** | Reject as a contact-free design |
| Early V3 slope 1.5, nine-section loft | Outer cap files split into eight components instead of four | Reject before equilibrium promotion |
| Corrected V3 slope 1.5, explicit land breakpoints | Straight assembly/part checks pass; **{len(bad_states)}/{n}** selected records still have guide contact | Retain as a documented engineering candidate; no release |

The matched saved-tension comparison uses the same 0.5 mm CAD resolution for
both designs. V3 is re-solved with its updated CAD mass; the last column records
that small equilibrium change rather than implying identical imposed shapes.

| Source inverse hold | V2 largest overlap, mm³ | Final V3 largest overlap, mm³ | Head change with V3 mass, mm |
|---|---:|---:|---:|
{paired_table}

The original nine axial loft sections missed the land boundaries at ±0.25 mm.
Consequently the early variants did not actually contain the intended constant
0.15 mm gap over the whole 0.5 mm land. With larger relief, the retaining groove
could sever a cap. Adding the exact land breakpoints fixes that construction
error. The final CAD uses eleven section planes at the outer stations;
**112 rays measured from actual source-CAD web faces** verify its exported gap
profile, with maximum error **1.53e-6 mm** against the nominal law. This is a
numerical CAD check, not a printer tolerance or bond qualification.

All eight final frames are watertight single components; cap and lockwire files
each contain four components. All eight straight assemblies return zero
guide/body intersection. Zero relief reproduces **all 24 V2 frame/cap/wire
STLs byte-for-byte**. The published candidate STLs and mass file match the
variant used for the final calculations.

The head remains **500 g**; lanes remain **21/24/28 mm** and stations remain
**−24/−12/+12/+24 mm**. Rope bore/mouth diameters remain Ø2.6/Ø3.0 mm and the
plate remains 3.2 mm thick. The central Ø1.8 mm NiTi backbone remains independent;
no end ferrule is added. Bodies, disks and anchors are the unchanged V2 parts.

![Actual final V3 M5 CAD, cutaway preview](../../cad/lanes_u4m2/guides_v3/M5_assembly_preview.png)

The cutaway hides part of the body; it does not prove installation access.

[CAD and installation limits](../../cad/lanes_u4m2/guides_v3/README.md)
· [Straight checks](../../cad/lanes_u4m2/guides_v3/geometry_check.json)
· [Actual gap measurements](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/socket_gap_verification.json)
· [V2 reproduction hashes](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/v2_reproduction.json)

'''
    text=re.sub(r'## 2\..*?(?=## 3\.)',lambda _:section2,text,flags=re.S)
    section3=f'''## 3. Updated mass and selected-path equilibria

The final geometry changes the CAD mass estimate by **{summary['total_mass_change_g']:.5f} g total**
relative to V2. Adhesive, closure tails and real harness mass remain excluded;
mass is distributed uniformly along the rod cells and the prior homogenised
stiffness is retained. The unchanged head is a separate 500 g payload.

The final set contains **{n} records / {path['unique_geometry_states']} unique geometries**.
It includes the original targeted 181 records (startup, inverse holds,
left/right outward and return phases, insertion/exit, phase boundaries and
recorded extrema), plus **36 distinct motion geometries not used by that
initial selection**, chosen deterministically with seed 20261115 before the
final CAD checks. This is not the full 2,526-state motion archive.

| Metric | Final candidate |
|---|---:|
| Equilibria solved at saved tensions | {n} / {n} |
| Largest head position change from V2 | {summary['largest_head_change_mm']:.5f} mm |
| Largest absolute yaw change | {summary['largest_yaw_change_deg']:.5f}° |
| Largest absolute elevation change | {summary['largest_elevation_change_deg']:.5f}° |
| Minimum scaled fixed-winch tangent eigenvalue | {summary['minimum_fixed_winch_eigenvalue']:.6f} |
| Largest equilibrium residual | {summary['maximum_equilibrium_residual']:.3g} |
| Saved tension range | {summary['minimum_tension_n']:.5f}–{summary['maximum_tension_n']:.5f} N |
| Guide-part Boolean checks at 0.5 mm CAD resolution | {n*8} |
| Checks returning positive overlap above 1e-6 mm³ | {len(bad)} |
| Records with at least one guide/body overlap | {len(bad_states)} / {n} |
| Largest guide/body overlap | {max_overlap:.6f} mm³ |

Rod geometry checks pass: **{summary['all_rod_geometry_checks_pass']}**. All selected fixed-winch
tangents are positive: **{summary['all_fixed_winch_tangents_positive']}**. These statements concern
the ideal quasi-static rod, not the physical guide mounting. The mass study
holds tensions fixed; **the closed-loop controller and full tank-envelope
cycle were not replayed**. Positive tangent stiffness is not dynamic stability.

The [consolidated pose table](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/selected_pose_metrics.csv.gz)
contains provenance, phase, head pose/material frame, internal geometric rope
lengths, tensions, guide overlaps and rope contact results. It is a table of
re-solved equilibria, not a new time history or winch command sequence.

[Selection](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/contact_subset_final/selection_summary.json)
· [Mass equilibria](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/v3_final_mass_holds/summary.json)
· [Complete selected-state contact results](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/v3_final_contact/summary.json)

'''
    text=re.sub(r'## 3\..*?(?=## 4\.)',lambda _:section3,text,flags=re.S)
    section4=f'''## 4. Rope contact is still a blocker

The final {n} equilibria were checked against the unchanged V2 M bodies at
0.5 mm axial CAD resolution with rope sample intervals no greater than 1 mm.

| Metric | Final selected records |
|---|---:|
| Minimum sampled middle-flexure clearance after rope radius/sampling allowance | {path['minimum_flexure_clearance_bound_mm']:.5f} mm |
| Middle-flexure screen failures | {path['flexure_screen_failed_states']} / {n} |
| Records with end-region rope-centre penetration | **{path['end_region_penetrating_states']} / {n}** |
| Largest sampled centre penetration | **{path['maximum_end_region_center_penetration_mm']:.5f} mm** |
| Largest single-hole force | {path['maximum_hole_force_n']:.5f} N |
| Largest station resultant force | {path['maximum_station_force_n']:.5f} N |
| Largest station resultant moment | {path['maximum_station_moment_nmm']:.5f} N mm |

The independent 36-hold resolution comparison found nine penetrating holds at
both 1 and 0.5 mm resolution; maximum depth changed from 0.23858 to 0.23931 mm.
The end-region failure persists after correcting the long-triangle error.

These are sampled rope-centre penetrations, not a finite-radius contact-force
solution. The middle-flexure figure subtracts a 1 mm rope radius and a 0.5 mm
sampling allowance; it does not bound CAD deformation error or manufacturing
tolerance. Finite guide-mouth, disk and anchor contact/friction remain unresolved.

[Rope/load evidence](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/v3_final_path/summary.json)
· [Preliminary load requirements](../../simulations/u4m2/lanes_20261113/guided_refinement_20261115/v3_final_design_loads.json)

'''
    text=re.sub(r'## 4\..*?(?=## 5\.)',lambda _:section4,text,flags=re.S)
    text=text.replace('**29 distinct tests passed:** 15','**30 distinct tests passed:** 16')
    assert 'PENDING' not in text
    report.write_text(text)

    readme=ROOT/'README.md';text=readme.read_text().replace('Updated 14 November 2026','Updated 15 November 2026')
    old='''### 14 November 2026: guided 500 g paths and a rejected rigid-mount candidate

Validated ideal guided startup and a complete 500 g closed-loop cycle, corrected archive coverage, and produced the V2 mounting CAD and guide loads. Physical mounting and finite end routing failed their separate checks. The 15 November Morning Report refines the coarse CAD collision screen; retain the older numbers as a dated snapshot.

[Full validation report](simulations/u4m2/lanes_20261113/GUIDED_VALIDATION.md) · [V2 CAD](cad/lanes_u4m2/guides_v2/README.md) · [Archived evidence](simulations/u4m2/lanes_20261113/guided_validation_20261114/)

'''
    text=re.sub(r'### 14 November 2026.*?(?=### 13 November)',lambda _:old,text,flags=re.S)
    latest=f'''### 15 November 2026 — Morning Report (latest): refined CAD checks and V3 saddle development

**Morning Report timing:** reporting cutoff and actual run start **15 November 2026 07:01:11 EST (12:01:11 UTC)**; report preparation **08:12:54 EST (13:12:54 UTC)** on the same date. These are recorded execution times; future morning runs are scheduled for **07:00 US Eastern Time (12:00 UTC in EST / 11:00 UTC in EDT)**, with a maximum runtime of **two hours**.

The head remains **500 g**. Today's work separates numerical collision error from actual mounting problems, and produces reproducible V3 CAD, updated mass equilibria and a detailed English report.

- **Corrected CAD deformation:** the source STL has triangles spanning 24.6 mm axially. Conforming surface refinement reduces the V2 175° maximum overlap from 31.10 to **5.97 mm³**; remaining contact lies at the outer saddles in the three checked holds. This reduction corrects the measurement rather than proving a mechanical improvement.
- **V3 geometry:** flared outer sockets retain a true **0.5 mm land**, a 0.15 mm central gap and **1.5:1 mouth relief**. Explicit loft breakpoints fix an error that otherwise distorted the land and could split caps. All eight straight assemblies pass; **112 exported-STL gap measurements** agree with the design. Rope lanes/stations and the independent NiTi backbone are retained; no end ferrule is added.
- **Expanded validation:** **{n} re-solved records / {path['unique_geometry_states']} unique geometries**, including 36 additional unseen motion geometries, receive **{n*8} guide-part checks**. **{len(bad_states)} records still have guide contact**, maximum **{max_overlap:.6f} mm³**. The earlier three-pose pass missed intermediate-angle failures; this remains a development candidate.
- **Rope and force evidence:** minimum sampled middle-flexure clearance **{path['minimum_flexure_clearance_bound_mm']:.3f} mm**, peak hole load **{path['maximum_hole_force_n']:.3f} N**. **{path['end_region_penetrating_states']}/{n} records** still contain end-region rope-centre penetration, maximum **{path['maximum_end_region_center_penetration_mm']:.4f} mm**.
- **Verification and limits:** 30 distinct tests and 11 configuration checks pass; all 24 V2 guide/cap/wire STLs reproduce exactly with relief disabled. The final nominal bonding area is only about **5.67 mm² per outer saddle**. Joint strength, mounting stiffness and finite rope contact remain unresolved; **not released for manufacture**, and no new full closed-loop replay is claimed. A 0.25 mm refinement attempt exceeded the 8 GiB memory limit; the completed contact results use 0.5 mm resolution.

[Full English Morning Report](reports/daily/Morning_Report_2026_11_15.md) · [V3 CAD and installation limits](cad/lanes_u4m2/guides_v3/README.md) · [Evidence and reproduction](simulations/u4m2/lanes_20261113/guided_refinement_20261115/README.md) · [Comparison figure](simulations/u4m2/lanes_20261113/guided_refinement_20261115/comparison.png)

'''
    if '### 15 November 2026' in text:text=re.sub(r'### 15 November 2026.*?(?=### 14 November)',lambda _:latest,text,flags=re.S)
    else:text=text.replace('### 14 November 2026',latest+'### 14 November 2026',1)
    next_steps='''## Next steps

1. Resolve the remaining guide/land contact with an explicit local structural/contact model and a defensible bonded, articulated or compliant attachment. Include the effect on M-module stiffness and guide position.
2. Revise finite end-hole/anchor routing and check the full 2 mm rope envelope, material bridges and contact/friction.
3. With a physically compatible candidate, update mass/stiffness and replay the complete **500 g** closed-loop path, including finer equilibrium meshes and uncertainty cases.
4. Qualify printed parts, adhesive, lockwire, assembly access and cyclic wear using the simultaneous exported guide loads.
5. Add measured friction/backlash/hysteresis, actuator/sensor dynamics, actual head/harness geometry and rear deployment hardware.

[Detailed roadmap](docs/roadmap.md) · [Current limitations](docs/limitations.md) · [Module test plan](simulations/u4m2/backbone_20261108/M_BACKBONE_TEST_PLAN.md).

'''
    text=re.sub(r'## Next steps.*?(?=## Geometry and input data)',lambda _:next_steps,text,flags=re.S)
    if '[V3 guide candidate]' not in text:text=text.replace('## Prototype\n','## Prototype\n\nThe [V3 guide candidate](cad/lanes_u4m2/guides_v3/README.md) is the latest mounting experiment and reuses V2 module bodies. It remains unqualified for manufacture; see the latest Morning Report.\n',1)
    readme.write_text(text)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
