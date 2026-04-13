# Value investment agent

Neuro-symbolic stack: symbolic **Fi** (DCF / P/S / PB-ROE), neural **Fm**, parameter synthesizer, **ViAgent** 编排与 LLM 子流程。标的目录名使用 slug：`cola`、`moutai`、`txrh`（行情 API 映射见 `value_investment_agent.config.symbols`）。

**数据流（原始 → 因子 → 估值）**：见 [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md)。

Install: `pip install -e ".[dev]"`

Run smoke test: `python -m value_investment_agent.examples.smoke_demo`

## cola 示例全流程（数据 → LLM 0–20 分 → DCF Fi → 图表）

```bash
set SEC_USER_AGENT=YourName you@example.com

python -m value_investment_agent.vi_agent.run_cola_pipeline --years 10 --freq annual
```

LLM 默认 **`auto`**：**优先 Gemini**（`GEMINI_API_KEY` / `GOOGLE_API_KEY`），其次 OpenAI（`OPENAI_API_KEY`），否则 mock。

```bash
pip install google-generativeai
set GEMINI_API_KEY=你的密钥
set GEMINI_MODEL=gemini-2.0-flash
python -m value_investment_agent.vi_agent.run_cola_pipeline --years 10 --freq annual --llm auto
```

仍可选用 OpenAI：`pip install openai` 并设置 `OPENAI_API_KEY`，或 `--llm openai`。默认输出目录 `data/cola_run/`（`cola_dashboard.png`）。

**兼容旧命令：** `python -m value_investment_agent.pipeline.run_ko_pipeline` 仍可用，内部已转发到新入口。

## moutai（茅台）五年季度 Fi 看板

```bash
python -m value_investment_agent.moutai_experiment.run_moutai_flow --years 5 --llm mock
```

重大新闻请维护 `data/moutai/raw/news/news_digest.csv`；`--refresh-yahoo-news` 可追加 Yahoo 近期标题。
