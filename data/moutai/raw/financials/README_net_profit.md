# 本地财报数值（可选）

## 东财原始宽表（推荐：下载到 `data/`，不进 `factors/`）

从东方财富拉取的 **原始** quantitative 宽表应落在：

- `financials/em/profit_sheet_quarterly_em.csv`
- `financials/em/cash_flow_sheet_quarterly_em.csv`
- （可选）`financials/sina/*.csv` — 新浪财经三大表

在项目根执行：

```bash
python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw
python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw --sina
```

元数据：`financials/em/download_meta.json`。合并后的 **长表** 仍由 `extract_moutai_quantitative` 写入 `factors/moutai/quantitative/`（加工结果）；`quant_extract.json` 中 `prefer_em_downloaded_csv` 为 true 时优先读上述 CSV。

## `net_profit_quarterly.csv`（单列净利润）

若希望**完全使用本地财报**而非 Yahoo，可在同目录放置：

**文件名：** `net_profit_quarterly.csv`

**列：**

- `period_end`：季度末日，格式 `YYYY-MM-DD`
- `net_profit`：归属母公司净利润（与报表一致单位，如「元」）

`extract_moutai_quantitative` 会将其映射为因子 `net_profit_attributable`（优先级高于 Yahoo，低于下方宽表）。

## `quarterly_financials_manual.csv`（推荐：与 PDF 一致的多指标宽表）

**原因**：Yahoo Finance 对 `600519.SS` 等 A 股季报往往只返回**最近约 4 个季度**的列，无法覆盖「完整约 5 年」；PDF 在仓库中仅做文本归档，**不自动从 PDF 抽数**。

**做法**：从年报/季报 PDF 手工或表格工具整理为宽表，复制 `quarterly_financials_manual.example.csv` 为 **`quarterly_financials_manual.csv`**（与 `factors/moutai/config/quant_extract.json` 中 `manual_quarterly_csv` 一致），按列填写：

- `period_end`（必填）
- 可选列（单位与报表一致）：`net_income`、`net_profit_attributable`、`net_profit`（同归母）、`gross_profit`、`operating_profit` / `operating_income`、`capex`、`free_cash_flow` / `fcf`、`debt_to_equity`

列名使用英文蛇形；合并时**该文件优先级最高**。

## 自动补历史（可选）

安装 `pip install -e ".[moutai]"`（含 `akshare`）后，`extract_moutai_quantitative` 可尝试从新浪财经拉取更长历史（仍可能受数据源限制）。详见 `factors/moutai/config/quant_extract.json` 中 `use_akshare`。
