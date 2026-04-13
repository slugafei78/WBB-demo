# moutai（贵州茅台）

- 标的 slug：`moutai`；行情映射见 `value_investment_agent.config.symbols`。

## 简化 Fi 流程（季度双曲线 + 五年图）

```bash
python -m value_investment_agent.moutai_experiment.run_moutai_flow --years 5 --llm mock
# 有 Gemini/OpenAI 时去掉 --llm mock，或 --refresh-yahoo-news 追加 Yahoo 标题到 digest
```

输出默认：`data/moutai_run/moutai_dashboard.png`、`fi_quarterly.csv`、`qual_four.json`。

## 一键抓取 / 合并（推荐）

**首次**：在项目根目录安装依赖（至少 pandas、yfinance；推荐整包可编辑安装）：

```bash
cd C:\Users\PC\Projects\wbb-demo
python -m pip install -e .
```

（抓取脚本已避免在导入时加载 `pydantic` 等整包依赖；若仍报错缺库，再执行上面命令。）

在项目根目录执行（需网络访问 Yahoo）：

```bash
python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data
```

- 写入 **`raw/trading/daily_600519_ss_yahoo.csv`**（默认过去约 5 年日线）。  
- 将内置 **提价 / i茅台** 等摘要行合并进 **`raw/news/news_digest.csv`**（同一日期不覆盖已有行）。  
- 仅行情：`... fetch_moutai_raw_data --no-news`；仅合并新闻：`... --no-trading`（仍建议先有一次日线）。

财报 PDF 请自行放入 `raw/financials/`，脚本不下载 PDF。

## 基本面因子（季度）

**定量**（原始东财表请先下载到 **`data/moutai/raw/financials/em/`**，再合并；见 `README_net_profit.md`）：

```bash
python -m pip install -e ".[moutai]"
python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw
python -m value_investment_agent.moutai_experiment.extract_moutai_quantitative
```

输出：`factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv`

**定性**（五步 Subagent，**共享**提示词见 `prompts/qualitative_subagent/`；该股参数见 `factors/moutai/config/`）：

```bash
python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent --llm mock
```

配置：`factors/moutai/config/qualitative_subagent.json`（`top_n_qualitative_factors` 默认 10）。定量抽取配置见同目录 `quant_extract.json`；约定说明见 `factors/moutai/README.md`。

## `raw/` 四类原始数据

| 子目录 | 内容 |
|--------|------|
| `trading/` | **`daily_600519_ss_yahoo.csv`**：由上述脚本生成；Yahoo 日线 OHLCV |
| `financials/` | 财报 **PDF**；**`em/`** 东财下载的原始宽表；**`sina/`** 可选新浪表；手工表见 **`quarterly_financials_manual.csv`** 等（见 `README_net_profit.md`） |
| `news/` | **`news_digest.csv`**：重大新闻一行（日期、摘要、URL） |
| `mdna/` | MD&A 文本（可选） |
