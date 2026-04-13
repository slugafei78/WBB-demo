# Step 3 — 从全局池选出最重要的 {{TOP_N}} 个定性因子

全局 **定性因子池**（JSON，含 `factor_id` 与中文名）：

```json
{{QUAL_POOL_JSON}}
```

评分量纲（全局统一）：**0–10 分，步长 0.5**（后续步骤使用）。

你已掌握：

- 商业模式理解：见上文 Step 1 输出摘要。
- 财务特点理解：见 Step 2 输出摘要。

请完成：

1. 从上述池子中 **恰好选出 {{TOP_N}} 个** `factor_id`（勿选池外 ID）。
2. 每个因子给 **1–3 句中文理由**，说明为何对 **{{COMPANY_NAME}}** 最重要。
3. 按重要性 **大致排序**（数组顺序即可）。

**只输出一个 JSON 对象**（不要 Markdown 围栏外多余文字），格式示例：

```json
{
  "selected": [
    {"factor_id": "pricing_power", "reason": "...", "rank": 1},
    {"factor_id": "branding_power", "reason": "...", "rank": 2}
  ],
  "audit_note": "可选：给人工审核的一句话说明"
}
```

`selected` 长度必须等于 {{TOP_N}}。
