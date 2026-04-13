"""过去约 5 年季度归属净利润序列：优先读本地 CSV，否则 Yahoo Finance。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker
from value_investment_agent.moutai_experiment.paths import net_profit_csv_path


def _find_net_income_row(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    idx = [str(x).lower() for x in df.index.astype(str)]
    needles = [
        "net income",
        "net income common",
        "net income common stockholders",
        "net income from continuing",
        "净利润",
    ]
    for needle in needles:
        for i, name in enumerate(idx):
            if needle in name:
                return df.iloc[i]
    return None


def load_net_profit_quarterly_from_yahoo(
    symbol: str = SYMBOL_MOUTAI,
    years: int = 5,
) -> pd.Series:
    t = yf.Ticker(yahoo_ticker(symbol))
    stmt = t.quarterly_income_stmt
    if stmt is None or stmt.empty:
        stmt = t.quarterly_financials
    row = _find_net_income_row(stmt)
    if row is None:
        raise ValueError("无法在 Yahoo 财报中找到净利润行，请提供 net_profit_quarterly.csv")
    s = pd.Series(dtype=float)
    for c in stmt.columns:
        try:
            ts = pd.Timestamp(c)
            val = float(row[c])
            s[ts.normalize()] = val
        except Exception:
            continue
    s = s.sort_index()
    cutoff = s.index.max() - pd.DateOffset(years=years)
    s = s[s.index >= cutoff]
    return s


def load_net_profit_quarterly(
    *,
    symbol: str = SYMBOL_MOUTAI,
    years: int = 5,
    csv_path: Path | None = None,
) -> pd.Series:
    csv_path = csv_path or net_profit_csv_path()
    if csv_path.exists():
        df = pd.read_csv(csv_path, encoding="utf-8")
        df["period_end"] = pd.to_datetime(df["period_end"])
        s = pd.Series(df["net_profit"].values, index=pd.DatetimeIndex(df["period_end"]).normalize())
        s = s.sort_index()
        cutoff = s.index.max() - pd.DateOffset(years=years)
        s = s[s.index >= cutoff]
        return s
    return load_net_profit_quarterly_from_yahoo(symbol=symbol, years=years)


def ttm_net_profit_at(asof: pd.Timestamp, ni_q: pd.Series) -> float:
    """截至 asof（含）最近 4 个季度净利润之和。"""
    past = ni_q[ni_q.index <= asof.normalize()].sort_index()
    if len(past) < 4:
        return float(past.sum()) if len(past) else float("nan")
    return float(past.iloc[-4:].sum())


def ttm_net_profit_proxy(asof: pd.Timestamp, ni_q: pd.Series) -> tuple[float, int, str]:
    """
    Run-rate **annual** net-profit proxy from **single-quarter** EPS/NI series.

    When fewer than four quarters exist before ``asof``, extrapolates to a full year:
    - 1 quarter: last quarter × 4
    - 2 quarters: sum(last 2) × 2
    - 3 quarters: sum(last 3) × (4/3)
    - ≥4 quarters: sum of last 4 (classic TTM)

    Returns ``(proxy_profit, quarter_count_used, method_tag)``.
    """
    past = ni_q[ni_q.index <= asof.normalize()].sort_index()
    n = len(past)
    if n == 0:
        return float("nan"), 0, "none"
    if n == 1:
        return float(past.iloc[-1]) * 4.0, 1, "annualize_1q"
    if n == 2:
        return float(past.iloc[-2:].sum()) * 2.0, 2, "annualize_2q"
    if n == 3:
        return float(past.iloc[-3:].sum()) * (4.0 / 3.0), 3, "annualize_3q"
    return float(past.iloc[-4:].sum()), 4, "ttm_4q"


def yoy_ttm_growth_at(asof: pd.Timestamp, ni_q: pd.Series) -> float:
    """TTM 净利润相对一年前 TTM 的增速，用于 DCF growth 输入。"""
    ttm0 = ttm_net_profit_at(asof, ni_q)
    asof_lag = asof - pd.DateOffset(years=1)
    ttm1 = ttm_net_profit_at(asof_lag, ni_q)
    if not (ttm0 > 0 and ttm1 and ttm1 > 0):
        return 0.05
    g = ttm0 / ttm1 - 1.0
    return float(max(-0.15, min(0.25, g)))
