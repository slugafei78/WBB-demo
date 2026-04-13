# 数据流（Data flow）

仓库内与 **标的研究 / 因子 / 估值** 相关的主线：**原始**素材落在 **`data/`**，**因子**时间序列在 **`factors/`**，**估值**结论与方法配置在 **`valuations/`**（与 `data/`、`factors/` 并列）。全局定义与提示词在仓库根 **`config/*.json`**、**`prompts/`**；代码包内 **`value_investment_agent/config/symbols.py`** 仅负责 slug ↔ 行情/SEC 映射（见 [`architecture.md`](architecture.md)）。

**全市场宏观**（CPI / PCE / 利率等）通常先于或并行于个股产出，落在 **`factors/macro/series/`**（原始抓取与转换路径见下文 **§1**）。本节主图以 **单股茅台 `moutai`** 为例，自 **`data/moutai/`** 起画到 **`valuations/moutai/`**，对应你描述的四层结构。

---

## 单股端到端数据流（以茅台 `moutai` 为例）

### 文字说明（中文）

1. **原始数据输入层 — `data/moutai/`**  
   - **`raw/trading/`**：日频交易数据，如 `daily_600519_ss_yahoo.csv`（Yahoo `600519.SS`）。  
   - **`raw/news/`**：新闻 digest，如 `news_digest.csv`（可合并模板行、追加 Yahoo 标题）。  
   - **`raw/financials/`**：三张财务报表相关的结构化原始/准原始表（典型为东财导出：`profit_sheet_quarterly_em.csv`、`balance_sheet_by_report_em.csv`、`cash_flow_sheet_quarterly_em.csv`；另可有 PDF 抽取文本、手工补充 CSV 等）。  
   - **`analysis/`**：人工深度分析或研究长文（如 `moutai_fundamental_analysis.md`），供定性 Subagent 通过 `human_dialogue_path` 等引用。  

2. **个股因子层 — `factors/moutai/`（季度粒度）**  
   由 `data/moutai/` 与全局配置抽取、打分得到的 **基本面因子**，与 `config/fundamental_factors.json` 对齐，主要包括：  
   - **`quantitative/`**：季度定量宽表，如 `moutai_fundamental_quant_quarterly.csv`。  
   - **`qualitative/`**：季度定性因子分，如 `moutai_qual_quarterly_scores.csv`（及 `review/` 下五步过程产物）。  

3. **宏观因子层 — `factors/macro/`（对所有个股有效）**  
   存放全市场共用的宏观时间序列（经清洗/对齐后的 CPI、PCE、政策利率等，文件形如 `factors/macro/series/macro_*_*.csv`）。**PE 季度内在价值**示例会读取配置中指定的一条（如中国存款利率序列）与个股因子一起进入估值核。  

4. **估值输出层 — `valuations/moutai/`（按方法分目录，如 `pe/`、`dcf/`）**  
   - **`pe/intrinsic_quarterly.csv`**：在同一季度行上同时给出 **未用定性因子修正**的每股内在价值（列 **`intrinsic_per_share_pe_simple`**，对应宏观锚定 PE × 盈利的路径），以及 **经定性乘子与上下限裁剪后**的每股内在价值（列 **`intrinsic_per_share_pe_qual_adjusted`**；中间列含 `qual_pe_multiplier`、`pe_after_qual` 等便于审计）。  
   - **`pe/moutai_price_vs_pe_intrinsic_overlay.png`**：日线价格与内在价值曲线等的**直观叠加图**。  
   - **DCF** 等其它方法可在 `valuations/moutai/dcf/` 等目录按同一分层思想扩展；当前仓库以 **PE 季度流水线**示例为主。  

### 流程图（中文）

以下建议用**等宽字体**阅读；箭头表示数据依赖方向（先有个股因子与宏观因子，再出估值与图）。

