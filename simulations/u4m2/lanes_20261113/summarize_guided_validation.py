"""Build the English readout and plot from saved guided validation evidence."""
import csv,json,re
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE/'guided_validation_20261114'

def read(p):return json.loads(p.read_text())
def replace_section(path,key,content):
    s=path.read_text();pattern=rf'<!-- {key} -->.*?<!-- END_{key} -->'
    s,n=re.subn(pattern,f'<!-- {key} -->\n{content}\n<!-- END_{key} -->',s,flags=re.S)
    if n!=1:raise ValueError(f'Missing unique marker {key} in {path}')
    path.write_text(s)

def main():
    data={}
    for name in ['baseline','candidate']:
        p=ROOT/name
        data[name]=dict(reference=read(p/'reference/nominal_summary.json'),closed=read(p/'closed_loop/nominal_summary.json'),
            audit=read(p/'path_audit/summary.json'),trace=read(p/'closed_loop/nominal_trace.json'))
    report=HERE/'GUIDED_VALIDATION.md'
    lines=['| Metric | Guided baseline | V2 with CAD mass |','|---|---:|---:|']
    def row(label,values):lines.append('| '+label+' | '+' | '.join(str(v) for v in values)+' |')
    items=[data['baseline'],data['candidate']]
    row('Startup / inverse yaw states',[f"{d['audit']['coverage'][0]['states']} / {d['audit']['coverage'][1]['states']}" for d in items])
    row('Reference states / failed checks',[f"{d['reference']['states']} / {d['reference']['failed_checks']}" for d in items])
    row('Closed-loop settled samples / failed checks',[f"{d['closed']['samples']} / {d['closed']['settled']['failed_checks']}" for d in items])
    row('Motion trace states, including initial state',[len(d['trace']) for d in items])
    row('Motion trace failed checks, excluding initial state',[d['closed']['trace']['failed_checks'] for d in items])
    for label,key,fmt in [('Minimum motion tension (N)','minimum_tension_n','.3f'),('Peak motion tension (N)','peak_tension_n','.3f'),
                          ('Minimum motion tank clearance, before 1.5 mm allowance (mm)','minimum_clearance_mm','.3f'),
                          ('Minimum scaled fixed-winch tangent eigenvalue','minimum_eigenvalue','.6f'),
                          ('Largest accepted node step (mm)','maximum_node_move_mm','.3f')]:
        row(label,[format(d['closed']['trace'][key],fmt) for d in items])
    row('Largest settled angle error (deg)',[f"{max(d['closed']['settled']['maximum_yaw_error_deg'],d['closed']['settled']['maximum_elevation_error_deg']):.3f}" for d in items])
    row('Largest motion angle error (deg)',[f"{max(max(abs(t['yaw_error_deg']),abs(t['elevation_error_deg'])) for t in d['trace']):.3f}" for d in items])
    row('Audited records across all five archives',[sum(c['states'] for c in d['audit']['coverage']) for d in items])
    row('Unique deformed-CAD rope geometries',[d['audit']['unique_geometry_states'] for d in items])
    row('Minimum rope/flexure clearance bound (mm)',[f"{d['audit']['minimum_flexure_clearance_bound_mm']:.3f}" for d in items])
    row('Failed rope/flexure records',[d['audit']['flexure_screen_failed_states'] for d in items])
    row('Records with rope-centre penetration of end-region material',[d['audit']['end_region_penetrating_states'] for d in items])
    row('Largest sampled rope-centre penetration into end-region material (mm)',[f"{d['audit']['maximum_end_region_center_penetration_mm']:.3f}" for d in items])
    row('Largest single-hole force (N)',[f"{d['audit']['maximum_hole_force_n']:.3f}" for d in items])
    row('Largest station resultant force (N)',[f"{d['audit']['maximum_station_force_n']:.3f}" for d in items])
    row('Largest station resultant moment (N mm)',[f"{d['audit']['maximum_station_moment_nmm']:.3f}" for d in items])
    lines+=['','The control/model check columns cover angle, tension, rod geometry/strain, fixed-winch stability and the 63 mm tank envelope; the new CAD contact checks are listed separately. All counts describe recorded equilibria, not physical time samples. The five-archive audit intentionally includes overlapping reference/settled/trace states; the separate unique-geometry count removes exact repeated rod states. A positive eigenvalue refers to the scaled quasi-static fixed-winch tangent, not dynamic controller stability.',
        '', '[Baseline evidence](guided_validation_20261114/baseline/) · [V2 evidence](guided_validation_20261114/candidate/) · [Motion force and clearance plot](guided_validation_20261114/candidate/path_overview.png)',
        '', '![V2 path overview](guided_validation_20261114/candidate/path_overview.png)']
    replace_section(report,'RESULTS_TABLES','\n'.join(lines))
    mount=read(ROOT/'candidate/mount_audit/summary.json')
    lines=['| Held yaw | Interfering guide assemblies / 8 | Largest overlap (mm³) | Location |','|---|---:|---:|---|']
    for label in mount['selected_states']:
        rows=[r for r in mount['rows'] if r['state']==label];worst=max(rows,key=lambda x:x['overlap_mm3'])
        lines.append(f"| {label[1:-3]}° | {sum(not r['pass_interference'] for r in rows)} / 8 | {worst['overlap_mm3']:.3f} | {worst['part']} |")
    lines+=['','[Per-part Boolean results and selected-state coverage](guided_validation_20261114/candidate/mount_audit/summary.json). These are selected-pose checks, not an assertion that every intermediate guide-body configuration was collision-tested. A failure is already sufficient to withhold release.']
    replace_section(report,'MOUNT_RESULTS','\n'.join(lines))
    loads=read(ROOT/'candidate/design_loads.json');d=loads['scaled_design_requirements']
    lines=[f"V2 operating maxima are **{data['candidate']['audit']['maximum_hole_force_n']:.3f} N per hole**, **{data['candidate']['audit']['maximum_station_force_n']:.3f} N station resultant**, and **{data['candidate']['audit']['maximum_station_moment_nmm']:.3f} N mm station moment**.",
        '', '| Preliminary requirement, factor 3 | Value |','|---|---:|',
        f"| Single-hole load | {d['single_hole_force_n']:.2f} N |",f"| Station resultant force | {d['station_net_force_n']:.2f} N |",f"| Station resultant moment | {d['station_net_moment_nmm']:.2f} N mm |",
        f"| Sum of absolute hole forces at one station | {d['station_sum_absolute_hole_forces_n']:.2f} N |",
        f"| Nominal cantilever-root normal stress comparison | {d['nominal_arm_normal_stress_mpa']:.2f} MPa |",
        f"| Nominal projected hole-bearing stress comparison | {d['nominal_hole_bearing_mpa']:.2f} MPa |",'',
        '[Per-hole CSV, gzip](guided_validation_20261114/candidate/path_audit/hole_loads.csv.gz) · [Per-state checks](guided_validation_20261114/candidate/path_audit/path_checks.csv) · [Peak locations](guided_validation_20261114/candidate/path_audit/summary.json) · [Sizing assumptions and requirements](guided_validation_20261114/candidate/design_loads.json)']
    replace_section(report,'LOAD_RESULTS','\n'.join(lines))
    mesh=read(ROOT/'candidate/mesh_convergence.json')
    lines=['Nine new targeted tests and fourteen existing numerical/control tests pass. They cover archive formats and count alignment, actual station placement after refinement, directional energy gradients at 8/16 cells, force-vector balance and rotation, CAD kinematics, solid-inside detection, mass assignment, interleaved hole-load aggregation and accepted-motion trace alignment. Eleven existing configuration files pass the repository validator.',
        '', '| Hold | 8→16 cell head difference (mm) | Yaw difference (deg) | Elevation difference (deg) |','|---|---:|---:|---:|']
    for r in mesh['rows']:
        lines.append(f"| {r['state'][1:-3]}° | {r['head_difference_mm']:.3f} | {r['yaw_difference_deg']:.4f} | {r['elevation_difference_deg']:.4f} |")
    lines+=['','[Refinement results](guided_validation_20261114/candidate/mesh_convergence.json). Tensions are held fixed and only three equilibria are refined; this is not a full fine-mesh control replay. The 175° elevation difference exceeds the 0.2° settling target, so accuracy at that target has not been established by mesh convergence.']
    replace_section(report,'VERIFICATION_RESULTS','\n'.join(lines))
    c=data['candidate'];s=c['closed'];a=c['audit']
    text=(f"V2 recorded **{s['samples']:,} settled samples** and **{len(c['trace']):,} motion trace states**. "
        f"Control and envelope failures (settled / motion): **{s['settled']['failed_checks']} / {s['trace']['failed_checks']}**. "
        f"Motion tension range: **{s['trace']['minimum_tension_n']:.2f}–{s['trace']['peak_tension_n']:.2f} N**. "
        f"The sampled rope/flexure clearance bound is **{a['minimum_flexure_clearance_bound_mm']:.2f} mm**; "
        f"the largest single-hole load is **{a['maximum_hole_force_n']:.2f} N**. "
        f"**{a['end_region_penetrating_states']:,} audited records** also contain rope-centre penetration of end-region material. "
        "The ideal-guide results do not resolve the rigid mounting or finite end-hole contact problems.")
    replace_section(HERE.parents[2]/'README.md','GUIDED_METRICS',text)
    overview(data['candidate'])
    (ROOT/'summary.json').write_text(json.dumps({k:{n:v for n,v in d.items() if n!='trace'} for k,d in data.items()},indent=2)+'\n')


