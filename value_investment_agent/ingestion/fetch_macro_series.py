"""
按 config/macro_indicators.json 抓取宏观时间序列，写入 data/macro/series/。

  美国（FRED）：需环境变量 FRED_API_KEY（免费注册 https://fred.stlouisfed.org/docs/api/api_key.html）
  中国（akshare）：需 pip install akshare 或 pip install -e ".[macro]"

  python -m value_investment_agent.ingestion.fetch_macro_series
  python -m value_investment_agent.ingestion.fetch_macro_series --years 5
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _config_path() -> Path:
    return repo_root() / "config" / "macro_indicators.json"


def _yf_us_10y_yield(*, start: str, end: str) -> pd.DataFrame:
    """无 FRED 密钥时的备用：Yahoo ^TNX（10 年期美债收益率，%）。"""
    t = yf.Ticker("^TNX")
    h = t.history(start=start, end=end, auto_adjust=False, actions=False)
    if h is None or h.empty:
        return pd.DataFrame(columns=["date", "value"])
    out = h[["Close"]].reset_index()
    out.columns = ["date", "value"]
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["value"])


def _fred_fetch_series(
    series_id: str,
    api_key: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "observation_end": end,
    }
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    obs = r.json().get("observations") or []
    rows = []
    for o in obs:
        v = o.get("value")
        if v in (".", "", None):
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        rows.append({"date": pd.Timestamp(o["date"]), "value": val})
    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _fred_yoy_from_index(
    series_id: str,
    api_key: str,
    start: str,
    end: str,
    lag_months: int = 12,
) -> pd.DataFrame:
    df = _fred_fetch_series(series_id, api_key, start, end)
    if df.empty:
        return df
    df = df.set_index("date").sort_index()
    # 月度指数：用月末对齐
    s = df["value"]
    yoy = (s / s.shift(lag_months) - 1.0) * 100.0
    out = yoy.dropna().reset_index()
    out.columns = ["date", "value"]
    return out


def _fred_target_mid(
    api_key: str,
    start: str,
    end: str,
    low_id: str,
    high_id: str,
) -> pd.DataFrame:
    a = _fred_fetch_series(low_id, api_key, start, end).rename(columns={"value": "low"})
    b = _fred_fetch_series(high_id, api_key, start, end).rename(columns={"value": "high"})
    m = pd.merge(a, b, on="date", how="inner")
    if m.empty:
        return pd.DataFrame(columns=["date", "value"])
    m["value"] = (m["low"] + m["high"]) / 2.0
    return m[["date", "value"]]


def _save_series(out_dir: Path, stem: str, df: pd.DataFrame, meta: dict[str, Any]) -> Path | None:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{stem}.csv"
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df.to_csv(p, index=False, encoding="utf-8-sig")
    meta["files"][stem] = {"rows": int(len(df)), "path": str(p.relative_to(repo_root()))}
    return p


def _akshare_lpr(term: str) -> pd.DataFrame:
    import akshare as ak

    df = ak.macro_china_lpr()
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    # 列名可能是「1年期」/「5年期」或英文
    date_col = [c for c in df.columns if "日" in str(c) or "date" in str(c).lower()][0]
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    val_col = None
    for c in df.columns:
        if c == "date":
            continue
        cs = str(c)
        if term == "1y" and ("1" in cs and "年" in cs):
            val_col = c
            break
        if term == "5y" and ("5" in cs and "年" in cs):
            val_col = c
            break
    if val_col is None:
        # 常见第二、三列
        num_cols = [c for c in df.columns if c != "date"]
        val_col = num_cols[0] if term == "1y" and len(num_cols) > 0 else (num_cols[1] if len(num_cols) > 1 else num_cols[0])
    out = df[["date", val_col]].rename(columns={val_col: "value"})
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)


def _akshare_bond_zh_us(start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    # 接口：返回中美国债收益率
    df = ak.bond_zh_us_rate(start_date=start.replace("-", ""), end_date=end.replace("-", ""))
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    date_col = [c for c in df.columns if "日" in str(c) or "date" in str(c).lower()][0]
    val_col = None
    for c in df.columns:
        if "中国" in str(c) and "10" in str(c):
            val_col = c
            break
    if val_col is None:
        for c in df.columns:
            if "中国" in str(c) and "国债" in str(c):
                val_col = c
                break
    if val_col is None:
        return pd.DataFrame(columns=["date", "value"])
    out = df[[date_col, val_col]].rename(columns={date_col: "date", val_col: "value"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)


def _akshare_cpi_yoy() -> pd.DataFrame:
    import akshare as ak

    # 优先使用月度 CPI 表（若接口存在）
    if hasattr(ak, "macro_china_cpi_monthly"):
        df = ak.macro_china_cpi_monthly()
    else:
        df = ak.macro_china_cpi()
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])

    cols = [str(c) for c in df.columns]
    date_col = next((c for c in df.columns if "月" in str(c) or "date" in str(c).lower()), df.columns[0])
    yoy_col = None
    for c in df.columns:
        s = str(c)
        if "同比" in s and ("全国" in s or "居民消费价格" in s or "总水平" in s):
            yoy_col = c
            break
    if yoy_col is None:
        for c in df.columns:
            if "同比" in str(c):
                yoy_col = c
                break
    if yoy_col is None:
        return pd.DataFrame(columns=["date", "value"])

    sub = df[[date_col, yoy_col]].copy()
    sub.columns = ["period", "value"]
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub["date"] = pd.to_datetime(sub["period"], errors="coerce")
    if sub["date"].isna().all():
        # 常见：「2023年10月份」
        sub["date"] = pd.to_datetime(sub["period"].astype(str).str.replace("年", "-").str.replace("月份", ""), errors="coerce")
    return sub[["date", "value"]].dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def run_fetch(*, years: int) -> dict[str, Any]:
    root = repo_root()
    cfg = json.loads(_config_path().read_text(encoding="utf-8"))
    out_dir = root / cfg.get("output_dir", "data/macro/series")
    end = date.today()
    start = pd.Timestamp(end) - pd.DateOffset(years=years)
    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")

    meta: dict[str, Any] = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "range": {"start": start_s, "end": end_s},
        "fred_api_key_set": bool(os.environ.get("FRED_API_KEY")),
        "files": {},
        "errors": [],
        "warnings": [],
    }

    fred_key = os.environ.get("FRED_API_KEY", "").strip()

    for spec in cfg.get("series", []):
        sid = spec["id"]
        src = spec["source"]
        try:
            if src == "fred":
                if not fred_key:
                    if spec.get("fred_id") == "DGS10" or sid == "us_treasury_10y_yield":
                        df = _yf_us_10y_yield(start=start_s, end=end_s)
                        meta["warnings"].append(
                            f"{sid}: 未设置 FRED_API_KEY，已用 Yahoo ^TNX 作为备用（与 FRED DGS10 可能有细微差别）"
                        )
                        _save_series(out_dir, sid, df, meta)
                    else:
                        meta["errors"].append(f"{sid}: skip (no FRED_API_KEY)")
                    continue
                df = _fred_fetch_series(spec["fred_id"], fred_key, start_s, end_s)
                _save_series(out_dir, sid, df, meta)
            elif src == "fred_yoy_index":
                if not fred_key:
                    meta["errors"].append(f"{sid}: skip (no FRED_API_KEY)")
                    continue
                # 同比需多取约 16 个月指数，否则窗口前段 YoY 为空
                ext_start = (pd.Timestamp(start_s) - pd.DateOffset(months=16)).strftime("%Y-%m-%d")
                df = _fred_yoy_from_index(spec["fred_id"], fred_key, ext_start, end_s)
                df = df[
                    (df["date"] >= pd.Timestamp(start_s)) & (df["date"] <= pd.Timestamp(end_s))
                ]
                _save_series(out_dir, sid, df, meta)
            elif src == "fred_target_mid":
                if not fred_key:
                    meta["errors"].append(f"{sid}: skip (no FRED_API_KEY)")
                    continue
                df = _fred_target_mid(
                    fred_key,
                    start_s,
                    end_s,
                    spec["fred_low"],
                    spec["fred_high"],
                )
                _save_series(out_dir, sid, df, meta)
            elif src == "akshare_lpr":
                try:
                    df = _akshare_lpr(spec.get("lpr_term", "1y"))
                    df = df[(df["date"] >= pd.Timestamp(start_s)) & (df["date"] <= pd.Timestamp(end_s))]
                    _save_series(out_dir, sid, df, meta)
                except Exception as e:
                    meta["errors"].append(f"{sid}: {e!r}")
            elif src == "akshare_bond_zh_us":
                try:
                    df = _akshare_bond_zh_us(start_s, end_s)
                    _save_series(out_dir, sid, df, meta)
                except Exception as e:
                    meta["errors"].append(f"{sid}: {e!r}")
            elif src == "akshare_cpi_yoy":
                try:
                    df = _akshare_cpi_yoy()
                    df = df[(df["date"] >= pd.Timestamp(start_s)) & (df["date"] <= pd.Timestamp(end_s))]
                    _save_series(out_dir, sid, df, meta)
                except Exception as e:
                    meta["errors"].append(f"{sid}: {e!r}")
            else:
                meta["errors"].append(f"{sid}: unknown source {src}")
        except Exception as e:
            meta["errors"].append(f"{sid}: {e!r}")

    meta_path = root / "data" / "macro" / "run_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta["meta_path"] = str(meta_path.relative_to(root))
    return meta


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Fetch macro time series into data/macro/series/")
    p.add_argument("--years", type=int, default=5, help="lookback years (default 5)")
    args = p.parse_args(argv)
    meta = run_fetch(years=args.years)
    root = repo_root()
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\nWrote meta: {root / 'data' / 'macro' / 'run_meta.json'}")


if __name__ == "__main__":
    main()
