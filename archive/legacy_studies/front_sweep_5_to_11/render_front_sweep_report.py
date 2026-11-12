from pathlib import Path
import csv,json,sys,os,hashlib,argparse
import numpy as np
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
import snake_model_front_sweep as W
p=argparse.ArgumentParser()
p.add_argument('--output-dir',type=Path,default=root/'front_sweep_results')
out=p.parse_args().output_dir
report=json.loads((out/'run_summary.json').read_text())
spec=report['config']
def load(name):
    rows=list(csv.DictReader(name.open()))
    for row in rows:
        for key,value in row.items():
            if value in ['True','False']:row[key]=value=='True'
            elif key not in ['combination','module_data_mode']:
                try:row[key]=int(value)
                except ValueError:
                    try:row[key]=float(value)
                    except ValueError:pass
    return rows
summaries=report['fronts']
refs=load(out/'reference_H8_U12_all_front_splits.csv')
fixed=load(out/'all_fixed_N31_combinations.csv')
W.overview(out,summaries,refs,fixed,spec)
for front in range(5,12):
    folder=out/f'front_{front:02d}'
    comparison=json.loads((folder/'reference_comparison.json').read_text())
    ref=comparison['with_backbone']
    counts=[ref[k] for k in ['n_high','n_uni','n_directional','n_low']]
    shapes=[]
    for name in ['reference_with_backbone','reference_without_backbone']:
        rows=load(folder/f'{name}_shape.csv')
        xy=np.array([[r['x_mm'],r['y_mm']] for r in rows])
        shapes.append((xy,int(sum(counts[:2])*16)))
    W.plot_front(folder,front,load(folder/'combinations.csv'),load(folder/'fixed_N31.csv'),
                 load(folder/'pareto_N31_reference_yield_only.csv'),counts,*shapes,300)

plt=W.plotting()
fig,ax=plt.subplots(figsize=(10,5.8),layout='constrained')
for front in range(5,12):
    y=[r['tip_drop_mm'] for r in refs if r['front_modules']==front]
    ax.vlines(front,min(y),max(y),color=W.BLUE,lw=2)
    ax.scatter([front]*len(y),y,color=W.BLUE,s=28,alpha=.65)
    ax.text(front,max(y)+14,f'{min(y):.0f}–{max(y):.0f}',ha='center',fontsize=10,color=W.BLUE)
ax.axhline(300,color=W.GRAY,ls=':',lw=1.5,label='Effective inspection height: 300 mm')
ax.axhline(268,color=W.GRAY,ls='--',lw=1.5,label='268 mm + 32 mm diameter = 300 mm')
ax.set(xlabel='Flexible front modules (48 mm each)',ylabel='Head drop from clamp (mm)',
       title='Head drop vs flexible front length',xticks=range(5,12),xlim=(4.6,11.4),ylim=(0,650))
ax.legend(frameon=False,loc='upper left',fontsize=9);ax.grid(axis='y',alpha=.15)
fig.supxlabel('Rear fixed at H8 + U12 = 960 mm. Ranges cover all directional/low splits; total length varies.\n'
              'Original module EI/masses | rear-only 4.2 mm SS304 | self weight only, no payload or contact',fontsize=9)
fig.savefig(out/'head_drop_vs_front_modules.png',dpi=180);plt.close(fig)

fig,ax=plt.subplots(figsize=(11,6),layout='constrained')
colors=plt.cm.Blues(np.linspace(.45,.95,7))
ax.axhspan(-268,0,color='#e8edf0',label='300 mm height / 32 mm capsule centreline range')
for front,color in zip(range(5,12),colors):
    xy=np.array([[r['x_mm'],r['y_mm']] for r in load(out/f'front_{front:02d}/reference_with_backbone_shape.csv')])
    ax.plot(xy[:,0],xy[:,1],color=color,lw=1.8)
    ax.plot(*xy[320],'s',color=color,ms=4)
    ax.plot(*xy[-1],'o',color=color,ms=4)
    r=next(s['reference'] for s in summaries if s['front_modules']==front)
    ax.text(xy[-1,0]+20,xy[-1,1],f"F{front}: D{r['n_directional']}/L{r['n_low']}",color=color,va='center',fontsize=10)
