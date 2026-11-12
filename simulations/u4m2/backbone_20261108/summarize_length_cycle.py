"""Aggregate completed cycle cases and document explicit acceptance failures."""
import hashlib, json, subprocess, importlib.metadata
from length_cycle import OUT, HERE, SOURCE, plot, spatial_rod, FastTank, to_tank, CASE_EN, PHASE_EN
import numpy as np
from spatial_model import DB, __file__ as SPATIAL_FILE
from pathlib import Path


def reasons(q):
    if q['status']!='solved':return ['solve_failed']
    fail=[]
    for name,ok in [
        ('tank_margin_below_5mm',q['clearance_margin_mm']>=5),
        ('unstable',q['eigenvalue']>1e-7),
        ('self_geometry',q['geometry_pass']),
        ('strain_above_5pct',q['strain']<=.05),
        ('pretension_below_0.95N',q['min_tension_n']>=.95),
        ('force_above_250N_diagnostic',q['peak_tension_n']<=250),
        ('step_above_5mm',q['max_point_step_mm']<=5.001),
        ('yaw_error_above_1deg',q['phase']=='straighten' or abs(q['yaw_error_deg'])<=1),
        ('elevation_error_above_5deg',q['phase']=='straighten' or abs(q['elevation_deg']-20)<=5)]:
        if not ok:fail.append(name)
    return fail

REASON_EN={'solve_failed':'Solver failure','tank_margin_below_5mm':'Tank clearance margin below 5 mm','unstable':'Unstable equilibrium','self_geometry':'Self-collision or curvature constraint','strain_above_5pct':'Strain above 5%','pretension_below_0.95N':'Pretension below 0.95 N','force_above_250N_diagnostic':'Force above 250 N diagnostic bound','step_above_5mm':'Sample displacement above 5 mm','yaw_error_above_1deg':'Yaw error above 1 deg','elevation_error_above_5deg':'Elevation error above 5 deg'}
def counts_en(values):
    return '; '.join(f'{REASON_EN.get(k,k)}: {v} samples' for k,v in values.items()) or 'None'
def prefix_en(values):
    return '; '.join(f'{PHASE_EN.get(k,k)}: {v:g} deg' for k,v in values.items())


