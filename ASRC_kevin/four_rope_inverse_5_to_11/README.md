四繩逆靜力模擬：前端5–11節

執行環境：Python、NumPy、SciPy、Matplotlib。原數據快照在 inputs/；原工程模型與結果均保留。

```sh
python run_all.py --workers 4
```

依序執行獨立單元檢查、主要掃描、上下共同對拉補查、相鄰配置延續重試、最終合併、全部狀態核對與代表案例加密、圖表輸出。已保存的組別會重用。

run_rope_sweep.py 支援 --front、--rear、--workers、--output-dir；同一數據與程式雜湊的已完成組合會重用。完整圖表需預設10,170配置全部完成。

rope_planar.py 是幾何非線性、可軸向壓縮的平面有限元與四繩靜力核心；rope_three_parameter.py 補上獨立上下共同對拉模式；run_rope_sweep.py 包含主要逆解與目標判斷。

匯出單一組合的中心線座標，例如：python export_case.py H8-U12-D4-L1 head_level。

[完整結果、張力表與限制](results/RESULTS.md)；[模型方程與方法](METHODS.md)。