ax.set(xlabel='Horizontal distance from clamp (mm)',ylabel='Height relative to clamp (mm)',
       title='Reference shapes: fixed H8 + U12 rear',xlim=(-40,1460),ylim=(-640,30))
ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15);ax.legend(frameon=False,loc='lower left',fontsize=9)
fig.supxlabel('Squares mark backbone termination. Each labelled D/L split is a reference, not an optimum.\n'
              'Centreline shapes only; no tendons, head payload or wall contact.',fontsize=9)
fig.savefig(out/'reference_shapes_5_to_11.png',dpi=180);plt.close(fig)

def bounds(v,digits=1):return '–'.join(f'{x:.{digits}f}' for x in v)
lines=['5 至 11 節前端完整自重模擬（2026-11-04）','',
       '已完成前端 5、6、7、8、9、10、11 節，每種模組至少一節，排列固定為 high → uni-d → directional → low。',
       '後段 high + uni-d 有 Ø4.2 mm 304 實心圓棒，前段 directional + low 沒有骨架。模組 EI 與質量沿用原論文，未做 PLA 或尺寸換算。','',
       '固定條件：每節 48 mm、外徑 32 mm、根部水平夾持、僅自重。前端長度依序為 240、288、336、384、432、480、528 mm。沒有繩索張力、頭部附件載荷或壁面接觸。',
       '有效檢查區依使用者確認為 1600 × 830 × 300 mm。','',
       '本次保留兩種比較，並分開保存數據：','',
       '- 原程序後段掃描：後段 2–20 節，每種前端節數掃描所有 high/uni-d 與 directional/low 正整數組合，共 9,310 組。',
       '- 固定總長比較：整機 31 節、1488 mm，後段為 31 減去前端節數，共 1,050 組。',
       '- 兩組比較有 190 組重疊；合計 10,170 個不重複配置。H8-U12 固定後段比較是完整掃描的一部分。','',
       '固定後段 H8-U12（960 mm）的比較；範圍涵蓋全部 directional/low 組合：','',
       '| 前端節數 | 前端長 mm | 整機長 mm | 頭部下垂 mm | 水平伸達 mm | 載重平衡附近前端柔順度 deg/(N·mm) |',
       '|---:|---:|---:|---:|---:|---:|']
for s in summaries:
    f=s['front_modules']
    lines.append(f"| {f} | {f*48} | {(f+20)*48} | {bounds(s['fixed_rear_reference_drop_range_mm'])} | {bounds(s['fixed_rear_reference_reach_range_mm'])} | {bounds(s['fixed_rear_reference_compliance_range_deg_per_nmm'],3)} |")
lines += ['', '柔順度為自重平衡附近、施加微小末端彎矩時，前端相對後端的轉角響應。它不等於最大可控彎角、最小轉彎半徑或檢查能力。上下限是組合最小／最大值，不是置信區間或材料誤差界限。','',
       '原後段 2–20 節掃描中的簡化空間與鋼芯參考屈服篩選：','',
       '| 前端節數 | 掃描組合 | 同時通過組合 | 掃描範圍內最長可通過後段 | 通過組合的最大水平伸達 mm |',
       '|---:|---:|---:|---:|---:|']
for s in summaries:
    best=s['max_reach_combined_candidate'];rear=s['maximum_rear_count_with_combined_pass']
    rear_text='無' if rear is None else f'{rear} 節 / {rear*48} mm'
    lines.append(f"| {s['front_modules']} | {s['swept_cases']} | {s['swept_combined_pass_count']} | {rear_text} | {'無' if best is None else format(best['tip_x_mm'],'.1f')} |")
lines += ['', '此處機身以直徑 32 mm 的連續膠囊包絡近似，檢查整體水平、垂直包絡能否放入空的有效檢查區，並假定可選擇最有利垂直位置。這是保守的幾何篩選；沒有核對指定入口、真實內部障礙、碰撞路徑、攝影視場或線圈距離。通過不是任務可行或強度認證。',
          '5 節在此次後段範圍全部通過；6 節在後段 20 節時有部分組合超出高度；7 節的可通過後段最長為 15 節。8–11 節在此次掃描均未通過包絡篩選。20 節是原程序掃描上限，不能據此宣稱是全域最大可行後段。','',
          '固定整機 31 節、1488 mm 的比較：','',
          '| 前端節數 | 後段節數 | 鋼芯應力/參考屈服範圍 | 通過參考屈服／組合總數 | 同時通過空間與參考屈服 |',
          '|---:|---:|---:|---:|---:|']
