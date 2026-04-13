# `factors/moutai/` — 贵州茅台因子

与全局 **`config/`**（`fundamental_factors.json` 等）分离：本目录放 **仅与 moutai 相关** 的配置与产出。

## 布局约定（其他 `factors/{symbol}/` 同理）

| 路径 | 说明 |
|------|------|
| **`config/`** | 该股专用 JSON：定量抽取、定性 Subagent **参数**（公司名、slug、输出目录等）。 |
| **`quantitative/`**、**`qualitative/`** | 运行产物（CSV/JSON/review）。 |

- **`config/quant_extract.json`**：`extract_moutai_quantitative` 使用；东财 **原始** 宽表请先 `download_moutai_quantitative_raw` 存 **`data/moutai/raw/financials/em/`**，合并长表仍写本目录 `quantitative/`。见 `data/moutai/raw/financials/README_net_profit.md`。  
- **`config/qualitative_subagent.json`**：`run_moutai_qualitative_subagent` 使用；**五步提示词**默认在仓库共享目录 **`prompts/qualitative_subagent/`**，不在本目录重复存放。若该股需定制提示词，可在 JSON 中设置可选字段 **`prompts_dir`** 指向自定义 `step_*.md` 目录。  
- **估值（PE 等）**：与 `factors/` 并列的 **`valuations/moutai/`**（如 `pe/` 子目录）；因子仍在本目录 `quantitative/`、`qualitative/`，估值产出与配置不在 `factors/`。
