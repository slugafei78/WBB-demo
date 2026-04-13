"""季度 DCF：纯量化 vs 叠加简化定性调制（不经 Parameter Synthesizer）。"""

from __future__ import annotations

import pandas as pd

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker
from value_investment_agent.moutai_experiment.net_profit_series import (
    load_net_profit_quarterly,
    ttm_net_profit_at,
    yoy_ttm_growth_at,
)
from value_investment_agent.moutai_experiment.qual_four import MoutaiQualFour, modulation_index
from value_investment_agent.valuation.dcf import dcf_intrinsic_per_share
import yfinance as yf


def _shares_and_debt(symbol: str) -> tuple[float, float]:
    t = yf.Ticker(yahoo_ticker(symbol))
    info = t.info or {}
    sh = float(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 1.26e9)
    bs = t.quarterly_balance_sheet
    debt = 0.0
    cash = 0.0
    if bs is not None and not bs.empty:
        cols = sorted(pd.to_datetime(bs.columns, errors="coerce"), reverse=True)
        if cols:
            c = cols[0]

            def pick(*needles: str) -> float:
                idx = [str(x).lower() for x in bs.index.astype(str)]
                for nd in needles:
                    for i, name in enumerate(idx):
                        if nd in name:
                            try:
                                return float(bs.iloc[i][c])
                            except Exception:
                                return 0.0
                return 0.0

            debt = max(0.0, pick("long term debt", "total debt non current")) + max(
                0.0, pick("current debt", "short long term debt")
            )
            cash = max(0.0, pick("cash and cash equivalents", "cash cash equivalents"))
    net_debt = debt - cash
    return sh, float(net_debt)


def build_quarterly_fi_moutai(
    *,
    symbol: str = SYMBOL_MOUTAI,
    years: int = 5,
    qual: MoutaiQualFour,
    ni_quarterly: pd.Series | None = None,
    fcf_from_ni_factor: float = 0.92,
    base_wacc: float = 0.095,
    base_terminal: float = 0.025,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    返回 (fi_vanilla, fi_adjusted, ttm_ni_per_share 用于说明) 均以季度末为索引。
    若传入 ni_quarterly 则不再从 Yahoo/本地 CSV 加载。
    """
    ni_q = (
        ni_quarterly
        if ni_quarterly is not None
        else load_net_profit_quarterly(symbol=symbol, years=years + 1)
    )
    shares, net_debt = _shares_and_debt(symbol)
    m = modulation_index(qual)

    end = ni_q.index.max()
    start = end - pd.DateOffset(years=years)
    quarters = ni_q[ni_q.index >= start].sort_index().index

    fi_v: list[float] = []
    fi_a: list[float] = []
    ttm_eps: list[float] = []
    idx_list: list[pd.Timestamp] = []

    for q in quarters:
        ttm = ttm_net_profit_at(q, ni_q)
        if not (ttm > 0 and shares > 0):
            continue
        growth = yoy_ttm_growth_at(q, ni_q)
        fcf_per_share = (ttm / shares) * fcf_from_ni_factor

        wacc_v = base_wacc
        g_v = growth
        if wacc_v <= base_terminal:
            wacc_v = base_terminal + 0.01

        v = dcf_intrinsic_per_share(
            fcf_per_share=fcf_per_share,
            shares_outstanding=shares,
            net_debt=net_debt,
            growth_rate=g_v,
            terminal_growth=base_terminal,
            wacc=wacc_v,
            forecast_years=5,
        )

        g_a = g_v + 0.015 * m
        w_a = wacc_v - 0.008 * m
        g_a = max(-0.1, min(0.28, g_a))
        w_a = max(base_terminal + 0.008, min(0.16, w_a))

        a = dcf_intrinsic_per_share(
            fcf_per_share=fcf_per_share,
            shares_outstanding=shares,
            net_debt=net_debt,
            growth_rate=g_a,
            terminal_growth=base_terminal,
            wacc=w_a,
            forecast_years=5,
        )

        fi_v.append(float(v))
        fi_a.append(float(a))
        ttm_eps.append(float(ttm / shares))
        idx_list.append(q.normalize())

    idx = pd.DatetimeIndex(idx_list)
    return (
        pd.Series(fi_v, index=idx),
        pd.Series(fi_a, index=idx),
        pd.Series(ttm_eps, index=idx),
    )
