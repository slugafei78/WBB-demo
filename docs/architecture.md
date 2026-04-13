# 项目架构与目录设计

本文描述**仓库物理布局**与 **`value_investment_agent` 包内模块分工**；与「某文件从哪来到哪去」的逐步对照见 [`DATA_FLOW.md`](DATA_FLOW.md)。需求级 Agent 划分见 [`REQUIREMENTS.md`](REQUIREMENTS.md)、总体设计见 [`DESIGN.md`](DESIGN.md)。

---

## 1. 仓库顶层目录（当前）

```
wbb-demo/
├── config/                    # 全局 JSON：因子池、财报指标 variant、宏观抓取与转换等
├── data/                      # 原始 / 准原始落盘（宏观 + 按 slug 的标的）
├── docs/                      # 设计、架构、数据流说明
├── factors/                   # 因子层：宏观序列、按标的的 quantitative / qualitative 等
├── prompts/                   # 共享 LLM 提示词（如 qualitative_subagent 五步）
├── valuations/                # 估值层：按标的、按方法的配置与产出（与 data、factors 并列）
├── tests/                     # pytest
├── pyproject.toml
└── value_investment_agent/    # Python 包（见 §3）
```

**与旧版文档的差异（需牢记）：**

- 除 **`data/`**、**`factors/`** 外，增加与二者**并列**的 **`valuations/`**，存放估值结果与方法专用 `config.json`（例如茅台 PE 内在价值序列与叠加图），避免与因子目录混放。
- **全局研究配置**在仓库根目录 **`config/`**（JSON）；**个股流水线参数**在 **`factors/{symbol}/config/`**（如 `quant_extract.json`、`qualitative_subagent.json`），二者不要混淆。
- **`value_investment_agent/config/`** 仅含 **`symbols.py`** 等代码（slug ↔ Yahoo / SEC 映射），不是根目录 `config/` 的 JSON。

---

## 2. `data/`、`factors/`、`valuations/`：谁放什么

**原则：先按「层」，再分「宏观」与「按标的」。**

| 层 | 路径 | 含义 |
|----|------|------|
| 原始 | **`data/macro/raw/`**、**`data/{slug}/raw/`**（`trading/`、`financials/`、`news/` 等） | 抓取、下载、手工归档；保留来源与原始 schema |
| 因子 | **`factors/macro/series/`**、**`factors/{slug}/quantitative|qualitative|…`** | 清洗、对齐、LLM 打分后的时间序列或表，供多业务复用 |
| 估值 | **`valuations/{slug}/{method}/`**（如 `moutai/pe/`） | 在因子（及必要时 `data/`）上按方法计算的结论、元数据与说明 |

**个股 slug** 与代码一致，统一小写：**`cola`、`moutai`、`txrh`**（见 `value_investment_agent/config/symbols.py`）。**`factors/macro/`** 与 **`factors/{slug}/`** 并列，**不在**个股目录下再嵌套 `macro/`。

**宏观血缘（简写）：** `data/macro/raw/` 宽表或抓取脚本 → `ingestion.macro_raw_to_factors` / `fetch_macro_series` 等 → **`factors/macro/series/`**（标准化时间序列）。抓取定义见根目录 **`config/macro_indicators.json`**、转换参数见 **`config/macro_raw_to_factors.json`**。

**个股 `data/{slug}/raw/` 典型子目录：** `trading/`、`financials/`、`news/`；设计稿中的 `mdna/` 可按需增加，与 `data/README.md` 一致即可。

---

## 3. `value_investment_agent` 包结构（与代码对齐）

```
value_investment_agent/
├── __init__.py                 # 懒加载 ViAgent，避免 import 即拉满 pydantic 等
├── config/
│   └── symbols.py              # slug ↔ Yahoo ticker、SEC CIK 等
├── vi_agent/
│   ├── core.py                 # ViAgent：主编排（当前与 QualitativeSubAgent 能力对齐，可扩展）
│   ├── run_cola_pipeline.py    # cola 示例 CLI
│   └── run_moutai_flow.py      # 转发至 moutai_experiment.run_moutai_flow
├── agents/                     # LLM 子流程：定性两回合、retrieval、llm_client
├── llm/                        # 底层 Gemini/OpenAI 调用与 JSON completion 辅助
├── ingestion/                  # 无 LLM 数据采集与宏观转换
│   ├── data_fetch.py           # Yahoo 行情/新闻等（新闻解析见 yahoo_news_items）
│   ├── yahoo_news_items.py     # yfinance news 新旧结构解析（供 digest 与 data_fetch 共用）
│   ├── fetch_macro_series.py   # 按 macro_indicators.json 拉宏观序列
│   └── macro_raw_to_factors.py # 宏观宽表 → factors/macro/series
├── moutai_experiment/          # 茅台专用：抓取、定量抽取、五步定性、季度 PE 内在价值等
├── factor_pipeline/            # 通用因子侧：LLM 定性 0–20、intrinsic 序列等（可被多标的复用）
├── synthesis/                  # Parameter Synthesizer：rules + MLP
├── valuation/                  # 估值核：DCF、P/S、PB-ROE、runner、pe_macro_qual、叠加图
├── models/                     # Fm 网络（如 fm_net）
├── training/                   # Fi/Fm 与 MLP synthesizer 训练入口
├── eval/                       # 指标与基线
├── backtest/                   # 可视化等
├── factors/                    # Pydantic / JSON schema（llm_schemas 等；非磁盘 factors/）
├── examples/                   # smoke_demo 等
├── pipeline/                   # 兼容：run_ko_pipeline → vi_agent.run_cola_pipeline
└── agent/                      # 兼容：重导出 agents + ViAgent
```

