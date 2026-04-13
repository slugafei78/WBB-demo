# `config/` 配置说明

## 为何之前只有 macro 相关？

宏观流水线（`macro_indicators.json`、`macro_raw_to_factors.json`）**先落地**，是因为 **WDI 宽表 → 季度因子** 的转换路径明确、与 **单标的基本面因子池** 生命周期不同：

| 文件 | 职责 |
|------|------|
| **`fundamental_factors.json`** | **核心**：全局 **定量 + 定性** 基本面因子 ID 与展示名；会随调测**频繁增删改**。 |
| **`global_metrics.json`** | 财报指标 **variant**（如 D/E、FCF 分子分母）与 **功能开关**（如 `compute_fm`），与定量因子 **交叉引用**。 |
| **`macro_indicators.json`** | 全市场 **宏观时间序列** 抓取定义（FRED/akshare 等），与个股基本面 **独立**。 |
| **`macro_raw_to_factors.json`** | `data/macro/raw` 宽表 → `factors/macro/series` **转换**参数。 |

个股 **启用子集 + 权重**（`w_initial` / `w_adjustment`）建议后续放在 **`config/factors/profiles/{symbol}.json`**（见 `docs/DESIGN.md`），与上表并列。

**个股专用流水线配置**（定量抽取、定性 Subagent 参数等）**不放在本目录**，而放在 **`factors/{symbol}/config/`**，与 `factors/README.md` 约定一致；**定性 Subagent 共享提示词**在 **`prompts/qualitative_subagent/`**，全局仍只保留上表中的共享 JSON。

---

## 合并成一个文件是否更合适？

| 做法 | 优点 | 缺点 |
|------|------|------|
| **合并为单文件**（如 `app.json` 含 fundamental + macro + metrics） | 一处浏览、单次 diff | 文件变大，宏观与基本面**不同修改频率**时易产生无关合并冲突 |
| **当前拆分**（基本面 + 全局指标 + 宏观） | 职责清晰、macro 可单独版本化 | 需读 `README` 了解全貌 |

**当前约定**：

- **基本面定义**：**`fundamental_factors.json`** 已把 **quantitative + qualitative 合在一处**（你最关心的「随时改补充」主要改这个文件）。  
- **财报口径**：**`global_metrics.json`** 单独维护，避免与因子 ID 列表搅在一起。  
- **宏观**：仍用 **`macro_*.json`**，避免与 `cola`/`moutai` 因子池混淆。

若你强烈希望 **物理上只有一个 JSON**，可以把 `fundamental_factors`、`global_metrics`、`macro_indicators` 三层嵌套进一个 `config/all.json`，由脚本拆分加载——功能等价，只是编辑单文件时更累。**默认推荐保持现拆分**，除非团队强需求单文件。

---

## 与文档的对应关系

- 人读叙事：`docs/REQUIREMENTS.md` §4、`docs/DESIGN.md`  
- 机读权威：**本目录 JSON**（以 `schema_version` 或文件日期为准）

修改 **`fundamental_factors.json`** 后，建议同步更新 `docs/REQUIREMENTS.md` 表格或至少在提交说明里写一句，避免「文档与配置漂移」。
