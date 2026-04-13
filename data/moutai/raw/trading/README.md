# 日线行情（原始抓取）

- **来源**：Yahoo Finance，`600519.SS`（与 `config/symbols.py` 中 `moutai` 映射一致）。  
- **生成**：固定脚本重复执行即可更新：

```bash
python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data
```

- **文件**：`daily_600519_ss_yahoo.csv` — 列为 Yahoo `history` 输出（含 `auto_adjust=False` 的 OHLCV 等）。  
- **说明**：财报以本地 PDF 为准；本目录不存放财务原始表。
