"""English figures and bilingual README from the saved study outputs."""
import json,sys,hashlib,platform
from pathlib import Path
import numpy as np
import scipy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.text import Text
from run_study import HERE,OUT,OLD,PAIRS,DATA,DB,DatabaseRod,dump,write_csv
from project_paths import KERNEL_PATH

COLORS={'baseline':'#707984','shape_only':'#c7602d','low_strain':'#246b9d'}
LABELS={'single':'1 set','two':'2 sets','three':'3 sets in U','three_distal':'3 sets with M anchor'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})

def save(fig,name):
    for t in fig.findobj(Text):
        assert all(ord(c)<128 for c in t.get_text()),t.get_text()
    fig.savefig(OUT/name,dpi=170,bbox_inches='tight');plt.close(fig)

def run():
    summary=json.loads((OUT/'summary.json').read_text())
    assert 'mesh_8_to_16_checked' in summary,'Complete refinement first'
    rows=json.loads((OUT/'all_equilibria.json').read_text())
    reps=json.loads((OUT/'representatives.json').read_text())
    refined=json.loads((OUT/'refined_equilibria.json').read_text())
    rz=np.load(OUT/'refined_states.npz')
    states={f'U{u}-M{m}':np.load(OUT/f'U{u}_M{m}_states.npz') for u,m in PAIRS}
    rr={(r['configuration'],r['state_id']):r for r in refined}
    def representative(name,pitch,mode):
        r=next(r for r in reps if r['configuration']==name and abs(r['pitch_deg']-pitch)<1e-6 and r['strain_mode']==mode)
        return rr[r['configuration'],r['state_id']]
    def points(r):
        key=r['configuration']+'_'+r['state_id']+'_points_m'
        return rz[key] if key in rz.files else states[r['configuration']][r['state_id']+'_points_m']
    comparison=[]
    for u,m in PAIRS:
        name=f'U{u}-M{m}'
        baseline=next(r for r in rows if r['configuration']==name and r['kind']=='natural_baseline' and abs(r['pitch_deg']-20)<1e-6)
        comparison.append(baseline)
        comparison.extend([representative(name,20,mode) for mode in ['shape_only','low_strain']])
    write_csv(OUT/'comparison_20deg.csv',comparison);dump(OUT/'comparison_20deg.json',comparison)
    # Figure 1: actively tensioned shapes, with sag as a reference only.
    fig,axs=plt.subplots(1,3,figsize=(14,5.1))
    for ax,(u,m) in zip(axs,PAIRS):
        name=f'U{u}-M{m}';rot=np.array([[np.cos(np.radians(20)),-np.sin(np.radians(20))],[np.sin(np.radians(20)),np.cos(np.radians(20))]])
        group=[r for r in comparison if r['configuration']==name]
        for r in group:
            mode='baseline' if r['kind']=='natural_baseline' else r['strain_mode']
            p=points(r)@rot*1000
            label={'baseline':'No tension reference','shape_only':'Shape optimized','low_strain':'Near 5% strain bound'}[mode]
            ax.plot(p[:,0],p[:,1],color=COLORS[mode],lw=2,label=label)
            ax.plot(p[-1,0],p[-1,1],'o',color=COLORS[mode],ms=4)
        r=representative(name,20,'shape_only')
        ax.axhline(0,color='#7a838c',ls='--',lw=.8)
        low_r=representative(name,20,'low_strain')
        ax.set(title=f'{name} | nominal {r["nominal_front_length_mm"]:.0f} mm\nShape anchors {r["anchors"]}\nLow-strain anchors {low_r["anchors"]}',xlabel='Projection along insertion axis (mm)',ylabel='Offset from insertion axis (mm)')
        ax.grid(alpha=.18);ax.set_aspect('equal',adjustable='box')
    fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=3,bbox_to_anchor=(.5,.045))
    fig.suptitle('Active insertion tension | 63 mm front | 500 g head | 20 deg root pitch',fontsize=14)
    fig.tight_layout(rect=(0,.15,1,.92))
    fig.text(.5,.012,'Selected controls were re-solved with 16 cells per module. Shape-only results use large-strain elastic extrapolation; 5% is a diagnostic, not an allowable strain.',ha='center',fontsize=8)
    save(fig,'active_front_shapes.png')
    # Figure 2: the original three layouts and one extra three-set layout.
    fig,axs=plt.subplots(2,3,figsize=(14,7),sharex='col')
    architectures=['single','two','three','three_distal'];x=np.arange(4);w=.34
    for j,(u,m) in enumerate(PAIRS):
        name=f'U{u}-M{m}'
        for delta,mode in [(-w/2,'shape_only'),(w/2,'low_strain')]:
            group=[next(r for r in rows if r['configuration']==name and r.get('kind')=='optimized' and r.get('architecture')==a and r.get('strain_mode')==mode and abs(r['pitch_deg']-20)<1e-6) for a in architectures]
            y=[r['maximum_axis_deviation_mm'] for r in group]
            strain=[100*r['max_abs_axial_strain'] for r in group]
            axs[0,j].bar(x+delta,y,w,color=COLORS[mode],label='Shape optimized' if mode=='shape_only' else 'Near 5% strain bound')
            axs[1,j].bar(x+delta,strain,w,color=COLORS[mode])
        axs[0,j].axhline(10,color='#6b747e',ls='--',lw=1)
        axs[1,j].axhline(5,color='#6b747e',ls='--',lw=1)
        axs[0,j].set_title(name);axs[0,j].set_ylabel('Maximum axis offset (mm)');axs[1,j].set_ylabel('Maximum absolute axial strain (%)')
        axs[1,j].set_xticks(x,['1','2','3U','3M']);axs[1,j].set_xlabel('Number and location of anchor sets')
        for ax in axs[:,j]:ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('Anchor layout comparison at 20 deg | 8 cells per module',fontsize=14)
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='lower center',ncol=2,bbox_to_anchor=(.5,.035))
    fig.tight_layout(rect=(0,.13,1,.95));fig.text(.5,.01,'3U: original mid-U / U-M / tip anchors. 3M: U-M / mid-M / tip anchors. Dashed lines: 10 mm offset and 5% strain diagnostics. Some high-strain shapes fail capsule checks.',ha='center',fontsize=8)
    save(fig,'anchor_layout_comparison.png')
    # Figure 3: complete front-only feed, including the initially external head.
    paths=json.loads((OUT/'refined_passing_path_checks.json').read_text())
    pc=np.load(OUT/'refined_path_curves.npz')
    example=next(r for r in paths if r['configuration']=='U4-M2' and abs(r['pitch_deg']-20)<1e-6)
    r=rr[example['configuration'],example['state_id']];p=points(r)*1000
    cad=json.loads((OLD/'results/cad_sections.json').read_text());main=next(s for s in cad['sections'] if s['width_mm']==648)
    prof=np.load(OLD/'results/cavity_profiles.npz');entry=np.array([449.,np.interp(449.,prof['length_mm'],prof['floor_mm'])]);v=np.array([np.cos(np.radians(20)),np.sin(np.radians(20))])
    fig,axs=plt.subplots(2,1,figsize=(12,7.8))
    for poly in main['union_polygons']:
        axs[0].add_patch(Polygon(poly['outer'],facecolor='#7c8790',edgecolor='#7c8790',lw=.4))
        for hole in poly['holes']:axs[0].add_patch(Polygon(hole,facecolor='white',edgecolor='#7c8790',lw=.4))
    for s,c in [(example['start_s_mm'],'#8b939c'),(0,'#246b9d'),(example['final_s_mm'],'#c7602d')]:
        q=p+entry+s*v;axs[0].plot(q[:,0],q[:,1],color=c,lw=2,label=f's = {s:.0f} mm');axs[0].plot(*q[-1],'o',color=c,ms=5)
    axs[0].set(xlim=(-350,1650),ylim=(-230,500),xlabel='Tank length coordinate (mm)',ylabel='Height (mm)',title=f'U4-M2 front-only entry at 20 deg | anchors {r["anchors"]} | strain {100*r["max_abs_axial_strain"]:.2f}%')
    axs[0].set_aspect('equal');axs[0].legend(fontsize=9);axs[0].grid(alpha=.15)
    for q in paths:
        key=q['configuration']+'_'+q['state_id'];s=pc[key+'_s_mm'];gap=pc[key+'_gap_mm']
        axs[1].plot(s,gap,lw=1.6,label=f'{q["configuration"]}, {q["pitch_deg"]:.0f} deg')
    axs[1].axhline(5,color='#6b747e',ls='--',label='5 mm clearance screen')
    axs[1].set(xlabel='Front interface insertion coordinate s (mm)',ylabel='Front envelope clearance (mm)',ylim=(0,150),title='Passing front sweeps rechecked at 16 cells per module')
    axs[1].legend(ncol=3,fontsize=9);axs[1].grid(alpha=.15)
    fig.tight_layout(rect=(0,.08,1,1));fig.text(.5,.015,'Saved five CAD sections only. Centreline snapshots; 63 mm capsules used for clearance. Initial head entry is included in this front-only moving-clamp screen.\nRear guide crossing, telescopic storage, sheath contact, actual head shape and full 3D deployment are unvalidated. Passing cases exceed the 5% strain diagnostic.',ha='center',fontsize=8)
    save(fig,'front_only_entry_screen.png')
    # Figure 4: load transfer and old rear tube reference, not new sheath design.
    rear=json.loads((OUT/'rear_reference.json').read_text())
    fig,axs=plt.subplots(1,2,figsize=(11,4.7));x=np.arange(3);w=.32
    for delta,mode in [(-w/2,'shape_only'),(w/2,'low_strain')]:
        group=[next(r for r in rear if r['configuration']==f'U{u}-M{m}' and r['strain_mode']==mode and r['layout']=='stepped_40_30' and abs(r['exposed_length_m']-1)<1e-8) for u,m in PAIRS]
        axs[0].bar(x+delta,[r['interface_vertical_deflection_down_mm'] for r in group],w,color=COLORS[mode],label='Shape optimized' if mode=='shape_only' else 'Near 5% strain bound')
        axs[1].bar(x+delta,[r['root_gravity_moment_nm'] for r in group],w,color=COLORS[mode])
    for ax in axs:ax.set_xticks(x,[f'U{u}-M{m}' for u,m in PAIRS]);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    axs[0].set(ylabel='Interface downward deflection (mm)',title='Ideal 40/30 mm beam at 1 m exposure')
    axs[1].set(ylabel='Base gravity moment (N m)',title='Front force and moment plus rear self weight')
    fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=2,bbox_to_anchor=(.5,.06));fig.tight_layout(rect=(0,.2,1,1))
    fig.text(.5,.015,'20 deg root pitch. Original 40/30 mm aluminium tubes are reference supporting beams, NOT 63 mm storage sheaths.\nJoint compliance, overlap, tendon and drive reactions, buckling and base anchorage are excluded.',ha='center',fontsize=8)
    save(fig,'rear_gravity_reference.png')

    def fmt(r):return f"{r['configuration']} | {str(r['anchors'])} | {r['maximum_axis_deviation_mm']:.2f} | {r['maximum_tangent_error_deg']:.2f} | {r['axial_projection_mm']:.1f} | {100*r['max_abs_axial_strain']:.2f}%"
    zh_table='| 配置 | 錨點節號 | 最大軸線偏差 mm | 最大切線誤差 deg | 軸向投影 mm | 最大絕對軸向應變 |\n|---|---|---:|---:|---:|---:|\n'
    en_table='| Configuration | Anchors | Axis offset mm | Tangent error deg | Projection mm | Max absolute axial strain |\n|---|---|---:|---:|---:|---:|\n'
    shape=[representative(f'U{u}-M{m}',20,'shape_only') for u,m in PAIRS]
    low=[representative(f'U{u}-M{m}',20,'low_strain') for u,m in PAIRS]
    shape_zh=zh_table+'\n'.join('| '+fmt(r)+' |' for r in shape)
    low_zh=zh_table+'\n'.join('| '+fmt(r)+' |' for r in low)
    shape_en=en_table+'\n'.join('| '+fmt(r)+' |' for r in shape)
    low_en=en_table+'\n'.join('| '+fmt(r)+' |' for r in low)
    path_zh='| 配置 | 安裝角度 deg | 最大應變 | 路徑最小間隙 mm | 最終接口 s mm |\n|---|---:|---:|---:|---:|\n'+'\n'.join(f"| {r['configuration']} | {r['pitch_deg']:.0f} | {100*r['max_abs_axial_strain']:.2f}% | {r['minimum_sampled_envelope_clearance_mm']:.2f} | {r['final_s_mm']:.0f} |" for r in paths)
    path_en='| Configuration | Pitch deg | Max strain | Minimum path clearance mm | Final interface s mm |\n|---|---:|---:|---:|---:|\n'+'\n'.join(f"| {r['configuration']} | {r['pitch_deg']:.0f} | {100*r['max_abs_axial_strain']:.2f}% | {r['minimum_sampled_envelope_clearance_mm']:.2f} | {r['final_s_mm']:.0f} |" for r in paths)
    size_rows='\n'.join(f'| U{u}+M{m} | {(u+m)*96} | {(u+m)*96+20} | {u*37.990+m*23.948:.3f} |' for u,m in PAIRS)
    checks=json.loads((OUT/'mesh_8_to_16_checks.json').read_text())
    low_mesh=max(r['tip_change_mm'] for r in checks if 'low_strain' in r['state_id'])
    readme=f'''# 63 mm U/M 模組主動張力入箱研究 / Active tension insertion study

2026-11-06 · 最新資料庫 / latest database · 外徑 / diameter 63 mm · 導孔半徑 / tendon radius 24 mm

## 中文

### 結論

進入油箱時允許主動拉索張力；本輪**沒有要求前端以自然下垂形狀進入**。自然下垂只作對照。

主動張力確實改善形狀，短配置U4+M2最值得繼續研究。在20°、錨點[4,5,6]的代表解中，16單元/節結果的最大軸線偏差為{shape[0]['maximum_axis_deviation_mm']:.2f} mm、切線誤差{shape[0]['maximum_tangent_error_deg']:.2f}°，但M段最大軸向應變為{100*shape[0]['max_abs_axial_strain']:.2f}%。因此不能把「已拉直」解讀為已通過實際承載要求。

本輪沒有找到同時通過接近直線幾何條件、5%軸向應變診斷及局部穩定篩選的案例。這是有限控制搜尋及局部優化的結果，**不是全域無解證明**。5%仍是診斷門檻，並非實測破壞或允許應變。

### 資料與尺寸

直接讀取根目錄的`module_stiffness.sqlite3`，資料庫以唯讀方式開啟；原資料和舊模擬均未修改。輸入快照為`module_stiffness_input.sqlite3`，完整參數及來源雜湊見`input_parameters.json`。

| 參數 | U / PA12+NiTi | M / PA12 |
|---|---:|---:|
| 節長 mm | 96 | 96 |
| 單節質量 g | 37.990 | 23.948 |
| EA N | 128122 | 166.694 |
| 垂直抗重力EI N·m² | 22.2052 | 0.0441178 |
| 水平EI N·m² | 1.67184 | 0.0441178 |
| 模組扭轉彈簧剛度 N·m/rad | 4.70037 | 0.437396 |

GJ欄位按資料庫定義理解為整節`T/θ`，沒有誤當作N·m²。本輪為平面計算，未使用扭轉自由度。U數據已包含NiTi結構效果，沒有再疊加一根中心金屬棒。剛度及質量不按63 mm再次縮放。

| 配置 | 柔性段 mm | 加20 mm接口後 mm | 模組質量 g |
|---|---:|---:|---:|
{size_rows}

頭部為500 g集中質量，沒有偏心力矩；幾何包絡暫用直徑63 mm，實際檢測頭外形仍未知。接口長20 mm、質量暫為零。模組尺寸按96 mm實際節長保留，因此三組前端不是0.5 m。增加U的同時也增加M長度及整體質量，這不是單純只改變U數量的比較。

### 拉索及錨點

比較15/20/25°、U近端/M遠端、高剛度方向抵抗重力。每組四條2 mm拉索，以舊模型的PA6實心代理剛度及密度計算，無摩擦；本平面主要調整上繩。每條繩都從基部經真實模組端盤到自身錨點，遠端繩索仍壓縮近端模組。新增繩質量已計入；錨定、導向、外皮、線路及接頭額外質量未量測。

| 配置 | 單組 | 兩組 | 原三組 3U | 補充三組 3M |
|---|---|---|---|---|
| U4+M2 | [6] | [4,6] | [2,4,6] | [4,5,6] |
| U6+M3 | [9] | [6,9] | [3,6,9] | [6,7,9] |
| U8+M4 | [12] | [8,12] | [4,8,12] | [8,10,12] |

3M是仍不超過三組的補充對照，用來檢查M段內部錨定是否改善形狀；不是新增第四組。既有四孔不能視為已能容納多組繩，實際布線尚待設計。

單組有限掃描使用上繩額外0–200 N、每繩共同基準0或2 N。局部優化各組上繩數值界限0–250 N，並使用下垂、估算重力補償、較簡單架構嵌入等初始分支。這些張力是數值搜尋界限，**不是繩、馬達或模組額定值**；部分解碰到250 N上限，不能宣告為真正最大能力。

### 20度代表結果

以下取局部穩定、中心線與非局部63 mm包絡及局部半徑曲率初篩通過的候選；按軸線偏差加投影損失分數選取，不宣稱全域最優。表中代表解已按相同張力加密至16單元/節。

**允許較大應變、以形狀為目標**

{shape_zh}

U8+M4另有3M高應變解在8單元/節達約74.49 mm偏差、30.17%應變，但局部半徑曲率包絡篩選未過，因此沒有將它當作有效幾何候選。

**接近5%應變診斷上限的代表解**

{low_zh}

應變受限後仍有顯著彎曲；單看低應變或頭部位置，不能視為已拉直。接近直線的暫定比較條件為最大偏差≤10 mm、最大切線誤差≤5°、沿軸投影≥各自名義長度95%，再另檢查應變及局部穩定。原475 mm投影門檻沒有錯套到不同長度上。

![主動張力形狀](results/active_front_shapes.png)

![錨點與應變比較](results/anchor_layout_comparison.png)

### 入箱路徑

對18個代表狀態，保持各自**主動張力平衡形狀**沿斜軸平移。起點接口s=−名義前端長度−150 mm，確認頭部及前端在箱外；不是從頭部已入箱的位置開始。路徑先4 mm初查，存在最終全前端入腔位置時再以2 mm重查。間隙下界另外扣除半個平移步長，利用剛性平移下距離函數的1-Lipschitz性處理步間漏查。

下列四個前端路徑在16單元/節重查仍通過保存截面的5 mm間隙篩選：

{path_zh}

所有通過案例都超過5%應變診斷。低應變代表的固定主動形狀未找到通過路徑；尚未優化「隨深度改變張力及形狀」的完整避障軌跡，因此不能說所有主動部署方式都失敗。

**這是前端移動夾持基座的幾何路徑，不是完整伸縮機構驗證。** 計算允許接口在原箱外導向基準後方，沒有虛構套管接觸支承；尚未解決前端在後端套管中的存放、導向基準穿越、拉索收放與完整收回。保存的五個寬度截面628/632/648/664/668 mm也不足以覆蓋63 mm前端的616.5–679.5 mm全寬，仍非全三維通過結論。

![前端入箱路徑](results/front_only_entry_screen.png)

### 後端及主要限制

以新前端質量及實際平衡形狀計算重力反力和力矩，重算原40/30 mm分段鋁梁及單30 mm梁在0.6/1.0 m外露長度的參考響應，見`rear_reference.csv`。這些管體是原有支撐梁對照，不能容納63 mm前端，不能作為新套管選型結論。尚未耦合接頭間隙、重疊質量、拉索/驅動局部載荷及基座柔度。

M的EA只有166.694 N，在5%線性應變下對應約8.33 N軸向力。作為直線姿態的量級估算，三組M段根部頭部及模組重力彎矩除以24 mm力臂，對應約38.64/59.28/80.81 N。這不是實際平衡張力或強度極限，但說明M段軸向承載與抗彎要求之間的矛盾。優先研究U4+M2，縮短M的無支撐長度、增加M的軸向承載路徑，或加入實際插入支撐。NiTi本構非線性、列印材料、接觸、屈曲及疲勞未由本輪線性EA/EI模型驗證。

![後端重力參考](results/rear_gravity_reference.png)

### 數值檢查與文件

- 單組掃描{summary['single_sweep_attempts']}次，{summary['single_sweep_equilibria']}個平衡；局部優化{summary['local_optimizer_attempts']}次；保存{summary['fine_best_records']}個8單元/節候選及9個自然下垂對照。
- 能量梯度、Hessian向量及控制導數已檢查，等張力軸向壓縮與獨立解析式一致。數值檢查是實作檢查，並非材料校準。
- 4→8單元/節最大頭部變化{summary['maximum_mesh_tip_change_mm']:.3f} mm，不能忽略；對{summary['mesh_8_to_16_checked']}個主要或敏感案例再做8→16加密，最大變化{summary['mesh_8_to_16_maximum_tip_change_mm']:.3f} mm。所選低應變代表最大變化{low_mesh:.3f} mm。已檢查案例的5%及近直線分類未改變，但靠近門檻的值仍對網格敏感。
- 舊CAD參考間隙重現誤差小於1e-6 mm；新增程式沒有安裝大型CAD依賴，也沒有複製STEP。
- 主要數據：`results/comparison_20deg.csv`、`all_equilibria.csv`、`refined_equilibria.json`、`summary.json`、`front_only_path_screen.json`、`refined_passing_path_checks.json`。

## English

### Findings

Active tendon tension is allowed during insertion. Passive sag is only a reference and is not imposed as the entry shape. U4+M2 is the most promising of the three tested lengths. At 20 degrees, anchors [4,5,6] give a 16-cell solution with {shape[0]['maximum_axis_deviation_mm']:.2f} mm maximum axis offset and {shape[0]['maximum_tangent_error_deg']:.2f} degrees maximum tangent error, but {100*shape[0]['max_abs_axial_strain']:.2f}% maximum axial strain in M. Shape improvement does not establish physical load capability.

No saved solution simultaneously passes the provisional straightness checks, the 5% strain diagnostic and local stability. These are finite searches and local optima, not a proof of global infeasibility. The 5% value is not a measured allowable or failure strain.

### Inputs and configurations

The database is opened read only. Its original values are retained without diameter scaling: U is PA12+NiTi, length 96 mm, mass 37.990 g, EA 128122 N, vertical EI 22.2052 N m² and horizontal EI 1.67184 N m². M is PA12, length 96 mm, mass 23.948 g, EA 166.694 N and EI 0.0441178 N m² in all directions. The database GJ entries 4.70037 and 0.437396 N m/rad are whole-module torsional spring stiffnesses T/theta. Torsion is not exercised in this planar study; no extra metal backbone is added to the U properties.

| Configuration | Flexible length mm | Including 20 mm interface mm | Bare module mass g |
|---|---:|---:|---:|
{size_rows}

All modules have 63 mm outer diameter and 24 mm tendon guide radius. U is proximal and its stiff bending plane opposes gravity. A 500 g point head and massless 20 mm rigid interface are assumed. The provisional head envelope is also 63 mm; actual head CAD and eccentricity are unknown. The requested counts retain their 96 mm lengths and do not produce a 0.5 m front. Both U and M length and mass increase across the configurations.

Each anchor set has four 2 mm ropes with the prior solid PA6 proxy properties, friction omitted. Every tendon runs from the base through real module guides to its own anchor; distal tendons still compress proximal modules. Rope mass is counted along each routed portion; new anchor hardware, sheaths, wiring and interface mass are not measured. Four existing holes do not establish space for multiple sets.

Layouts are head-only [N], two sets [U,N], original three sets [U/2,U,N], and a supplementary three-set layout [U,U+floor(M/2),N]. The supplementary layout remains three sets and tests an anchor inside M. Pitches are 15, 20 and 25 degrees. Single-anchor extra upper tension is sampled from 0 to 200 N with 0 or 2 N common tension per rope. Optimization bounds each upper set at 250 N; these are numerical bounds, not hardware ratings. Several results reach the bound.

### Representative results at 20 degrees

Candidates are selected among locally stable states passing the preliminary centreline, nonlocal 63 mm capsule and local radius-curvature checks. The selection score combines axis offset and projection loss. These representatives are re-solved at unchanged tensions with 16 cells per module, not re-optimized globally.

**Shape objective with larger strain permitted**

{shape_en}

The U8+M4 three-set M-anchor alternative reaches about 74.49 mm offset and 30.17% strain at eight cells per module, but fails the local radius-curvature envelope screen and is excluded from the geometric candidate table.

**Candidates near the 5% strain diagnostic bound**

{low_en}

The provisional straightness checks are offset at most 10 mm, tangent error at most 5 degrees, and projection at least 95% of each configuration's nominal length. The old fixed 475 mm threshold is not applied to the new lengths. Large-strain results extrapolate constant EA/EI and do not model material transformation, damage, local buckling or fatigue.

### Front-only entry screening

Eighteen selected actively tensioned shapes are translated along the installation axis, starting with the head and front outside the tank. The start interface is s = minus nominal front length minus 150 mm. Four millimetre searches locate final placements; possible complete front sweeps are rechecked at 2 mm. A half-step clearance deduction provides a conservative continuous-translation lower bound for the sampled section polygons.

The following four front-only sweeps remain clear when rechecked at 16 cells per module:

{path_en}

All four exceed the 5% strain diagnostic. No selected low-strain fixed-shape sweep passes. A trajectory that changes tendon tensions and equilibrium shape with depth has not been optimized; failed fixed-shape sweeps do not prove that all active deployment paths fail.

This is a translating-front-clamp screen, not a completed telescopic mechanism. The front base may move behind the previous front guide; tube storage, crossing the guide, sheath support/contact, rope take-up and complete retraction remain unvalidated. Five saved width planes at 628/632/648/664/668 mm do not cover the full 616.5 to 679.5 mm band of a 63 mm front. Neither complete width clearance nor full 3D installation is established.

### Rear reference and engineering implication

New front gravity reactions and moments are applied to the original ideal 40/30 mm aluminium beam and single 30 mm beam at 0.6 and 1.0 m exposure. These supporting beams cannot store a 63 mm front and are not a new sheath design. Joint compliance, overlap mass, local tendon/drive reactions, buckling and anchorage are excluded.

M has only 166.694 N axial rigidity: 5% linear strain corresponds to 8.33 N. For scale, the straight M-root moment from the head and M self weight divided by the 24 mm tendon arm is approximately 38.64, 59.28 and 80.81 N. This is not a solved tendon tension or a failure threshold, but indicates why improving U alone does not resolve M compression. Prioritize U4+M2 and investigate shorter unsupported M length, a distinct axial load path or a real insertion support.

### Verification and reproduction

The study contains {summary['single_sweep_attempts']} single-anchor attempts ({summary['single_sweep_equilibria']} equilibria), {summary['local_optimizer_attempts']} local optimization attempts, {summary['fine_best_records']} eight-cell candidates and nine natural baselines. Energy, Hessian-vector and control derivatives and an independent axial load case are checked. Four-to-eight-cell head changes reach {summary['maximum_mesh_tip_change_mm']:.3f} mm; {summary['mesh_8_to_16_checked']} selected or sensitive cases receive eight-to-sixteen-cell checks, reaching {summary['mesh_8_to_16_maximum_tip_change_mm']:.3f} mm maximum change ({low_mesh:.3f} mm for selected low-strain cases). Checked strain and straightness classifications remain unchanged; near-threshold values are still mesh-sensitive. These checks verify implementation consistency, not physical calibration.

The database snapshot is `module_stiffness_input.sqlite3`. SHA256: `{DATA['database_sha256']}`. Run from the project root with an existing NumPy/SciPy/Matplotlib environment. No CAD runtime installation is needed for these saved-section checks. To reproduce the frozen input in PowerShell:

```powershell
$env:ASRC_STIFFNESS_DB = (Resolve-Path 'simulations/u4m2/stiffness_63mm_20261106/module_stiffness_input.sqlite3').Path
python simulations/u4m2/stiffness_63mm_20261106/run_study.py validate
python simulations/u4m2/stiffness_63mm_20261106/run_study.py mechanics --u 4 --m 2
python simulations/u4m2/stiffness_63mm_20261106/run_study.py mechanics --u 6 --m 3
python simulations/u4m2/stiffness_63mm_20261106/run_study.py mechanics --u 8 --m 4
python simulations/u4m2/stiffness_63mm_20261106/postprocess.py
python simulations/u4m2/stiffness_63mm_20261106/refine_study.py
python simulations/u4m2/stiffness_63mm_20261106/render_and_document.py
Remove-Item Env:ASRC_STIFFNESS_DB
```

The original project rod kernel, tendon catalogue and saved CAD polygons are read dependencies. Previous simulations and the source database are preserved. Results and figures are in `results`; the README is bilingual and figure text is English. No new large dependencies or STEP copies were created.
'''
    (HERE/'README.md').write_text(readme,encoding='utf-8')
    import sqlite3
    con=sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True);integrity=con.execute('PRAGMA integrity_check').fetchone()[0];con.close()
    manifest=dict(database_integrity=integrity,source_database_unchanged=hashlib.sha256(DB.read_bytes()).hexdigest()==DATA['database_sha256'],
        database_sha256=DATA['database_sha256'],python=sys.version,numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,
        files_sha256={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
        original_kernel_sha256=hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest(),
        figures_english_only=True,readme_bilingual=True)
    assert manifest['source_database_unchanged'] and integrity=='ok'
    dump(OUT/'delivery_validation.json',manifest)
    print('Bilingual README and four English figures created')
    print('Total study bytes',sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file()))

if __name__=='__main__':run()
