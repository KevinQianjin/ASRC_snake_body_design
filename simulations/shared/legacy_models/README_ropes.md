# 四根尼龍拉索＋中央可塑性被動骨架

這是獨立的新模型。`snake_model.py` 和 `craft_data.py` 保持原樣，只讀取其中的 module 類型、材料資料和組合字串解析函數。

新增的整體水平控制與 XYZ 目標位置收繩反算，請看 [README_horizontal_inverse.md](README_horizontal_inverse.md)。反算另存結果，保留本文件的原案例。

## 執行

在本資料夾執行：

```bash
python3 snake_model_ropes.py
```

需要 NumPy、SciPy；繪圖另外使用 Matplotlib。若執行時出現 `ModuleNotFoundError`，請用**執行程式的同一個 Python** 安裝依賴；系統 Python 和 Miniconda 的套件互不共用。在本資料夾執行：

```bash
python -m pip install -r requirements_ropes.txt
```

例如使用 Miniconda 的 `/opt/miniconda3/bin/python` 時：

```bash
/opt/miniconda3/bin/python -m pip install -r requirements_ropes.txt
/opt/miniconda3/bin/python snake_model_ropes.py
```

若從編輯器的執行按鈕啟動，編輯器選取的 interpreter 也須是已安裝依賴的那一套。只輸出數據可用：

```bash
python3 snake_model_ropes.py --no-plots
python3 snake_model_ropes.py --list-materials
python3 snake_model_ropes.py --material al1100_o
python3 snake_model_ropes.py --material cu110_o60,ss304_annealed
python3 -m unittest -v test_snake_model_ropes.py
```

`--config`、`--catalog`、`--database`、`--output-dir` 可分別指定設定檔、材料 JSON、SQLite 資料庫和輸出資料夾。設定及結果預設相對於程式所在資料夾；材料 JSON 和 SQLite 預設位於專案的 `data/materials/`。路徑不受執行時的工作目錄影響。每次完整運行會在 SQLite 新增一筆 run；輸出資料夾中的比較檔會更新成最近一次運行。

## 這一版的配置

- 預設只計算 **D 方案、31 個 modules**：`8*high, 13*unidirectional:y, 8*directional:y, 2*low`，原先 12 段／576 mm 案例已從預設設定移除。
- 每個 module 長 48 mm，總長 **1488 mm（1.488 m，名義約 1.5 m）**；沒有為湊足 1500 mm 另加接頭。
- 四根 Ø2 mm 尼龍繩，按 top／right／bottom／left 排列在周向 0°／90°／180°／270°。
- 導孔中心到 module 中心距離先設為 **13 mm**，可修改。
- 四根繩索都固定在末端，由根部各自收繩或放繩；沿各節端盤的導孔導向，假設無摩擦，因此同一根繩的張力沿路相同。
- 中央骨架按 **Ø4.2 mm 實心圓棒**計算，在每個 module 端盤上夾持固定，與 modules 共用中心線、彎曲和軸向應變，無相對滑動。
- 根部位置及初始參考框架固定，第一個 module 仍可彎曲；沒有額外 carrier。
- 初始軸線為全域 X；Y 向上、Z 為側向。繩索名稱跟隨局部截面，彎曲後不必仍與全域上下左右一致。

## 新增：頭部掛載 500 g，保留原案例

原本的 `rope_config.json` 和 `rope_results/` 保留為沒有額外負載的 D 方案。新增獨立啟動程式：

```bash
/opt/miniconda3/bin/python snake_model_ropes_tip500g.py
```

也可由共用程式指定新設定；設定中的輸出路徑會自動避免覆寫原結果：

```bash
/opt/miniconda3/bin/python snake_model_ropes.py --config rope_config_tip500g.json
```

- 新設定：`rope_config_tip500g.json`；新結果：`rope_results_tip500g/`。
- 組裝沿用 D：31 段、1488 mm，三種 Ø4.2 mm 中央骨架分別計算。
- 「頭部」定義為最末端第 31 節後的節點。`payload_node: null` 會自動選擇末端。
- 500 g 換算為 `payload_kg: 0.5`；正常重力下向下作用力為 **4.905 N**。按末端點質量建模，沒有另外加入物體外形、碰撞或轉動慣量。
- 沿用上收 10／下放 10 mm，以及再加入右收 6／左放 6 mm。

新案例由沒有塑性歷史的狀態開始，先施加自重，再掛載物體。以下八階段連續繼承各自的塑性歷史：

