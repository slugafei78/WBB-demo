# `valuations/moutai/` — 贵州茅台估值产出

与 **`factors/moutai/`**（因子）分离：本目录仅放 **估值方法、配置与结果**。

| 子目录 | 方法 | 说明 |
|--------|------|------|
| **`pe/`** | 简化季度 PE（宏观存款利率调 PE + 可选定性乘子） | 见 [`pe/README.md`](pe/README.md) |

后续可并列增加 `dcf/`、`ps/`、`pb_roe/`、`ev_ebitda/` 等，各自 `config.json` + 产出序列 + README。
