# 宏观时间序列（`data/macro/series/`）

- **定义与业务含义**：见 **`factors/macro/README.md`**；机读抓取清单见 **`config/macro_indicators.json`**。  
- **生成**：在项目根目录执行：

```bash
set FRED_API_KEY=你的密钥
python -m pip install akshare
python -m value_investment_agent.ingestion.fetch_macro_series --years 5
```

- **文件**：每个指标一个 **`{id}.csv`**，列为 `date`, `value`。  
- **元数据**：同目录上级 `data/macro/run_meta.json` 记录抓取时间、行数与错误信息。