| 階段 | 末端物體 | 重力 | 繩索狀態 |
|---|---:|---|---|
| `self_weight` | 0 g | 保留 | 四捲筒鎖定 |
| `tip_payload_500g` | 逐步加至 500 g | 保留 | 四捲筒鎖定 |
| `pull_top_10mm` | 500 g | 保留 | 上收 10、下放 10 mm |
| `pull_top_right` | 500 g | 保留 | 上下維持，再右收 6、左放 6 mm |
| `return_zero` | 500 g | 保留 | 四捲筒回零並鎖定 |
| `free_spool` | **仍掛著 500 g** | 保留 | 四繩自由放出，張力為零 |
| `payload_removed` | 移除至 0 g | **仍保留** | 保持自由放繩 |
| `unloaded_residual` | 0 g | 關閉 | 計算完整循環後的殘留偏移 |

因此，掛著物體放開繩索的實際自重狀態應看 `free_spool`；移除物體後、仍有自重的形狀應看 `payload_removed`。最後一行才是數值上去除全部外載後的殘留形狀。

共輸出 **25 個結果**：一個初始 module-only 自重基準，加上三種骨架 × 八階段。終端和 CSV 都會明列 `payload_kg`、`payload_force_n`、`payload_node`。`total_mass_g` 仍表示模擬機械臂本體質量，`system_mass_g` 則包含當下掛載物體。SQLite 新增一筆獨立 run，以 `scenario_name = D_tip_500g` 區分，原有 run 及無負載輸出檔案保留。

## 改參數的位置

所有幾何和控制參數集中在 `rope_config.json`：

| 參數 | 用途／單位 |
|---|---|
| `assembly_name` | 組裝方案名稱，目前為 D |
| `scenario_name` | 選填的情境名稱，新增掛載案例為 D_tip_500g |
| `output_directory` | 選填的獨立輸出資料夾，掛載案例為 rope_results_tip500g |
| `stack` | 目前為 `8*high, 13*unidirectional:y, 8*directional:y, 2*low`，根部到末端 |
| `module_diameter_mm` | module 直徑；沿用原程式的均勻幾何縮放假設 |
| `module_length_mm` | 基準直徑 32 mm 時的單個 module 長度，預設 48 mm |
| `extras_g_per_module` | 每個 module 的額外質量，不包含已另算的四繩和中央骨架 |
| `backbone.diameter_mm` | 中央骨架直徑，預設 4.2 mm |
| `backbone.materials` | 要分別計算的材料 ID，預設三種全部計算 |
| `ropes.diameter_mm` | 繩索直徑，預設 2 mm |
| `ropes.routing_radius_mm` | 導孔半徑，預設 13 mm，**不是繩索自身半徑** |
| `ropes.pretension_n` | 四根繩的初始預緊張力，N；預設全零 |
| `ropes.effective_axial_rigidity_n` | 實際繩的有效 EA，N；`null` 代表用材料 E × 圓截面 A |
| `ropes.effective_linear_density_kg_m` | 實際繩的線密度，kg/m；`null` 代表用材料密度 × A |
| `payload_node` | `null` 表示末端；整數 0..n 指定其他節點，0 是固定根部 |
| `protocol` | 依序加載、收繩、回零和卸載；每一階段繼承塑性歷史 |

預設 D 組合共 31 個 modules，中心線基準總長 `31 × 48 = 1488 mm`：

| 根部到末端的位置 | 類型 | 數量 | 段長 |
|---|---|---:|---:|
| 1–8 | high | 8 | 384 mm |
| 9–21 | unidirectional:y | 13 | 624 mm |
| 22–29 | directional:y | 8 | 384 mm |
| 30–31 | low | 2 | 96 mm |

三種骨架材料均使用同一個 D 組合；module-only 對照也使用相同 31 段。沒有同時計算其他拼裝方案。實際計算總長為：

```text
module 數量 × module_length_mm × module_diameter_mm / 32
```

中央骨架及繩索的直徑、導孔半徑都保持設定值，不隨 module 直徑自動縮放。程式會檢查繩索是否超出 module 外徑或與中央骨架重疊。只改 `module_length_mm` 不會重新辨識 module 原始 EI 或材料質量；若是實際結構改版，需要更新相應實測資料。

### 收繩控制

每個階段的 `take_up_mm` 都按 **[top, right, bottom, left]**，代表相對於初始繩長的**累計指令**，不是相對上一階段的增量。

```json
{
  "name": "my_pull",
  "take_up_mm": [10, 6, -10, -6],
  "gravity_scale": 1.0,
  "payload_kg": 0.0,
  "free_spool": false,
  "steps": 20
}
```