def overview(data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    trace=data['trace'];x=np.arange(len(trace))
    with (ROOT/'candidate/path_audit/path_checks.csv').open() as f:
        checks=[r for r in csv.DictReader(f) if r['archive'].endswith('nominal_trace_states.npz')]
    if len(checks)!=len(trace):raise ValueError('Plot trace alignment mismatch')
    fig,axs=plt.subplots(4,1,figsize=(12,11),sharex=True)
    axs[0].plot(x,[t['yaw_error_deg'] for t in trace],label='Yaw');axs[0].plot(x,[t['elevation_error_deg'] for t in trace],label='Elevation')
    axs[0].axhline(1,color='gray',ls='--');axs[0].axhline(-1,color='gray',ls='--');axs[0].set_ylabel('Angle error (deg)');axs[0].legend()
    axs[1].plot(x,[t['minimum_tension_n'] for t in trace],label='Minimum rope tension');axs[1].plot(x,[t['peak_tension_n'] for t in trace],label='Maximum rope tension')
    axs[1].axhline(2.5,color='gray',ls='--');axs[1].set_ylabel('Tension (N)');axs[1].legend()
    axs[2].plot(x,[float(t['flexure_clearance_bound_mm']) for t in checks],label='Rope/flexure bound')
    axs[2].plot(x,[t['clearance_mm']-1.5 for t in trace],label='Tank envelope bound')
    axs[2].fill_between(x,0,1,where=np.array([int(t['end_region_centerline_points_inside'])>0 for t in checks]),transform=axs[2].get_xaxis_transform(),color='crimson',alpha=.15,label='End-region centre penetration')
    axs[2].set_yscale('symlog',linthresh=1);axs[2].set_ylabel('Clearance (mm, symlog)');axs[2].legend()
    axs[3].plot(x,[float(t['maximum_hole_force_n']) for t in checks],label='Largest hole force')
    axs[3].plot(x,[float(t['maximum_station_force_n']) for t in checks],label='Largest station resultant')
    axs[3].set_ylabel('Guide load (N)');axs[3].legend()
    previous=None;ticks=[];labels=[]
    for i,t in enumerate(trace):
        if t['phase']!=previous:
            previous=t['phase'];ticks.append(i);labels.append(previous.replace('_',' '))
            for ax in axs:ax.axvline(i,color='.85',lw=.7)
    for ax in axs:ax.grid(alpha=.2)
    axs[-1].set_xticks(ticks,labels,rotation=20,ha='right');axs[-1].set_xlabel('Accepted equilibrium sequence (not physical time)')
    fig.suptitle('500 g payload, V2 CAD mass and ideal four-station guides\nGuide mounting and end-region rope interference remain unresolved',fontsize=14)
    fig.tight_layout();fig.savefig(ROOT/'candidate/path_overview.png',dpi=150);plt.close(fig)
if __name__=='__main__':main()
