import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/asrc_four_rope_mpl')
os.environ.setdefault('XDG_CACHE_HOME','/private/tmp/asrc_four_rope_cache')
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,csv,json,collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from rope_planar import PlanarRod,HERE
from run_rope_sweep import BASE_FIELDS,write_json,jsonable,SETTINGS

COLORS=['#34678f','#bc6c2d','#748145']
LIST_FIELDS=['rope_path_lengths_mm','rope_strains','take_up_mm','slack_ropes']

def read_rows(path):
    rows=list(csv.DictReader(path.open()))
    for r in rows:
        for k,v in r.items():
            if v=='':r[k]=None
            elif v in ['True','False']:r[k]=v=='True'
            elif k in LIST_FIELDS:r[k]=json.loads(v)
            else:
                try:r[k]=int(v)
                except ValueError:
                    try:r[k]=float(v)
                    except ValueError:pass
    return rows

def write_csv(path,rows,fields=None):
    fields=fields or (list(rows[0]) if rows else BASE_FIELDS)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in r.items()})

def screened(r):
    return bool(r['target_reached'] and r['stable_in_plane'] and r['passes_self_envelope_screen']
                and r['passes_reference_yield'] and r['passes_empty_box'])

def state_for(row,output):
    f,r=row['front_modules'],row['rear_modules'];d=row['n_directional'];h=row['n_high']
    i=((h-1)*(f-1)+(d-1))*3+{'head_level':0,'front_semicircle_up':1,'front_semicircle_down':2}[row['target']]
    groupdir=output/'final_groups' if (output/'final_groups').is_dir() else output/'groups'
    z=np.load(groupdir/f'F{f:02d}_R{r:02d}_states.npz')
    x=z['state'][i]
    if not np.isfinite(x).all():return None,None
    rod=PlanarRod((h,r-h,d,f-d),int(row['cells_per_module']))
    return rod,rod.evaluate(x,detail=True)[3]

