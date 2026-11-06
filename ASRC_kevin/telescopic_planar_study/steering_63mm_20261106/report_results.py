"""Create source-backed bilingual results and English steering figures."""
import json,hashlib,sys,platform
from pathlib import Path
import numpy as np
import scipy,numba,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator
from spatial_model import HERE,DATA,DB,dump,write_csv
from search_steering import OUT

PAIRS=[(4,2),(6,3),(8,4)]
NAMES=[f'U{u}-M{m}' for u,m in PAIRS]
COLORS={'low_strain':'#246b9d','exploratory':'#c7602d'}
LABELS={'right':'Right','left':'Left','up':'Up','down':'Down','right_level':'Right at held elevation','left_level':'Left at held elevation'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False})

def save(fig,name):
    for t in fig.findobj(Text):assert all(ord(c)<128 for c in t.get_text()),t.get_text()
    fig.savefig(OUT/name,dpi=165,bbox_inches='tight',facecolor='white');plt.close(fig)

def run():
    allrows=[];sensitivity=[];checks=[];curves=[];attempts=[];coarse=[];states={};baselines=[]
    for u,m in PAIRS:
        prefix=f'U{u}_M{m}'
        assert json.loads((OUT/f'{prefix}_refinement_completion.json').read_text())['completed']
        assert json.loads((OUT/f'{prefix}_force_curve_completion.json').read_text())['completed']
        allrows.extend(json.loads((OUT/f'{prefix}_maximums.json').read_text()))
        sensitivity.extend(json.loads((OUT/f'{prefix}_pitch_sensitivity.json').read_text()))
        checks.extend(json.loads((OUT/f'{prefix}_refinement_checks.json').read_text()))
        curves.extend(json.loads((OUT/f'{prefix}_force_curves.json').read_text()))
        attempts.extend(json.loads((OUT/f'{prefix}_optimization_attempts.json').read_text()))
        coarse.extend(json.loads((OUT/f'{prefix}_coarse.json').read_text()))
        baselines.extend(json.loads((OUT/f'{prefix}_baselines.json').read_text()))
        states[f'U{u}-M{m}']=np.load(OUT/f'{prefix}_selected_states.npz')
    # Explicit missing mirror rows preserve the four-direction table schema.
    for name in NAMES:
        for mode in COLORS:
            for direction in LABELS:
                if not any(r['configuration']==name and r['direction']==direction and r['strain_mode']==mode for r in allrows):
                    allrows.append(dict(configuration=name,direction=direction,strain_mode=mode,maximum_angle_deg=None,status='no_qualifying_refined_equilibrium_found'))
    def get(name,mode,direction):return next(r for r in allrows if r['configuration']==name and r['strain_mode']==mode and r['direction']==direction)
    write_csv(OUT/'maximum_steering.csv',allrows);dump(OUT/'maximum_steering.json',allrows)
    write_csv(OUT/'pitch_sensitivity.csv',sensitivity);write_csv(OUT/'mesh_checks.csv',checks);write_csv(OUT/'force_continuations.csv',curves)
    tensions=[]
    for row in allrows:
        if 'tensions_n' not in row:continue
        for anchor,T in zip(row['anchors'],row['tensions_n']):
            tensions.append(dict(configuration=row['configuration'],direction=row['direction'],strain_mode=row['strain_mode'],anchor_module=anchor,
                up_n=T[0],right_n=T[1],down_n=T[2],left_n=T[3],angle_deg=row['directional_angle_deg'],positive_direction_reached=row['maximum_angle_deg'] is not None,
                max_abs_axial_strain=row['max_abs_axial_strain'],status=row['status']))
    write_csv(OUT/'tendon_tensions.csv',tensions)
    # Figure 1 includes signed upward recovery; a negative value is deliberately
    # shown below zero rather than mislabeled as a positive upward maximum.
    fig,axs=plt.subplots(1,3,figsize=(14,5.3),sharey=True)
    directions=['left','right','up','down'];x=np.arange(4);w=.35
    for ax,name in zip(axs,NAMES):
        for offset,mode in [(-w/2,'low_strain'),(w/2,'exploratory')]:
            vals=[]
            for direction in directions:
                r=get(name,mode,direction);vals.append(r.get('directional_angle_deg',np.nan))
            bars=ax.bar(x+offset,vals,w,color=COLORS[mode],label='5% strain diagnostic' if mode=='low_strain' else 'Larger-strain exploration')
            for bar,direction,value in zip(bars,directions,vals):
                if not np.isfinite(value):continue
                r=get(name,mode,direction)
                ax.text(bar.get_x()+bar.get_width()/2,value+4 if value>=0 else value/2,f'{r["maximum_single_tendon_n"]:.1f} N',ha='center',va='bottom' if value>=0 else 'center',fontsize=8,rotation=90,color='black' if value>=0 else 'white')
        ax.axhline(0,color='#6b747e',lw=.8);ax.axhline(180,color='#6b747e',ls='--',lw=.9)
        ax.set_xticks(x,[LABELS[d] for d in directions]);ax.set_title(name);ax.set_ylim(-120,230);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    axs[0].set_ylabel('Signed directional endpoint angle (deg)')
    fig.suptitle('Largest refined endpoint angles found | 500 g head | 20 deg base pitch',fontsize=14)
    fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=2,bbox_to_anchor=(.5,.065))
    fig.tight_layout(rect=(0,.19,1,.92));fig.text(.5,.015,'Labels show peak individual tendon tension, not total pull. Negative Up: head remains below the base axis.\nYaw near 180 deg can accompany a downward-looking head. 180 deg and 250 N are search bounds; mesh/boundary flags are in the tables.',ha='center',fontsize=8)
    save(fig,'steering_angle_and_pull.png')
    # Figure 2: heading coupled to pitch, plus the inspection-attitude diagnostic.
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    x=np.arange(3)
    for offset,mode in [(-.17,'low_strain'),(.17,'exploratory')]:
        yaw=[get(n,mode,'right').get('directional_angle_deg',np.nan) for n in NAMES]
        elev=[get(n,mode,'right').get('world_elevation_deg',np.nan) for n in NAMES]
        axs[0].bar(x+offset,elev,.34,color=COLORS[mode],label='5% strain diagnostic' if mode=='low_strain' else 'Larger-strain exploration')
        for i,(a,e) in enumerate(zip(yaw,elev)):
            if np.isfinite(e):axs[0].text(i+offset,e/2,f'yaw {a:.1f}',ha='center',va='center',fontsize=8,rotation=90,color='white')
        for i,n in enumerate(NAMES):
            r=get(n,mode,'right_level')
            if 'directional_angle_deg' in r:axs[1].bar(i+offset,r['directional_angle_deg'],.34,color=COLORS[mode])
            elif mode=='low_strain':axs[1].text(i+offset,8,'Not found',ha='center',va='bottom',rotation=90,color=COLORS[mode],fontsize=9)
    axs[0].axhspan(15,25,color='#dce8d9',alpha=.8,label='Base pitch +/- 5 deg')
    axs[0].set(title='Head elevation at unrestricted right yaw endpoint',ylabel='World head elevation (deg)',ylim=(-100,35))
    axs[1].axhline(180,color='#6b747e',ls='--',lw=.9);axs[1].set(title='Yaw with world head elevation held at 20 +/- 5 deg',ylabel='Right endpoint yaw found (deg)',ylim=(0,205))
    for ax in axs:ax.set_xticks(x,NAMES);ax.set_xlim(-.6,2.6);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.06));fig.tight_layout(rect=(0,.19,1,1))
    fig.text(.5,.012,'Unrestricted yaw is not a constant-elevation horizontal sweep. No low-strain held-elevation candidate was found in the documented searches.\nHeld-elevation exploratory results may reach strain, angle or tension bounds; they are not hardware ratings or validated continuous paths.',ha='center',fontsize=8)
    save(fig,'heading_and_elevation.png')
    # Figure 3: physical shapes show why projected angles require cross angles.
    fig=plt.figure(figsize=(14,12))
    for i,name in enumerate(NAMES):
        for j,direction in enumerate(['right','up','down']):
            ax=fig.add_subplot(3,3,i*3+j+1,projection='3d')
            row=get(name,'low_strain',direction)
            if 'state_id' not in row:continue
            p=states[name][row['state_id']+'_points_world_m']*1000
            ax.plot(p[:,0],p[:,2],p[:,1],color=COLORS['low_strain'],lw=2)
            ax.scatter(*[p[-1,0],p[-1,2],p[-1,1]],color='#c7602d',s=20)
            ax.scatter(0,0,0,color='black',s=15)
            flag=' *' if not row.get('mesh16_qualifies') else ''
            ax.set_title(f'{name} | {LABELS[direction]} {row["directional_angle_deg"]:.1f} deg{flag}\nPeak pull {row["maximum_single_tendon_n"]:.1f} N',fontsize=10)
            ax.set_xlabel('Forward mm',fontsize=8,labelpad=1);ax.set_ylabel('Lateral mm',fontsize=8,labelpad=1);ax.set_zlabel('Height mm',fontsize=8,labelpad=1)
            ax.tick_params(labelsize=7,pad=0);ax.view_init(elev=21,azim=-58)
            span=max(float(np.ptp(p,axis=0).max()),200);centre=(p.min(axis=0)+p.max(axis=0))/2
            ax.set_xlim(centre[0]-span*.55,centre[0]+span*.55);ax.set_ylim(centre[2]-span*.55,centre[2]+span*.55);ax.set_zlim(centre[1]-span*.55,centre[1]+span*.55)
            ax.set_box_aspect((1,1,1));ax.set_proj_type('ortho')
            for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.set_major_locator(MaxNLocator(3))
    fig.suptitle('Spatial endpoint shapes under the 5% strain diagnostic | free space',fontsize=14)
    fig.subplots_adjust(left=.02,right=.96,bottom=.08,top=.92,wspace=.12,hspace=.28);fig.text(.5,.01,'Eight-cell endpoint centrelines; * marks a sixteen-cell boundary warning. Capsule screening is separate. Up candidates remain below the base axis.\nLeft states are independently checked reflections. Equal-scale axes within each panel; shapes do not establish a safe trajectory between endpoints.',ha='center',fontsize=8)
    save(fig,'spatial_steering_shapes.png')
    # Figure 4: genuine force continuations with a fixed allocation vector.
    fig,axs=plt.subplots(2,3,figsize=(14,7),sharex='col')
    styles={'right':'-','up':'--','down':':'}
    for j,name in enumerate(NAMES):
        for mode in COLORS:
            for direction in styles:
                group=sorted([r for r in curves if r['configuration']==name and r['strain_mode']==mode and r['direction']==direction and r.get('converged')],key=lambda r:r['fraction'])
                if not group:continue
                force=[r['maximum_single_tendon_n'] for r in group]
                valid=[r['geometry_pass'] and r['stable_fixed_winch'] and r['directional_angle_deg']<=180.01 and (r['max_abs_axial_strain']<=.05 if mode=='low_strain' else r['max_compression']<=.300001 and r['max_extension']<=.150001) for r in group]
                axs[0,j].plot(force,[r['directional_angle_deg'] if ok else np.nan for r,ok in zip(group,valid)],styles[direction],color=COLORS[mode],marker='.',ms=3,label=f'{LABELS[direction]}, '+('5% endpoint' if mode=='low_strain' else 'exploratory endpoint'))
                axs[1,j].plot(force,[100*r['max_abs_axial_strain'] if ok else np.nan for r,ok in zip(group,valid)],styles[direction],color=COLORS[mode],marker='.',ms=3)
        axs[0,j].set_title(name);axs[0,j].set_ylabel('Signed endpoint angle (deg)');axs[1,j].set_ylabel('Maximum absolute axial strain (%)')
        axs[1,j].axhline(5,color='#6b747e',ls='--',lw=.8);axs[1,j].set_xlabel('Peak individual tendon tension (N)')
        axs[0,j].axhline(180,color='#6b747e',ls='--',lw=.6);axs[1,j].set_ylim(bottom=0)
        for ax in axs[:,j]:ax.set_xscale('symlog',linthresh=1);ax.set_xlim(left=0);ax.grid(alpha=.17)
    fig.suptitle('Force continuation along selected tension allocations | 4 cells per module',fontsize=14)
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.04),fontsize=9)
    fig.tight_layout(rect=(0,.18,1,.95));fig.text(.5,.01,'Each curve scales one selected tension allocation; it is not reoptimized at each force. Samples failing strain, capsule, stability or angle-cap screens are omitted.\nGaps and signed negative Up values must not be read as a validated connected control trajectory; all diagnostic samples remain in CSV.',ha='center',fontsize=8)
    save(fig,'force_angle_strain_curves.png')

    def angle(r,zh=False):
        if 'directional_angle_deg' not in r:return '未找到' if zh else 'Not found'
        value=r['directional_angle_deg']
        if r['direction']=='up' and value<=0:return ('未達上轉；最佳 ' if zh else 'Not above base; best ')+f'{value:.2f}'
        return f'{value:.2f}'+(' *' if r.get('orientation_search_cap_reached') else '')
    def number(r,k,d=2):return f'{r[k]:.{d}f}' if k in r else '—'
    def table(mode,zh=False):
        headers=['配置','方向','角度 deg','最大單繩 N','最大應變 %','世界仰角 deg','16網格檢查'] if zh else ['Configuration','Direction','Angle deg','Peak tendon N','Max strain %','World elevation deg','16 cell check']
        s='| '+' | '.join(headers)+' |\n|'+'---|'*len(headers)+'\n'
        for name in NAMES:
            for direction in ['right','left','up','down']:
                r=get(name,mode,direction);mesh=('通過' if zh else 'Pass') if r.get('mesh16_qualifies') else ('邊界/未確認' if zh else 'Boundary or unconfirmed')
                strain=f'{100*r["max_abs_axial_strain"]:.2f}' if 'max_abs_axial_strain' in r else '—'
                s+='| '+' | '.join([name,LABELS[direction],angle(r,zh),number(r,'maximum_single_tendon_n'),strain,number(r,'world_elevation_deg'),mesh])+' |\n'
        return s
    def tensor_table(zh=False):
        heads=['配置','類別','方向','錨點節號','各組張力 [上,右,下,左] N'] if zh else ['Configuration','Mode','Direction','Anchors','Tensions per set [up right down left] N']
        s='| '+' | '.join(heads)+' |\n|'+'---|'*len(heads)+'\n'
        for r in allrows:
            if 'tensions_n' not in r:continue
            # Left is fully present in CSV; the symmetric printed table avoids
            # duplicating long arrays and explains the swap explicitly.
            if r['direction'].startswith('left'):continue
            tt=' ; '.join('['+', '.join(f'{v:.2f}' for v in T)+']' for T in r['tensions_n'])
            s+='| '+' | '.join([r['configuration'],r['strain_mode'],LABELS[r['direction']],str(r['anchors']),tt])+' |\n'
        return s
    shape_table_zh=table('low_strain',True);shape_table_en=table('low_strain')
    exploratory_zh=table('exploratory',True);exploratory_en=table('exploratory')
    tension_zh=tensor_table(True);tension_en=tensor_table()
    level_rows=[]
    for name in NAMES:
        for mode in COLORS:
            r=get(name,mode,'right_level')
            level_rows.append(dict(configuration=name,strain_mode=mode,angle=angle(r),peak=number(r,'maximum_single_tendon_n'),strain=f'{100*r["max_abs_axial_strain"]:.2f}' if 'max_abs_axial_strain' in r else '—',mesh=r.get('mesh16_qualifies')))
    level_table='| Configuration | Mode | Yaw deg | Peak tendon N | Max strain % |\n|---|---|---:|---:|---:|\n'+'\n'.join(f'| {r["configuration"]} | {r["strain_mode"]} | {r["angle"]} | {r["peak"]} | {r["strain"]} |' for r in level_rows)
    mesh=[c for c in checks if c.get('kind')=='mesh8_to16']
    verified=[r for r in allrows if r.get('qualifies')]
    summary=dict(database_sha256=DATA['database_sha256'],coarse_local_optimization_attempts=len(attempts),
        coarse_qualified_records=sum(r.get('qualifies',False) for r in coarse),selected_records=len(verified),
        mirrored_records=sum(r.get('mirror_equilibrium_verified',False) for r in allrows),
        orientation_cap_records=sum(r.get('orientation_search_cap_reached',False) for r in verified),
        tension_cap_records=sum(r.get('tension_bound_reached',False) for r in verified),
        mesh16_checks=len(mesh),mesh16_qualified=sum(r.get('qualifies',False) for r in mesh),
        maximum_mesh8_to16_angle_change_deg=max(r.get('angle_change_deg',0) for r in mesh),
        low_strain_held_elevation_found=sum(get(n,'low_strain','right_level').get('qualifies',False) for n in NAMES),
        pitch_sensitivity_records=len(sensitivity),force_continuation_records=len(curves),
        physical_maximum_established=False,tank_clearance_validated=False)
    dump(OUT/'summary.json',summary)
    u4right=get('U4-M2','low_strain','right');u4up=get('U4-M2','low_strain','up');u4down=get('U4-M2','low_strain','down')
    text=f'''# 水平及垂直轉向角與拉索張力 / Spatial steering angles and tendon tensions

2026-11-06 · 63 mm外徑 / diameter · 24 mm導孔半徑 / guide radius · 500 g頭部 / head

## 中文

### 先看結論

本研究完成U4+M2、U6+M3、U8+M4的自由空間帶載三維轉向搜尋，主算基部仰角20°。下表是有明確數值界限的「最大已找到端點」，不是材料、繩索或馬達的物理額定極限。

**水平方位角與可用的水平姿態必須一起看。** 例如U4+M2低應變診斷候選的左右方位角約{u4right['directional_angle_deg']:.2f}°，但頭部世界仰角為{u4right['world_elevation_deg']:.2f}°，即明顯朝下。這不表示前端已能在水平或基部方向完成約360°掃描，也沒有驗證端點之間的連續路徑。

三組配置在本輪5%應變診斷搜尋中，都未找到頭部世界仰角維持20±5°的水平轉向候選。上轉搜尋的最佳低應變姿態也仍低於基部軸線。以U4+M2為例，上拉後相對基部角度為{u4up['vertical_projected_deg']:.2f}°，向下端點為{u4down['vertical_projected_deg']:.2f}°；最大單繩張力分別為{u4up['maximum_single_tendon_n']:.2f}與{u4down['maximum_single_tendon_n']:.2f} N。這些端點之間的角度差不等於已驗證可連續掃過的範圍。

### 角度及張力定義

- 世界X為基部朝前的水平方向，Y向上，Z向右；基部在X-Y平面仰起20°。
- 水平方位角：末端切線在世界X-Z平面的有號投影角。左、右分開記錄，表內方向角以對應方向為正。
- 垂直轉角：末端切線在世界X-Y平面的有號投影角減去基部20°，沿桿的框架序列展開。正值代表從基部方向上轉，負值代表下轉；這與世界仰角不是同一個量。
- 世界仰角：末端切線相對水平面的仰角，範圍±90°。同時輸出真正三維軸線夾角、材料總扭轉及頭部位置。投影模長低於0.1的近奇異姿態不作主方向候選。
- 自然下垂只作各配置的參照。`upward_recovery_from_natural_deg`表示相對帶500 g自然下垂姿態抬高了多少。
- 每組拉索依序為 **[上, 右, 下, 左]**；每一項都是N。`maximum_single_tendon_n`是最大單繩張力，`sum_tensions_n`才是全部張力總和。

### 輸入與模型

資料直接來自唯讀`module_stiffness.sqlite3`，輸入快照為`module_stiffness_input.sqlite3`。U為PA12+NiTi，96 mm、37.990 g、EA=128122 N、垂直EI=22.2052 N·m²、水平EI=1.67184 N·m²；M為PA12，96 mm、23.948 g、EA=166.694 N、各方向EI=0.0441178 N·m²。63 mm沒有再次觸發剛度或質量縮放。三組柔性長度為576/864/1152 mm，加20 mm無質量接口後為596/884/1172 mm。

資料庫的扭轉欄位為整節`T/θ`，U=4.70037、M=0.437396 N·m/rad。轉成連續桿係數時乘上0.096 m，並在細分時保持整節扭轉能量一致。U剛度已包含NiTi效果，沒有額外再加金屬棒。資料未提供正反向不同的剛度，因此各主彎曲方向暫採對稱線性係數。

頭部為500 g集中質量，沒有偏心力矩；模組本身及實際繞行長度的繩質量已計入。各組四條2 mm拉索，沿用先前PA6實心代理EA與密度、無摩擦。每條繩從基部經真實模組端盤到自己的錨點，遠端繩索仍壓縮近端。新增錨定硬體、外皮、線路及真實接頭質量未量測。

| 配置 | 單組 | 兩組 | 三組U分段 | 三組M分段 |
|---|---|---|---|---|
| U4+M2 | [6] | [4,6] | [2,4,6] | [4,5,6] |
| U6+M3 | [9] | [6,9] | [3,6,9] | [6,7,9] |
| U8+M4 | [12] | [8,12] | [4,8,12] | [8,10,12] |

採可軸向伸縮、有限旋轉Kirchhoff桿，包含兩個材料彎曲方向及獨立扭轉。所有繩張力與重力同時作用；最大角不靠鎖住另一平面的自由度取得。左轉由精確對稱模型的右轉狀態鏡像，並重新檢查力平衡、幾何及穩定性；真實列印誤差和摩擦不一定對稱。

### 5%應變診斷結果

{shape_table_zh}

「未達上轉」表示最高合格頭部方向仍低於基部軸線，並非0°。該列張力對應最佳抬升候選。左右鏡像的最大張力相同，但左右繩分量互換。U6+M3左右候選在16單元/節的應變為5.0015%，嚴格超過5%；因此179.94°不能當作已通過細網格低應變診斷的最大角。接近邊界的值不能只看四捨五入。

![角度與最大單繩張力](results/steering_angle_and_pull.png)

### 大應變探索結果

{exploratory_zh}

星號表示達到180°方向角搜尋上界，不代表找到了真正機械極限。上/下180°代表投影框架轉到反向附近，不是頭部世界仰角180°。部分16單元/節核對會跨出角度、應變、幾何或姿態限制，因此表中邊界案例只能作探索，不作已收斂的最大能力。

### 保持頭部仰角的水平轉向補查

另外要求頭部世界仰角落在20±5°；此條件與不限制俯仰的方位角搜尋分開報告。低應變候選未找到，大應變候選仍受數值邊界與細網格敏感性限制。

{level_table}

![方位角與仰角](results/heading_and_elevation.png)

### 對應完整拉索張力

下面各括號對應一組錨點，順序與錨點列表一致，括號內為[上,右,下,左] N。表中顯示到0.01 N，原始精度保存在JSON及CSV。左轉的數據在`tendon_tensions.csv`完整列出；它與右轉的右/左分量互換。這些是找到該端點的一組張力解，不宣稱是最小張力解。

{tension_zh}

![三維端點形狀](results/spatial_steering_shapes.png)

### 搜尋、加密及限制

初始搜尋用2單元/節，包含帶載下垂、小張力、上一輪主動拉直及非平面起始分支。使用平衡等式、非負張力和幾何不等式作局部優化。每根繩的數值範圍0–250 N；低應變粗網格限制±4.75%以預留加密餘量，大應變為−30%至+15%。這些是數值域，不是任何部件的強度或額定值。每格旋轉分量亦有數值界限，另以rκ≤0.98作局部曲率餘量。非局部63 mm膠囊檢查只比較材料弧長相隔至少126 mm的段，未驗證詳細模組接觸或材料壓屈。

最大候選加密到4及8單元/節；必要時重新局部優化或沿控制向量縮放恢復可行邊界。每個最終候選再做同張力16單元/節核對。局部穩定以固定捲筒、彈性繩並額外1 m自由繩長的切線Hessian檢查；另保留恆張力Hessian結果。這是局部診斷，不是動態閉迴路控制或實物穩定性證明。

本輪共{summary['coarse_local_optimization_attempts']}次初始/補充局部優化，16網格核對{summary['mesh16_checks']}個候選，最大角度變化{summary['maximum_mesh8_to16_angle_change_deg']:.3f}°。詳細收斂、回復方法及邊界分類在`mesh_checks.csv`和各配置的`refinement_checks.json`。

15°及25°只對20°選定張力重新求平衡，數據見`pitch_sensitivity.csv`；沒有把它稱作重新優化後的最大角。若姿態或應變條件改變，該點會標為不通過。

力—角度—應變曲線以4單元/節、按比例縮放一組選定張力向量求平衡，並非把不同錨定的最優點直接連線。曲線中間點可能跨過應變、自包絡或穩定篩選，不能當作已驗證連續控制路徑。

![力角度應變曲線](results/force_angle_strain_curves.png)

尚未驗證NiTi轉變、本構非線性、列印材料局部失效、接頭間隙、拉索摩擦、馬達/繩索強度、動態或油箱三維碰撞。尤其不能把250 N數值上限當成可施加的硬體張力。當前優先問題仍是M段的軸向承載及帶載頭部抬升，而非只追求較大的投影角。

## English

### Findings and interpretation

This is a bounded free-space spatial steering study of U4+M2, U6+M3 and U8+M4 carrying a 500 g point head at 20 degrees base pitch. Results are the largest refined endpoints found in documented local searches, not physical material or actuator ratings.

Unrestricted yaw must be read with head elevation. For U4+M2, the low-strain right/left yaw is {u4right['directional_angle_deg']:.2f} degrees, while world head elevation is {u4right['world_elevation_deg']:.2f} degrees. A downward-looking head can have large azimuth changes with much smaller true axis changes. This does not establish a constant-elevation or continuous 360 degree inspection sweep.

No tested configuration produced a low-strain candidate with world head elevation held at 20 +/- 5 degrees. The highest low-strain upward candidates remain below the base axis. For U4+M2 the signed upward candidate is {u4up['vertical_projected_deg']:.2f} degrees relative to the base, and the downward endpoint is {u4down['vertical_projected_deg']:.2f} degrees; peak tendon tensions are {u4up['maximum_single_tendon_n']:.2f} and {u4down['maximum_single_tendon_n']:.2f} N. The difference between endpoint angles is not a proven connected controllable range.

### Definitions and inputs

World X points horizontally forward, Y upward and Z right. The base is pitched 20 degrees in X-Y. Yaw is the signed endpoint tangent projection in world X-Z. Vertical turning is the unwrapped tangent projection in world X-Y minus base pitch. World elevation is separately measured against the horizontal plane and lies between +/-90 degrees. True 3D axis angle, material twist and head position are also saved. Projection norms below 0.1 are rejected as near singular. Negative signed Up means the head still points below the base; it is not a zero-degree upward maximum.

Every set is ordered **[up, right, down, left]**, in N. Peak individual tendon force and sum of all tendon forces are distinct columns. Natural loaded sag is a reference, not a required insertion or steering shape. Vertical recovery from natural sag is recorded separately.

The read-only source database supplies 96 mm modules. U is PA12+NiTi, 37.990 g, EA 128122 N, vertical EI 22.2052 N m² and horizontal EI 1.67184 N m². M is PA12, 23.948 g, EA 166.694 N and EI 0.0441178 N m² in all directions. Diameter is 63 mm and tendon radius 24 mm; no stiffness or mass scaling is applied. Flexible lengths are 576, 864 and 1152 mm, or 596, 884 and 1172 mm including a massless 20 mm interface. Both U and M length and weight change across configurations.

Whole-module torsion coefficients are U 4.70037 and M 0.437396 N m/rad. They are multiplied by 0.096 m to form the rod coefficient, preserving module twist energy under subdivision. No additional metal backbone is added. Positive/negative bending is assumed symmetric because asymmetric data were not supplied. EA/EI remain constant; NiTi transformation and local component failure are not modeled.

Four 2 mm tendons per anchor set use the prior solid PA6 proxy properties with no friction. Every tendon runs from the base through actual module disk guides to its anchor, so distal tendons still compress proximal modules. Routed rope mass and supplied module mass are included; new anchors, sheaths, wiring, head eccentricity and actual joint mass are unmeasured.

Layouts are head-only [N], two sets [U,N], three sets [U/2,U,N], and three sets [U,U+floor(M/2),N]. Left results are independently checked reflections of right states under the exact symmetric model, not additional independent optimization searches. Real manufacturing and friction may break this symmetry.

### Low-strain diagnostic endpoints

{shape_table_en}

The 5% value is a comparison diagnostic, not a measured allowable strain. The Up force belongs to the best recovery candidate when no positive upward angle is found. U6+M3 yaw reaches 5.0015% strain at sixteen cells per module, strictly above 5%; its 179.94 degree candidate is not a confirmed fine-mesh low-strain maximum. Boundary values must not be rounded into acceptance.

### Larger-strain exploratory endpoints

{exploratory_en}

An asterisk denotes the 180 degree orientation search cap. It is not a demonstrated mechanical limit. Up/down 180 degree projected turning does not mean 180 degree world elevation. Some same-tension 16-cell checks cross an angular, strain, geometry or posture boundary; those points remain exploratory rather than converged maxima.

### Horizontal inspection-attitude diagnostic

The following additional search holds world head elevation at 20 +/- 5 degrees. It is separate from unrestricted yaw of a sagged tip. No low-strain candidate was found in the documented searches.

{level_table}

### Full tendon forces

Each bracket corresponds to one listed anchor, ordered [up,right,down,left] N. Printed values are rounded to 0.01 N. Exact arrays and complete left-force records are in `tendon_tensions.csv` and `maximum_steering.json`; left swaps the right/left entries. These are force allocations found for the endpoint, not certified minimum-force solutions.

{tension_en}

### Search bounds and verification

The spatial extensible Kirchhoff rod retains finite rotations, two anisotropic bending components and independent twist. Gravity and all tendons act simultaneously. Initial two-cell-per-module searches use loaded-sag, small-tension, previously straightened and nonplanar branches. Each rope is bounded at 0 to 250 N. Coarse low-strain bounds are +/-4.75% with refinement margin; exploratory strain bounds are -30% to +15%. Per-cell rotation bounds and an optimization margin r*kappa <= 0.98 are numerical. Nonlocal 63 mm capsules are checked only for segments separated by at least 126 mm reference arc length, not detailed module contact.

Candidate maxima are re-equilibrated and, when needed, locally re-optimized at four and eight cells per module. Documented force-ray recovery is used for some fine boundary states. Each selected state receives a same-tension sixteen-cell check. Fixed-winch elastic-tendon local stability includes 1 m additional free rope; constant-tension Hessian results are retained separately. Local stability does not validate dynamics or a transition path.

There are {summary['coarse_local_optimization_attempts']} initial/supplementary local optimization attempts and {summary['mesh16_checks']} sixteen-cell checks, with {summary['maximum_mesh8_to16_angle_change_deg']:.3f} degrees maximum change. Energy gradients, planar energy/deformation equivalence and module twist energy are independently checked. Left mirror energy/gradient symmetry is verified. Numerical consistency does not establish physical material validity.

Pitch sensitivities at 15 and 25 degrees re-equilibrate the selected 20-degree tensions; they are not re-optimized maxima. Force curves use four cells per module and scale one fixed allocation vector through equilibrium solves. Intermediate samples can cross strain, geometry or stability screens, so these curves are not certified trajectories.

The angular cap, tendon cap or strain boundary can limit a result. No global optimum, physical maximum, real actuator rating or fuel-tank collision clearance is established. M axial load transfer and loaded head recovery remain the main design concerns.

### Files and reproduction

- `results/maximum_steering.csv` and `.json`: all selected endpoints and mesh flags.
- `results/tendon_tensions.csv`: one row per anchor set, with all four rope forces.
- `results/pitch_sensitivity.csv`: same-force 15/25 degree checks.
- `results/mesh_checks.csv`: fine mesh changes and boundary recovery records.
- `results/force_continuations.csv`: force-angle-strain samples.
- Four English PNG figures are linked above; the source database and earlier simulations remain unchanged.

Input SHA256: `{DATA['database_sha256']}`. Existing Python NumPy/SciPy/Numba/Matplotlib packages are used; no large dependencies or CAD runtimes are installed. The original project planar kernel and tendon catalogue remain read dependencies. From the project root:

```powershell
python telescopic_planar_study/steering_63mm_20261106/search_steering.py validate
python telescopic_planar_study/steering_63mm_20261106/search_steering.py coarse --u 4 --m 2
python telescopic_planar_study/steering_63mm_20261106/extend_search.py --u 4 --m 2
python telescopic_planar_study/steering_63mm_20261106/refine_steering.py --u 4 --m 2
python telescopic_planar_study/steering_63mm_20261106/force_curves.py --u 4 --m 2
# Repeat the preceding four study steps for --u 6 --m 3 and --u 8 --m 4
python telescopic_planar_study/steering_63mm_20261106/report_results.py
```

To reproduce a frozen source after the main database changes, set `ASRC_STIFFNESS_DB` to this study's `module_stiffness_input.sqlite3` before running. Input and code hashes are stored with the validation output. Existing results must be preserved before rerunning.
'''
    (HERE/'README.md').write_text(text,encoding='utf-8')
    assert hashlib.sha256(DB.read_bytes()).hexdigest()==DATA['database_sha256']
    manifest=dict(database_unchanged=True,database_sha256=DATA['database_sha256'],python=sys.version,
        numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__,matplotlib=matplotlib.__version__,
        script_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
        readme_bilingual=True,figures_english=True,free_space_only=True)
    dump(OUT/'delivery_validation.json',manifest)
    print(json.dumps(summary,indent=2));print('Study size MB',sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())/1024**2)

if __name__=='__main__':run()