for s in summaries:
    lines.append(f"| {s['front_modules']} | {31-s['front_modules']} | {bounds(s['fixed_total_reference_yield_ratio_range'],4)} | {s['fixed_total_reference_yield_pass_count']}/{s['fixed_total_cases']} | {s['fixed_total_combined_pass_count']} |")
lines += ['', '固定總長的 1,050 組沒有組合同時通過兩項簡化篩選。參考屈服值為目前材料目錄採用的 205 MPa，並非這根鋼棒的實測值。超過此值的計算只保留作線彈性外推與篩選警示，不視為有效彈性形狀或塑性變形預測。',
          '保留的 N31 Pareto 曲線僅比較水平伸達與微小彎矩柔順度，先排除超過參考屈服者；檔名與圖例均標明 yield-only。另存的 empty-box Pareto 同時要求空箱包絡與參考屈服通過。兩者不可混為已滿足實際檢查需求的最優解。','',
          '結果圖：','',
          '- [下垂與前端節數](head_drop_vs_front_modules.png)',
          '- [伸達、柔順度、下垂與應力總覽](front_5_to_11_overview.png)',
          '- [後段／前段組合空間與參考屈服篩選](rear_front_envelope_screen.png)',
          '- [七種參考形狀](reference_shapes_5_to_11.png)','']
for f in range(5,12):lines.append(f'- [{f} 節前端的四項詳細圖](front_{f:02d}/simulation_summary.png)')
lines += ['', '每個 front_05 至 front_11 資料夾均包含完整組合表、固定總長表、固定 H8-U12 表、兩種 Pareto 表、參考配置有／無骨架形狀座標，以及 summary.json。數值欄位名稱含單位。','',
          '驗證：全部算例收斂；既有 5 項力學單元測試通過。各前端節數均做 8/16/32 cells 網格比較、重力步數加倍、零重力解析柔順度比對，以及獨立連續梁邊值解比對。另對每種節數最接近高度或參考屈服邊界的 14 個算例加密至 64 cells，分類沒有改變。',
          f"16 → 32 cells 的參考下垂最大變化 {max(c['fine_drop_change_mm'] for c in report['validation']['per_front']):.5f} mm；32 cells 與獨立連續解的下垂最大差 {max(c['independent_continuum_drop_error_mm'] for c in report['validation']['per_front']):.5f} mm。與上一輪資料重疊的 4,396 個數值逐項相同。",
          '數值收斂不表示原論文參數已在這個整機上由實物校準。原論文模組包含 PC 柔性元件與 PLA 結構；本次依指示使用原始數據，沒有把它們換成全 PLA 參數。',
          '專案文件中的 0.5 kg 載荷目標沒有當作實際頭部質量加入本次自重算例。實際相機、感應線圈與線材重量仍待提供。','',
          '主要資料：[彙總 CSV](front_count_summary.csv)、[原後段掃描 CSV](all_rear_sweep_combinations.csv)、[固定 N31 CSV](all_fixed_N31_combinations.csv)、[數值驗證](validation.json)、[邊界加密與舊結果比對](boundary_and_prior_result_checks.json)。']
(out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
(root/'README_front_sweep.md').write_text('5 至 11 節前端自重模擬\n\n'
    '本資料夾包含 Python 程式、獨立配置檔、原模型輸入快照及完整結果。原正式 11 節配置未被修改。\n\n'
    '以 NumPy、SciPy、Matplotlib 執行：\n\n```sh\npython snake_model_front_sweep.py\npython verify_front_sweep_results.py\npython render_front_sweep_report.py\n```\n\n'
    '預設讀取 inputs/ 的原模型快照，結果寫入 front_sweep_results/。亦可用 --project 指定含原求解器的專案資料夾；--output-dir 可指定另一輸出位置。\n\n'
    'study 配置位於 front_sweep_config.json；原模組與鋼棒參數仍讀取 rear_backbone_config.json、craft_data.py 與 rope_materials.json，沒有材料或尺寸縮放。\n\n'
    '[查看完整結果與限制](front_sweep_results/RESULTS.md)\n')
print(out/'RESULTS.md')
