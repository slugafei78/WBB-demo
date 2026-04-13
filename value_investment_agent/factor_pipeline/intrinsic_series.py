"""
由 RawDataBundle 与 LLM 定性分构造季度 Fi，并前向填充到日频。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from value_investment_agent.config.symbols import SYMBOL_COLA
from value_investment_agent.llm.llm_provider import LLMProvider
from value_investment_agent.factor_pipeline.llm_qualitative import (
    QualitativeScore0To20Output,
    run_llm_qualitative_0_20,
    scores_0_20_to_synthesizer_1_10,
)
from value_investment_agent.ingestion.data_fetch import RawDataBundle
from value_investment_agent.synthesis.rules_synthesizer import RulesParameterSynthesizer


def _find_row(df: pd.DataFrame, needles: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    idx = [str(x).lower() for x in df.index.astype(str)]
    for n in needles:
        nl = n.lower()
        for i, name in enumerate(idx):
            if nl in name:
                return df.iloc[i]
    return None


def _col_on_or_before(cols: pd.DatetimeIndex, q: pd.Timestamp) -> pd.Timestamp | None:
    valid = [c for c in cols if pd.Timestamp(c) <= q.normalize()]
    if not valid:
        return None
    return max(valid, key=lambda x: pd.Timestamp(x))


def build_quant_snapshot(
    bundle: RawDataBundle,
    quarter_end: pd.Timestamp,
) -> tuple[dict[str, Any], str]:
    cf = bundle.financials.get("cashflow") or pd.DataFrame()
    bs = bundle.financials.get("balance_sheet") or pd.DataFrame()
    inc = bundle.financials.get("income_stmt") or pd.DataFrame()

    def col(df: pd.DataFrame) -> pd.Timestamp | None:
        if df is None or df.empty:
            return None
        cols = pd.to_datetime(df.columns, errors="coerce")
        return _col_on_or_before(cols, quarter_end)

    c_cf, c_bs, c_inc = col(cf), col(bs), col(inc)
    ocf_row = _find_row(cf, ["Operating Cash Flow", "Cash From Operating Activities", "Operating Cashflow"])
    capex_row = _find_row(cf, ["Capital Expenditure", "Capital Expenditures"])
    shares_row = _find_row(bs, ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"])

    ocf = float(ocf_row[c_cf]) if ocf_row is not None and c_cf is not None and c_cf in ocf_row.index else float("nan")
    capex = float(capex_row[c_cf]) if capex_row is not None and c_cf is not None and c_cf in capex_row.index else float("nan")
    if np.isfinite(ocf) and np.isfinite(capex):
        fcf = ocf + capex if capex < 0 else ocf - abs(capex)
    else:
        fcf = float("nan")

    shares = bundle.info.get("sharesOutstanding")
    if shares_row is not None and c_bs is not None and c_bs in shares_row.index:
        try:
            shares = float(shares_row[c_bs])
        except Exception:
            pass
    if shares is None or not np.isfinite(float(shares)) or float(shares) <= 0:
        shares = 4.3e9

    debt = 0.0
    cash = 0.0
    lt = _find_row(bs, ["Long Term Debt"])
    st = _find_row(bs, ["Current Debt", "Short Long Term Debt"])
    ce = _find_row(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    if lt is not None and c_bs is not None and c_bs in lt.index:
        debt += max(float(lt[c_bs]), 0.0)
    if st is not None and c_bs is not None and c_bs in st.index:
        debt += max(float(st[c_bs]), 0.0)
    if ce is not None and c_bs is not None and c_bs in ce.index:
        cash += max(float(ce[c_bs]), 0.0)
    net_debt = debt - cash

    rev_row = _find_row(inc, ["Total Revenue", "Operating Revenue"])
    growth_rate = 0.03
    if rev_row is not None and c_inc is not None:
        cols_sorted = sorted(pd.to_datetime(inc.columns, errors="coerce"), reverse=True)
        try:
            i0 = cols_sorted.index(pd.Timestamp(c_inc))
            if i0 + 1 < len(cols_sorted):
                c_prev = cols_sorted[i0 + 1]
                r0 = float(rev_row[c_inc])
                r1 = float(rev_row[c_prev])
                if r1 > 0:
                    growth_rate = (r0 / r1) ** (1.0 / 4.0) - 1.0
                    growth_rate = float(max(-0.1, min(0.2, growth_rate)))
        except Exception:
            pass

    fcf_ps = fcf / float(shares) if np.isfinite(fcf) and float(shares) > 0 else 0.5
    if not np.isfinite(fcf_ps) or fcf_ps <= 0:
        fcf_ps = max(float(bundle.info.get("trailingEps") or 0.5) * 0.8, 0.1)

    wacc = 0.085
    terminal_growth = 0.022
    fcf_ps = float(max(0.05, min(12.0, fcf_ps)))

    base = {
        "fcf_per_share": float(fcf_ps),
        "shares_outstanding": float(shares),
        "net_debt": float(net_debt),
        "growth_rate": float(growth_rate),
        "terminal_growth": float(terminal_growth),
        "wacc": float(wacc),
        "forecast_years": 5,
    }

    snippet = (
        f"Quarter end (report column used): {quarter_end.date()}\n"
        f"FCF/share (approx): {fcf_ps:.4f}, implied YoY quarterly revenue growth (approx): {growth_rate:.2%}\n"
        f"Shares outstanding: {shares:.0f}, net_debt (approx): {net_debt:.0f}\n"
        f"Assumed baseline WACC {wacc:.2%}, terminal growth {terminal_growth:.2%} (modulated by qualitative scores).\n"
    )
    return base, snippet


def quarterly_fi_series(
    bundle: RawDataBundle,
    *,
    symbol: str = SYMBOL_COLA,
    llm_provider: LLMProvider = "auto",
    use_openai: bool | None = None,
    freq: str = "quarterly",
) -> tuple[pd.Series, list[QualitativeScore0To20Output]]:
    cf = bundle.financials.get("cashflow") or pd.DataFrame()
    if cf.empty:
        raise ValueError("缺少现金流量表，请检查网络或数据源。")
    cols = sorted(pd.to_datetime(cf.columns, errors="coerce"))
    p_start = bundle.prices.index.min()
    p_end = bundle.prices.index.max()
    cols = [c for c in cols if pd.Timestamp(c) <= p_end and pd.Timestamp(c) >= p_start - pd.DateOffset(months=15)]
    if freq == "annual":
        cols = [c for c in cols if pd.Timestamp(c).month == 12]
    if len(cols) < 2:
        cols = sorted(pd.to_datetime(cf.columns, errors="coerce"))[-8:]
    synth = RulesParameterSynthesizer()
    fis: list[float] = []
    idx: list[pd.Timestamp] = []
    qual_outputs: list[QualitativeScore0To20Output] = []

    name = str(bundle.info.get("longName") or bundle.info.get("shortName") or symbol)
    summary = str(bundle.info.get("longBusinessSummary") or "")

    for c in cols:
        q = pd.Timestamp(c)
        base, qtxt = build_quant_snapshot(bundle, q)
        news_df = bundle.news
        if news_df is not None and not news_df.empty and "published" in news_df.columns:
            sub = news_df[pd.to_datetime(news_df["published"]) <= q]
            lines = [f"- {r['title']}" for _, r in sub.tail(25).iterrows()]
            news_excerpt = "\n".join(lines) if lines else "(no news dated on or before quarter in feed)"
        else:
            news_excerpt = "(no news available)"

        qual = run_llm_qualitative_0_20(
            company_name=name,
            symbol=symbol,
            asof_date=q.strftime("%Y-%m-%d"),
            business_summary=summary,
            quantitative_snippet=qtxt,
            news_excerpt=news_excerpt,
            llm_provider=llm_provider,
            use_openai=use_openai,
        )
        qual_outputs.append(qual)
        m = {f.name: float(f.score_0_to_20) for f in qual.factors}
        m10 = scores_0_20_to_synthesizer_1_10(m)
        fi = synth.intrinsic_value("dcf", base, m10)
        fis.append(float(fi))
        idx.append(q.normalize())

    s = pd.Series(fis, index=pd.DatetimeIndex(idx))
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s, qual_outputs


def forward_fill_fi_to_daily(fi_q: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    out = []
    for d in daily_index:
        past = fi_q[fi_q.index <= d]
        out.append(float(past.iloc[-1]) if len(past) else float("nan"))
    return pd.Series(out, index=daily_index)


def add_ma120(prices: pd.Series) -> pd.Series:
    return prices.rolling(120, min_periods=60).mean()
