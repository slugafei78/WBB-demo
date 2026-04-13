# 宏观因子（季度）`factors/macro/series/`

由 **`data/macro/raw/`** 中自下载的宽表 CSV **转换**而来，**不**从网上抓取。

## 固定转换命令

在项目根目录：

```bash
python -m value_investment_agent.ingestion.macro_raw_to_factors
```

- **配置**：`config/macro_raw_to_factors.json`（输入路径、输出目录、`quarterly_mode`）。  
- **输入**：默认 `data/macro/raw/Macro-indicators.csv`（World Bank 样式：`Country Code`, `Series Code`, `2005 [YR2005]` …）。  
- **可选说明表**：`data/macro/raw/Macro-indicators - Metadata.csv`（从含 `Code,` 表头段落解析指标定义，写入各序列旁 `.meta.json` 与 `macro_indicator_catalog.json`）。

## 输出约定

| 文件 | 含义 |
|------|------|
| `macro_{CC}_{SERIES}.csv` | 两列：`period_end`（季度末日）、`value`（与原始指标一致的量纲）。 |
| `macro_{CC}_{SERIES}.meta.json` | 国家、指标代码、名称、来自 Metadata 的说明（若有）。 |
| `macro_indicator_catalog.json` | 按 `Series Code` 汇总的指标元数据。 |
| `run_convert_meta.json` | 本次转换摘要（写入了哪些 stem、跳过了哪些空序列）。 |

**季度规则**：源数据为**年度**时，默认将当年官方值 **复制到四个季度末**（03-31、06-30、09-30、12-31），便于与季报估值对齐；见 `config/macro_raw_to_factors.json` 中 `quarterly_mode`。

## 与估值（factor / macro）的关系

此处序列为 **统一季度频率** 的宏观输入，可在后续 Parameter Synthesizer 或规则中作为 **macro factor** 与 Fi/Fm 结合使用；具体权重与符号由标的层配置决定（见项目需求/设计文档）。
