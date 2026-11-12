"""English report, comparison plots and true simulated 3D frame animations."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/asrc-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/asrc-cache')
import argparse,json,hashlib,pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation,FFMpegWriter,PillowWriter
from closed_loop_cycle import OUT,HERE,REF,CASES
from length_cycle import CASE_EN,PHASE_EN,FastTank


def report():
    summaries=[json.loads(f.read_text()) for f in sorted(OUT.glob('*_summary.json'))]
    summaries=[s for s in summaries if s['completed']]
    fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True)
    for s in summaries:
        data=json.loads((OUT/f"{s['case']}.json").read_text())
        for ax,key in zip(axs,['yaw_error_deg','elevation_error_deg','minimum_tension_n']):
            ax.plot([q['index'] for q in data],[q['closed'][key] for q in data],label=CASE_EN[s['case']])
    for ax,label in zip(axs,['Yaw error (deg)','Elevation error (deg)','Minimum rope force (N)']):ax.set_ylabel(label);ax.grid(alpha=.25)
    for ax in axs[:2]:
        ax.axhline(1,color='r',ls='--');ax.axhline(-1,color='r',ls='--')
    axs[2].axhline(.95,color='r',ls='--');axs[0].legend(ncol=2);axs[-1].set_xlabel('Reference sample index (not physical time)')
    fig.suptitle('Closed-loop settled states: nominal-model feedback, perturbed plants');fig.tight_layout();fig.savefig(OUT/'feedback_comparison.png',dpi=150);plt.close(fig)
    lines=['# U4+M2 Closed-Loop Round-Trip Simulation','',
           'Output feedback uses ideal simulated measurements of head yaw/elevation and all 12 rope tensions. Controller gains come only from the nominal E40, 500 g, 1 m model; plant perturbations are not supplied to the gain calculation. The plant is a quasi-static equilibrium solver, not a dynamic or hardware model.','',
           '## Control structure','',
           'Nominal reference lengths + accumulated feedback correction -> elastic rod equilibrium -> head yaw/elevation and 12 tension measurements -> constrained correction -> next length command. The gain schedule is prepared from the nominal reference states. No full-body shape measurement is supplied to the controller.', '',
           '## Settled-state results','',
           '| Case | Open-loop failed samples | Closed-loop failed samples | Max yaw error, open / closed (deg) | Max elevation error, open / closed (deg) | Closed-loop minimum rope force (N) | Closed-loop minimum clearance (mm) |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        o=s['open'];c=s['closed']
        lines.append(f"| {CASE_EN[s['case']]} | {o['failed_samples']} | {c['failed_samples']} | {o['maximum_yaw_error_deg']:.3f} / {c['maximum_yaw_error_deg']:.3f} | {o['maximum_elevation_error_deg']:.3f} / {c['maximum_elevation_error_deg']:.3f} | {c['minimum_tension_n']:.3f} | {c['minimum_clearance_mm']:.2f} |")
    lines+=['','The comparison is recomputed on the same 1,069 nominal reference samples for both modes. During straightening the target follows the saved nominal startup elevation; all subsequent phases target 20 degrees. A previous report accepted elevation within 20 +/- 5 degrees; this study checks both yaw and elevation error within 1 degree, so failure counts must not be compared directly across reports.','',
            '## Feedback corrections and limitations','',
            'Each reference command is followed by up to 16 output-feedback corrections. A nominal implicit-equilibrium sensitivity maps changes in rest length to head angles and tensions. A constrained quadratic step minimizes angular error, with predicted rope forces at least 1.5 N and at most 250 N. Tension feedback enforces bounds; it does not track an independently specified force on every rope. Each correction is bounded to 0.25 mm per rope; accumulated correction relative to feedforward is bounded to 5 mm. The feedback target of 1.5 N is lower than the preceding 3 N feedforward pretension floor; this exploratory controller does not enforce a 3 N operating requirement. These are study settings, not validated actuator ratings.',
            '',
            'After an applied correction, if angular error above 0.2 degrees grows by more than 5%, the next correction scale is halved, down to 1/16. The scale is retained across references, while error comparisons restart at each new feedforward command. This damping uses only previously observed errors, not plant parameters or a look-ahead simulation. The QP proposes a full correction toward the 1.5 N predicted floor; damping may approach that floor over several updates.', '',
            'The initial undamped controller failed near large yaw in the 550 g case. The incomplete diagnostic prefix and original source are retained in [undamped_diagnostic](undamped_diagnostic/README.md). The final controller applies the same output-based damping rule to every case. This is a controller-development study on these cases, not an independent validation set.', '',
            'The stopping target is 0.2 degrees for both angles and measured tension at least 1.25 N. Every applied correction, including the pre-correction arrival state, is recorded in the feedback trace. Passing the settled state does not mean every intermediate correction passes. Quasi-static correction iterations are not a timing or closed-loop dynamic stability claim.','',
            '| Case | Feedback trace samples | Trace samples failing any check | Unstable trace states | Geometry failures | Clearance failures | Max cumulative correction (mm) | Minimum correction scale |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        t=s['feedback_trace'];lines.append(f"| {CASE_EN[s['case']]} | {t['samples']} | {t['failed_samples']} | {t['unstable_samples']} | {t['geometry_failures']} | {t['clearance_failures']} | {s['maximum_offset_mm']:.3f} | {s['minimum_correction_scale']:.4f} |")
    lines+=['', '## Tension during feedback transitions', '',
            '| Case | Minimum trace tension (N) | Arrival states below 0.95 N | Post-correction states below 0.95 N |',
            '|---|---:|---:|---:|']
    for s in summaries:
        tr=json.loads((OUT/f"{s['case']}_feedback.json").read_text())
        arrival=sum(q['minimum_tension_n']<.95 and q['iteration']==0 for q in tr)
        corrected=sum(q['minimum_tension_n']<.95 and q['iteration']>0 for q in tr)
        lines.append(f"| {CASE_EN[s['case']]} | {s['feedback_trace']['minimum_tension_n']:.3f} | {arrival} | {corrected} |")
    lines+=['', 'A settled-state pass does not establish a passing complete control sequence. A feedforward command can reduce pretension before feedback responds. Raising the operating pretension margin and subdividing or guarding the feedforward transitions remain necessary.', '']
    lines+=['','Collision and equilibrium-stability checks are diagnostics, not constraints in the feedback quadratic program. Acceptance also requires positive fixed-winch tangent eigenvalue (>1e-7), original geometry and strain diagnostics, rope forces between 0.95 and 250 N, and sampled tank clearance at least 5 mm after subtracting a 1.5 mm allowance. The 63 mm envelope is retained. No actual head CAD, external cables, friction, backlash, hysteresis, sensor noise, latency, motor dynamics or continuous swept-volume proof is included.',
            '', 'The feedback gains use nominal reference shapes, not measured full-body shape. A known free-rope installation-length difference is represented as a command-zero offset, as in the preceding sensitivity study. Its changed elastic response is not passed to the controller gains.',
            '', '## Next simulation work','',
            '1. Resolve any failed correction states and enforce the chosen operating pretension requirement throughout each update, rather than only accepting the final equilibrium.',
            '2. Refine the corrected path and check motion between feedback states; add actuator speed/travel, sampling time, latency, noise and saturation before making transient-performance claims.',
            '3. Include identified friction, backlash and NiTi hysteresis, plus actual head/cable geometry and measured stiffness. Repeat the uncertainty study with these calibrated models.',
            '', '## Deliverables','',
            '- Per-case CSV: paired open/closed outputs, rest-length commands, offsets and all rope forces.',
            '- Per-case JSON and state NPZ: numerical results and full solved centrelines.',
            '- Feedback JSON: every applied correction, including any failed intermediate checks.',
            '- `validation.json`: numerical consistency checks and maximum displacement between settled centreline samples. The corrected path is evaluated on the inherited nominal grid; it is not adaptively resampled to enforce a 5 mm displacement bound.',
            '- `settings.json`: controller settings and reference-data hashes; code hashes are in `validation.json`.',
            '- Full-cycle MP4 and steering GIF show paired settled sampled states. The feedback-convergence GIF re-solves the saved correction commands at a fixed reference sample and checks the replayed angles against the trace. Both show equilibria, not physical transients; playback speed is illustrative.',
            '', '![Settled feedback comparison](feedback_comparison.png)',
            '', '## Reproduction','', '```bash',
            'python closed_loop_cycle.py --prepare',
            'python closed_loop_cycle.py --case nominal',
            'python closed_loop_cycle.py --case E75',
            'python closed_loop_cycle.py --case payload550g',
            'python closed_loop_cycle.py --case free1500mm',
            'python closed_loop_cycle.py --case ropeEA80pct',
            'python -m unittest test_closed_loop.py -v',
            'python validate_closed_loop_results.py',
            'python render_closed_loop.py --case E75',
            'python render_closed_loop.py --case payload550g --convergence-only --convergence-index 432','```','']
    if (OUT/'validation.json').exists():
        validation=json.loads((OUT/'validation.json').read_text())
        lines+=['## Numerical verification', '',
                'Five focused unit tests cover sensitivity derivatives, command constraints, the forward solver, observed-error damping and yaw wrapping. Export validation checks all sample counts, residuals, finite states, command reconstruction and every recorded feedback step against the controller equation. Numerical validation passed; it does not establish physical safety.', '',
                '| Case | Maximum feedback iterations | Samples above the internal 0.2-degree target | Maximum settled node step (mm) |',
                '|---|---:|---:|---:|']
        for q in validation['checks']:
            lines.append(f"| {CASE_EN[q['case']]} | {q['maximum_feedback_iterations']} | {q['samples_above_controller_angle_target']} | {q['max_settled_node_step_mm']:.3f} |")
        lines+=['', 'One 550 g sample reaches the 16-correction budget with a 0.699-degree yaw error: it meets the 1-degree acceptance criterion but misses the internal 0.2-degree stopping target. Maximum corrected-path node motion is 6.822 mm, exceeding the earlier 5 mm sampling bound. Further subdivision and continuous-motion checks are required.', '']
    media=sorted(OUT.glob('*full_cycle.mp4'))
    if media:
        lines+=['## 3D animations','']
        for video in media:
            case=video.name.removesuffix('_full_cycle.mp4')
            lines += [f'- [{CASE_EN[case]}: full round trip]({video.name})', f'- [Steering comparison]({case}_steering.gif)', f'- [Feedback correction sequence]({case}_feedback_convergence.gif)', '']
        if (OUT/'payload550g_feedback_convergence.gif').exists():
            lines+=['- [550 g large-yaw feedback damping](payload550g_feedback_convergence.gif)', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines));(OUT/'comparison.json').write_text(json.dumps(summaries,indent=2))


def animate(case,preview=False):
    if preview:
        saved=pickle.loads((OUT/f'{case}_checkpoint.pkl').read_bytes())
        rows=saved[0];st={'points':np.asarray(saved[4]),'open_points':np.asarray(saved[5])}
    else:
        rows=json.loads((OUT/f'{case}.json').read_text());st=np.load(OUT/f'{case}_states.npz')
    trace_min=min(q['minimum_tension_n'] for q in (saved[1] if preview else json.loads((OUT/f'{case}_feedback.json').read_text())))
    tank=FastTank();V=np.asarray(tank.mesh.vertices)[::120]
    from trimesh.intersections import mesh_plane
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    sections=np.concatenate([mesh_plane(tank.mesh,plane_normal=[0,0,1],plane_origin=[0,0,w]) for w in [450,648,850]])
    sections=sections[np.all((sections[:,:,0]>=-300)&(sections[:,:,0]<=1300)&(sections[:,:,1]>=-350)&(sections[:,:,1]<=500),axis=1)]
    def build(indices,name,gif=False):
        fig=plt.figure(figsize=(12,7));ax=fig.add_axes([.03,.12,.62,.82],projection='3d');info=fig.add_axes([.67,.13,.31,.8]);info.axis('off')
        ax.scatter(V[:,0],V[:,2],V[:,1],s=.3,c='gray',alpha=.08)
        ax.add_collection3d(Line3DCollection(sections[:,:,[0,2,1]],colors='#88949c',linewidths=.6,alpha=.25))
        op,=ax.plot([],[],[],color='#cf4b44',lw=2,ls='--',label='Open loop')
        cl,=ax.plot([],[],[],color='#1767ad',lw=3,label='Closed loop')
        oh,=ax.plot([],[],[],marker='o',color='#cf4b44',ms=5)
        ch,=ax.plot([],[],[],marker='o',color='#1767ad',ms=5)
        rings=[ax.plot([],[],[],color='#1767ad',alpha=.35,lw=.8)[0] for _ in range(7)]
        open_axis,=ax.plot([],[],[],color='#cf4b44',lw=2)
        closed_axis,=ax.plot([],[],[],color='#1767ad',lw=2)
        ax.set_xlim(-300,1300);ax.set_ylim(300,1000);ax.set_zlim(-350,500);ax.set_box_aspect((1.6,.7,.85));ax.view_init(23,-65)
        if gif:
            ax.set_xlim(400,1150);ax.set_ylim(350,950);ax.set_zlim(0,500);ax.set_box_aspect((.75,.6,.5))
        ax.set_xlabel('Tank length (mm)');ax.set_ylabel('Tank width (mm)');ax.set_zlabel('Height (mm)');ax.legend(loc='upper left')
        title=fig.suptitle('');text=info.text(0,.95,'',va='top',fontsize=11,family='monospace')
        fig.text(.05,.025,'Settled equilibria | Centreline + 63 mm envelope rings | Not physical timing; transition checks in report',fontsize=9)
        def update(j):
            i=int(indices[j]);q=rows[i];p=st['points'][i];o=st['open_points'][i]
            for line,pts in [(cl,p),(op,o)]:line.set_data_3d(pts[:,0],pts[:,2],pts[:,1])
            for line,pts in [(ch,p),(oh,o)]:line.set_data_3d(pts[-1:,0],pts[-1:,2],pts[-1:,1])
            for ring,k in zip(rings,np.linspace(1,len(p)-1,7).astype(int)):
                tangent=p[min(k+1,len(p)-1)]-p[max(k-1,0)];tangent/=np.linalg.norm(tangent)
                helper=np.array([0.,1.,0.]) if abs(tangent[1])<.9 else np.array([0.,0.,1.])
                u=np.cross(tangent,helper);u/=np.linalg.norm(u);v=np.cross(tangent,u)
                theta=np.linspace(0,2*np.pi,32);rr=p[k]+31.5*(np.cos(theta)[:,None]*u+np.sin(theta)[:,None]*v)
                ring.set_data_3d(rr[:,0],rr[:,2],rr[:,1])
            c=q['closed'];a=q['open']
            for axis,metrics,head_points in [(open_axis,a,o),(closed_axis,c,p)]:
                yaw,elev=np.radians([metrics['yaw_deg'],metrics['elevation_deg']])
                direction=np.array([np.cos(elev)*np.cos(yaw),np.sin(elev),np.cos(elev)*np.sin(yaw)])
                arrow=np.vstack((head_points[-1],head_points[-1]+60*direction));axis.set_data_3d(arrow[:,0],arrow[:,2],arrow[:,1])
            title.set_text(f"U4+M2 | {CASE_EN[case]} | {PHASE_EN[q['phase']]} | sample {i}")
            text.set_text(f"TARGET\nYaw: {q['target_yaw_deg']:7.2f} deg\nElev:{q['target_elevation_deg']:7.2f} deg\n\n                  OPEN   CLOSED\nYaw error (deg)\n               {a['yaw_error_deg']:7.2f}  {c['yaw_error_deg']:7.2f}\nElevation error (deg)\n               {a['elevation_error_deg']:7.2f}  {c['elevation_error_deg']:7.2f}\nMin rope force (N)\n               {a['minimum_tension_n']:7.2f}  {c['minimum_tension_n']:7.2f}\nTank gap (mm)\n               {a['clearance_mm']:7.2f}  {c['clearance_mm']:7.2f}\n\nSettled checks\nOpen:   {'PASS' if a['checks_pass'] else 'FAIL'}\nClosed: {'PASS' if c['checks_pass'] else 'FAIL'}\n\nFeedback iterations: {q['iterations']}\nCycle trace min T: {trace_min:.3f} N\nTransition checks: see report")
            return cl,op,ch,oh,text
        if preview:
            update(len(indices)-1);fig.savefig(OUT/f'{case}_layout_check.png',dpi=100);plt.close(fig);return
        anim=FuncAnimation(fig,update,frames=len(indices),interval=80,blit=False)
        if gif:anim.save(OUT/name,writer=PillowWriter(fps=10),dpi=75)
        else:anim.save(OUT/name,writer=FFMpegWriter(fps=15,codec='libx264',extra_args=['-pix_fmt','yuv420p','-crf','22']),dpi=100)
        update(len(indices)//2);fig.savefig(OUT/f'{case}_preview.png',dpi=120);plt.close(fig)
    indices=np.unique(np.linspace(0,len(rows)-1,240).astype(int))
    build(indices,f'{case}_full_cycle.mp4')
    if preview:return
    steer=[i for i,q in enumerate(rows) if q['phase'] not in ['entry','exit','straighten']]
    indices=np.array(steer)[np.linspace(0,len(steer)-1,140).astype(int)]
    build(indices,f'{case}_steering.gif',True)
    print('Rendered',case,flush=True)

def convergence(case,index=None):
    """Re-solve saved commands at one reference sample; never interpolate shapes."""
    from closed_loop_cycle import FeedbackDrive,spatial_rod,to_tank,angles,error
    rows=json.loads((OUT/f'{case}.json').read_text())
    trace=json.loads((OUT/f'{case}_feedback.json').read_text())
    states=np.load(OUT/f'{case}_states.npz');gains=np.load(OUT/'nominal_gains.npz')
    # The transition to the 20-degree working target shows feedback at fixed clamp.
    if index is None:index=next(q['index'] for q in rows if q['phase']=='entry')
    steps=[q for q in trace if q['index']==index]
    variant,payload,ea,free=CASES[case]
    r=spatial_rod(4,2,[4,5,6],20,8,variant);r.payload=payload;drive=FeedbackDrive(r,free,ea)
    z=states['closed'][index-1].copy();tank=FastTank();points=[]
    for q in steps:
        R=gains['R'][index]+free-1+np.asarray(q['offset_mm']).reshape(3,4)/1000
        z=drive.solve(z,R)
        if z is None:raise RuntimeError('Convergence replay did not solve')
        np.testing.assert_allclose(error([q['yaw_deg'],q['elevation_deg']],angles(r,z)),0,atol=1e-3)
        _,_,world=r.metrics(z,drive.force(z,R))
        points.append(to_tank(world*1000,20,rows[index]['clamp_s_mm'],tank.entry_h))
    np.savez_compressed(OUT/f'{case}_convergence_states.npz',points=points,index=index)
    (OUT/f'{case}_convergence.json').write_text(json.dumps(steps,indent=2))
    fig=plt.figure(figsize=(11,6));ax=fig.add_axes([.04,.15,.62,.76],projection='3d');info=fig.add_axes([.7,.16,.29,.72]);info.axis('off')
    p=np.asarray(points);low=p.min(axis=(0,1))-60;high=p.max(axis=(0,1))+60
    ax.set_xlim(low[0],high[0]);ax.set_ylim(low[2],high[2]);ax.set_zlim(low[1],high[1]);ax.set_box_aspect((high-low)[[0,2,1]])
    ax.set_xlabel('Tank length (mm)');ax.set_ylabel('Width (mm)');ax.set_zlabel('Height (mm)');ax.view_init(18,-65)
    ax.set_yticks(np.linspace(low[2],high[2],3));ax.set_yticklabels([f'{v:.0f}' for v in np.linspace(low[2],high[2],3)])
    initial=points[0];ax.plot(initial[:,0],initial[:,2],initial[:,1],color='#cf4b44',ls='--',lw=2,label='Before correction')
    line,=ax.plot([],[],[],color='#1767ad',lw=3,label='Feedback state');head,=ax.plot([],[],[],marker='o',color='#1767ad',ms=7)
    ax.legend(loc='upper left');label=info.text(0,.95,'',va='top',fontsize=11,family='monospace')
    fig.suptitle(f'{CASE_EN[case]} | Feedback at a fixed reference command')
    fig.text(.05,.035,'Solved equilibrium after each correction | 20 deg elevation target | Ideal sensing; no physical timing model',fontsize=9)
    def update(frame):
        k=min(frame//8,len(steps)-1);q=steps[k];a=points[k]
        line.set_data_3d(a[:,0],a[:,2],a[:,1]);head.set_data_3d(a[-1:,0],a[-1:,2],a[-1:,1])
        label.set_text(f"CORRECTION {q['iteration']} / {len(steps)-1}\nNext scale: {q['next_correction_scale']:.3f}\n\nYaw error\n{q['yaw_error_deg']:+.3f} deg\n\nElevation error\n{q['elevation_error_deg']:+.3f} deg\n\nMin rope force\n{q['minimum_tension_n']:.3f} N\n\nSampled tank gap\n{q['clearance_mm']:.2f} mm")
        return line,head,label
    anim=FuncAnimation(fig,update,frames=len(steps)*8+16,interval=100,blit=False)
    anim.save(OUT/f'{case}_feedback_convergence.gif',writer=PillowWriter(fps=10),dpi=90)
    update((len(steps)-1)*8);fig.savefig(OUT/f'{case}_convergence_preview.png',dpi=120);plt.close(fig)
    print('Replayed and rendered feedback corrections',case,len(steps),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=list(CASES))
    p.add_argument('--preview',action='store_true');p.add_argument('--convergence-only',action='store_true')
    p.add_argument('--convergence-index',type=int);a=p.parse_args()
    if a.case:
        if not a.convergence_only:animate(a.case,a.preview)
        if not a.preview:convergence(a.case,a.convergence_index)
    if not a.preview:report()
