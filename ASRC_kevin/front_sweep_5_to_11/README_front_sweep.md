5 至 11 節前端自重模擬

本資料夾包含 Python 程式、獨立配置檔、原模型輸入快照及完整結果。原正式 11 節配置未被修改。

以 NumPy、SciPy、Matplotlib 執行：

```sh
python snake_model_front_sweep.py
python verify_front_sweep_results.py
python render_front_sweep_report.py
```

預設讀取 inputs/ 的原模型快照，結果寫入 front_sweep_results/。亦可用 --project 指定含原求解器的專案資料夾；--output-dir 可指定另一輸出位置。

study 配置位於 front_sweep_config.json；原模組與鋼棒參數仍讀取 rear_backbone_config.json、craft_data.py 與 rope_materials.json，沒有材料或尺寸縮放。

[查看完整結果與限制](front_sweep_results/RESULTS.md)