這表示上方收 10 mm、右側收 6 mm、下方放 10 mm、左側放 6 mm。正數收繩，負數放繩。若其餘三根指令維持 0，表示那些根部捲筒鎖在原長度，它們可能因彎曲而產生對抗張力，並非自動鬆開。

終端會逐根顯示兩種長度，單位都是 mm：`take_up` 是相對初始位置的累計收放量，`move` 是本階段相對上一階段的收放動作。例如 `pull_top_right` 的累計長度是 `[10, 6, -10, -6]`，但這一步只新增 `[0, 6, 0, -6]`；上繩沒有再次收 10 mm。

| 階段 | 累計收放量：上／右／下／左 (mm) | 本階段動作：上／右／下／左 (mm) |
|---|---|---|
| `self_weight` | 0／0／0／0 | 0／0／0／0 |
| `pull_top_10mm` | +10／0／−10／0 | +10／0／−10／0 |
| `pull_top_right` | +10／+6／−10／−6 | 0／+6／0／−6 |
| `return_zero` | 0／0／0／0 | −10／−6／+10／+6 |
| `free_spool` | 自由放繩，無指定長度 | 解除捲筒鎖定 |
| `unloaded_residual` | 保持自由放繩 | 無指定收放動作 |

預設載入順序：

1. `self_weight`：只施加自重，四捲筒鎖在零指令。
2. `pull_top_10mm`：上方收 10 mm，下方放 10 mm。
3. `pull_top_right`：保留上方收繩，再加入右側收 6 mm及左側放 6 mm。
4. `return_zero`：四個指令回到 0，繩索仍鎖定，可能造成反向塑性。
5. `free_spool`：放開根部捲筒，所有拉索張力降為 0，保留自重。
6. `unloaded_residual`：保持自由放繩，再將重力降為 0，觀察完整上述循環後的殘留形狀。

**回到零收繩指令不等於零張力；零張力也不等於零外載，因為仍可能有重力。** 自由放繩的過渡以逐步降低繩索作用力近似。`unloaded_residual` 是整個示範控制循環後的狀態；若只想看單次彎曲後的保形，可移除 `return_zero`，由拉繩直接進入 `free_spool`，結果可能不同。

`gravity_scale` 同時縮放所有自重和 payload 的重力；`payload_kg` 可隨階段改變。第一階段從無重力、無負載、零收繩、無塑性狀態開始。`steps` 越大，載入路徑越細；求解失敗時還會自動二分步長。

## 三種中央骨架材料與資料庫

三者都先按 Ø4.2 mm 實心圓棒比較：

| ID | 材料狀態 | E (GPa) | 屈服參考值 (MPa) | 密度 (kg/m³) | EI (N·m²) | 首次屈服彎矩 (N·m) | 質量 (g/m) |
|---|---|---:|---:|---:|---:|---:|---:|
| `al1100_o` | 1100-O 退火鋁 | 69 | 20 | 2700 | 1.0539 | 0.1455 | 37.41 |
| `cu110_o60` | C11000-O60 退火銅 | 117 | 68.95 | 8910 | 1.7871 | 0.5015 | 123.44 |
| `ss304_annealed` | 304 退火不鏽鋼 | 200 | 205 | 7900 | 3.0549 | 1.4911 | 109.45 |

選這三種是為比較較低定型力／較輕的鋁、較重且延展的銅、較高剛度和成形力的不鏽鋼；不是對具體供應商線材的採購定案。材料加工狀態必須相符，退火線與硬拉線的屈服表現會不同。

資料分為：

- `../../../data/materials/rope_materials.json`：可讀、可編輯的材料資料表，包含單位、狀態、逐項來源、查閱日期和 `calibrated: false` 標記。
- `../../../data/materials/rope_materials.sqlite3`：實際 SQLite 資料庫。每次執行把 JSON 同步進資料表，模型再從 SQLite 讀取參數。**要永久改材料，請改 JSON**；直接修改 SQLite 的材料列，會在下次同步時被 JSON 覆蓋。

SQLite 中有 `materials`、`sources`、`property_sources`、`runs`、`cases`。每個 run 都保留完整設定及材料快照，避免之後改材料表使舊結果失去依據。可用 SQLite 工具查詢：

