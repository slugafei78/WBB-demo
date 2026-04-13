# 估值层 `valuations/`

与 **`data/`**（原始素材）、**`factors/`**（因子时间序列）**并列**：本目录存放 **按标的、按估值方法** 组织的 **估值结果、说明与专用配置**。

## 与 `factors/` 的分工

| 目录 | 放什么 |
|------|--------|
| **`factors/`** | 清洗后的因子序列（宏观、个股定量/定性等），供多条业务线复用。 |
| **`valuations/`** | 在因子（及必要时 `data/`）之上 **算出的估值结论**、各方法的 README、以及 **该方法专用的 JSON 配置**（例如 PE 乘子上下限、默认定性分）。 |

同一套因子可被多种估值方法读取；**方法特有的假设与输出路径**放在 `valuations/{symbol}/{method}/`，避免与因子目录混放。

## 建议结构

```
valuations/
  README.md                 # 本文件
  {symbol}/                 # 个股 slug，与 factors/{symbol}/ 对齐
    README.md               # 该股估值总览（用了哪些方法、入口命令）
    pe/                     # 简化 PE 等
      README.md
      config.json
      intrinsic_quarterly.csv
      intrinsic_quarterly_meta.json
    dcf/                    # 后续可增
    ps/
    pb_roe/
    ev_ebitda/
```

新增标的时：在 `valuations/` 下建与 `factors/{symbol}/` 同名的二级目录，再按方法分子目录即可。

**与 `data/`、`factors/` 的串联及命令**：[`docs/DATA_FLOW.md`](../docs/DATA_FLOW.md)。
