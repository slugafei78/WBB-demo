"""维护 news_digest.csv：重大新闻一行一条（日期、摘要、URL）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker
from value_investment_agent.ingestion.yahoo_news_items import (
    yahoo_news_item_link,
    yahoo_news_item_pub_date,
    yahoo_news_item_title,
)
from value_investment_agent.moutai_experiment.paths import news_digest_path


def load_news_digest(path: Path | None = None) -> str:
    """读入摘要文本块，供 LLM 使用。"""
    path = path or news_digest_path()
    if not path.exists():
        return "(暂无 news_digest.csv)"
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return "(news_digest 为空)"
    lines = []
    for _, r in df.iterrows():
        lines.append(f"- {r.get('date', '')}: {r.get('summary', '')} | {r.get('url', '')}")
    return "\n".join(lines)


def append_yahoo_headlines_to_digest(
    *,
    symbol: str = SYMBOL_MOUTAI,
    limit: int = 15,
    path: Path | None = None,
) -> Path:
    """
    将 Yahoo 近期新闻标题追加到 digest（去重：同 url 不重复）。
    提价类重大新闻建议人工在摘要列写完整一句；此处仅作标题抓取补充。
    """
    import yfinance as yf

    path = path or news_digest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    t = yf.Ticker(yahoo_ticker(symbol))
    try:
        raw = t.news or []
    except Exception:
        raw = []
    rows = []
    if path.exists():
        existing = pd.read_csv(path, encoding="utf-8-sig")
        seen = set(existing["url"].astype(str).tolist()) if "url" in existing.columns else set()
        rows = existing.to_dict("records")
    else:
        seen = set()
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        link = yahoo_news_item_link(item).strip()
        if not link or link in seen:
            continue
        dt = yahoo_news_item_pub_date(item)
        title = yahoo_news_item_title(item)
        rows.append(
            {
                "date": dt,
                "summary": title[:500],
                "url": link,
            }
        )
        seen.add(link)
    # 勿对整表 drop_duplicates(subset=["url"])：多条手工摘要 url 为空时会被 pandas 视为同一 NaN 而只保留一行。
    deduped: list[dict] = []
    seen_url: set[str] = set()
    seen_blank: set[tuple[str, str]] = set()
    for r in rows:
        u = str(r.get("url") or "").strip()
        if not u or u.lower() == "nan":
            key = (str(r.get("date", "")), str(r.get("summary", ""))[:300])
            if key in seen_blank:
                continue
            seen_blank.add(key)
            deduped.append(r)
            continue
        if u in seen_url:
            continue
        seen_url.add(u)
        deduped.append(r)
    pd.DataFrame(deduped).to_csv(path, index=False, encoding="utf-8-sig")
    return path
