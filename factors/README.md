# 因子层 `factors/`

与 `data/` **并列**：存放 **清洗、对齐、计算后** 的**时间序列因子**（频率可不同：日/周/月/季等）。

## 数据血缘

| 层 | 路径 | 含义 |
|----|------|------|
| **抓取** | **`data/`** | 原始或准原始文件（含 **`data/macro/raw/`** 的宏观抓取）。 |
| **因子** | **`factors/`**（本目录） | **多数**从对应 `data/` 读取后经 ETL/公式得到；亦可由 `data/` 多表联结或经 LLM 打分写入。 |
| **估值** | **`valuations/`** | 在 **`factors/`**（及必要时 **`data/`**）之上按方法计算的估值序列、方法专用配置与 README；与个股因子目录对齐为 **`valuations/{symbol}/`**。 |

概括：**`data/` = 抓取的落地；`factors/` = 因子序列；`valuations/` = 估值结论与方法配置。** 宏观路径：**`data/macro/raw/` → `factors/macro/series/`**。详见 **`valuations/README.md`**。  
**各阶段输入/输出文件名**：[`docs/DATA_FLOW.md`](../docs/DATA_FLOW.md)。

## 目录结构

```
factors/
  macro/                    # 全市场共用宏观时间序列（与个股目录并列）
    README.md               # 指标定义、更新频率、文件命名约定
    series/                 # 各指标一条序列一个文件（或分子目录）
  {symbol}/                 # 个股 slug：cola、moutai、txrh …
    config/                 # 该股因子流水线 JSON（定量抽取、定性 Subagent 等），非估值专用
    quantitative/
    qualitative/
    momentum/
    risk_premium/

valuations/                 # 与 data/、factors/ 并列（见 valuations/README.md）
  {symbol}/
    pe/ dcf/ ...            # 按估值方法分子目录
```

- **`macro/`**：**不与** `cola`、`moutai` 等混放。宏观指标对所有个股有效；**原始抓取**在 **`data/macro/raw/`**，标准化后的 TS 在 **`factors/macro/series/`**（见 `macro/README.md`）。
- **`{symbol}/`**：仅放**该标的**的量化/定性/动量/风险溢价等因子；**不再**包含 `macro/` 子目录。该股 **pipeline 级配置**（与全局 `fundamental_factors.json` 不同）放在 **`{symbol}/config/`**，避免与根目录 `config/` 混淆；新标的（如 `cola`）按同样模式增加 **`factors/cola/config/`** 等即可。

**定性 Subagent** 的五步提示词为 **全库共享**：**`prompts/qualitative_subagent/`**；各标的仅在 **`factors/{symbol}/config/qualitative_subagent.json`** 中写公司名、输出路径等；若某标的需微调提示词，可在该 JSON 中设置可选字段 **`prompts_dir`** 指向单独目录（仍建议从共享目录拷贝再改）。

建议个股因子文件命名携带 **频率与 as-of 规则**，例如：`daily_2020-01-02.parquet`、`quarterly_end.csv`。宏观序列见 `macro/README.md`。
