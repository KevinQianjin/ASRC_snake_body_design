# D 方案：保持水平與目標位置的收繩反算

沿用 D 方案 31 段、1488 mm、四根 Ø2 mm 尼龍繩、導孔半徑 13 mm、三種 Ø4.2 mm 骨架。原模型、無額外負載結果及 500 g 結果保留；新增反算結果另存，各有獨立 SQLite 資料庫。

組裝與材料物性取自來源 `rope_results_tip500g/comparison.json` 的快照。若改了原組裝或材料設定，須先重新執行 `snake_model_ropes_tip500g.py` 產生對應正向結果，再做反算。

## 保持整體水平

```bash
/opt/miniconda3/bin/python snake_model_ropes_hold_horizontal.py
```

主設定是 `rope_config_hold_horizontal.json`，共用搜尋參數在 `rope_config_level.json`；結果在 `rope_results_level_hold/`。

`target.mode = horizontal_shape` 的預設判定：

- 所有 module 中心線節點的 Y/Z 合成偏差不超過 **1 mm**。
- 每一節的軸向相對全域 +X 的傾角不超過 **1°**。
- 末端向前伸出至少總長的 **99%**，容許 1 mm 位置誤差。

可修改主設定的 `target.tolerance_mm`、`angle_tolerance_deg`、`minimum_forward_ratio`。末端回到根部高度但中間拱起，或末端高度正確但方向傾斜，都不算整體水平達標。

程式從無塑性歷史的直線骨架開始，以 20 步數值載入自重並調整繩索，再以 20 步把末端物體加到 500 g。各步先求受力平衡，再反算捲筒收放量。這是各載入步完成後的準靜態控制，不計動態過程；分步載入重力是數值求解路徑。

若某一步未達標，就記錄該步及之前最後達標狀態，停止增加負載。部分載入達標**不會**報告成 500 g 達標。最後達標的測試點不是經證明的最大載荷；`gravity_scale = 0` 的達標狀態僅代表無負載初始直線。

## 獨立的 XYZ 目標位置反算

```bash
/opt/miniconda3/bin/python snake_model_ropes_target_position.py
```

設定是 `rope_config_target_position.json`；結果在 `rope_results_target_position/`。預設目標 **(X, Y, Z) = (1488, 0, 0) mm**，三維位置誤差容差 1 mm。座標原點是根部，X 向前、Y 向上、Z 為側向。

修改設定的 `target.tip_x_mm`、`tip_y_mm`、`tip_z_mm`，或直接從指令列輸入目標，例如：

```bash
/opt/miniconda3/bin/python snake_model_ropes_target_position.py --target-mm 1400 -100 50 --output-dir rope_results_custom_target
```

這些示例座標不保證可達。反算從原來已掛 500 g 的 `tip_payload_500g` 狀態開始，包含已累積的塑性歷史。此模式只要求末端 XYZ，不要求整條中心線或末端方向水平。

所有入口都支援 `--material ss304_annealed`、`--no-plots`、`--output-dir`。`snake_model_ropes_target_position.py` 和 `snake_model_ropes_level.py` 也支援 `--target-mm X Y Z`。

## 可選的較寬鬆目標

```bash
/opt/miniconda3/bin/python snake_model_ropes_level.py
```

這個入口使用 `rope_config_level.json` 的 `target.mode = level_tip`，從已掛 500 g、下垂的狀態開始恢復；結果在 `rope_results_level/`。

它要求末端 Y/Z = 0、合成誤差不超過 1 mm、向前伸出至少 90%（1339.2 mm，容許 1 mm 誤差）。它不代表整體水平。伸出限制避免機械臂折回根部附近而假達標。

## 反算方法與塑性歷史

預設 `search.parameterization = winch_length`，直接搜尋捲筒收放長度。每次從目前已接受狀態，試算各捲筒微調對目標誤差的影響，再用 [SciPy 有界線性最小平方](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html) 決定方向。每步最多改變 2 mm；每個候選都重新以原正向物理模型計算，只有誤差確實降低才採用。

保持水平時，上、下繩各自控制，左右捲筒使用相同收放量。XYZ 反算預設 `balanced_sides = false`，四捲筒獨立控制；非零側向目標必須使用四繩獨立控制。

