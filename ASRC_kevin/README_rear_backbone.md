# 後段 304 backbone＋固定 11 節靈活前端

按已確認設定：**後段加入 Ø4.2 mm 實心 304 不鏽鋼 backbone，前端固定 11 節、528 mm，前端沒有 backbone**。沒有繩索及末端額外負載；根部固定、初始中心線水平。

由根部到頭部的順序固定為 high → uni-d → directional → low。後段由 high＋uni-d 組成，前段由 directional＋low 組成。每類至少一節，前端 directional＋low 恆為 11 節；後段掃描 2–20 節。共有 **1900 種組合**，其中總數 31 節時有 **190 種**。

## 數據與連接方式

模組的 EI 及材料質量直接讀取 `craft_data.py`，沒有材料模量、密度或尺寸換算。採用方向維持 high:x、uni-d:y、directional:y、low:x。每節 48 mm 是原檔案的既有幾何假設，因此「11 節＝528 mm」亦承接此假設。

backbone 直接讀取現有 `rope_materials.json` 中的 `ss304_annealed`：

| 參數 | 採用值 |
|---|---:|
| 實心圓棒直徑 | 4.2 mm |
| 彈性模量 | 200 GPa |
| 密度 | 7900 kg/m³ |
| 屈服強度參考值 | 205 MPa |

來源及適用範圍沿用現有材料表：ATI 304 退火板／帶材規格參考值，並非使用者實際圓棒的實測曲線。逐項來源另保存於 `rear_backbone_results/backbone_properties.json`。

沿用每節端盤夾持、無相對滑動的中心線近似。backbone 從根部延伸到最後一節 uni-d 的端盤，在前段開始的端盤截止；前段的質量與剛度完全保留原模組值。只在後段加入：

\[
(EI)_{\rm rear}=(EI)_{\rm module}+E_s\frac{\pi d^4}{64},\qquad
m_{\rm core}=\rho_s\frac{\pi d^2}{4}L_{\rm rear}.
\]

backbone 的質量亦產生自重。後段增加剛度的同時，會增加整體質量。

## 剛性與靈活性指標

同時輸出：

- 自重下的頭部下垂與水平伸出。
- 後段端部下垂、後段與前段交界的角度。
- 前端相對於後段的微小轉角／頭部測試彎矩，單位 deg/(N·mm)。這是自重平衡形狀附近的微小擾動柔順度，並不承諾大角度運動線性。
- 無重力時的前、後段彎矩柔順度，方便檢查設計本身的剛度分配。
- backbone 最大彎曲應力與 205 MPa 屈服參考值的比值。

柔順度由平衡方程的切線剛度求得，未加入實際繩索。前段轉角以頭部角度減去後／前段交界角度計算，避免把整條結構的轉動都當作前端彎曲。自由端半單元柔度及交界兩側 EI 不同的切線插值均納入。

本版採線彈性 backbone，並作參考屈服檢查。超出屈服參考值的組合會被排除於 Pareto 候選，不把超出彈性範圍的形狀當作可靠預測。沒有計算塑性殘留、列印彈性件破壞、接觸或夾持滑動；軸向伸長、剪切及扭轉沿用目前模型的忽略假設。

## 執行

```bash
/opt/miniconda3/bin/python -B snake_model_rear_backbone.py
/opt/miniconda3/bin/python -B -m unittest -v test_snake_model_rear_backbone.py
```

可用 `--config`、`--catalog`、`--output-dir` 指定檔案及輸出位置，或用 `--no-plots` 只計算數據。設定在 `rear_backbone_config.json`。依賴既有 `snake_model_pla_sag.py`、`craft_data.py`、NumPy、SciPy、Matplotlib。

## 預設參考組合與結果

為滿足前端 11 節，本版參考配置使用 **H8／U12／D8／L3**，共 31 節：後段 20 節＝960 mm，前段 11 節＝528 mm，總長 1488 mm。這個配置與先前 H8／U13／D8／L2 相差一節 uni-d 換成 low，所有對照均使用本版同一配置。

| 項目 | 沒有 backbone | 後段加入 backbone |
|---|---:|---:|
| 模組質量 | 130.4 g | 130.4 g |
| backbone 質量 | 0 g | 105.1 g |
| 頭部下垂 | 1395.2 mm | 588.2 mm |
| 水平伸出 | 245.5 mm | 1107.3 mm |
| 後段端部下垂 | 867.2 mm | 110.7 mm |

加入 backbone 後，自重平衡附近的前端柔順度約 **4.604 deg/(N·mm)**，無重力基準為 **9.724 deg/(N·mm)**。參考配置的 backbone 最大彎曲應力約 180.1 MPa，是材料表屈服參考值的 0.879 倍。掃描中最大比值約 0.938；這是材料參考篩選，未包含額外強度裕量。

## 圖表與結果

結果保存在 `rear_backbone_results/`：

- `combinations.csv`：全部 1900 種組合及剛性、靈活性、應力指標。
- `fixed_N31.csv`：固定 31 節的 190 種組合。
- `pareto_N31.csv`：同時最大化水平伸出與自重下前端柔順度、通過參考屈服篩選的候選。
- `rear_length_vs_shape.png`：後段長度與下垂、水平伸出的關係。
- `composition_and_flexibility.png`：固定長度下的組合熱力圖，以及水平伸出與前端柔順度的權衡。
- `reference_shape_comparison.png`：同一配置有／無後段 backbone 的形狀，比例相同。
- `reference_shapes.json`、`run_summary.json`：參考形狀及完整設定、來源與結果。
- `validation.json`：收斂、前段長度固定、無 backbone 回歸、零重力解析柔順度及網格加密核對。

五項獨立測試另檢查：core 只出現在後段、質量守恆、1900 組枚舉完整性、零重力柔順度、根部力矩平衡、超屈服排除，以及獨立連續體邊值方程的形狀和微小彎矩反應。

參考配置每節 8→16 單元的頭部下垂差約 0.039 mm，16→32 差約 0.010 mm；獨立連續體方程及正負小彎矩差分測試通過。這些檢查說明數值一致性，實際夾持及圓棒性質仍須對照實物。
