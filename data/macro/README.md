# 宏观数据 `data/macro/`

| 路径 | 说明 |
|------|------|
| **`series/`** | **标准化时间序列** `{id}.csv`（`date`, `value`），由抓取脚本写入。 |
| **`run_meta.json`** | 最近一次抓取元数据（根目录下，与 `series/` 并列）。 |
| **`raw/`** | 自下载宏观原始表（如 World Bank 导出的 `Macro-indicators.csv` + Metadata）。 |

## 本地 CSV → 季度宏观因子（推荐，无需联网）

将 `raw/` 中宽表转为 **`factors/macro/series/`** 下季度序列（见 `factors/macro/README.md`）：

```bat
python -m value_investment_agent.ingestion.macro_raw_to_factors
```

配置：`config/macro_raw_to_factors.json`。

---

**以下为可选：从网上抓取 FRED/akshare（若你未自下载数据）**  

**定义**：`config/macro_indicators.json` + `factors/macro/README.md`  
**命令**（在项目根目录）：

```bat
python -m pip install akshare yfinance pandas requests
set FRED_API_KEY=你的FRED密钥
python -m value_investment_agent.ingestion.fetch_macro_series --years 5
```

- **美国**：联邦基金、目标区间中点、核心/总体 PCE 同比 **需 [FRED API Key](https://fred.stlouisfed.org/docs/api/api_key.html)**。  
- **未设密钥时**：仅 **`us_treasury_10y_yield`** 会用 Yahoo **`^TNX`** 作备用（`run_meta.json` 的 `warnings` 会注明）。  
- **中国**：LPR、中美国债表、CPI 同比依赖 **`akshare`**（网络需能访问数据源）。
