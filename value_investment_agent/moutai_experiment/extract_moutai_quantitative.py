"""
从 `data/moutai/raw/financials/` 的 PDF 抽取文本归档，并合并 **多数据源** 季度指标为长表 CSV：
`factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv`。

数据源优先级（同日期、同因子，序号越小越优先）：
1. 手动宽表 `quarterly_financials_manual.csv`（与 PDF/财报一致，推荐）
2. `net_profit_quarterly.csv`（仅归母净利润）
3. **东方财富按单季度**：优先读 ``data/moutai/raw/financials/em/*.csv``（由 ``download_moutai_quantitative_raw`` 下载）；缺失时再请求 API
4. 新浪财经 akshare（补充）
5. Yahoo 季报（列数常很少，仅作补充）

  python -m value_investment_agent.moutai_experiment.extract_moutai_quantitative
  python -m value_investment_agent.moutai_experiment.extract_moutai_quantitative --no-akshare

配置：`factors/moutai/config/quant_extract.json`

说明：PDF 仅写入 `_extracted_text/` 供核对；**数值默认不从 PDF 自动解析**，请用上述 CSV 或 akshare/Yahoo。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from value_investment_agent.config.symbols import SYMBOL_MOUTAI
from value_investment_agent.moutai_experiment.paths import moutai_quant_extract_config, moutai_raw, repo_root
from value_investment_agent.moutai_experiment.quant_extract_data import (
    merge_rows,
    rows_from_akshare_sina,
    rows_from_eastmoney_csv_paths,
    rows_from_eastmoney_quarterly,
    rows_from_manual_wide_csv,
    rows_from_net_profit_csv,
    rows_from_yahoo,
    rows_to_dataframe,
)


def _cfg() -> dict:
    p = moutai_quant_extract_config()
    return json.loads(p.read_text(encoding="utf-8"))


def _extract_pdf_text_to_dir(fin_dir: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        import pdfplumber
    except ImportError:
        return written
    for pdf in sorted(fin_dir.glob("*.pdf")):
        parts: list[str] = []
        with pdfplumber.open(pdf) as doc:
            for page in doc.pages:
                t = page.extract_text() or ""
                parts.append(t)
        txt = out_dir / (pdf.stem + ".txt")
        txt.write_text("\n\n".join(parts), encoding="utf-8")
        written.append(txt)
    return written


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="moutai 定量因子季度长表（多源合并）")
    ap.add_argument("--years", type=int, default=None, help="覆盖配置中的 lookback_years（默认约 5 年）")
    ap.add_argument("--no-akshare", action="store_true", help="不调用 akshare（仅用 CSV + Yahoo）")
    args = ap.parse_args(argv)

    cfg = _cfg()
    root = repo_root()
    years = args.years if args.years is not None else int(cfg.get("lookback_years", 5))
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=years)

    fin = moutai_raw() / "financials"
    ext_dir = root / cfg.get("pdf_extracted_text_dir", "data/moutai/raw/financials/_extracted_text")
    pdf_written = _extract_pdf_text_to_dir(fin, ext_dir)

    manual_rel = cfg.get("manual_quarterly_csv", "data/moutai/raw/financials/quarterly_financials_manual.csv")
    np_rel = cfg.get("net_profit_quarterly_csv", "data/moutai/raw/financials/net_profit_quarterly.csv")

    all_rows: list[dict[str, object]] = []
    all_rows.extend(rows_from_manual_wide_csv(root / manual_rel, cutoff))
    all_rows.extend(rows_from_net_profit_csv(root / np_rel, cutoff))

    use_ak = cfg.get("use_akshare", True) and not args.no_akshare
    stock_code = str(cfg.get("akshare_stock_code", "600519"))
    em_symbol = str(cfg.get("akshare_em_symbol", "SH600519"))
    em_profit_rel = cfg.get(
        "em_profit_quarterly_csv",
        "data/moutai/raw/financials/em/profit_sheet_quarterly_em.csv",
    )
    em_cf_rel = cfg.get(
        "em_cashflow_quarterly_csv",
        "data/moutai/raw/financials/em/cash_flow_sheet_quarterly_em.csv",
    )
    em_bal_rel = cfg.get(
        "em_balance_report_csv",
        "data/moutai/raw/financials/em/balance_sheet_by_report_em.csv",
    )
    prefer_em_csv = cfg.get("prefer_em_downloaded_csv", True)
    ak_meta: dict[str, object] = {}
    em_meta: dict[str, object] = {}
    if use_ak:
        em_profit_p = root / em_profit_rel
        em_cf_p = root / em_cf_rel
        if prefer_em_csv and em_profit_p.is_file() and em_cf_p.is_file():
            em_bal_p = root / em_bal_rel
            em_rows, em_meta = rows_from_eastmoney_csv_paths(
                profit_csv=em_profit_p,
                cashflow_csv=em_cf_p,
                cutoff=cutoff,
                balance_csv=em_bal_p if em_bal_p.is_file() else None,
            )
        else:
            em_rows, em_meta = rows_from_eastmoney_quarterly(em_symbol=em_symbol, cutoff=cutoff)
        all_rows.extend(em_rows)
        ak_rows, ak_meta = rows_from_akshare_sina(stock_code=stock_code, cutoff=cutoff)
        all_rows.extend(ak_rows)
    else:
        ak_meta = {"skipped": "flag_or_config"}
        em_meta = {"skipped": "flag_or_config"}

    y_rows, factor_notes = rows_from_yahoo(symbol=SYMBOL_MOUTAI, cutoff=cutoff)
    all_rows.extend(y_rows)

    merged = merge_rows(all_rows)
    df = rows_to_dataframe(merged)

    out = root / cfg.get("output_csv", "factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        print(
            "警告：合并后仍无行。请检查：1) 运行 download_moutai_quantitative_raw 将东财宽表存到 data/.../em/；"
            "2) 或放置 quarterly_financials_manual.csv；3) 网络与 Yahoo 可用。"
        )
    df.to_csv(out, index=False, encoding="utf-8-sig")

    by_source = df.groupby("source").size().to_dict() if not df.empty else {}
    meta = {
        "output_csv": str(out.relative_to(root)),
        "lookback_years": years,
        "cutoff_date_approx": cutoff.strftime("%Y-%m-%d"),
        "pdf_text_files": [str(p.relative_to(root)) for p in pdf_written],
        "factor_notes": factor_notes,
        "eastmoney": em_meta,
        "akshare_sina": ak_meta,
        "rows": int(len(df)),
        "rows_by_source": {str(k): int(v) for k, v in by_source.items()},
        "manual_quarterly_csv": manual_rel,
        "net_profit_quarterly_csv": np_rel,
        "em_profit_quarterly_csv": em_profit_rel,
        "em_cashflow_quarterly_csv": em_cf_rel,
        "em_balance_report_csv": em_bal_rel,
        "prefer_em_downloaded_csv": prefer_em_csv if use_ak else None,
    }
    (out.parent / "moutai_quant_extract_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