**模块职责速查：**

| 目录 | 职责 |
|------|------|
| **`vi_agent/`** | 对外主入口之一：`ViAgent`、`run_cola_pipeline`；茅台简化看板命令可经 `run_moutai_flow` 转发 |
| **`agents/`** | `QualitativeSubAgent`、router/qualitative 解析、与 `factor_pipeline` 协同 |
| **`moutai_experiment/`** | `fetch_moutai_raw_data`、`download_moutai_quantitative_raw`、`extract_moutai_quantitative`、`run_moutai_qualitative_subagent`、`pe_intrinsic_quarterly`、`news_digest`（Yahoo 标题并入 CSV）等 |
| **`factor_pipeline/`** | `llm_qualitative`、`intrinsic_series` 等与标的无关或可复用的管线逻辑 |
| **`ingestion/`** | Yahoo/SEC 等原始拉取；宏观序列与宽表转换 |
| **`valuation/`** | 符号估值核与 `plot_price_vs_pe_intrinsic_overlay` |
| **`synthesis/`** | `rules_synthesizer`、`mlp_synthesizer` |
| **`factors/`（包内）** | `llm_schemas`、`schemas`：结构化输出契约，**不是**仓库根下磁盘目录 `factors/` |

### 3.1 English: package layout and roles

Same tree as above; comments are translated for readers who prefer English.

```
value_investment_agent/
├── __init__.py                 # Lazy-load ViAgent so `import value_investment_agent` does not eagerly pull pydantic and other heavy deps
├── config/
│   └── symbols.py              # slug ↔ Yahoo ticker, SEC CIK, etc.
├── vi_agent/
│   ├── core.py                 # ViAgent: top-level orchestration (currently aligned with QualitativeSubAgent; intended to grow)
│   ├── run_cola_pipeline.py    # CLI for the cola reference pipeline
│   └── run_moutai_flow.py      # Thin wrapper → moutai_experiment.run_moutai_flow
├── agents/                     # LLM subflows: two-turn qualitative, retrieval, llm_client
├── llm/                        # Low-level Gemini/OpenAI calls and JSON-completion helpers
├── ingestion/                  # Non-LLM ingestion and macro transforms
│   ├── data_fetch.py           # Yahoo prices/news, etc. (news field parsing lives in yahoo_news_items)
│   ├── yahoo_news_items.py     # Old vs new yfinance `news` payload shapes; shared by digest + data_fetch
│   ├── fetch_macro_series.py   # Pull macro series per repo-root config/macro_indicators.json
│   └── macro_raw_to_factors.py # Macro wide tables → factors/macro/series
├── moutai_experiment/          # Moutai-specific: fetch, quantitative extract, five-step qualitative, quarterly PE intrinsic value, etc.
├── factor_pipeline/            # Reusable factor side: LLM qualitative 0–20, intrinsic series, etc.
├── synthesis/                  # Parameter synthesizer: rule-based + MLP paths
├── valuation/                  # Valuation kernels: DCF, P/S, PB-ROE, runners, pe_macro_qual, price–intrinsic overlays
├── models/                     # Fm-style nets (e.g. fm_net)
├── training/                   # Training entry points for Fi/Fm and the MLP synthesizer
├── eval/                       # Metrics and baselines
├── backtest/                   # Visualization and related tooling
├── factors/                    # Pydantic / JSON contracts (llm_schemas, etc.) — not the on-disk repo factors/ tree
├── examples/                   # smoke_demo and similar
├── pipeline/                   # Compatibility: run_ko_pipeline → vi_agent.run_cola_pipeline
└── agent/                      # Compatibility: re-exports agents + ViAgent
```

**Module roles (quick reference, English):**

