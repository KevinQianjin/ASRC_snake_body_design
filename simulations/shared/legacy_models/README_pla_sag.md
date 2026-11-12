# CRAFT 原論文數據：自重下垂與組合掃描

本版直接讀取 `craft_data.py` 的原論文 EI 及 PC＋PLA 材料質量。材料模量比例、密度比例、直徑縮放及自訂剛度／質量覆蓋功能已移除。`snake_model_pla_sag.py`、`pla_sag_config.json` 及 `pla_sag_results/` 沿用歷史檔名，實際計算材料為原論文的 **PC 彈性件＋PLA 圓盤／環**。

根部固定、初始中心線水平，頭部自由；沒有繩索、中央骨架或末端額外負載。固定順序為 **high → uni-d → directional → low**，數量記為 H/U/D/L。預設每類至少 1 節，總節數 4–31，共 31,465 種組合；固定 31 節有 4,060 種。

## 直接使用的數據

來源：`craft_data.py` 所引用的 [CRAFT 預印本 rs-8482576/v1](https://doi.org/10.21203/rs.3.rs-8482576/v1)，表 1 的模組力學性質、表 2 的列印材料用量。

| 模組 | 設定的重力彎曲方向 | EI（N·m²） | PC（g） | PLA（g） | 每節總質量（g） |
|---|---|---:|---:|---:|---:|
| high | x | 0.028 | 2.4 | 2.7 | 5.1 |
| uni-d | y | 0.061 | 1.2 | 2.7 | 3.9 |
| directional | y | 0.0035 | 1.3 | 2.7 | 4.0 |
| low | x | 0.0024 | 0.9 | 2.7 | 3.6 |

EI 直接取所選彎曲方向的原始值。質量直接取 `pc_g + pla_g`；只在進入求解器時將 g 轉成 kg。程式會拒絕舊的材料換算設定、自訂性質覆蓋、額外質量及幾何縮放，避免再次混用換算數據。

`module_properties.csv` 同時列出 EI 來源欄位、三個方向的 EI、EA、原文標為 GJ 的單模組扭轉剛度及 PC／PLA 質量，便於逐項核對。EA 與扭轉剛度作資料記錄；本次平面不可伸長模型的求解僅使用 EI 與質量。

## 必須保留的幾何及模型假設

- 模組直徑為 32 mm。
- **每節 48 mm 是 `craft_data.py` 的既有假設**：45 mm 彈性件加兩個 1.5 mm 端盤。論文未明確給出組裝節距；不能將 48 mm 標為論文實測節長。31 節的模型總長為 1488 mm。
- uni-d、directional 沿用既有 D 組合的 y 朝向；這是本次安裝設定。可在 `axes` 選擇原數據包含的 x、-x、y、-y 方向。uni-d 的 y 向較硬；directional 的 x 與 -x 會切換朝下彎曲時使用的原始 EI。
- 原數據未提供 -Y 的獨立測值，程式沿用 EI(-Y)=EI(Y) 的既有對稱假設。
- low 的 EI 在原文正文為 0.024、表 1 為 0.0024 N·m²。程式延續 `craft_data.py`，使用表 1 的 **0.0024**。
- 表 2 是材料用量，未包含鉚釘、膠水或頭部附件的額外質量。

本版只移除材料及幾何性質換算，保留目前非線性細分求解器。每節預設 8 個單元、8 步重力載入。這與 `snake_model.py` 的一節一連桿粗網格不同，因此即使使用相同原始數據，數值也不會完全相同。

## 執行

在本資料夾執行，使用已驗證的 Python 環境：

```bash
/opt/miniconda3/bin/python -B snake_model_pla_sag.py
```

其他用法：

```bash
# 僅比較固定總節數，四類數量仍可任意分配
/opt/miniconda3/bin/python -B snake_model_pla_sag.py --total 31 --output-dir paper_sag_N31

# 更改總節數範圍，不改每節的原始剛度及質量
/opt/miniconda3/bin/python -B snake_model_pla_sag.py --total-min 4 --total-max 40 --output-dir paper_sag_to40

# 容許部分種類數量為 0；剩餘模組仍保持固定順序
/opt/miniconda3/bin/python -B snake_model_pla_sag.py --total 31 --min-each 0 --output-dir paper_sag_allow_zero

# 只計算 H/U/D/L = 8/13/8/2
/opt/miniconda3/bin/python -B snake_model_pla_sag.py --counts 8 13 8 2 --output-dir paper_sag_reference

# 加密，並只輸出數據
/opt/miniconda3/bin/python -B snake_model_pla_sag.py --cells-per-module 16 --no-plots --output-dir paper_sag_refined

# 檢查原始數據及獨立數值測試
/opt/miniconda3/bin/python -B -m unittest -v test_snake_model_pla_sag.py
```

依賴 NumPy、SciPy、Matplotlib。設定集中在 `pla_sag_config.json`；`data_mode` 固定為 `paper_original`。再次執行會更新輸出目錄中的同名檔案。`craft_data.py`、`snake_model.py` 及既有繩索模型保持原樣。

## 自重平衡方程

以平面不可伸長的彈性鏈近似模組，保留大轉角。每個單元的角度代表其中心切線；根部採半單元轉動柔度，內部採相鄰半單元柔度之和，處理固定根部與 EI 交界。

單元自重集中於中點。對絕對角度 φ，總勢能為：

\[
\Pi=\tfrac12\sum_i k_i(\phi_i-\phi_{i-1})^2+
\sum_i g\ell_i\left(\sum_{j>i}m_j+\tfrac12m_i\right)\sin\phi_i,
\quad \phi_{-1}=0.
\]

以解析梯度與三對角 Hessian 求靜態平衡，重力逐步增加至 9.81 m/s²。下垂高度為根部高度減去頭部高度，向下為正。`tip_x_mm` 另記錄水平伸出距離。

## 輸出與結果

預設結果在 `pla_sag_results/`：

- `combinations.csv`：所有組合的四類數量、總長、總質量、頭部下垂、水平伸出距離及收斂狀態。
- `summary_by_total.csv`：各總節數的最小／最大下垂及對應組合。
- `ranking_N31.csv`：31 節組合按下垂高度排序。
- `sag_vs_total.png`：總節數與下垂高度、下垂／總長比例。邊線表示組合範圍。
- `composition_heatmaps_N31.png`：low 數量的全部 28 個切片，採共同色階；橫軸 high、縱軸 uni-d，directional = 31 − high − uni-d − low。
- `composition_preview_N31.png`：含原組合與最小值所在切片的精簡圖。星號是原組合、圓圈是最小值，空白為不可行或未收斂組合。
- `representative_shapes.png`／`.json`：31 節最小、最大下垂及原 8/13/8/2 組合的中心線，物理比例相同。
- `module_properties.csv`：直接使用的原論文數據。
- `run_summary.json`、`validation.json`：設定、來源、原始檔案雜湊、原始性質一致性及數值檢查。

預設 31 節、1488 mm 模型的更新結果：

| H/U/D/L | 每節材料質量加總（g） | 頭部下垂（mm） | 說明 |
|---|---:|---:|---|
| 1/5/1/24 | 115.0 | 1355.7 | 掃描中的最小值 |
| 8/13/8/2 | 130.7 | 1395.3 | 原有 D 組合 |
| 28/1/1/1 | 154.3 | 1403.5 | 掃描中的最大值 |

七項測試檢查原論文數值、拒絕換算／縮放、組合完整性、獨立連續體邊值解、混合 EI 的虛功積分、獨立平衡方程、零重力及加密。三個代表組合由每節 8→16 單元的下垂變化均小於 0.03 mm。

原始材料性質與數值收斂不等於實物預測已校準。模型忽略軸向伸長、剪切、扭轉、接觸、蠕變及損傷；根部及自由懸空長度須與實物一致。下垂最小也不是承載能力或應力最小的判定。原論文 55／33 mm 的翼內案例配置與本次 31 節模型不同，不能作直接等值比較。

## 為何增加 low 有時反而減少頭部下垂

`diagnose_sag_low.py` 專門檢查此現象。固定總數 31、high=1、directional=1，以 low 替換 uni-d，使用每節 32 個單元；原始掃描的設定及輸出不改動。

| low | uni-d | 原論文質量下垂（mm） | 固定每節 3.9 g 的對照下垂（mm） |
|---:|---:|---:|---:|
| 1 | 28 | 1377.1 | 1377.2 |
| 24 | 5 | 1355.7 | 1361.7 |
| 28 | 1 | 1388.0 | 1390.5 |

因此趨勢具有非單調性，並非 low 越多就一直越少下垂。等質量對照仍重現下降，說明單靠 low 較輕不足以解釋。

在目前的大變形狀態，較軟的遠端更接近垂直懸掛，改變重量相對根部的水平力臂。等質量對照中，low=1→24 時，根部重力彎矩由 0.3126 降至 0.2780 N·m，使近根部彎曲減少，頭部高度可能略為提高。原質量案例同時把水平伸出由約 345 mm 減至 271 mm；只按頭部垂直位置排序會隱藏伸出距離的損失。

另一個診斷把重力縮至原來的十萬分之一，使變形很小。在等質量對照下，low 增加時下垂單調增加，符合小撓度條件下剛度降低的預期。等質量及減小重力均是明確標示的診斷控制，不會寫回原論文輸入。

兩個等質量正常重力案例另由獨立的分段連續體邊值方程核對，與離散結果相差小於 0.003 mm。診斷圖、CSV、JSON 保存在 `pla_sag_results/low_count_diagnostic.*`。重現方式：

```bash
/opt/miniconda3/bin/python -B diagnose_sag_low.py
```
