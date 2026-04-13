# 定性 Subagent — 共享提示词（全个股通用）

五步流水线由各标的入口脚本按顺序加载 **`step_01` … `step_05`**（占位符在运行时替换）。

**个股差异**通过 **`factors/{symbol}/config/qualitative_subagent.json`** 配置（公司名、`symbol`、`top_n_qualitative_factors`、输出目录等），一般 **无需复制** 本目录。若某标的需定制措辞或步骤，可在该股配置里设置可选字段 **`prompts_dir`**，指向另一套 `step_*.md`（仍建议从本目录拷贝再改，保持一致性）。

占位符：

| 占位符 | 含义 |
|--------|------|
| `{{COMPANY_NAME}}` | 公司显示名（来自配置） |
| `{{SYMBOL}}` | slug（来自配置） |
| `{{TOP_N}}` | 从全局池选出的因子个数（见 **`factors/{symbol}/config/qualitative_subagent.json`** → `top_n_qualitative_factors`） |
| `{{QUAL_POOL_JSON}}` | `config/fundamental_factors.json` 中 qualitative 列表的 JSON 片段 |
| `{{BUSINESS_MODEL_DRAFT}}` | 第 1 步模型输出摘要 |
| `{{FINANCIAL_SUMMARY}}` | 近 N 年利润表/资产负债/现金流要点（脚本生成） |
| `{{SELECTED_FACTORS_JSON}}` | 第 3 步选定因子 + 理由（供第 4、5 步使用） |
| `{{EVIDENCE_MATRIX_JSON}}` | 第 4 步按「季度×因子」抽取的决策信息 |
| `{{NEWS_DIGEST}}` | 该股 `news_digest` 合并文本 |
| `{{PDF_CORPUS_EXCERPT}}` | PDF 抽取文本摘要（前若干字符） |

修改任意 `step_*.md` 后重新运行 Subagent；**除非增删步骤**，一般不必改 Python。
