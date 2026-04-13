"""
数据采集（无 LLM）：按标的 slug 从 Yahoo / SEC 等拉取原始数据，便于写入 `data/{slug}/raw/`。

说明：
- 对外只使用 slug：`cola`、`moutai`、`txrh`；Yahoo 代码在 `config.symbols` 中映射。
- Compustat 等需另行接入；SEC companyfacts 仅适用于有 CIK 的标的。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from value_investment_agent.config.symbols import sec_cik, yahoo_ticker
from value_investment_agent.ingestion.yahoo_news_items import (
    yahoo_news_item_link,
    yahoo_news_item_pub_date,
    yahoo_news_item_title,
)


def _sec_headers() -> dict[str, str]:
    ua = os.environ.get(
        "SEC_USER_AGENT",
        "ValueInvestmentAgent/0.1 (academic research; contact@example.com)",
    )
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def fetch_yahoo_prices(symbol: str, years: int = 10) -> pd.DataFrame:
    """日线 OHLCV，索引为日期。"""
    t = yf.Ticker(yahoo_ticker(symbol))
    end = datetime.now(timezone.utc).date()
    start = pd.Timestamp(end) - pd.DateOffset(years=years)
    df = t.history(start=start, end=end, auto_adjust=True, actions=False)
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def fetch_yahoo_info(symbol: str) -> dict[str, Any]:
    t = yf.Ticker(yahoo_ticker(symbol))
    return dict(t.info or {})


def fetch_yahoo_financials(symbol: str) -> dict[str, pd.DataFrame]:
    t = yf.Ticker(yahoo_ticker(symbol))
    out: dict[str, pd.DataFrame] = {}
    for name, fn in [
        ("income_stmt", lambda: t.quarterly_income_stmt),
        ("balance_sheet", lambda: t.quarterly_balance_sheet),
        ("cashflow", lambda: t.quarterly_cashflow),
    ]:
        try:
            df = fn()
            out[name] = df if df is not None else pd.DataFrame()
        except Exception:
            out[name] = pd.DataFrame()
    return out


def fetch_yahoo_news(symbol: str, limit: int = 50) -> pd.DataFrame:
    t = yf.Ticker(yahoo_ticker(symbol))
    rows: list[dict[str, Any]] = []
    try:
        raw = t.news or []
    except Exception:
        raw = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        link = yahoo_news_item_link(item).strip()
        if not link:
            continue
        d_str = yahoo_news_item_pub_date(item)
        try:
            published = (
                datetime.strptime(d_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).replace(tzinfo=None)
                if d_str
                else pd.NaT
            )
        except ValueError:
            published = pd.NaT
        content = item.get("content") or {}
        publisher = ""
        if isinstance(content, dict):
            prov = content.get("provider") or {}
            if isinstance(prov, dict):
                publisher = str(prov.get("displayName", "") or "")
        if not publisher:
            publisher = str(item.get("publisher", "") or "")
        rows.append(
            {
                "published": published,
                "title": yahoo_news_item_title(item),
                "link": link,
                "publisher": publisher,
            }
        )
    return pd.DataFrame(rows)


def fetch_sec_company_facts(cik: str, sleep_s: float = 0.2) -> dict[str, Any]:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    time.sleep(sleep_s)
    r = requests.get(url, headers=_sec_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def _pick_us_gaap_facts(facts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return (facts.get("facts") or {}).get("us-gaap") or {}


def facts_to_quarterly_series(
    facts_json: dict[str, Any],
    tag_candidates: list[str],
    unit: str = "USD",
) -> pd.Series:
    us = _pick_us_gaap_facts(facts_json)
    for tag in tag_candidates:
        if tag not in us:
            continue
        units = us[tag].get("units") or {}
        if unit not in units:
            continue
        pts = units[unit]
        rows = []
        for p in pts:
            if p.get("fp") not in ("Q1", "Q2", "Q3", "Q4"):
                continue
            end = p.get("end")
            if not end:
                continue
            rows.append((pd.Timestamp(end), float(p["val"])))
        if not rows:
            continue
        s = pd.Series(dict(rows))
        s = s.sort_index()
        s = s[~s.index.duplicated(keep="last")]
        return s
    return pd.Series(dtype=float)


@dataclass
class RawDataBundle:
    """内存中的原始抓取结果，可持久化到任意 output_dir（例如缓存目录）。"""

    symbol: str
    prices: pd.DataFrame
    info: dict[str, Any]
    financials: dict[str, pd.DataFrame]
    news: pd.DataFrame
    sec_facts: dict[str, Any] | None = None
    sec_revenue_q: pd.Series = field(default_factory=pd.Series)
    sec_ocf_q: pd.Series = field(default_factory=pd.Series)

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.prices.to_csv(output_dir / "prices_daily.csv")
        with open(output_dir / "yahoo_info.json", "w", encoding="utf-8") as f:
            json.dump(self.info, f, indent=2, default=str)
        for k, df in self.financials.items():
            df.to_csv(output_dir / f"financials_{k}.csv")
        self.news.to_csv(output_dir / "news.csv", index=False)
        if self.sec_facts is not None:
            with open(output_dir / "sec_companyfacts.json", "w", encoding="utf-8") as f:
                json.dump(self.sec_facts, f, default=str)
        if not self.sec_revenue_q.empty:
            self.sec_revenue_q.rename("value").to_frame().to_csv(output_dir / "sec_revenue_quarterly.csv")
        if not self.sec_ocf_q.empty:
            self.sec_ocf_q.rename("value").to_frame().to_csv(output_dir / "sec_ocf_quarterly.csv")

    @classmethod
    def load(cls, symbol: str, output_dir: Path) -> RawDataBundle:
        prices = pd.read_csv(output_dir / "prices_daily.csv", index_col=0, parse_dates=True)
        with open(output_dir / "yahoo_info.json", encoding="utf-8") as f:
            info = json.load(f)
        financials = {}
        for name in ("income_stmt", "balance_sheet", "cashflow"):
            p = output_dir / f"financials_{name}.csv"
            financials[name] = pd.read_csv(p, index_col=0, parse_dates=True) if p.exists() else pd.DataFrame()
        news = (
            pd.read_csv(output_dir / "news.csv", parse_dates=["published"])
            if (output_dir / "news.csv").exists()
            else pd.DataFrame()
        )
        sec_path = output_dir / "sec_companyfacts.json"
        sec_facts = None
        if sec_path.exists():
            with open(sec_path, encoding="utf-8") as f:
                sec_facts = json.load(f)
        sr = (
            pd.read_csv(output_dir / "sec_revenue_quarterly.csv", index_col=0, parse_dates=True)["value"]
            if (output_dir / "sec_revenue_quarterly.csv").exists()
            else pd.Series(dtype=float)
        )
        so = (
            pd.read_csv(output_dir / "sec_ocf_quarterly.csv", index_col=0, parse_dates=True)["value"]
            if (output_dir / "sec_ocf_quarterly.csv").exists()
            else pd.Series(dtype=float)
        )
        return cls(
            symbol=symbol,
            prices=prices,
            info=info,
            financials=financials,
            news=news,
            sec_facts=sec_facts,
            sec_revenue_q=sr,
            sec_ocf_q=so,
        )


def fetch_raw_bundle(
    symbol: str,
    years: int = 10,
    output_dir: Path | None = None,
    skip_sec: bool = False,
) -> RawDataBundle:
    """抓取并可选落盘。symbol 为 slug（如 cola）。"""
    prices = fetch_yahoo_prices(symbol, years=years)
    info = fetch_yahoo_info(symbol)
    financials = fetch_yahoo_financials(symbol)
    news = fetch_yahoo_news(symbol, limit=50)
    sec_facts = None
    sec_rev = pd.Series(dtype=float)
    sec_ocf = pd.Series(dtype=float)
    cik = sec_cik(symbol)
    if not skip_sec and cik:
        try:
            sec_facts = fetch_sec_company_facts(cik)
            sec_rev = facts_to_quarterly_series(
                sec_facts,
                ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
            )
            sec_ocf = facts_to_quarterly_series(
                sec_facts,
                ["NetCashProvidedByUsedInOperatingActivities"],
            )
        except Exception:
            sec_facts = None
    bundle = RawDataBundle(
        symbol=symbol,
        prices=prices,
        info=info,
        financials=financials,
        news=news,
        sec_facts=sec_facts,
        sec_revenue_q=sec_rev,
        sec_ocf_q=sec_ocf,
    )
    if output_dir is not None:
        bundle.save(output_dir)
    return bundle
