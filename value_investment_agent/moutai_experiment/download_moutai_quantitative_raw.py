"""
从东方财富（akshare）等接口下载 **原始** quantitative 财报宽表，落盘到 **data/** 目录。

不落盘到 ``factors/``；合并后的长表仍由 ``extract_moutai_quantitative`` 写入 ``factors/moutai/quantitative/``。

  python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw
  python -m value_investment_agent.moutai_experiment.download_moutai_quantitative_raw --sina

配置默认与 ``factors/moutai/config/quant_extract.json`` 中 ``akshare_em_symbol`` / ``akshare_stock_code`` 一致。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from value_investment_agent.moutai_experiment.paths import (
    moutai_em_quantitative_raw_dir,
    moutai_quant_extract_config,
    moutai_sina_financials_raw_dir,
    repo_root,
)


def _cfg() -> dict:
    return json.loads(moutai_quant_extract_config().read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="下载 moutai 原始财报宽表到 data/moutai/raw/financials/")
    ap.add_argument("--no-em", action="store_true", help="不下载东方财富按单季度表")
    ap.add_argument("--sina", action="store_true", help="同时下载新浪财经三大表（宽表 CSV）")
    args = ap.parse_args(argv)

    try:
        import akshare as ak  # noqa: PLC0415
        import pandas as pd
    except ImportError as e:
        raise SystemExit("需要安装 akshare、pandas：pip install -e \".[moutai]\"") from e

    root = repo_root()
    cfg = _cfg()
    em_sym = str(cfg.get("akshare_em_symbol", "SH600519"))
    sina_code = str(cfg.get("akshare_stock_code", "600519"))

    em_dir = moutai_em_quantitative_raw_dir()
    em_dir.mkdir(parents=True, exist_ok=True)

    meta: dict[str, object] = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "akshare_em_symbol": em_sym,
        "akshare_sina_stock_code": sina_code,
        "files": {},
    }

    if not args.no_em:
        profit_path = em_dir / "profit_sheet_quarterly_em.csv"
        cf_path = em_dir / "cash_flow_sheet_quarterly_em.csv"
        bal_path = em_dir / "balance_sheet_by_report_em.csv"
        try:
            pdf = ak.stock_profit_sheet_by_quarterly_em(symbol=em_sym)
            pdf.to_csv(profit_path, index=False, encoding="utf-8-sig")
            meta["files"]["profit_sheet_quarterly_em"] = str(profit_path.relative_to(root))
        except Exception as e:  # noqa: BLE001
            meta["profit_em_error"] = str(e)
        try:
            cdf = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=em_sym)
            cdf.to_csv(cf_path, index=False, encoding="utf-8-sig")
            meta["files"]["cash_flow_sheet_quarterly_em"] = str(cf_path.relative_to(root))
        except Exception as e:  # noqa: BLE001
            meta["cashflow_em_error"] = str(e)
        try:
            bdf = ak.stock_balance_sheet_by_report_em(symbol=em_sym)
            bdf.to_csv(bal_path, index=False, encoding="utf-8-sig")
            meta["files"]["balance_sheet_by_report_em"] = str(bal_path.relative_to(root))
        except Exception as e:  # noqa: BLE001
            meta["balance_em_error"] = str(e)

    if args.sina:
        sdir = moutai_sina_financials_raw_dir()
        sdir.mkdir(parents=True, exist_ok=True)
        for name in ("利润表", "现金流量表", "资产负债表"):
            safe = {"利润表": "profit_sina", "现金流量表": "cash_flow_sina", "资产负债表": "balance_sina"}[name]
            p = sdir / f"{safe}.csv"
            try:
                df = ak.stock_financial_report_sina(stock=sina_code, symbol=name)
                df.to_csv(p, index=False, encoding="utf-8-sig")
                meta["files"][safe] = str(p.relative_to(root))
            except Exception as e:  # noqa: BLE001
                meta[f"{safe}_error"] = str(e)

    (em_dir / "download_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
