"""
贵州茅台（moutai）定性 Subagent 入口：五步 **共享** 提示词见 `prompts/qualitative_subagent/`，
该股仅通过 `factors/moutai/config/qualitative_subagent.json` 提供名称、输出路径等参数。

  python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent
  python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent --llm mock
  # 手工多轮：在网页里跑完前几步后，将回答保存到 factors/moutai/qualitative/review/ 再只跑后续步：
  python -m value_investment_agent.moutai_experiment.run_moutai_qualitative_subagent --llm gemini --from-step 4 --to-step 5
  # 基本面长文：见 data/moutai/analysis/*.md，并在 qualitative_subagent.json 配置 human_dialogue_path 后同上命令（勿用 mock）。

配置：`factors/moutai/config/qualitative_subagent.json`；可选 `prompts_dir` 覆盖共享提示词目录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Literal

import pandas as pd
import yfinance as yf

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker
from value_investment_agent.llm.gemini_call import gemini_generate_text
from value_investment_agent.llm.json_completion import complete_json_gemini, complete_json_openai
from value_investment_agent.llm.llm_provider import (
    dotenv_load_hint_for_error,
    gemini_api_key,
    load_dotenv_from_repo_root,
    resolve_llm_provider,
)
from value_investment_agent.moutai_experiment.news_digest import load_news_digest
from value_investment_agent.moutai_experiment.paths import (
    moutai_qualitative_subagent_config,
    moutai_raw,
    repo_root,
    shared_qualitative_subagent_prompts_dir,
)


def _cfg() -> dict:
    return json.loads(moutai_qualitative_subagent_config().read_text(encoding="utf-8"))


def _load_fundamental_qual_pool() -> list[dict]:
    p = repo_root() / "config" / "fundamental_factors.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("qualitative", {}).get("factors", []))


def _prompt(path: Path, mapping: dict[str, str]) -> str:
    t = path.read_text(encoding="utf-8")
    for k, v in mapping.items():
        t = t.replace("{{" + k + "}}", v)
    return t


def _pdf_corpus_excerpt(max_chars: int = 12000) -> str:
    ext = moutai_raw() / "financials" / "_extracted_text"
    if not ext.exists():
        return "(尚未运行 extract_moutai_quantitative 生成 PDF 文本；请先运行以生成 _extracted_text/*.txt)"
    chunks: list[str] = []
    for f in sorted(ext.glob("*.txt")):
        chunks.append(f"===== {f.name} =====\n" + f.read_text(encoding="utf-8", errors="replace"))
    s = "\n\n".join(chunks)
    return s[:max_chars]


def _financial_summary_block(years: int) -> str:
    """优先从本地东财 CSV 读取，绕过 yfinance 的 rate limit。"""
    root = repo_root()
    em_dir = root / "data" / "moutai" / "raw" / "financials" / "em"
    
    lines = ["# 财报摘要（数据源：本地东财原始表）", ""]
    
    # 尝试加载本地 CSV
    files = {
        "Profit (利润表)": em_dir / "profit_sheet_quarterly_em.csv",
        "Balance (资产负债表)": em_dir / "balance_sheet_by_report_em.csv",
        "Cashflow (现金流量表)": em_dir / "cash_flow_sheet_quarterly_em.csv"
    }
    
    found_local = False
    for name, path in files.items():
        if path.is_file():
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
                # 只取最近几行关键列，避免 token 爆炸
                # 选取包含 'DATE', 'INCOME', 'PROFIT', 'LIABILITIES', 'EQUITY', 'CASH' 等关键字的列
                cols = [c for c in df.columns if any(k in str(c).upper() for k in ["DATE", "INCOME", "PROFIT", "COST", "LIABILITIES", "EQUITY", "CASH", "ASSET"])]
                cols = [c for c in cols if "_QOQ" not in str(c).upper() and "_YOY" not in str(c).upper()]
                # 截取前 8 个报告期
                summary_df = df[cols].head(8)
                lines.append(f"## {name}")
                lines.append(summary_df.to_string(index=False)[:8000])
                lines.append("")
                found_local = True
            except Exception as e:
                lines.append(f"## {name}: (read error: {e})")
        else:
            lines.append(f"## {name}: (file not found: {path.name})")

    if not found_local:
        # 最后的兜底逻辑：尝试 yfinance (但通常会报错)
        lines.append("## 注意：未找到本地东财数据，尝试请求 Yahoo Finance...")
        try:
            t = yf.Ticker(yahoo_ticker(SYMBOL_MOUTAI))
            info = t.info or {}
            lines.insert(0, f"longBusinessSummary: {info.get('longBusinessSummary', '')[:2000]}\n")
            inc = t.quarterly_income_stmt
            if inc is not None and not inc.empty:
                lines.append("## Income (Yahoo)\n" + inc.iloc[:25].to_string()[:5000])
        except Exception as e:
            lines.append(f"## Yahoo Error: {e}")
            
    return "\n".join(lines)[:24000]


def _pause_between_gemini_steps(resolved: str) -> None:
    """缓解 RPM：设置 GEMINI_STEP_PAUSE_SEC=3 等（仅 gemini 模式）。"""
    if resolved != "gemini":
        return
    raw = os.environ.get("GEMINI_STEP_PAUSE_SEC", "").strip()
    if not raw:
        return
    try:
        time.sleep(float(raw))
    except ValueError:
        pass


def _quarter_ends(years: int) -> list[str]:
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    qs = pd.date_range(start=start, end=end, freq="QE")
    return [d.strftime("%Y-%m-%d") for d in qs]


def _complete_text(system: str, user: str, provider: Literal["gemini", "openai", "mock"]) -> str:
    if provider == "mock":
        return (
            "[mock — 未调用云端 LLM]\n\n"
            "System 摘要:\n"
            + system[:400]
            + "\n\nUser 摘要:\n"
            + user[:1200]
        )
    if provider == "gemini":
        load_dotenv_from_repo_root(override=True)
        if not gemini_api_key():
            raise ValueError(
                "缺少 GEMINI_API_KEY / GOOGLE_API_KEY。请在仓库根目录放置 .env，"
                "或设置环境变量；每行格式 GEMINI_API_KEY=你的密钥。\n"
                "也可设置环境变量 DOTENV_PATH 指向你的 .env 绝对路径。\n\n"
                + dotenv_load_hint_for_error()
            )
        return gemini_generate_text(system, user, temperature=0.2)
    # openai
    from openai import OpenAI

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    r = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return r.choices[0].message.content or ""


def _read_review_text(review: Path, fname: str) -> str:
    p = review / fname
    if not p.is_file():
        raise FileNotFoundError(
            f"缺少文件: {p}\n请先完成更前序步骤并保存输出，或用手工对话将模型回答写入该路径。"
        )
    return p.read_text(encoding="utf-8")


def _read_review_json(review: Path, fname: str) -> dict:
    return json.loads(_read_review_text(review, fname))


def _load_human_dialogue_notes(root: Path, rel_or_abs: str, *, max_chars: int = 120000) -> str:
    """从人工整理的研究笔记 / 与网页版模型的对话导出文件读取（.md / .txt / .docx）。"""
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = root / rel_or_abs
    if not p.is_file():
        raise FileNotFoundError(
            f"配置项 human_dialogue_path 指向的文件不存在: {p}\n"
            "请将 Google Docs 导出为 .txt，或将 Word 另存为 .txt/.md，或安装 python-docx 后使用 .docx。"
        )
    suf = p.suffix.lower()
    if suf in (".txt", ".md"):
        text = p.read_text(encoding="utf-8", errors="replace")
    elif suf == ".docx":
        try:
            import docx  # type: ignore
        except ImportError as e:
            raise ImportError(
                "读取 .docx 需要 python-docx：pip install python-docx（或 pip install -e \".[moutai]\"）"
            ) from e
        document = docx.Document(str(p))
        text = "\n".join(par.text for par in document.paragraphs)
    else:
        raise ValueError(
            f"不支持的扩展名 {suf}；请使用 .md / .txt / .docx，或将在线文档导出为纯文本。"
        )
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n…（已截断至约 {max_chars} 字符）"
    return text


def run(
    *,
    llm: str | None = None,
    from_step: int = 1,
    to_step: int = 5,
) -> dict:
    if not (1 <= from_step <= to_step <= 5):
        raise ValueError("需要 1 <= from_step <= to_step <= 5")

    root = repo_root()
    load_dotenv_from_repo_root(override=True)
    cfg = _cfg()
    llm = llm or cfg.get("llm", "auto")
    resolved = resolve_llm_provider(llm if llm in ("auto", "gemini", "openai", "mock") else "auto")  # type: ignore
    if llm == "mock":
        resolved = "mock"

    top_n = int(cfg.get("top_n_qualitative_factors", 10))
    yfin_y = int(cfg.get("lookback_years_financials", 6))
    company = cfg.get("company_display_name", "贵州茅台")
    sym = cfg.get("symbol", SYMBOL_MOUTAI)
    out_dir = root / cfg.get("output_dir", "factors/moutai/qualitative")
    review = out_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    override = (cfg.get("prompts_dir") or "").strip()
    pdir = root / override if override else shared_qualitative_subagent_prompts_dir()

    qual_pool = _load_fundamental_qual_pool()
    qual_json = json.dumps(qual_pool, ensure_ascii=False, indent=2)
    news = load_news_digest()
    pdf_ex = _pdf_corpus_excerpt()
    fin_sum = _financial_summary_block(yfin_y)[:20000]
    quarter_list = _quarter_ends(yfin_y)

    human_path = (cfg.get("human_dialogue_path") or "").strip()
    if human_path:
        max_h = int(cfg.get("human_dialogue_max_chars", 120000))
        human_notes = _load_human_dialogue_notes(root, human_path, max_chars=max(8000, max_h))
    else:
        human_notes = (
            "(未配置 human_dialogue_path：无分析师对话摘录；"
            "请仅依据下方新闻/PDF/财报与既有材料。若已有人工长对话，请在 qualitative_subagent.json 中设置该路径。)"
        )

    common = {
        "COMPANY_NAME": company,
        "SYMBOL": sym,
        "TOP_N": str(top_n),
        "QUAL_POOL_JSON": qual_json,
        "LOOKBACK_YEARS": str(yfin_y),
        "NEWS_DIGEST": news[:12000],
        "PDF_CORPUS_EXCERPT": pdf_ex,
        "FINANCIAL_SUMMARY": fin_sum,
        "HUMAN_DIALOGUE_TEXT": human_notes,
    }

    selected_factor_ids = [str(x.get("factor_id", "")) for x in qual_pool[:top_n]]

    def _complete_json(
        system: str,
        user: str,
        provider: Literal["gemini", "openai", "mock"],
        *,
        json_step_index: int,
    ) -> str:
        if provider == "gemini":
            return complete_json_gemini(system, user)
        if provider == "openai":
            return complete_json_openai(system, user)
        # mock：json_step_index 0=step3 选因子, 1=step4 矩阵, 2=step5 打分
        n = json_step_index + 1
        if n == 1:
            sel = [
                {"factor_id": fid, "reason": f"[mock] 自因子池选入，用于离线验证流水线。", "rank": i + 1}
                for i, fid in enumerate(selected_factor_ids)
            ]
            return json.dumps({"selected": sel, "audit_note": "mock_offline"}, ensure_ascii=False)
        if n == 2:
            matrix: list[dict[str, object]] = []
            for pe in quarter_list:
                for i, fid in enumerate(selected_factor_ids):
                    matrix.append(
                        {
                            "period_end": pe,
                            "factor_id": fid,
                            "text_evidence": f"[mock] 新闻/PDF 摘录占位：{company} {fid} @ {pe}" if i == 0 else None,
                            "data_snippet": f"[mock] Yahoo 季报表片段占位（Income 行节选）period={pe}" if i == 0 else None,
                            "source": "mixed" if i == 0 else "inferred",
                            "confidence": "medium" if i == 0 else "low",
                        }
                    )
            return json.dumps({"matrix": matrix, "notes_for_human": "mock：证据为占位符，请用 gemini/openai 重跑"}, ensure_ascii=False)
        if n == 3:
            scores: list[dict[str, object]] = []
            for pe in quarter_list:
                for fid in selected_factor_ids:
                    scores.append(
                        {
                            "period_end": pe,
                            "factor_id": fid,
                            "score": 7.0,
                            "rationale": "[mock] 与对应 matrix 行 text/data 占位一致；真实运行将由模型填写。",
                        }
                    )
            return json.dumps({"scores": scores, "global_note": "mock_offline"}, ensure_ascii=False)
        return "{}"

    business = ""
    fin_overview = ""
    sel_obj: dict = {}
    ev_obj: dict = {}
    sc_obj: dict = {}

    # Step 1
    if from_step <= 1 <= to_step:
        s1_sys = _prompt(pdir / "step_01_business_model.md", common)
        u1 = (
            "请基于以下材料完成分析：\n\n"
            + fin_sum[:8000]
            + "\n\n新闻摘要：\n"
            + news[:6000]
            + "\n\nPDF节选：\n"
            + pdf_ex[:4000]
        )
        business = _complete_text(s1_sys, u1, resolved)
        (review / "step01_business_model.md").write_text(business, encoding="utf-8")
        _pause_between_gemini_steps(resolved)
    elif from_step > 1 and to_step >= 1:
        business = _read_review_text(review, "step01_business_model.md")

    # Step 2
    if from_step <= 2 <= to_step:
        common["BUSINESS_MODEL_DRAFT"] = business[:20000]
        s2 = _prompt(pdir / "step_02_financials_overview.md", common)
        u2 = "请直接回答 Step 2 要求。"
        fin_overview = _complete_text(s2, u2, resolved)
        (review / "step02_financials_overview.md").write_text(fin_overview, encoding="utf-8")
        _pause_between_gemini_steps(resolved)
    elif from_step > 2 and to_step >= 3:
        fin_overview = _read_review_text(review, "step02_financials_overview.md")

    # Step 3 — JSON
    if from_step <= 3 <= to_step:
        common["BUSINESS_MODEL_DRAFT"] = business[:8000]
        s3 = _prompt(pdir / "step_03_select_factors.md", common)
        u3 = (
            "Step1 摘要：\n"
            + business[:4000]
            + "\n\nStep2 摘要：\n"
            + fin_overview[:4000]
            + "\n\n只输出 JSON。"
        )
        raw3 = _complete_json(
            "你只输出合法 JSON，键与模板一致。",
            s3 + "\n\n" + u3,
            resolved,
            json_step_index=0,
        )
        (review / "step03_select_factors_raw.json").write_text(raw3, encoding="utf-8")
        try:
            sel_obj = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw3.strip(), flags=re.MULTILINE))
        except json.JSONDecodeError:
            sel_obj = {"selected": [], "audit_note": "parse_error", "raw": raw3}
        (review / "step03_select_factors.json").write_text(
            json.dumps(sel_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _pause_between_gemini_steps(resolved)
    elif from_step > 3 and to_step >= 4:
        sel_obj = _read_review_json(review, "step03_select_factors.json")

    sel_json = json.dumps(sel_obj, ensure_ascii=False, indent=2)
    common["SELECTED_FACTORS_JSON"] = sel_json

    # Step 4
    if from_step <= 4 <= to_step:
        common["EVIDENCE_MATRIX_JSON"] = "{}"  # filled by model
        s4 = _prompt(pdir / "step_04_evidence_by_quarter.md", common)
        u4 = (
            f"相关季度列表（period_end）：{json.dumps(quarter_list)}\n\n"
            "请输出 JSON matrix。"
        )
        raw4 = _complete_json(
            "只输出合法 JSON。",
            s4 + "\n" + u4,
            resolved,
            json_step_index=1,
        )
        (review / "step04_evidence_raw.json").write_text(raw4, encoding="utf-8")
        try:
            ev_obj = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw4.strip(), flags=re.MULTILINE))
        except json.JSONDecodeError:
            ev_obj = {"matrix": [], "notes_for_human": "parse_error", "raw": raw4}
        (review / "step04_evidence_matrix.json").write_text(
            json.dumps(ev_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _pause_between_gemini_steps(resolved)
    elif from_step > 4 and to_step >= 5:
        ev_obj = _read_review_json(review, "step04_evidence_matrix.json")

    ev_json = json.dumps(ev_obj, ensure_ascii=False, indent=2)

    # Step 5
    if from_step <= 5 <= to_step:
        common["EVIDENCE_MATRIX_JSON"] = ev_json
        s5 = _prompt(pdir / "step_05_score_factors.md", common)
        u5 = "请输出 scores JSON。"
        raw5 = _complete_json(
            "只输出合法 JSON。",
            s5 + "\n" + u5,
            resolved,
            json_step_index=2,
        )
        (review / "step05_scores_raw.json").write_text(raw5, encoding="utf-8")
        try:
            sc_obj = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw5.strip(), flags=re.MULTILINE))
        except json.JSONDecodeError:
            sc_obj = {"scores": [], "global_note": "parse_error", "raw": raw5}
        (review / "step05_scores.json").write_text(
            json.dumps(sc_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    scores = sc_obj.get("scores") or []
    if from_step <= 5 <= to_step and scores:
        pd.DataFrame(scores).to_csv(out_dir / "moutai_qual_quarterly_scores.csv", index=False, encoding="utf-8-sig")

    summary = {
        "output_dir": str(out_dir.relative_to(root)),
        "llm_resolved": resolved,
        "from_step": from_step,
        "to_step": to_step,
        "top_n_qualitative_factors": top_n,
        "review_files": [str(p.relative_to(root)) for p in sorted(review.glob("*"))],
    }
    (out_dir / "run_qual_subagent_meta.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="moutai 定性 Subagent（五步）")
    ap.add_argument("--llm", default=None, help="auto|gemini|openai|mock")
    ap.add_argument(
        "--from-step",
        type=int,
        default=1,
        metavar="N",
        help="起始步骤 1–5；大于 1 时从 review/ 读取前面步骤的手工或已保存输出",
    )
    ap.add_argument(
        "--to-step",
        type=int,
        default=5,
        metavar="N",
        help="结束步骤 1–5；小于 5 时不写最终 CSV（仅当执行到第 5 步且产出 scores 时写入）",
    )
    args = ap.parse_args(argv)
    s = run(llm=args.llm, from_step=args.from_step, to_step=args.to_step)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