```
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (1) 原始数据输入层   data/moutai/                                                                                                                       │
  │      raw/trading/daily_600519_ss_yahoo.csv                                                                                                               │
  │      raw/news/news_digest.csv                                                                                                                            │
  │      raw/financials/   → 利润表 / 资产负债表 / 现金流量表 等（如 em/*.csv；及 PDF 文本、手工表）                                                           │
  │      analysis/       → 人工基本面长文、研究笔记（*.md 等）                                                                                               │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                                  │
                                          extract_moutai_quantitative  ·  run_moutai_qualitative_subagent  ·  config + prompts
                                                                                                  │
                                                                                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (2) 个股因子层（季度）   factors/moutai/                                                                                                                │
  │      quantitative/moutai_fundamental_quant_quarterly.csv                                                                                                 │
  │      qualitative/moutai_qual_quarterly_scores.csv   （及 qualitative/review/ 过程文件）                                                                   │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                                  │
                    (3) 宏观因子层（全市场）  factors/macro/series/*.csv  ·  CPI / PCE / 利率等；与 (2) 并行，经 valuations/moutai/pe/config.json 指定路径读入估值核
                                                                                                  │
                                                                                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (4) 估值输出层   valuations/moutai/                                                                                                                       │
  │      pe/config.json  →  pe_intrinsic_quarterly  →  pe/intrinsic_quarterly.csv                                                                            │
  │          · 含「未用定性修正」每股内在价值：intrinsic_per_share_pe_simple                                                                                    │
  │          · 含「定性修正后」每股内在价值：intrinsic_per_share_pe_qual_adjusted（及 qual_pe_multiplier、pe_after_qual 等）                                     │
  │      pe/moutai_price_vs_pe_intrinsic_overlay.png   ←  plot_price_vs_pe_intrinsic_overlay（日线 + 内在价值等）                                              │
  │      （其它方法如 DCF 可置于 valuations/moutai/dcf/ …，按同一 data → factors → valuations 思想扩展）                                                       │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Narrative (English)

1. **Raw input layer — `data/moutai/`**  
   - **`raw/trading/`**: daily OHLCV, e.g. `daily_600519_ss_yahoo.csv`.  
   - **`raw/news/`**: news digest, e.g. `news_digest.csv`.  
   - **`raw/financials/`**: structured inputs for the **three financial statements** (e.g. EM exports: `profit_sheet_quarterly_em.csv`, `balance_sheet_by_report_em.csv`, `cash_flow_sheet_quarterly_em.csv`; plus optional PDF text extracts and manual CSVs).  
   - **`analysis/`**: human-written fundamentals / research notes (e.g. `*.md`) referenced by the qualitative pipeline.  

2. **Per-ticker factor layer — `factors/moutai/` (quarterly)**  
   Fundamental factors derived from `data/moutai/` under global definitions:  
   - **`quantitative/`**: quarterly wide table, e.g. `moutai_fundamental_quant_quarterly.csv`.  
   - **`qualitative/`**: quarterly qualitative scores, e.g. `moutai_qual_quarterly_scores.csv` (plus `review/` artefacts).  

3. **Macro factor layer — `factors/macro/` (cross-ticker)**  
   Economy-wide time series (CPI, PCE, interest rates, …) as `factors/macro/series/*.csv`. The sample **PE intrinsic** job reads whichever series `valuations/moutai/pe/config.json` points to (e.g. deposit rate) **together with** the moutai factor CSVs.  

4. **Valuation output layer — `valuations/moutai/` (by method: `pe/`, `dcf/`, …)**  
   - **`pe/intrinsic_quarterly.csv`**: per quarter, **plain** intrinsic value per share without the qualitative modulation (**`intrinsic_per_share_pe_simple`**) and **qual-adjusted** intrinsic per share (**`intrinsic_per_share_pe_qual_adjusted`**, with `qual_pe_multiplier`, `pe_after_qual`, … for audit).  
   - **`pe/moutai_price_vs_pe_intrinsic_overlay.png`**: overlay of market prices vs intrinsic tracks for quick visual read.  
   - **DCF** and other kernels can live under `valuations/moutai/dcf/` following the same layering. The repo currently stresses the **quarterly PE** path.  

### Flow diagram (English)

```
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (1) Raw inputs        data/moutai/                                                                                                                      │
  │      raw/trading/daily_600519_ss_yahoo.csv                                                                                                               │
  │      raw/news/news_digest.csv                                                                                                                            │
  │      raw/financials/   → P&L, balance sheet, cash flow tables (e.g. em/*.csv; PDF text; manual CSVs)                                                     │
  │      analysis/       → human fundamentals / notes (*.md, …)                                                                                              │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                                  │
                                          extract_moutai_quantitative  ·  run_moutai_qualitative_subagent  ·  config + prompts
                                                                                                  │
                                                                                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (2) Ticker factors (quarterly)   factors/moutai/                                                                                                          │
  │      quantitative/moutai_fundamental_quant_quarterly.csv                                                                                                 │
  │      qualitative/moutai_qual_quarterly_scores.csv   (+ qualitative/review/ artefacts)                                                                    │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                                  │
                    (3) Macro layer (all tickers)  factors/macro/series/*.csv  ·  CPI / PCE / rates … ; read in parallel with (2) per valuations/moutai/pe/config.json
                                                                                                  │
                                                                                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  (4) Valuation outputs   valuations/moutai/                                                                                                              │
  │      pe/config.json  →  pe_intrinsic_quarterly  →  pe/intrinsic_quarterly.csv                                                                             │
  │          · per-share intrinsic **without** qual adjustment: intrinsic_per_share_pe_simple                                                                 │
  │          · per-share intrinsic **with** qual adjustment: intrinsic_per_share_pe_qual_adjusted (+ qual_pe_multiplier, pe_after_qual, …)                   │
  │      pe/moutai_price_vs_pe_intrinsic_overlay.png   ←  plot_price_vs_pe_intrinsic_overlay (daily prices + intrinsic tracks)                               │
  │      (Other methods, e.g. DCF under valuations/moutai/dcf/, follow the same data → factors → valuations idea.)                                          │
  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. 宏观（全市场）

| 阶段 | 原始 / 输入文件 | 处理入口 | 产出文件 |
|------|-----------------|----------|----------|
| 宽表 → 因子序列 | `data/macro/raw/Macro-indicators.csv`（及可选 `Macro-indicators - Metadata.csv`） | `python -m value_investment_agent.ingestion.macro_raw_to_factors`（配置 `config/macro_raw_to_factors.json`） | `factors/macro/series/macro_{CC}_{SERIES}.csv`、`*.meta.json`、`macro_indicator_catalog.json`、`run_convert_meta.json` |
| API / 多源直连 | `config/macro_indicators.json`（序列定义：FRED、akshare 等） | `python -m value_investment_agent.ingestion.fetch_macro_series` | 默认 **`data/macro/series/*.csv`**（见配置中 `output_dir`） |

**估值消费示例（当前仓库默认）**：`factors/macro/series/macro_CHN_FR_INR_DPST.csv`（中国存款利率，季度）→ `pe_intrinsic_quarterly`（路径由 `valuations/moutai/pe/config.json` 的 `macro_deposit_csv` 指定）。若改用 `data/macro/series/` 下文件，需自行对齐列名 / 增加转换或改写配置。

---

## 2. 茅台（moutai）`data/moutai/`：原始 `raw/` 与手工 `analysis/`

| 阶段 | 原始 / 输入 | 处理入口 | 产出文件 |
|------|-------------|----------|----------|
| 行情 | Yahoo `600519.SS` | `python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data` | `data/moutai/raw/trading/daily_600519_ss_yahoo.csv` |
| 新闻 digest | 内置补充行 + 已有表 | `fetch_moutai_raw_data`（可 `--no-trading`）合并模板行 | `data/moutai/raw/news/news_digest.csv` |
| Yahoo 新闻标题 | Yahoo / yfinance `Ticker.news` | `value_investment_agent.moutai_experiment.news_digest.append_yahoo_headlines_to_digest`，或 `run_moutai_flow --refresh-yahoo-news` | 按 URL 去重**追加**至同一 `news_digest.csv` |
| 东财宽表 | akshare 等 | `python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw` | `data/moutai/raw/financials/em/profit_sheet_quarterly_em.csv` 等 |
| 财报 PDF | 用户放入 | `python -m value_investment_agent.moutai_experiment.extract_moutai_quantitative`（抽取文本） | `data/moutai/raw/financials/_extracted_text/*.txt` |
| 手工/补充表 | 用户维护（可选） | — | `data/moutai/raw/financials/quarterly_financials_manual.csv`、`net_profit_quarterly.csv` 等 |
| 人工分析 `analysis/` | 用户维护 | — | `data/moutai/analysis/*.md` 等（典型如 `moutai_fundamental_analysis.md`；路径由 `qualitative_subagent.json` 的 `human_dialogue_path` 指向） |

---

## 3. 茅台因子层 `factors/moutai/`

| 阶段 | 主要输入 | 配置 | 处理入口 | 产出文件 |
|------|----------|------|----------|----------|
| 定量长表 | `data/moutai/raw/financials/**`（含 `em/*.csv`、manual、net_profit、PDF 文本等） | `factors/moutai/config/quant_extract.json` | `python -m value_investment_agent.moutai_experiment.extract_moutai_quantitative` | `factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv`、`moutai_quant_extract_meta.json` |
| 定性 Subagent | `config/fundamental_factors.json`、`data/moutai/raw/news/news_digest.csv`、`data/moutai/raw/financials/**`（摘要）、`human_dialogue_path` 文档、共享 `prompts/qualitative_subagent/*.md` | `factors/moutai/config/qualitative_subagent.json` | `python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent` | `factors/moutai/qualitative/review/step01_*.md` … `step05_*.json`、`moutai_qual_quarterly_scores.csv`、`run_qual_subagent_meta.json` |

---

## 4. 茅台估值层 `valuations/moutai/pe/`

| 阶段 | 主要输入 | 配置 | 处理入口 | 产出文件 |
|------|----------|------|----------|----------|
| 季度 PE 内在价值 | `factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv`、`factors/moutai/qualitative/moutai_qual_quarterly_scores.csv`、`factors/macro/series/macro_CHN_FR_INR_DPST.csv` | `valuations/moutai/pe/config.json` | `python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly` | `valuations/moutai/pe/intrinsic_quarterly.csv`（含 **`intrinsic_per_share_pe_simple`** 与 **`intrinsic_per_share_pe_qual_adjusted`** 等列）、`intrinsic_quarterly_meta.json` |
| 价格 vs 内在价值图 | `data/moutai/raw/trading/daily_600519_ss_yahoo.csv`、`intrinsic_quarterly.csv`、`moutai_qual_quarterly_scores.csv` | CLI 默认路径 | `python -m value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay` | `valuations/moutai/pe/moutai_price_vs_pe_intrinsic_overlay.png` |

---

## 5. 其他入口（简记）

| 模块 | 典型输出位置 | 说明 |
|------|--------------|------|
| `moutai_experiment.run_moutai_flow` | 默认 `data/moutai_run/` | 季度 Fi 看板类流程（与上表 PE 估值流水线独立） |
| `vi_agent.run_cola_pipeline` | 默认 `data/cola_run/` | cola 示例管线 |

---

## 6. 配置文件速查

| 文件 | 作用 |
|------|------|
| `config/fundamental_factors.json` | 全局定量 + 定性因子定义、量纲与解释性字段（如 `interpretation_*`） |
| `config/global_metrics.json` | 财报衍生指标 variant、与定量因子交叉引用 |
| `config/macro_indicators.json` | 宏观序列抓取定义（`fetch_macro_series`） |
| `config/macro_raw_to_factors.json` | 宏观宽表 → `factors/macro/series/` |
| `factors/moutai/config/quant_extract.json` | 定量合并：输入 `data/` 路径、输出 `factors/.../moutai_fundamental_quant_quarterly.csv` |
| `factors/moutai/config/qualitative_subagent.json` | 定性五步：输出目录、`human_dialogue_path`、LLM 等 |
| `valuations/moutai/pe/config.json` | PE 季度内在价值：输入因子 CSV、宏观 CSV、定性锚点、输出 `intrinsic_quarterly.csv` |

更细目录约定见：`data/README.md`、`factors/README.md`、`valuations/README.md`、`factors/moutai/README.md`、`valuations/moutai/pe/README.md`、`config/README.md`。包与磁盘目录对照见 [`architecture.md`](architecture.md)。