遇到鬆繩時，微小收繩可能不產生張力；求解器會擴大微調探測，並使用多種步長的座標搜尋，避免將鬆弛區誤判成該捲筒無作用。

被拒絕的試算不改寫塑性歷史；採用的每步都繼承先前塑性。最後另檢查平衡殘差及局部穩定性。若沒有找到目標解，保留最佳穩定候選，並標示未達標。四個捲筒對應三維位置時，解可能不唯一；目前不額外最小化總張力或耗能。

`take_up_*_mm` 是相對初始繩長的累計量：**正數收繩、負數放繩**，單位 mm。它已包含尼龍伸長的影響。零張力時可能只是收進鬆繩，並不表示已受拉。

也保留進階的 `parameterization = tension`：先以張力預測，再按 `L_rest = L_path / (1 + T/EA)` 換算收繩量，並從同一已接受歷史以原收繩模型重新正向驗證；不直接把張力控制的預測當成解。零張力繩預留 1 mm 鬆弛裕量。

## 搜尋範圍與模型限制

預設每繩張力搜尋上限 1000 N，收繩／放繩界限各 500 mm；這些是數值界限，並非馬達或繩索額定能力。模型參考範圍另檢查尼龍應變不超過 2%、單節彎曲角不超過 0.5 rad，也不是實測材料失效界限。

`target_reached_within_screening` 表示指定目標及模型參考範圍都符合；`target_reached_extrapolated` 表示目標符合但超出參考範圍；`target_not_reached` 表示本次搜尋未達標。保持流程使用對應的 `hold_target_*` 狀態，只有完整指定載入完成才報告達標。

局部搜尋失敗不等於已證明所有可能控制路徑都不可行。結果依賴塑性歷史、初始狀態、容差、步長及搜尋界限。現有模型沒有加工硬化、接觸、自碰撞、繩索摩擦或獨立扭轉。

## 輸出與驗證

本次預設計算沒有找到達標解。保持流程三種材料均在第一個數值自重載入點（`gravity_scale = 0.05`、物體 0 g）未達標，所以沒有繼續掛載至 500 g。下表的水平候選並非正常重力下的 500 g 解。

| 骨架 | 第一個載入點的中心線最大偏差（mm） | 已掛 500 g 後反算至 (1488, 0, 0) 的末端誤差（mm） |
|---|---:|---:|
| Al 1100-O | 4.634 | 1765.468 |
| Cu C110-O60 | 4.509 | 1627.883 |
| SS 304 退火 | 2.489 | 1292.378 |

XYZ 反算的三種材料均用盡本次 400 次正向試算預算，尚未達標；這不證明所有控制路徑都不可行。位置反算另以 31 段、500 g 的一個可達局部三維目標驗證，正向回算誤差約 0.0063 mm；該彎曲形狀超出單節角度參考範圍，只作數值功能驗證，詳見 `rope_results_target_position/validation.json`。

- `inverse_summary.csv`：每材料狀態、實際負載、目標誤差、四繩收放量與張力。**未達標列的收繩量只是候選，不是目標解。**
- `inverse_results.json`：設定與材料快照、正向驗證結果、塑性狀態、控制軌跡及來源雜湊。
- `control_trace.csv`：已採用控制步的指令、張力與末端位置。
- `inverse_results.sqlite3`：獨立反算資料庫，保留各次運行。
- `inverse_level.png`：目標位置搜尋前後的 XY 投影；保持流程是 `hold_horizontal.png`。
- `load_steps.csv`：保持流程每步的重力比例、負載、四繩收放量／張力及是否達標。
- `last_level_summary.csv`：保持流程最後達標的實際載入點，須同時查看重力比例與負載。

```bash
/opt/miniconda3/bin/python -B -m unittest -v test_snake_model_ropes.py test_snake_model_ropes_level.py
```

測試涵蓋力與長度控制的等效性、正向平衡、可達的小負載目標、三維位置反算、被拒絕試算的歷史隔離、末端同高但身體彎曲的假達標、折回根部的假達標，以及部分載入不冒充完整指定負載達標。