| Path | Role |
|------|------|
| **`vi_agent/`** | Primary user-facing entry: `ViAgent`, `run_cola_pipeline`; the simplified Moutai dashboard CLI is forwarded via `run_moutai_flow` |
| **`agents/`** | `QualitativeSubAgent`, router / qualitative JSON parsing, coordination with `factor_pipeline` |
| **`moutai_experiment/`** | `fetch_moutai_raw_data`, `download_moutai_quantitative_raw`, `extract_moutai_quantitative`, `run_moutai_qualitative_subagent`, `pe_intrinsic_quarterly`, `news_digest` (append Yahoo headlines into CSV), etc. |
| **`factor_pipeline/`** | Cross-ticker or reusable pipeline pieces: `llm_qualitative`, `intrinsic_series`, … |
| **`ingestion/`** | Raw Yahoo/SEC pulls; macro series and wide-table conversion |
| **`valuation/`** | Symbolic valuation kernels and `plot_price_vs_pe_intrinsic_overlay` |
| **`synthesis/`** | `rules_synthesizer`, `mlp_synthesizer` |
| **`factors/` (inside the package)** | `llm_schemas`, `schemas`: structured I/O contracts — **not** the repository’s on-disk **`factors/`** data directory |

---

## 4. 配置与提示词（跨目录）

| 位置 | 内容 |
|------|------|
| **`config/fundamental_factors.json`** | 全局定量 + 定性因子 ID、量纲、解释性字段（如 `interpretation_*`） |
| **`config/global_metrics.json`** | 财报衍生指标 variant、与定量因子交叉引用 |
| **`config/macro_indicators.json`** | 宏观序列抓取定义（FRED/akshare 等） |
| **`config/macro_raw_to_factors.json`** | 宏观宽表 → `factors/macro/series` |
| **`factors/{slug}/config/*.json`** | 该股定量抽取、定性 Subagent 路径与参数 |
| **`prompts/qualitative_subagent/`** | 五步共享 Markdown；个股可通过 JSON 中 `prompts_dir` 覆盖 |

---

## 5. 功能模块 vs Agent

**固定 2 个 Agent**（与 `REQUIREMENTS.md` §3.6、`DESIGN.md` 一致）：

- **ViAgent（主）**：整体流程与多轮交互编排。  
- **Qualitative Factors Subagent**：定性因子与重大新闻驱动的打分（量纲以 `fundamental_factors.json` 为准，如 **0–10、步长 0.5**；茅台简化实验另有 `qual_four` 等）。

采集、量化因子、Synthesizer、NN、回测等为**普通 Python 模块**，由主 Agent 或 CLI 调用，**不**再包装为独立 Agent。

---

## 6. 与架构图的对应关系（更新）

| 架构图元素 | 仓库落点 |
|------------|----------|
| Raw data | `data/{slug}/raw/*`、`data/macro/raw/*` + `ingestion/` |
| Factors pool | `factors/macro/series/*`、`factors/{slug}/*` + `factor_pipeline/`、`moutai_experiment/`（标的专用 ETL） |
| 全局配置 | 根目录 `config/*.json` + `value_investment_agent/config/symbols.py` |
| Qualitative Subagent + Prompt | `agents/`、`prompts/qualitative_subagent/`、`factor_pipeline/llm_qualitative.py`、`moutai_experiment/run_moutai_qualitative_subagent.py` |
| Parameter Synthesizer | `synthesis/` |
| 估值核（Fi） | `valuation/`（DCF、P/S、PB-ROE 等） |
| 估值产出与专用配置 | **`valuations/{slug}/{method}/`** |
| NN（Fm） | `models/` + `training/` |
| 回测 / 评估 | `backtest/`、`eval/` |
| 总编排 | `vi_agent/core.py`（`ViAgent`） |

---

## 7. 命名说明

- **`cola` / `moutai` / `txrh`**：用户与目录面向的 **slug**；Yahoo 代码等为 **`YAHOO_TICKER_BY_SYMBOL`** 中的实现细节。  
- **`ViAgent`**：总价值代理；当前实现与 `QualitativeSubAgent` 的两回合能力对齐，后续可扩展串联 ingestion、估值与回测。  
- **磁盘 `factors/`** 与 **包 `value_investment_agent.factors`** 同名不同物：前者为数据产物目录，后者为 schema 代码包。

---

## 8. 常用入口（便于对照架构）

| 目的 | 命令或模块（均在仓库根执行） |
|------|------------------------------|
| cola 示例全流程 | `python -m value_investment_agent.vi_agent.run_cola_pipeline` |
| 茅台日线 + digest 合并 | `python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data` |
| Yahoo 标题追加 digest | `append_yahoo_headlines_to_digest`（见 `moutai_experiment.news_digest`）或 `run_moutai_flow --refresh-yahoo-news` |
| 茅台定量长表 | `download_moutai_quantitative_raw` → `extract_moutai_quantitative` |
| 茅台五步定性 | `python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent` |
| 茅台季度 PE 内在价值 | `python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly` |
| 股价 vs 内在价值图 | `python -m value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay` |
| 冒烟演示 | `python -m value_investment_agent.examples.smoke_demo` |

更完整的文件级输入输出表见 [`DATA_FLOW.md`](DATA_FLOW.md)。
