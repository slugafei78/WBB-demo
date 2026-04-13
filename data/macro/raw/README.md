# 宏观原始数据 `data/macro/raw/`

本目录存放 **从外部数据源抓取或下载的原始/准原始素材**，与个股无关、不按 `cola`/`moutai` 分目录。

## 与 `factors/` 的关系（数据血缘）

| 层 | 路径 | 含义 |
|----|------|------|
| **抓取层** | **`data/`**（含本目录） | 爬虫、API、手工下载的落地文件；尽量保持供应商原始形态与抓取时间戳。 |
| **标准化时间序列** | **`data/macro/series/`** | 由 API（FRED / akshare 等）直接写入或与 **`config/macro_indicators.json`** 对齐后的 **`{id}.csv`**；供全市场 join。 |
| **因子层（可选镜像）** | **`factors/macro/series/`** | 若需与 `factors/{symbol}` 并列归档，可从 **`data/macro/series/`** 复制或软链；**权威落地以 `data/macro/series/` 为准**。 |

典型流程：**API/爬虫 → `data/macro/series/`（本仓库抓取脚本）**；若需保留供应商原始响应，可另存 **`data/macro/raw/`**。

个股因子同理：**抓取 → `data/{symbol}/raw/...` → `factors/{symbol}/...`**。

## 本目录建议组织

可按 **数据源** 或 **指标 stem**（与 `factors/macro/README.md` 中的文件 stem 对齐）分子目录，例如：

```
data/macro/raw/
  README.md              # 本文件
  fred/                  # 美 FRED API 导出或快照（示例）
  pboc/                  # 人民银行 LPR 等页面抓取或公告 PDF（示例）
  treasury/              # 美债收益率原始 CSV（示例）
  stats_gov_cn/          # 国家统计局等（示例）
```

具体子目录名随数据源演进；**原始文件名**建议包含 **抓取日期** 或 **数据截止日期**，便于 PIT（point-in-time）审计。

## 与 `factors/macro/` 指标表的对应

指标定义见 **`factors/macro/README.md`** 与 **`config/macro_indicators.json`**。本目录只负责 **「原始落地」**；**`data/macro/series/`** 为 **用于建模的干净时间序列**。

---

| 日期 | 说明 |
|------|------|
| 2026-04-04 | 初版：宏观抓取独立目录；与 factors 血缘说明 |