def main():
    results=[]
    for f in sorted(OUT.glob('*_summary.json')):
        summary=json.loads(f.read_text()); rows=json.loads((OUT/f"{summary['case']}.json").read_text())
        counts={}; first={}; legs={}
        for q in rows:
            why=reasons(q)
            for reason in why:
                counts[reason]=counts.get(reason,0)+1
                first.setdefault(reason,{k:q.get(k) for k in ['index','phase','target_yaw_deg','yaw_deg','clamp_s_mm']})
            if q['status']=='solved':
                a=legs.setdefault(q['phase'],dict(states=0,failed_checks=0,min_clearance_mm=1e9,min_eigenvalue=1e9,max_yaw_error_deg=0.,min_tension_n=1e9))
                a['states']+=1;a['failed_checks']+=bool(why)
                a['min_clearance_mm']=min(a['min_clearance_mm'],q['clearance_mm'])
                a['min_eigenvalue']=min(a['min_eigenvalue'],q['eigenvalue'])
                a['max_yaw_error_deg']=max(a['max_yaw_error_deg'],abs(q['yaw_error_deg']))
                a['min_tension_n']=min(a['min_tension_n'],q['min_tension_n'])
        summary.update(failure_counts=counts,first_failures=first,phases=legs)
        prefix={}
        for phase in ['right_out','left_out']:
            last=0.
            for q in [v for v in rows if v['phase']==phase]:
                if reasons(q):break
                last=abs(q['target_yaw_deg'])
            prefix[phase]=last
        summary['all_checks_passing_outbound_prefix_deg']=prefix
        results.append(summary)
    provenance=dict(source=str(SOURCE.relative_to(HERE)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    database_sha256=hashlib.sha256(Path(DB).read_bytes()).hexdigest(),
                    spatial_kernel_sha256=hashlib.sha256(Path(SPATIAL_FILE).read_bytes()).hexdigest(),
                    git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
                    packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','numba','trimesh','rtree','vtk']},
                    code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'length_cycle.py',HERE/'backbone.py',HERE/'tank3d_screen.py']})
    (OUT/'comparison.json').write_text(json.dumps(dict(provenance=provenance,cases=results),indent=2))
    interpretation=['## Engineering interpretation','',
        'Numerical completion does not establish an executable trajectory. Negative tangent eigenvalues identify equilibria that cannot be treated as stable quasi-static motion.','']
    nominal=next((r for r in results if r['case']=='nominal'),None)
    if nominal:
        n=nominal
        interpretation += [
            f"- Nominal case: {n['states']} samples; {n['failed_checks']} fail at least one check. Failure counts overlap: {counts_en(n['failure_counts'])}.",
            f"- Maximum steering/elevation error: {n['maximum_yaw_error_deg']:.3f} / {n['maximum_elevation_error_deg']:.3f} deg. Peak rope force: {n['peak_tension_n']:.2f} N.",
            f"- Minimum sampled tank clearance: {n['minimum_clearance_mm']:.2f} mm; {n['minimum_clearance_mm']-1.5:.2f} mm after the 1.5 mm sampling/mesh allowance.",
            f"- Outbound sample prefixes passing all checks from zero yaw: {prefix_en(n['all_checks_passing_outbound_prefix_deg'])}. These are not continuous safety guarantees or geometric limits.",
            f"- Minimum straightening tangent eigenvalue: {n['phases']['straighten']['min_eigenvalue']:.4f}. Paying out the upper ropes by 10 mm is a specified initial condition for this study; failure here does not imply that every straightening procedure fails."]
        for phase in ['entry','right_out','right_return','left_out','left_return','exit']:
            q=n['phases'][phase]
            interpretation.append(f"- {PHASE_EN[phase]}: {q['failed_checks']} of {q['states']} samples fail; minimum rope force {q['min_tension_n']:.3f} N; minimum stability eigenvalue {q['min_eigenvalue']:.4f}.")
    interpretation += ['',
        '- Sensitivities replay the same open-loop commands. Changes in backbone stiffness or payload affect posture; rope stiffness and free length also affect pretension. Good angular tracking alone is insufficient.',
        '- Next step: add pretension margin and stability constraints, redesign startup and rope-length commands, then repeat the sensitivity cases. These corrections have not been implemented in this study.','']
    lines=['# U4+M2 Multi-Rope Length-Controlled Round-Trip Study','',
           'Rest-length commands for 12 ropes are derived from the existing E40, 20-degree, anchor [4,5,6] reference states at eight cells per module. Each commanded state is then solved forward from the preceding equilibrium, rather than replaying the stored posture.','',
           *interpretation,
           '## Results','',
           '| Case | Numerical cycle completed | All checks pass | Samples | Minimum tank clearance (mm) | Minimum stability eigenvalue | Peak force (N) | Maximum yaw error (deg) |',
           '|---|---|---|---:|---:|---:|---:|---:|']
    for s in results:
        lines.append(f"| {CASE_EN[s['case']]} | {'Yes' if s['completed'] else 'No'} | {'Yes' if s['all_checks_pass'] else 'No'} | {s['states']} | {s['minimum_clearance_mm']:.2f} | {s['minimum_eigenvalue']:.4g} | {s['peak_tension_n']:.2f} | {s['maximum_yaw_error_deg']:.2f} |")
    lines+=['','Completion means stationary solutions were obtained throughout the numerical cycle. Failed samples are retained to locate limitations; their presence does not authorize execution of the commands.','']
    for s in results:
        lines += [f"### {CASE_EN[s['case']]}",'',
                  f"- Samples failing one or more checks: {s['failed_checks']}.",
                  f"- Failure counts: {counts_en(s['failure_counts'])}.",
                  f"- Head position error after returning to zero yaw at equal clamp depth: {s.get('return_head_error_mm',float('nan')):.4f} mm.",
                  f"- Outbound passing sample prefixes: {prefix_en(s['all_checks_passing_outbound_prefix_deg'])}; not a continuous safety guarantee.",
                  f"- First failure locations: see `{s['case']}.json` and `comparison.json`.",'']
    lines += ['## Method and limitations','',
              '- Baseline: U4+M2, 20-degree installation, 500 g payload, E40 backbone, 1 m free rope length, database rope EA, eight cells per module.',
              '- Initial condition: clamp at s=-750 mm outside the tank; the three upper ropes are paid out 10 mm from baseline. The initial payout transient is not simulated. Straightening reels in from the resulting stationary state, which may be unstable.',
              '- Cycle: straighten; insert to s=15 mm while holding posture; right sweep to 175 degrees; return; left sweep to -175 degrees; return; withdraw to s=-750 mm while holding posture.',
              '- Reference poses are spaced by 5 degrees. Rest lengths are linearly interpolated with command increments no greater than 1 mm. Steps exceeding 5 mm displacement at any centreline node are recursively subdivided to depth nine; unresolved excess is a failure. This controls sampled resolution and does not prove continuous safety.',
              '- Rope force: T = EA max(0, L + Lfree - R) / R. Stability uses the same rest lengths, rope stiffness and active-rope set in the elastic energy Hessian.',
              '- Left commands swap the right/left rope channels. Both directions are forward-solved independently; the tank geometry is not mirrored.',
              '- One-factor sensitivities replay identical open-loop commands without reoptimization: E75 backbone; 550 g payload; rope EA scaled by 0.8; free rope length 1.5 m, with a matching 0.5 m command-zero offset. These are assumed scenarios, not measured probability distributions.',
              '- Tank screen: 362 solids, 0.5 mm mesh deflection; centreline distances sampled at about 2 mm spacing, minus a 31.5 mm envelope radius. A further 1.5 mm sampling/mesh allowance is subtracted. Mesh deflection is not a verified global error bound.',
              '- Acceptance: clearance after allowance at least 5 mm; stability eigenvalue above 1e-7; existing self-collision/local-curvature constraints; axial strain at most 5%; each rope between 0.95 and 250 N; yaw error at most 1 degree; elevation within 20 +/- 5 degrees. Elevation/yaw tracking is not required during straightening. The 0.95 N threshold permits numerical tolerance around 1 N. The 250 N and 5% bounds are diagnostics, not hardware ratings.',
              '- Excluded: dynamics, friction, backlash, NiTi hysteresis, actual sensor-head geometry, external cables, the rear telescopic mechanism, contact forces and recovery control. Withdrawal is rigid translation of the clamped front.',
              '- Per-step output includes rest lengths, pull-in relative to baseline, forces for all 12 ropes, head position/orientation, clearance, geometry checks, equilibrium residual and stability. No time scale, motor speed or torque commands are provided.',
              '', '## Reproduction','', '```bash',
              'python length_cycle.py', 'python summarize_length_cycle.py',
              'python -m unittest test_length_cycle.py -v','```','',
              'Dependencies: NumPy, SciPy, Numba, Matplotlib, cadquery-ocp, VTK, trimesh and rtree. The original STEP model and reference states are supplied by the repository.',
              '', '## Figures','', '![Round-trip comparison](cycle_comparison.png)', '', '![Nominal three-dimensional steering path](nominal_3d.png)']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    plot()
    if (OUT/'nominal_states.npz').exists():
        import matplotlib.pyplot as plt
        tank=FastTank(); rod=spatial_rod(4,2,[4,5,6],20,8)
        rows=[q for q in json.loads((OUT/'nominal.json').read_text()) if q['status']=='solved']
        zs=np.load(OUT/'nominal_states.npz')['z']
        fig=plt.figure(figsize=(11,8));ax=fig.add_subplot(111,projection='3d')
        V=np.asarray(tank.mesh.vertices)[::50]
        ax.scatter(V[:,0],V[:,2],V[:,1],s=.2,c='gray',alpha=.12)
        for phase,color in [('right_out','tab:blue'),('left_out','tab:orange')]:
            rr=[q for q in rows if q['phase']==phase]
            ax.plot([q['head_x_mm'] for q in rr],[q['head_z_mm'] for q in rr],[q['head_y_mm'] for q in rr],color=color,label=PHASE_EN[phase]+' head path')
            for yaw in [0,45,90,135,175]:
                rec=min(rr,key=lambda q:abs(abs(q['target_yaw_deg'])-yaw));idx=rows.index(rec)
                _,d=rod.kinematic_metrics(zs[idx])
                world=np.vstack((np.zeros(3),(d['points']+np.array([.02,0,0]))@rod.R0.T))*1000
                P=to_tank(world,20,rec['clamp_s_mm'],tank.entry_h)
                ax.plot(P[:,0],P[:,2],P[:,1],color=color,alpha=.5,lw=1)
        ax.set_xlabel('Tank length (mm)');ax.set_ylabel('Tank width (mm)');ax.set_zlabel('Height (mm)')
        ax.set_title('Nominal steering: centreline snapshots and head path\nClearance uses a 63 mm envelope; only the centreline is drawn');ax.legend();ax.set_box_aspect((1.5,1,1));fig.tight_layout();fig.savefig(OUT/'nominal_3d.png',dpi=160);plt.close(fig)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