```sql
SELECT id, temper, young_modulus_pa/1e9 AS E_GPa,
       yield_strength_pa/1e6 AS yield_MPa, density_kg_m3
FROM materials WHERE role = 'backbone';

SELECT m.id, p.property_name, s.title, s.url
FROM materials AS m
JOIN property_sources AS p ON p.material_id = m.id
JOIN sources AS s ON s.id = p.source_id;

SELECT material_id, stage, tip_drop_mm, residual_tip_mm,
       take_up_top_mm, take_up_right_mm, take_up_bottom_mm, take_up_left_mm,
       take_up_change_top_mm, take_up_change_right_mm,
       take_up_change_bottom_mm, take_up_change_left_mm
FROM cases WHERE run_id = (SELECT MAX(id) FROM runs);

SELECT scenario_name, material_id, stage, payload_kg, payload_force_n,
       tip_drop_mm, residual_tip_mm
FROM cases WHERE run_id = (SELECT MAX(id) FROM runs);
```

來源和採用方式：

- [Lichen Aluminium 1100-O 資料表，第 1 頁](https://www.lichenalu.com/uploads/file/1100-o-aluminum-circle.pdf)：E 範圍 68–70 GPa 取中值 69 GPa，密度 2700 kg/m³，Rp0.2 為 20 MPa。是板／圓片資料，外推到圓棒作初步比較。
- [Copper Development Association C11000](https://alloys.copper.org/alloy/C11000)：E 17000 ksi 約 117 GPa、比重 8.91；[Alcobra C110 O60](https://alcobrametals.com/copper-product-guide/) 的屈服 10000 psi 轉為 68.95 MPa。
- [ATI 304 資料表，第 3–4 頁](https://www.atimaterials.com/Products/Documents/datasheets/stainless-specialty-steel/austenitic/ati_302_304_304l_305_tds_en2_v1.pdf)：E 200 GPa、密度 7900 kg/m³，205 MPa 是退火板／帶材的規格下限，作此處的比較值，不是已測定的線材屈服點。
- [Mitsubishi Chemical Group PA6](https://www.mcam.com/mcam/products/nylons)：E 3300 MPa、密度 1150 kg/m³，作尼龍材料參考。這是工程實心料數據，**不是 Ø2 mm 編織繩的實測有效剛度或破斷強度**。

對尼龍繩，最有用的校準是拉力–伸長試驗和 g/m 實測。若長 L 的繩在拉力增量 ΔT 下伸長 ΔL，可在近線性區估算 `EA = ΔT × L / ΔL`，填入 `effective_axial_rigidity_n`。模型不會把尼龍棒的強度當作實際繩索的額定承載能力。

## 計算方法

每個 module 有兩個彎曲角度及可選軸向應變。局部旋轉用旋轉矩陣逐節累乘，允許中心線在三維空間彎曲。**沒有獨立扭轉或剪切自由度**，因此原資料中的 GJ 未用於本版計算；此處不是完整六自由度 Cosserat 桿。

Module 彎曲剛度沿用 `EI/L`，正負 X 可不同，另一個方向使用 EI_y。`:x`、`:-x`、`:y`、`:-y` 對應橫截面材料主軸的 0°／180°／90°／−90° 安裝方向；EI(-Y)=EI(Y) 仍是假設。任意方向的彎曲能量是兩個主軸分量之和，沒有另行量測的耦合項。Module 軸向剛度使用 EA。

四根繩分別沿每節導孔形成三維折線，整根的路徑長度為 `L_path`。預緊後初始無應力長度為 `L_initial = L_reference / (1 + T_pre / EA)`，捲筒控制後為：

```text
L_rest = L_initial - take_up_mm / 1000
T = EA × max((L_path - L_rest) / L_rest, 0)
```

每根是**一根連續、可滑過無摩擦導孔的繩**，不是每個 module 各自一條彈簧。拉索作用由路徑長度的幾何導數求得，同時計入偏心彎曲和軸向壓縮；沒有把滑動繩當作黏合複合梁直接增加 module 的 EI。[理想繩索參考](https://doc.comsol.com/6.3/doc/com.comsol.help.sme/sme_ug_theory.06.161.html)

中央實心圓棒的截面量：

```text
A = πd²/4
I = πd⁴/64
EI = E I
M_first_yield = σ_y I / (d/2)
M_fully_plastic = σ_y d³/6
```

骨架以每節均勻曲率及圓截面纖維積分近似。預設 5 個徑向 Gauss 點 × 24 個周向點，共 120 條纖維／節。纖維應變為軸向應變減去曲率與截面座標的內積。各纖維使用彈性–理想塑性應力返回法，並儲存塑性應變、累積塑性應變及耗散能；**成功求得平衡後才提交歷史**。這可模擬卸載及部分留形，且區分首次屈服與整截面塑化。[彈性–理想塑性參考](https://opensees.berkeley.edu/OpenSees/manuals/usermanual/171.htm)

求解器逐步最小化 module 彈性能、骨架增量塑性勢、繩索拉伸能及重力勢能的總和，使用解析梯度。平衡結果須通過力矩和軸向力殘差門檻，並檢查末端階段的受約束局部穩定性。`ok` 代表這個數值模型的檢查通過，不代表實驗驗證。

## 輸出與如何解讀

`rope_results/` 中包含：

- `comparison.csv`：每種材料、每個階段的下垂、側向位移、完全卸載後的末端殘留偏移、各繩累計／本階段收放長度、四繩張力、質量及求解殘差。
- `comparison.json`：設定與材料快照、中心線座標、截面框架、四根繩的導孔座標、應變及塑性歷史。
- `backbone_properties.csv`：三種 Ø4.2 mm 骨架的 EI、屈服彎矩、線密度等派生量。
- `comparison.png`：截面配置與材料比較。
- `shapes_3d.png`：同一物理比例下的三維載入／卸載形狀。

`tip_drop_mm > 0` 表示向下，負數表示末端高於根部；`tip_z_mm` 是側向位移。

終端的 `residual` 與匯出欄位 `residual_tip_mm` 表示末端相對初始直線軸的 Y/Z 合成殘留偏移：`sqrt(Y_tip² + Z_tip²)`，不包含 X 方向的縮短量。只有重力為零且四根繩索張力都為零時才填值；其他階段終端顯示 `-- (loaded)`，CSV 為空值，SQLite 為 NULL。它是指定載入循環後的結果，不能當作材料固有常數。

`take_up_top_mm` 等四欄是累計收放量；`take_up_change_top_mm` 等四欄是本階段動作。正數收繩，負數放繩。自由放繩時沒有固定長度指令，這些欄位為空；若由自由放繩重新鎖定，先前自由放出的長度不是已知的鎖定指令，因此本階段增量也保留空值。

終端與比較 CSV 已移除 `plastic` 計數顯示。為了繼續計算可塑性骨架的卸載與殘留形狀，塑性應變及其歷史仍保留在求解器、詳細 JSON 和 SQLite 內部欄位中。SQLite 更新採新增欄位，保留舊 run；更新前的歷史列在新欄位中為 NULL。

`free_spool` 下張力和彈性繩應變都為零；JSON 中 `locked_rope_rest_length_m` 只保留放開前捲筒長度的參考值。自重按參考段長守恆集中到段中點；拉入捲筒的一小部分繩質量變化未另外計算。

預設示範得到 D 方案的 1 個 module-only 基準及 3 種材料 × 6 個階段，共 **19 個結果，全部為 31 段／1488 mm**。純 module 基準關閉骨架、繩索及軸向伸縮，用於對照原程式的平面假設。三種新模型則計入骨架／繩索質量及軸向應變；自重階段即使零收繩，鎖定的繩索仍可能因下垂伸長而有張力。比較輸出會被本次 D 方案結果更新；SQLite 中的既有 run 仍保留為歷史記錄，查詢最新 run 即只得到目前 D 方案。

## 已做驗證與適用範圍

`test_snake_model_ropes.py` 驗證圓截面積分、旋轉與完整能量梯度、小變形 EI、鬆繩與預緊、四繩等量收繩的軸向壓縮、兩個方向的彎曲及鏡像對稱、關閉新增元件後與原模型一致、塑性卸載的殘留彎曲，以及 SQLite 來源關聯與歷史保存。新增的一節連桿獨立力矩平衡測試亦核對 0.5 kg 的末端力為 4.905 N，並確認相同點負載放在固定根部時不會產生彎曲；共 12 項測試。

預設運行亦檢查原始兩個 Python 檔案的 SHA256。D 方案／31 段的鋁骨架六個階段另以雙倍載入步數核對，末端位置差小於 0.007 mm、張力差小於 0.0003 N；詳細結果在 `rope_results/step_refinement_al31.json`。這是步長檢查，不是實物校準。D 方案的銅骨架部分階段單節彎曲超過 0.5 rad，會在終端、CSV 和詳細結果標註幾何近似提示；數值收斂不代表這些大彎曲形狀已經實物驗證。

模型目前未包含導孔摩擦、繩結、蠕變、濕度依賴、金屬加工硬化、疲勞破壞、接觸／自碰撞和獨立扭轉。圓棒實際牌號及退火狀態尚未選定，尼龍實際 EA 尚未量測，所有比較都標記為參考值。若中央件實際是空心管、編織線、鋼絲繩或可定型蛇管，應改用相應截面或實測力矩–曲率曲線，不能沿用實心圓棒公式。
