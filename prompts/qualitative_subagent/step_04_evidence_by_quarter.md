# Step 4 — 按「季度 × 因子」抽取决策相关信息（供人工审核）

**已选定因子清单（JSON）**：

```json
{{SELECTED_FACTORS_JSON}}
```

**可用原始材料**：

### 基本面分析文档（**主证据来源**，`human_dialogue_path`）

以下为仓库内用户维护的 Markdown（可含表格），通常已覆盖商业模式、三张表及对各因子的定性判断。请 **优先从本节摘录** `text_evidence` 与 `data_snippet`（表格可压缩为一行关键数字）；仅当本节缺项时再用下方新闻/PDF/脚本财报摘要补充。若与新闻/PDF 冲突，**以本节为准**。

若文档以年度视角为主、而任务要求按季度 `period_end` 填行：对无单独季度表述的历史季度，可将 `text_evidence`/`data_snippet` 写为该文档中与之最接近的摘录并注明「年度视角/延续」，或将 `confidence` 降为 `medium`/`low`。

```
{{HUMAN_DIALOGUE_TEXT}}
```

### 新闻与事件 digest

```
{{NEWS_DIGEST}}
```

### 年报/PDF 等抽取文本摘要

```
{{PDF_CORPUS_EXCERPT}}
```

### 财报与数据摘要（含表格字符串，可作数值支撑）

以下为脚本拉取的 Yahoo 季报/摘要片段，可在 `data_snippet` 中 **摘录与因子相关的数字行或表片段**（不必全文）：

```
{{FINANCIAL_SUMMARY}}
```

请为 **每一个已选因子**，在 **每一个** 脚本给出的日历季度（`period_end`：季度末日 YYYY-MM-DD）填写支撑信息：

- **text_evidence**：**优先** 来自上文「基本面分析文档」的短引文或一句话摘要；必要时辅以新闻/PDF（无则 `null`）。
- **data_snippet**：**优先** 来自该文档中的表格行或数字；其次用「财报与数据摘要」脚本片段（无则 `null`）。若仅有定性推断、无数值，写 `null` 并将 `confidence` 降为 `low` 或 `medium`。
- **source**：填 `analyst_note`（证据主要来自基本面文档）、`financial_summary`、`news_digest`、`pdf`、`mixed`、`inferred` 之一。
- 若该季度确实无材料：`text_evidence` 与 `data_snippet` 均可为 `null`，`confidence` 为 `low`。

**只输出一个 JSON**，结构如下：

```json
{
  "matrix": [
    {
      "period_end": "2024-12-31",
      "factor_id": "pricing_power",
      "text_evidence": "新闻/PDF 中与该因子相关的短摘录或 null",
      "data_snippet": "财报摘要中与该因子相关的数字/表行或 null",
      "source": "analyst_note|news_digest|pdf|financial_summary|inferred|mixed",
      "confidence": "high|medium|low"
    }
  ],
  "notes_for_human": "给人工审核的说明"
}
```

要求：

- `matrix` 必须覆盖 **所有** `selected` 中的 `factor_id` × **用户消息中给出的全部季度列表**（每个组合一行，勿省略季度）。
- 信息尽量 **可追溯到原文或数据摘要**；`data_snippet` 优先填与护城河、盈利质量、杠杆、现金流、渠道/品牌等相关的表内数字。