def number(v):return '未找到' if v is None else f'{v:.3f}'

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=HERE/'results');a=p.parse_args();out=a.output_dir
    rows=read_rows(out/'all_targets.csv')
    keys={(r['combination'],r['target']) for r in rows}
    assert len(rows)==30510 and len(keys)==30510
    assert sum(r['target']=='head_level' for r in rows)==10170
    assert not any(r['status']=='numeric_exception' for r in rows)
    refs=[]
    for f in range(5,12):
        d=round(f*8/11)
        refs.extend(r for r in rows if r['n_high']==8 and r['n_uni']==12 and r['n_directional']==d and r['front_modules']==f)
    assert len(refs)==21
    write_csv(out/'reference_H8_U12.csv',refs)
    write_csv(out/'head_level_all_configurations.csv',[r for r in rows if r['target']=='head_level'])
    write_csv(out/'semicircle_targets_and_angle_diagnostics.csv',[r for r in rows if r['target']!='head_level'])
    summary=[]
    for f in range(5,12):
        rr=[r for r in rows if r['front_modules']==f];level=[r for r in rr if r['target']=='head_level']
        up=[r for r in rr if r['target']=='front_semicircle_up' and r['head_x_mm'] is not None]
        down=[r for r in rr if r['target']=='front_semicircle_down' and r['head_x_mm'] is not None]
        s=dict(front_modules=f,front_nominal_length_mm=f*48,unique_configurations=len(level),
            level_equilibria_found=sum(r['target_reached'] for r in level),
            level_screened_candidates=sum(screened(r) for r in level),
            level_large_axial_strain=sum(r['target_reached'] and bool(r['axial_strain_exceeds_5_percent']) for r in level),
            fixed_N31_level_found=sum(r['target_reached'] and r['comparison_fixed_N31'] for r in level),
            semicircle_up_found=sum(r['target_reached'] for r in up),semicircle_down_found=sum(r['target_reached'] for r in down),
            best_searched_up_arc_error_mm=min((r['semicircle_max_error_mm'] for r in up),default=None),
            best_searched_down_arc_error_mm=min((r['semicircle_max_error_mm'] for r in down),default=None))
        summary.append(s)
        write_csv(out/f'front_{f:02d}_all_targets.csv',rr)
    write_csv(out/'front_count_summary.csv',summary)
    write_json(out/'study_summary.json',dict(unique_configurations=10170,target_rows=len(rows),fronts=summary,
        reference_cases=refs,minimum_claim=SETTINGS['minimum_claim'],
        target_not_found_is_not_global_infeasibility_proof=True,
        plane='vertical symmetry plane; side tensions equal; independent twist/spatial instability not tested'))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(13,5.4),layout='constrained')
    lev=[next(r for r in refs if r['front_modules']==f and r['target']=='head_level') for f in range(5,12)]
    axs[0].plot(range(5,12),[r['target_total_tension_n'] if r['target_reached'] else np.nan for r in lev],
                color=COLORS[0],marker='o',label='Lowest total tension found')
    for f,r in zip(range(5,12),lev):
        if r['target_reached']:axs[0].annotate(f"{r['target_total_tension_n']:.3f}",(f,r['target_total_tension_n']),xytext=(0,8),textcoords='offset points',ha='center',fontsize=10)
    if any(not r['target_reached'] for r in lev):
        axs[0].text(.97,.15,'Missing points: no level solution found\nin the documented search',transform=axs[0].transAxes,ha='right',fontsize=9,color='#555555')
    axs[0].set(xlabel='Flexible front modules',ylabel='Tension (N)',title='Head level with root; no lateral offset',xticks=range(5,12),xlim=(4.5,11.5),ylim=(0,3.5))
    axs[0].legend(frameon=False,loc='upper left',fontsize=9)
    for target,color,marker,label in [('front_semicircle_up',COLORS[1],'o','Upward 180-degree equilibrium'),
                                       ('front_semicircle_down',COLORS[2],'^','Downward 180-degree equilibrium')]:
        rr=[next(r for r in refs if r['front_modules']==f and r['target']==target) for f in range(5,12)]
        axs[1].plot(range(5,12),[r['semicircle_max_error_mm'] for r in rr],color=color,marker=marker,label=label)
    axs[1].axhline(1,color='#555555',ls='--',label='Required semicircle error: <= 1 mm')
    axs[1].set(xlabel='Flexible front modules',ylabel='Maximum centreline error from semicircle (mm)',
                title='180 degrees of turning does not ensure a semicircle',xticks=range(5,12),yscale='log',ylim=(.7,800))
    axs[1].legend(frameon=False,fontsize=8,loc='upper left')
    for ax in axs:ax.grid(alpha=.15)
    fig.suptitle('Reference rear H8 + U12 (960 mm): four-tendon inverse statics',fontsize=15)
    fig.supxlabel('Original module EI/EA/masses | rear-only 4.2 mm SS304 | 2 mm ropes at 13 mm radius | self weight only\n'
                  'Symmetry-plane search, zero pretension. Circle failures are diagnostics, not successful semicircle tensions.',fontsize=9)
    fig.savefig(out/'reference_force_and_circle_error.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    for target,col,lab in [('front_semicircle_up',COLORS[1],'Total tension: upward turning'),('front_semicircle_down',COLORS[2],'Total tension: downward turning')]:
        rr=[next(r for r in refs if r['front_modules']==f and r['target']==target) for f in range(5,12)]
        ax.plot(range(5,12),[r['diagnostic_total_tension_n'] if not r['target_reached'] else r['target_total_tension_n'] for r in rr],color=col,marker='o',label=lab)
    ax.set(xlabel='Flexible front modules',ylabel='Tension (N)',title='180-degree angle diagnostics — semicircle shape target not met',xticks=range(5,12),ylim=(0,None))
    ax.legend(frameon=False);ax.grid(alpha=.15)
    fig.supxlabel('H8/U12 rear. These are free-equilibrium angle diagnostics; do not use them as successful semicircle solutions.',fontsize=9)
    fig.savefig(out/'reference_180_angle_diagnostic_forces.png',dpi=180);plt.close(fig)
    for f in range(5,12):
        fig,ax=plt.subplots(figsize=(12,5),layout='constrained')
        d=round(f*8/11)
        for name,col,label in [('head_level',COLORS[0],'Head level'),('front_semicircle_up',COLORS[1],'Upward 180-degree diagnostic'),
                               ('front_semicircle_down',COLORS[2],'Downward 180-degree diagnostic')]:
            r=next(r for r in refs if r['front_modules']==f and r['target']==name)
            rod,data=state_for(r,out)
            if data is None:continue
            coordinates=out/'coordinates';coordinates.mkdir(exist_ok=True)
            with (coordinates/f"{r['combination']}_{name}.csv").open('w',newline='') as stream:
                w=csv.writer(stream)
                w.writerow(['node','reference_s_mm','x_mm','y_mm','z_mm','pitch_deg','is_actual_disk','target_reached'])
                for i,(point,angle) in enumerate(zip(data['points'],data['theta'])):
                    w.writerow([i,i*rod.l*1000,point[0]*1000,point[1]*1000,0,np.degrees(angle),i%rod.sub==0,r['target_reached']])
            xy=data['points']*1000;ax.plot(xy[:,0],xy[:,1],color=col,lw=2,label=label)
            ax.plot(*xy[-1],'o',color=col,ms=4);ax.plot(*xy[rod.b],'s',color=col,ms=4)
            if name!='head_level':
                sense=1 if name.endswith('_up') else -1
                length=r['front_current_length_mm'];t=np.linspace(0,np.pi,100)
                local=length/np.pi*np.c_[np.sin(t),sense*(1-np.cos(t))]
                angle=np.radians(r['rear_angle_deg']);rot=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]])
                ideal=local@rot+xy[rod.b]
                ax.plot(ideal[:,0],ideal[:,1],ls='--',lw=1.2,color=col,label='Required semicircle '+('up' if sense>0 else 'down'))
        ax.plot(0,0,'ks',ms=5);ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15)
        ax.set(xlabel='Horizontal distance from root (mm)',ylabel='Height relative to root (mm)',
               title=f'Front {f} modules: H8 / U12 / D{d} / L{f-d}')
        ax.legend(frameon=False,fontsize=8,loc='lower left')
        fig.supxlabel('Solid: actual free-equilibrium shape. Dashed: requested semicircle from the actual rear/front interface.\n'
                      'The rear is allowed to bend. A missing level curve means no solution was found for that reference case.',fontsize=9)
        fig.savefig(out/f'front_{f:02d}_reference_shapes.png',dpi=180);plt.close(fig)
    # Per-front composition curves include every H/U split. Each faint marker
    # is one composition; the median summarises, rather than replacing, them.
    for f in range(5,12):
        panels=(f-1+2)//3
        fig,axs=plt.subplots(panels,3,figsize=(15,3.3*panels),layout='constrained',squeeze=False)
        for d,ax in zip(range(1,f),axs.flat):
            subset=[r for r in rows if r['target']=='head_level' and r['front_modules']==f and r['n_directional']==d]
            found=[r for r in subset if r['target_reached']]
            ax.scatter([r['rear_modules'] for r in found],[r['target_total_tension_n'] for r in found],
                       s=13,alpha=.24,color=COLORS[0],edgecolors='none')
            rears=sorted({r['rear_modules'] for r in subset})
            for rear in rears:
                selected=[r for r in found if r['rear_modules']==rear]
                if selected:
                    ax.plot(rear,np.median([r['target_total_tension_n'] for r in selected]),'_',ms=12,color='#142b3c')
            missing=len(subset)-len(found)
            ax.set(title=f'D{d} / L{f-d} | found {len(found)}/{len(subset)}',xlabel='Rear modules H + U',ylabel='Total tension (N)',ylim=(0,None),xlim=(1.5,max(rears)+.5))
            ax.grid(alpha=.15)
        for ax in list(axs.flat)[f-1:]:ax.set_visible(False)
        fig.suptitle(f'Front {f} modules: head-level tension for every enumerated H/U composition',fontsize=14)
        fig.supxlabel('Dots: individual H/U splits; dark ticks: median for each rear count. Missing solutions are omitted, never set to zero.\n'
                      'These are mathematical target equilibria. Check stability, envelope, core stress and axial-strain flags in the CSV.',fontsize=9)
        fig.savefig(out/f'front_{f:02d}_configuration_tensions.png',dpi=180);plt.close(fig)
    grid=np.zeros((7,19));safe=np.zeros_like(grid)
    for f in range(5,12):
        for rear in range(2,21):
            group=[r for r in rows if r['target']=='head_level' and r['front_modules']==f and r['rear_modules']==rear]
            grid[f-5,rear-2]=sum(r['target_reached'] for r in group)/len(group)
            safe[f-5,rear-2]=sum(screened(r) for r in group)/len(group)
    fig,axs=plt.subplots(2,1,figsize=(15,7.2),layout='constrained')
    for ax,data,title in zip(axs,[grid,safe],['Head-level target equilibria found','Head-level candidates passing planar stability, self-envelope, box and core reference yield']):
        im=ax.imshow(data,origin='lower',aspect='auto',vmin=0,vmax=1,cmap='cividis',extent=(1.5,20.5,4.5,11.5))
        ax.set(xlabel='Rear modules (48 mm each)',ylabel='Front modules',title=title,xticks=range(2,21),yticks=range(5,12))
        cb=fig.colorbar(im,ax=ax,pad=.015);cb.ax.yaxis.set_major_formatter(PercentFormatter(1));cb.set_label('Fraction of enumerated configurations')
    fig.supxlabel('All positive H/U and D/L splits. This is a finite planar search, not a global feasibility proof.\n'
                  '5% axial compression is reported separately; material nonlinearity, actual tank openings and spatial stability remain uncalibrated.',fontsize=9)
    fig.savefig(out/'head_level_configuration_map.png',dpi=180);plt.close(fig)
    lines=['四繩逆靜力計算結果（2026-11-04）','',
      '完成前端 5–11 節、10,170 個不重複配置；每配置計算頭尾同高、前端向上半圓、前端向下半圓三項目標，共 30,510 列。',
      f"本次找到 {sum(s['level_equilibria_found'] for s in summary):,} 個頭尾同高平衡解，其中 {sum(s['level_screened_candidates'] for s in summary):,} 個通過空箱、自包絡、平面穩定與鋼芯參考屈服篩選；較大軸向應變仍須另查。固定總長31節（1488 mm）的組合均未找到同高解。11節前端沒有組合同時通過上述四項篩選。這些都是本次有限平面搜尋的結果，未證明全域無解。",'',
      '四繩順序為上／右／下／左。模組原論文 EI、EA 與質量不做材料換算；後段 Ø4.2 mm 304 實心圓棒，前段沒有骨架；四條 Ø2 mm 尼龍繩沿真實端盤 13 mm 半徑導孔走線，均錨定於頭部。僅自重，包含繩索原長質量，附件載荷 0。','',
      '頭尾同高目標只要求末端與固定根部的高度、側向坐標相同，並非整機伸直，也沒有最低前伸比例。四根繩皆可鬆弛；搜尋以總非負張力最小為目標，輸出是記錄範圍內找到的最低值，不宣稱已證明所有空間姿態的全域最小。','',
      '半圓目標同時檢查前端相對轉角 180°（容許 1°）及與要求圓弧的最大中心線偏差 ≤1 mm。未通過圓弧誤差者，目標張力欄留空，另存角度 180° 的診斷拉力。不存在強制形狀的外加支撐反力。','',
      '固定 H8-U12 後段（960 mm）的代表配置：','',
      '| 前端 | D/L | 頭尾同高：上/右/下/左 N | 180°向上診斷：上/右/下/左 N | 180°向下診斷：上/右/下/左 N | 向上/下圓弧最大誤差 mm |',
      '|---:|---:|---|---|---|---|']
    for f in range(5,12):
        rr={r['target']:r for r in refs if r['front_modules']==f};l=rr['head_level'];u=rr['front_semicircle_up'];dn=rr['front_semicircle_down']
        tension='未找到解' if not l['target_reached'] else ' / '.join(number(l[f'target_tension_{s}_n']) for s in ['top','right','bottom','left'])
        forces=lambda row:' / '.join(number(row[f'diagnostic_tension_{s}_n']) for s in ['top','right','bottom','left'])
        lines.append(f"| {f} | {round(f*8/11)}/{f-round(f*8/11)} | {tension} | {forces(u)} | {forces(dn)} | {u['semicircle_max_error_mm']:.2f} / {dn['semicircle_max_error_mm']:.2f} |")
    circles=sum(r['target_reached'] for r in rows if r['target']!='head_level')
    best_arc=min(r['semicircle_max_error_mm'] for r in rows if r['target']!='head_level' and r['semicircle_max_error_mm'] is not None)
    lines += ['',f'整體搜尋找到符合半圓誤差的狀態共 {circles} 個；最佳已找到的圓弧最大偏差為 {best_arc:.3f} mm，仍大於1 mm。上表兩個 180° 欄位是角度診斷，不能解讀為已形成半圓。',
      '由於零預緊、垂直平面對稱且目標採最低總張力，代表同高解通常只需上繩，其他繩可以是 0 N。上表的同高欄先列數學平衡解，適用性須另查空箱、自包絡、平面穩定與鋼芯參考屈服旗標。若加入共同收緊力，上下／左右分配可能有多解；本模型保存其中一組非負分配。','',
      '| 前端 | 配置總數 | 找到同高解 | 通過空箱/自包絡/平面穩定/鋼芯參考屈服 | 同高解軸向壓縮超過5% | 固定N31找到同高解 |',
      '|---:|---:|---:|---:|---:|---:|']
    for s in summary:lines.append('| '+' | '.join(str(s[k]) for k in ['front_modules','unique_configurations','level_equilibria_found','level_screened_candidates','level_large_axial_strain','fixed_N31_level_found'])+' |')
    lines += ['', '重要的解讀範圍：','',
      '- 四繩張力在無摩擦路徑中各自保持一致。模型使用實際端盤之間的直線繩段，網格加密不會增加虛構導孔。',
      '- 以垂直對稱平面求解，右左張力相等；平面外彎曲、獨立扭轉及空間失穩沒有驗證。因此不宣稱完整三維全域最優或三維穩定。',
      '- 主要搜尋使用有符號上下差值 D 及左右共同張力 S；另外對所有配置補查上下共同對拉 A 與混合對拉。四繩分配為 [max(D,0)+A/2, S/2, max(-D,0)+A/2, S/2]。實際導孔直線繩段的上下共同模式與左右共同模式不假定等價；A、S 採有限網格，未對所有可能值作全域證明。缺失同高解再以相鄰已收斂配置延續重試，最終都重新滿足自身參數的平衡。',
      '- uni-d 和 directional 使用原表的 Y 向 EI；原表沒有獨立的負 Y 測值，向上／向下沿用同一 Y 向數值是對稱性假設。',
      '- 模組軸向壓縮使用原論文線性 EA。超過 5% 只是明確標示較大應變外推，5% 並非實測允許變形或破壞界限；這些列仍保留數學計算值，不能據此認證實物能力。',
      '- 繩索 PA6 的 E、密度是既有實心材料代理值，並非實際編織繩的有效參數。繩索自重按原長均勻轉移至機身，不求鬆繩懸垂曲線。零張力繩選擇額外放出1 mm作為一組鬆弛指令；該指令不是唯一值。',
      '- 鋼芯應力包含軸向及彎曲，以 205 MPa 目錄參考值篩選，並非實際鋼棒實測屈服。超過參考值不作有效線彈性設計。',
      '- 空間檢查為實際形狀加32 mm膠囊包絡能否放入1600×830×300 mm空箱，並檢查保守自包絡干涉；不包含實際入口、油箱障礙及接觸力。',
      '- 未找到同高解只代表此次分支與有限範圍搜尋沒有得到解，不是全域無解證明。角度診斷達180°亦不代表半圓目標達成。','',
      '數值檢查：能量一階／二階導數、頭部位置雅可比、繩索虛功、真實導孔數量、零張力極限、原模組參數與後段骨架質量、固定繩長回代均有獨立檢查。主要搜尋使用4 cells/module，保存結果再加密至8；補查與延續在8進行。最終所有已保存狀態均重新檢查平衡殘差、非負張力、固定繩長回代及目標標記；21個代表目標中的已找到狀態另加密至16。數值與加密誤差保存在 [最終數值檢查](final_numerical_audit.json)。','',
      '檔案：','',
      '- [全部目標與狀態 CSV](all_targets.csv)',
      '- [同高目標所有配置](head_level_all_configurations.csv)',
      '- [半圓目標與180°診斷](semicircle_targets_and_angle_diagnostics.csv)',
      '- [H8-U12參考四繩張力](reference_H8_U12.csv)',
      '- [前端節數彙總](front_count_summary.csv)',
      '- [同高拉力與半圓誤差比較圖](reference_force_and_circle_error.png)',
      '- [180°轉角診斷力圖](reference_180_angle_diagnostic_forces.png)',
      '- [完整後段組合圖](head_level_configuration_map.png)','']
    for f in range(5,12):
        lines.append(f'- [{f}節參考形狀](front_{f:02d}_reference_shapes.png)、[{f}節所有配置的同高張力](front_{f:02d}_configuration_tensions.png)')
    lines += ['', 'final_groups/ 保存每個前端／後段組合的最終CSV及8 cells/module角度／軸向應變狀態NPZ，可重建逐組形狀。groups/ 是主要搜尋與鄰近配置延續的中間資料；opposing_pair_trials/ 保存上下對拉與混合對拉補查。失敗列對應NaN，不能當作零張力成功解。',
      '欄位 target_tension_* 僅在目標達成時填入；diagnostic_tension_* 是半圓未達標時的180°診斷。是否通過鋼芯、空間和穩定性請同時檢查相關旗標。',
      '方法參考：[Li 等（2022）幾何非線性索驅連續體模型](https://yuan.mae.sustech.edu.cn/pdf/2022Li-acta-mechanics.pdf)。原論文性質仍是 PC 柔性元件與 PLA 結構，依指示未換成全PLA參數。']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    (HERE/'README.md').write_text('四繩逆靜力模擬：前端5–11節\n\n'
      '執行環境：Python、NumPy、SciPy、Matplotlib。原數據快照在 inputs/；原工程模型與結果均保留。\n\n'
      '```sh\npython run_all.py --workers 4\n```\n\n'
      '依序執行獨立單元檢查、主要掃描、上下共同對拉補查、相鄰配置延續重試、最終合併、全部狀態核對與代表案例加密、圖表輸出。已保存的組別會重用。\n\n'
      'run_rope_sweep.py 支援 --front、--rear、--workers、--output-dir；同一數據與程式雜湊的已完成組合會重用。完整圖表需預設10,170配置全部完成。\n\n'
      'rope_planar.py 是幾何非線性、可軸向壓縮的平面有限元與四繩靜力核心；rope_three_parameter.py 補上獨立上下共同對拉模式；run_rope_sweep.py 包含主要逆解與目標判斷。\n\n'
      '匯出單一組合的中心線座標，例如：python export_case.py H8-U12-D4-L1 head_level。\n\n'
      '[完整結果、張力表與限制](results/RESULTS.md)；[模型方程與方法](METHODS.md)。\n')
    print(json.dumps(dict(rows=len(rows),configurations=10170,semicircle_targets_found=circles,summary=summary),default=jsonable),flush=True)

if __name__=='__main__':main()
