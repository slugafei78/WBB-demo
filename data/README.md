# 原始数据层 `data/`

与 `factors/`（因子层）并列：本目录放 **抓取或下载得到的原始/准原始素材**；**不做**「已对齐、可直接进模型」的因子形态承诺（因子在 `factors/`）。

## 数据血缘（总览）

```
抓取 / 下载
    → data/ ...           # 原始落地（本目录）
    → [清洗、对齐、计算]   # 通常在 ingestion / factor_pipeline 中完成
    → factors/ ...        # 因子时间序列（多数由 data 衍生）
    → valuations/ ...     # 估值结果与方法配置（由 factors 等计算，与 data/、factors/ 并列）
```

- **`data/`**：爬虫、API、供应商文件、手工归档；尽量保留 **来源、抓取时间、原始 schema**。  
- **`factors/`**：从 `data/` 读取后计算或转换得到；少数因子可能由多源 `data/` 合成。  
- **`valuations/`**：在因子等输入上的估值产出；见仓库 **`valuations/README.md`**。  
  **端到端文件名与阶段对照**：[`docs/DATA_FLOW.md`](../docs/DATA_FLOW.md)。

## 目录一览

| 目录 | 内容 |
|------|------|
| **`macro/raw/`** | **全市场宏观**原始抓取：美利率、中国 LPR、国债收益率、PCE/CPI 等（详见 `macro/raw/README.md`）。 |
| **`cola/`** | 可口可乐（slug：`cola`） |
| **`moutai/`** | 贵州茅台（slug：`moutai`） |
| **`txrh/`** | Texas Roadhouse（slug：`txrh`） |

## 各标的下结构（`cola`、`moutai`、`txrh`）

每只股票下一般为：

```
raw/
  trading/     # 交易数据（OHLCV、复权等）
  financials/  # 财报（年报/季报全文或结构化导出）
  news/        # 新闻存档
  mdna/        # MD&A 文本（可按季分子目录）
```

详见各子目录内 `README.md`。
