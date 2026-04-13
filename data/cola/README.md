# cola（可口可乐）

- 标的 slug：`cola`（与 `data/cola`、`factors/cola` 一致）
- 行情/SEC 映射见 `value_investment_agent.config.symbols`（含 Yahoo 代码与 SEC CIK）

## `raw/` 四类原始数据

| 子目录 | 内容 |
|--------|------|
| `trading/` | 日线/分钟等行情、成交量等（CSV、Parquet 等自管） |
| `financials/` | 10-K、10-Q 全文或从 EDGAR/供应商导出的财报文件 |
| `news/` | 新闻条目（标题、时间、正文或链接列表） |
| `mdna/` | 各期 MD&A 单独文本（如 `mdna_YYYY-MM-DD_10Q.txt`）；Q4 常与 10-K Item 7 对应 |

财报与 MD&A 可拆分存放：`financials` 放完整报表，`mdna` 放摘录段落便于检索。
