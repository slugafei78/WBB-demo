# `valuations/moutai/pe/` — 简化季度 PE 内在价值

本目录包含 **配置**（`config.json`）、**产出 CSV / meta**，与 **`pe_intrinsic_quarterly` 流水线**一一对应。输入因子仍来自 `factors/`（定量、定性、宏观），不在此重复存因子。

## 两套估值序列（同一 CSV 两列）

| 估值含义 | 概要 | 列名 |
|----------|------|------|
| **仅定量 + 简单 PE** | 宏观存款利率在历史区间映射 `pe_macro`（默认约 18～22）× **TTM EPS**；不用定性。 | **`intrinsic_per_share_pe_simple`** |
| **+ 定性调整** | `pe_macro` × 10 因子乘子映射（约 0.5～1.2），PE 再裁剪到 10～24，× 同一 TTM EPS。 | **`intrinsic_per_share_pe_qual_adjusted`** |

- **公式模块**（可复用）：`value_investment_agent/valuation/pe_macro_qual.py`  
- **合并与写表**：`value_investment_agent/moutai_experiment/pe_intrinsic_quarterly.py`  
- **产出**：`intrinsic_quarterly.csv`、`intrinsic_quarterly_meta.json`

**运行：**

```bash
python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly
```

可选：自定义配置路径  

```bash
python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly --config path/to/config.json
```

**定性分缺失**：10 因子不齐则 **沿用上一季**；首段无历史则用 `qual_default_score`（或 `qual_default_scores`）。列 **`qual_scores_fill_source`**：`observed` / `carry_forward` / `default`。

**TTM / 盈利口径**：依赖 `net_profit_attributable` 为 **单季**。不足 4 个季度时，对净利润做年化近似后再 ÷ 股本（见 `ttm_net_profit_proxy`、`ttm_quarters_used`、`ttm_proxy_method`：`annualize_1q`×4、`annualize_2q`×2、`annualize_3q`×4/3、`ttm_4q` 为真 TTM）。另有 `pe_anchor_reference`、`macro_pe_vs_anchor`（= `pe_macro`/锚定 PE）供核对。

## 可视化（日线 vs 内在价值）

模块：`value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay`（默认茅台路径；其他标的可传 `--daily-csv`、`--intrinsic-csv`、`--out`）。

```bash
python -m value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay
```

可选 `--no-annotations` 关闭季度标签；`--qual-scores-csv` 指定定性长表（默认 `factors/moutai/qualitative/moutai_qual_quarterly_scores.csv`）。

**图上季度说明框（当前逻辑）**  
仅在**相邻两季度之间**至少一项发生变化时才绘制（首季无「上一季」故不画）：  

1. **Macro PE:** `pe_macro` 上一季 → 本季（宏观利率映射后的 PE，见 `pe_macro_qual.pe_from_deposit_rate_linear`）。  
2. **Qual mult:** `qual_pe_multiplier` 上一季 → 本季（由 10 个定性分经 `qualitative_pe_multiplier_from_scores` 得到）。  
3. **`<factor_id>`:** 本季**得分最高**的因子；数字为该因子在**上一季得分 → 本季得分**（同一 `factor_id` 对齐比较）。  

说明框使用**英文与数字**，避免 Matplotlib 默认字体缺中文字形。位置在 **数据坐标** 下按序号横向错开日期、纵向错开价格，并自动抬高 y 轴上限，减轻重叠。

**关于「balance_sheet_health: 1,733 15.1% …」这类乱码**  
定性明细在 CSV 的 **`rationale`** 列（中文长句，见 `factors/moutai/qualitative/moutai_qual_quarterly_scores.csv`）。旧版图表曾把 `rationale` **强行转成 ASCII** 用于标注，非 ASCII 字符被替换为空格，只剩零星数字与符号，**没有独立指标含义**，也不是项目里另行定义的字段。含义请以 **`rationale` 全文**为准；当前图已改为上述 **old→new 三行**，不再嵌入 `rationale` 摘要。

默认输出 **`moutai_price_vs_pe_intrinsic_overlay.png`**（与本目录 `intrinsic_quarterly.csv` 同文件夹）。曲线为：日收盘价、120 日均线、无定性 / 有定性两条 **每股** 内在价值（季度末取值按交易日 `merge_asof` 向后对齐，`steps-post` 展示）。
