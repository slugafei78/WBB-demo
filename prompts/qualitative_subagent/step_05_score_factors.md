# Step 5 — 对 {{TOP_N}} 个因子按季度打分（与证据匹配）

**证据矩阵（JSON）**：

```json
{{EVIDENCE_MATRIX_JSON}}
```

**已选因子（JSON）**：

```json
{{SELECTED_FACTORS_JSON}}
```

**财报数据摘要（与 Step 4 一致，便于核对数值）**：

```
{{FINANCIAL_SUMMARY}}
```

**基本面分析文档（与 Step 4 一致；`rationale` 应优先引用本节及 Step 4 矩阵中与该因子对应的证据；年度视角文档可对各 `period_end` 作合理外推或明确标注证据不足）**：

```
{{HUMAN_DIALOGUE_TEXT}}
```

请对每个 **`period_end` × `factor_id`** 组合给出 **一个分数**（**每个季度每个因子各一条**）：

- 范围 **0–10**，步长 **0.5**。
- 分数须与 Step 4 矩阵中 **同一 `period_end` + `factor_id`** 的 `text_evidence` / `data_snippet` 一致；二者皆空时分数偏保守（约 mid-range）并在 `rationale` 说明依据不足。
- `rationale` 必须 **简短引用** 本条对应的 `text_evidence` 或 `data_snippet`（可截断），勿与证据矛盾。

**只输出一个 JSON**：

```json
{
  "scores": [
    {
      "period_end": "2024-12-31",
      "factor_id": "pricing_power",
      "score": 8.5,
      "rationale": "与 text_evidence/data_snippet 对应的一句话说明"
    }
  ],
  "global_note": "可选"
}
```

`scores` 行数应等于：Step 4 `matrix` 行数（即每个季度 × 每个已选因子全覆盖）。
