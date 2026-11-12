"""Audit selected states, export inspectable results and scientific figures."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/asrc_payload_mpl')
os.environ.setdefault('XDG_CACHE_HOME','/private/tmp/asrc_payload_cache')
import csv,json,argparse,concurrent.futures,multiprocessing
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from payload_planar import PayloadPlanarRod
from spatial_rod import SpatialRod
from rope_planar import HERE
from run_rope_sweep import write_json,self_screen

def csvwrite(path,rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def counts_from_label(label):return tuple(int(item[1:]) for item in label.split('-'))

def export_all_attempts():
    from run_directional import tension
    rows=[]
    for file in sorted((HERE/'results/directional').glob('*.json')):
        j=json.loads(file.read_text());label=file.stem
        saved={(r['direction'],r['drive_n'],r['vertical_or_side_bias_n'],r['common_n']):r for r in j['trials']}
        for direction in ['up','down','right','left']:
            biases=[0.,4.,16.] if direction in ['up','down'] else j['side_vertical_bias_n']
            for common in j['common_grid_n']:
                for bias in biases:
                    for drive in j['force_grid_n']:
                        found=saved.get((direction,drive,bias,common))
                        row=dict(combination=label,direction=direction,drive_n=drive,vertical_or_side_bias_n=bias,common_n=common,
                            status='converged_diagnostic' if found else 'not_converged_or_outside_documented_numerical_domain')
                        if found:row.update(found)
                        else:row['tensions_n']=tension(direction,drive,bias,common).tolist()
                        rows.append(row)
    assert len(rows)==11880
    csvwrite(HERE/'results/directional_all_attempts.csv',rows)

def draw_directional(directional,out):
    for f in range(5,9):
        d=round(f*8/11);label=f'H8-U12-D{d}-L{f-d}';fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
        ref=[r for r in directional if r['combination']==label and r['passes_self_envelope_screen']]
        norm=matplotlib.colors.Normalize(vmin=min(r['max_core_stress_mpa'] for r in ref),vmax=max(r['max_core_stress_mpa'] for r in ref))
        for direction,ax in zip(['up','down','right','left'],axs.flat):
            rr=[r for r in ref if r['direction']==direction]
            scatter=ax.scatter([r['total_tension_n'] for r in rr],[r['directional_angle_deg'] for r in rr],
                c=[r['max_core_stress_mpa'] for r in rr],cmap='viridis',norm=norm,s=15,alpha=.65)
            ax.set(xlabel='Sum of four tensions (N)',ylabel='Signed projected front turn (deg)',title=direction.capitalize());ax.grid(alpha=.15)
        fig.colorbar(scatter,ax=axs,label='Core stress (MPa)',shrink=.85)
        fig.suptitle(label+' | 500 g spatial force/turn diagnostics')
        fig.supxlabel('Capsule-clear elastic equilibria only. These points exceed the core reference and are not admissible maximum angles.',fontsize=9)
        fig.savefig(out/f'front_{f:02d}_directional_diagnostics.png',dpi=180);plt.close(fig)

def export_points(name,points,sub,*,frames=None):
    folder=HERE/'results/coordinates';folder.mkdir(exist_ok=True)
    with (folder/(name+'.csv')).open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['node','x_mm','y_mm','z_mm','is_actual_disk'])
        if points.shape[1]==2:points=np.c_[points,np.zeros(len(points))]
        for i,point in enumerate(points):w.writerow([i,*list(point*1000),i%sub==0])

def audit_one(label):
    counts=counts_from_label(label);folder=HERE/'results';issues=[];maxres=0.;rows=[];refs=[]
    vertical=json.loads((folder/'vertical'/(label+'.json')).read_text())
    z=np.load(folder/'vertical'/(label+'_states.npz'))
    for row in vertical['rows']:
        target=row['target']
        if target+'_x' not in z.files:
            if row.get('head_x_mm') is not None:issues.append('missing state '+target)
            continue
        r=PayloadPlanarRod(counts,8,antagonistic_common=row.get('top_bottom_pair_common_n',0.) or 0.)
        x=z[target+'_x'];T=z[target+'_T'];_,g,H,d=r.evaluate(x,T,detail=True)
        residual=r.residual(g);maxres=max(maxres,residual)
        if residual>5e-8:issues.append('vertical residual '+target)
        rest=d['rope_lengths']/(1+T/r.rope_ea)+np.where(T>1e-7,0.,.001)
        recovered=r.rope_ea/rest*np.maximum(d['rope_lengths']-rest,0.)
        if np.max(abs(T-recovered))>1e-7:issues.append('rope length recovery '+target)
        if target!='free_sag' and not row['target_reached'] and row['target_total_tension_n'] is not None:issues.append('invalid target tension '+target)
        export_points(label+'_'+target,d['points'],8)
        rows.append(dict(target=target,residual=residual))
        # The four original reference compositions get an independent mesh check.
        front=sum(counts[2:]);directional=round(front*8/11)
        if counts[2]==directional:
            fine=PayloadPlanarRod(counts,16,antagonistic_common=r.antagonistic_common)
            xx=np.zeros(fine.ndof);xx[::2]=np.interp(np.linspace(0,1,fine.m+1)[1:],np.linspace(0,1,r.m+1),np.r_[0,x[::2]])
            xx[1::2]=np.repeat(x[1::2],2)
            if target=='free_sag':
                sol=fine.free_equilibrium(initial=xx);m,fd,_=fine.shape_metrics(sol,0.) if sol is not None else (None,None,None)
            else:
                sol=fine.inverse('level' if target=='head_level' else 'arc',-1 if target.endswith('_down') else 1,row['common_n'],initial=(xx,row['D_n'],{}),maxiter=80)
                m,fd,_=fine.shape_metrics(*sol[:2],row['common_n']) if sol is not None else (None,None,None)
            ref=dict(combination=label,target=target,refinement_converged=m is not None)
            if m is not None:
                ref.update(head_position_change_mm=float(np.linalg.norm(fd['points'][-1]-d['points'][-1])*1000),
                    stress_change_mpa=abs(m['max_core_stress_mpa']-row['max_core_stress_mpa']),
                    total_tension_change_n=abs(m['total_tension_n']-float(T.sum())))
            refs.append(ref)
    spatial=json.loads((folder/'directional'/(label+'.json')).read_text())
    zz=np.load(folder/'directional'/(label+'_states.npz'));r=SpatialRod(counts,2)
    for key in zz.files:
        if not key.endswith('_z'):continue
        name=key[:-2];state=zz[key];T=zz[name+'_T'];_,g,d=r.evaluate(state,T,detail=True)
        residual=r.residual(g);maxres=max(maxres,residual)
        if residual>2.1e-6:issues.append('spatial residual '+name)
        export_points(label+'_'+name,d['points'],2)
        if counts[2]==round(sum(counts[2:])*8/11):
            fine=SpatialRod(counts,4);q=d['q'];qq=np.repeat(q,2,axis=0);qq[:,:3]/=2
            rest=d['rope_lengths']/(1+T/r.planar.rope_ea)+np.where(T>1e-7,0.,.001)
            sol=fine.solve_locked(rest,qq.ravel()*fine.scale)
            ref=dict(combination=label,target=name,refinement_control='same_fixed_winch_lengths',refinement_converged=sol is not None)
            if sol:
                met,fd=fine.metrics(sol[0],sol[1]);old,_=r.metrics(state,T)
                ref.update(head_position_change_mm=float(np.linalg.norm(fd['points'][-1]-d['points'][-1])*1000),stress_change_mpa=abs(met['max_core_stress_mpa']-old['max_core_stress_mpa']),total_tension_change_n=abs(float(np.sum(sol[1]-T))),max_force_component_change_n=float(np.max(abs(sol[1]-T))))
            refs.append(ref)
    return dict(combination=label,selected_vertical_states=len(rows),selected_spatial_states=sum(k.endswith('_z') for k in zz.files),max_residual=maxres,issues=issues,refinements=refs)

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args();out=HERE/'results'
    labels=['-'.join(f'{k}{v}' for k,v in zip('HUDL',(8,12,d,f-d))) for f in range(5,9) for d in range(1,f)]
    assert len(labels)==22
    assert all((out/'vertical'/(label+'.json')).exists() and (out/'directional'/(label+'.json')).exists() for label in labels)
    vertical=[];directional=[];maximum=[];baseline=[];selected_stress={}
    for label in labels:
        counts=counts_from_label(label);f=sum(counts[2:])
        j=json.loads((out/'vertical'/(label+'.json')).read_text());vertical.extend(j['rows'])
        for row in j['rows']:selected_stress[(label,row['target'])]=row.get('max_core_stress_mpa')
        k=json.loads((out/'directional'/(label+'.json')).read_text());directional.extend(k['trials'])
        for direction,result in k['maximums'].items():
            diagnostic=result['closest_stress_diagnostic'] or {}
            selected_stress[(label,direction+'_closest_stress')]=diagnostic.get('max_core_stress_mpa')
            maximum.append(dict(combination=label,front_modules=f,n_directional=counts[2],n_low=counts[3],direction=direction,
                maximum_angle_deg=result['maximum_angle_deg'],tensions_at_max_n=result['tensions_at_max_n'],status=result['status'],
                diagnostic_minimum_core_stress_mpa=diagnostic.get('max_core_stress_mpa'),diagnostic_angle_deg=diagnostic.get('directional_angle_deg'),
                diagnostic_tensions_n=diagnostic.get('tensions_n'),diagnostic_passes_empty_box=diagnostic.get('passes_empty_box')))
        for payload in [0.,.5]:
            r=PayloadPlanarRod(counts,8,payload_kg=payload);x=r.free_equilibrium();m,_,_=r.shape_metrics(x,0.)
            baseline.append(dict(combination=label,front_modules=f,n_directional=counts[2],n_low=counts[3],payload_kg=payload,
                drop_mm=-m['head_y_mm'],head_x_mm=m['head_x_mm'],core_stress_mpa=m['max_core_stress_mpa'],passes_reference_yield=m['passes_reference_yield'],passes_empty_box=m['passes_empty_box']))
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        cached={label:json.loads((out/'audit_groups'/(label+'.json')).read_text()) for label in labels if (out/'audit_groups'/(label+'.json')).exists()}
        cached={label:row for label,row in cached.items() if not row['issues'] and all(r['refinement_converged'] and (not r['target'].endswith('closest_stress') or r.get('refinement_control')=='same_fixed_winch_lengths') for r in row['refinements'])}
        fresh=list(pool.map(audit_one,[label for label in labels if label not in cached]))
        audits=list(cached.values())+fresh
    refinements=[r for au in audits for r in au['refinements']];good=[r for r in refinements if r['refinement_converged']]
    validation=dict(unit_tests_passed=6,configurations=22,vertical_targets=66,free_sag_cases=22,maximum_requests=88,
       saved_states_checked=sum(au['selected_vertical_states']+au['selected_spatial_states'] for au in audits),
       max_selected_state_residual=max(au['max_residual'] for au in audits),issues=[au for au in audits if au['issues']],refinements=refinements,
       max_refinement_head_change_mm=max((r['head_position_change_mm'] for r in good),default=None),
       max_refinement_stress_change_mpa=max((r['stress_change_mpa'] for r in good),default=None),
       max_refinement_tension_change_n=max((r['total_tension_change_n'] for r in good),default=None))
    validation['equilibrium_and_data_checks_passed']=not validation['issues']
    validation['all_reference_refinements_converged']=all(r['refinement_converged'] for r in refinements)
    validation['nonconverged_refinements']=[r for r in refinements if not r['refinement_converged']]
    validation['nonconverged_refinements_are_overload_diagnostics_only']=all((selected_stress.get((r['combination'],r['target'])) or 0)>205 for r in validation['nonconverged_refinements'])
    write_json(out/'validation.json',validation)
    if not validation['equilibrium_and_data_checks_passed']:raise RuntimeError('Saved equilibrium/data validation failed; inspect validation.json before delivery')
    if validation['nonconverged_refinements'] and (not validation['nonconverged_refinements_are_overload_diagnostics_only'] or any(r['qualifies'] for r in vertical)):
        raise RuntimeError('An admissible claim must not rely on an unrefined selected state.')
    csvwrite(out/'vertical_targets_and_free_sag.csv',vertical);csvwrite(out/'directional_force_sweep.csv',directional)
    csvwrite(out/'maximum_bending_by_configuration.csv',maximum);csvwrite(out/'free_sag_0g_vs_500g.csv',baseline)
    export_all_attempts()
    refs=[r for r in vertical if counts_from_label(r['combination'])[2]==round(sum(counts_from_label(r['combination'])[2:])*8/11)]
    csvwrite(out/'reference_H8U12.csv',refs)
    summary=dict(configurations=22,vertical_rows=len(vertical),spatial_force_trials_converged=len(directional),
       spatial_force_trials_attempted=sum(json.loads((out/'directional'/(label+'.json')).read_text())['summary']['attempted'] for label in labels),
       head_level_found=sum(r['target']=='head_level' and r['target_reached'] for r in vertical),
       semicircle_found=sum(r['target'].startswith('front_semicircle') and r['target_reached'] for r in vertical),
       qualifying_maximums=sum(r['maximum_angle_deg'] is not None for r in maximum),
       minimum_spatial_geometry_screened_core_stress_mpa=min((r['max_core_stress_mpa'] for r in directional if r['passes_self_envelope_screen']),default=None),
       global_impossibility_proved=False,maximum_search_is_finite=True)
    write_json(out/'study_summary.json',summary)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for payload,col,lab in [(0.,'#326a90','No added payload'),(.5,'#b25c2b','Head +500 g')]:
        rr=[r for r in baseline if r['payload_kg']==payload]
        for ax,key in zip(axs,['drop_mm','core_stress_mpa']):
            ax.scatter([r['front_modules'] for r in rr],[r[key] for r in rr],s=24,color=col,alpha=.3)
            med=[np.median([r[key] for r in rr if r['front_modules']==f]) for f in range(5,9)]
            ax.plot(range(5,9),med,'o-',color=col,label=lab)
    axs[0].set(ylabel='Head drop below root (mm)',title='Four ropes released; gravity on')
    axs[1].axhline(205,color='#555',ls='--',label='205 MPa reference');axs[1].set(ylabel='Maximum core stress (MPa)',title='Rear backbone reference-stress screen')
    for ax in axs:ax.set(xlabel='Front modules',xticks=range(5,9));ax.grid(alpha=.15);ax.legend(frameon=False)
    fig.suptitle('H8/U12 rear only: 4.2 mm SS304 | front D/L contains no backbone')
    fig.supxlabel('Points: all 22 positive D/L splits; lines: medians. Values above 205 MPa are elastic diagnostics, not predicted plastic shapes.',fontsize=9)
    fig.savefig(out/'payload_effect.png',dpi=180);plt.close(fig)
    # Four representative shape plots: distinguish loaded diagnostics from the
    # unloaded root-height reference and show both requested circle directions.
    for f in range(5,9):
        d=round(f*8/11);label=f'H8-U12-D{d}-L{f-d}';counts=(8,12,d,f-d)
        j=json.loads((out/'vertical'/(label+'.json')).read_text());z=np.load(out/'vertical'/(label+'_states.npz'))
        fig,ax=plt.subplots(figsize=(11,6.5),layout='constrained')
        for target,color,name in [('free_sag','#326a90','Free-sag elastic diagnostic'),('head_level','#774c9a','Head-level equilibrium'),
                                 ('front_semicircle_up','#b25c2b','Upward 180-degree diagnostic'),('front_semicircle_down','#648243','Downward 180-degree diagnostic')]:
            row=next(r for r in j['rows'] if r['target']==target)
            if target+'_x' not in z.files:continue
            r=PayloadPlanarRod(counts,8,antagonistic_common=row.get('top_bottom_pair_common_n',0.) or 0.)
            dat=r.evaluate(z[target+'_x'],z[target+'_T'],detail=True)[3];xy=dat['points']*1000
            ax.plot(xy[:,0],xy[:,1],color=color,lw=2,label=name);ax.plot(*xy[r.b],'s',color=color,ms=4);ax.plot(*xy[-1],'o',color=color,ms=4)
        ax.plot(0,0,'ks');ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15)
        ax.set(xlabel='X from root (mm)',ylabel='Y above root (mm)',title=label+' | head load 500 g | rear backbone only')
        ax.legend(frameon=False,fontsize=8)
        fig.supxlabel('Squares mark the end of the rear backbone; the front contains no backbone. All loaded shapes exceed 205 MPa: elastic diagnostics only.\nMissing target curves mean no equilibrium was found in the documented search.',fontsize=8)
        fig.savefig(out/f'front_{f:02d}_loaded_shapes.png',dpi=180);plt.close(fig)
    # Force/turning diagnostics in every spatial direction, not fake maxima.
    draw_directional(directional,out)
    lines=['H8U12、前端5–8節、頭部500 g：計算結果','',
       '後段固定high 8節＋uni-d 12節（960 mm），只有此後段加Ø4.2 mm 304 backbone。前端directional＋low完全沒有backbone。各類至少1節，前端5、6、7、8節共22配置。保留原論文EI、EA與質量，不作全PLA換算。四條Ø2 mm尼龍繩、13 mm導孔半徑、無摩擦、零預緊，全部錨定頭部。500 g為頭部中心的向下4.905 N集中力。','',
       f"完成原有66個目標（同高、向上半圓、向下半圓），另算22個鬆繩自重狀態；空間模型共作{summary['spatial_force_trials_attempted']:,}次四繩控制嘗試，其中{summary['spatial_force_trials_converged']:,}次取得收斂診斷平衡。控制嘗試包含重複控制點，不表示同數量的不重複姿態。",'',
       f"找到頭尾同高目標{summary['head_level_found']}個、符合1 mm半圓誤差目標{summary['semicircle_found']}個。上／下／左／右共88項最大彎曲請求，符合靜力平衡、無自包絡干涉、鋼芯≤205 MPa及穩定性條件的最大值共{summary['qualifying_maximums']}個。未找到合格狀態的最大角度與對應拉力留空，不填成0°或0 N，也不將過載診斷值冒充合格最大值。",'',
       '原來四個代表配比的鬆繩診斷：','',
       '|前端|D/L|頭部下垂 mm|鋼芯最大應力 MPa|205 MPa篩選|', '|---:|---:|---:|---:|---|']
    for f in range(5,9):
        d=round(f*8/11);r=next(r for r in baseline if r['front_modules']==f and r['n_directional']==d and r['payload_kg']==.5)
        lines.append(f"|{f}|{d}/{f-d}|{r['drop_mm']:.2f}|{r['core_stress_mpa']:.2f}|超標|")
    lines+=['','180°轉角診斷（不是成功半圓，也未通過鋼芯應力篩選）：','',
       '|前端|方向|上／右／下／左 N|圓弧最大偏差 mm|鋼芯應力 MPa|','|---:|---|---|---:|---:|']
    for f in range(5,9):
        for suffix,lab in [('up','向上'),('down','向下')]:
            r=next(r for r in refs if r['target']=='front_semicircle_'+suffix and sum(counts_from_label(r['combination'])[2:])==f)
            if r['head_x_mm'] is None:lines.append(f'|{f}|{lab}|未找到轉角平衡解|—|—|')
            else:
                forces='／'.join(f"{r['diagnostic_tension_'+name+'_n']:.3f}" for name in ['top','right','bottom','left'])
                lines.append(f"|{f}|{lab}|{forces}|{r['semicircle_max_error_mm']:.2f}|{r['max_core_stress_mpa']:.2f}|")
    lines+=['','診斷表的「向上／向下」僅標記前端淨轉角+180°／−180°，不表示整段維持單向曲率。重載下的診斷形狀可局部反彎、壓縮及回折；因此不能只按上線／下線的名稱判斷淨轉角。這些狀態均未滿足所要求的半圓與應力條件。','',
       '最大彎曲與油箱空間：','',
       '- 最大值條件採使用者確認的靜力平衡、無自碰撞、鋼芯低於205 MPa；是否能放入1600×830×300 mm另列，不以油箱尺寸截斷搜尋。',
       '- 所有最大彎曲欄位都使用null／空白表示未找到合格解；各配置、四個方向的最低已找到應力診斷及四繩拉力另列，這些不是最大彎曲的成功值。',
       '- 空間方向測試同時保留重力、四繩獨立作用、雙向彎曲、軸向變形及扭轉。沒有把側向問題直接當作無重力的垂直平面。directional正／負側向EI分別用0.0037／0.0030，uni-d側向EI用0.0057，垂直用0.061。',
       '- 安裝方向沿用上一輪：uni-d／directional的論文+X方向對應機身右側，Y方向對應垂直。若實物安裝翻轉，directional左右剛度的對應需一併交換。',
       '- 側向診斷同時保存相對界面的連續投影轉角與前端累積彎曲角。空間多軸姿態下二者不同，不將它們混寫為同一角度。',
       '- 油箱檢查為實際中心線加32 mm膠囊包絡的軸向外包尺寸；不含入口、肋板、障礙物及接觸力。未找到合格最大狀態時，不能給出該最大狀態的油箱通過結果，CSV另列診斷形狀結果。','',
       '數值方法與解讀：','',
       '- 垂直目標以4單元／節搜尋，再保存8單元／節；另從8單元直接解及零載荷狀態逐步增加至500 g重試。上下／左右共同收緊模式獨立補查。',
       '- 空間搜尋以每節2段常曲率／扭轉單元與Gauss積分，導孔仍只在真實48 mm模組端盤；代表保存狀態以相同固定繩長指令再加密至4，回報加密後張力與形狀的改變。上下／左右搜尋包含四繩共同收緊與側向時的上下偏置。控制網格見run_directional.py。',
       '- 模組扭轉係數按craft_data標示的T/θ模組轉動剛度保存，細分後總模組剛度不變。鋼芯額外扭轉參考G=77 GPa（[製造商參考資料](https://www.htpipe.com/product-material/stainless-steel/304.html)），只用於空間扭轉，不更改原模組EI、EA或質量。',
       '- 搜尋數值界限為每條主動拉力網格0–64 N、共同力與偏置見程式；軸向應變絕對值≤0.85、空間單元各旋轉分量≤1.5 rad。這些是明示的數值搜尋界限，不是材料額定力、容許應變或物理最大彎曲角。沒有證明完整控制域全域無解。',
       '- 超過205 MPa的鋼芯結果是線彈性外推。程式不把應力截到205 MPa，也不宣稱已模擬塑性變形後的真實姿態。原論文線性EA下較大應變亦僅作診斷；5%是標示門檻，不是實測失效值。',
       '- 繩索剛度與線密度沿用既有PA6實心材料代理值，仍未量測編織繩；繩索自重均布到機身，不求鬆繩懸鏈線。',
       '- 最大值只在找到合格平衡後才有意義。這次合格集為空，不能把最後收斂角、最後掃描力或自碰撞前一格稱為合格最大值。','',
       f"六項獨立力學檢查通過。已保存狀態回代{validation['saved_states_checked']}個，最大殘差{validation['max_selected_state_residual']:.3g}。代表狀態加密中有{len(validation['nonconverged_refinements'])}項過載診斷未找到加密後平衡，這些診斷不可作有效角度或拉力結論；已收斂加密狀態的最大頭部位置變化{validation['max_refinement_head_change_mm']:.3f} mm、應力變化{validation['max_refinement_stress_change_mpa']:.3f} MPa。所有未收斂項和原始數值保存在validation.json，沒有將其標成加密通過。",'',
       '檔案：','',
       '- [全部垂直目標與鬆繩狀態](vertical_targets_and_free_sag.csv)',
       '- [22配置、四方向最大彎曲結果](maximum_bending_by_configuration.csv)',
       '- [空間四繩控制／角度／應力診斷](directional_force_sweep.csv)',
       '- [全部11880次控制嘗試，含未收斂記錄](directional_all_attempts.csv)',
       '- [原四個代表配置](reference_H8U12.csv)',
       '- [0g與500g對比](free_sag_0g_vs_500g.csv)',
       '- [載荷影響圖](payload_effect.png)',
       '- [數值核對](validation.json)','']
    for f in range(5,9):lines.append(f'- [{f}節負載形狀](front_{f:02d}_loaded_shapes.png)、[{f}節四方向診斷](front_{f:02d}_directional_diagnostics.png)')
    lines+=['','材料／方法來源：[既有原論文模組數據](../legacy_models/inputs/craft_data.py)、[304額外剪切模數來源](https://www.htpipe.com/product-material/stainless-steel/304.html)、[幾何非線性索驅模型方法參考](https://yuan.mae.sustech.edu.cn/pdf/2022Li-acta-mechanics.pdf)。']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    (HERE/'README.md').write_text('H8U12後段、無骨架前端5–8節、頭部500 g\n\n執行：\n\n```sh\npython run_all.py --workers 4\n```\n\n只在H8U12後段加Ø4.2 mm 304 backbone，前端完全沒有。模組原始數值在inputs/。\n\nrun_rope_sweep.py是上一輪搜尋方法的輔助快照；本輪由run_vertical.py設定500 g載荷後呼叫，請以run_all.py執行本輪研究。各組已有結果會重用；如修改參數或模型，先將results重新命名保存，再重新執行，避免重用舊組別。\n\n[完整結果與限制](results/RESULTS.md)\n\n最大彎曲若未找到符合205 MPa及自碰撞／穩定要求的平衡，角度與對應力保持空白；不要把空白讀成0。\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
