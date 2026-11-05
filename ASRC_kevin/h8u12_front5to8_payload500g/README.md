H8U12後段、無骨架前端5–8節、頭部500 g

執行：

```sh
python run_all.py --workers 4
```

只在H8U12後段加Ø4.2 mm 304 backbone，前端完全沒有。模組原始數值在inputs/。

run_rope_sweep.py是上一輪搜尋方法的輔助快照；本輪由run_vertical.py設定500 g載荷後呼叫，請以run_all.py執行本輪研究。各組已有結果會重用；如修改參數或模型，先將results重新命名保存，再重新執行，避免重用舊組別。

[完整結果與限制](results/RESULTS.md)

最大彎曲若未找到符合205 MPa及自碰撞／穩定要求的平衡，角度與對應力保持空白；不要把空白讀成0。
