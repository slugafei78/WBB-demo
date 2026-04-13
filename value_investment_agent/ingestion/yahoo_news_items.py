"""Parse yfinance Ticker.news entries (legacy flat dicts and nested content.*)."""

from __future__ import annotations

from datetime import datetime, timezone


def yahoo_news_item_link(item: dict) -> str:
    if item.get("link"):
        return str(item["link"])
    content = item.get("content") or {}
    if not isinstance(content, dict):
        return ""
    cu = content.get("canonicalUrl")
    if isinstance(cu, dict) and cu.get("url"):
        return str(cu["url"])
    ct = content.get("clickThroughUrl")
    if isinstance(ct, dict) and ct.get("url"):
        return str(ct["url"])
    pv = content.get("previewUrl")
    return str(pv) if pv else ""


def yahoo_news_item_title(item: dict) -> str:
    if item.get("title"):
        return str(item["title"])
    content = item.get("content") or {}
    if isinstance(content, dict) and content.get("title"):
        return str(content["title"])
    return ""


def yahoo_news_item_pub_date(item: dict) -> str:
    """UTC calendar date YYYY-MM-DD for CSV / display."""
    ts = item.get("providerPublishTime")
    if ts is not None:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            pass
    content = item.get("content") or {}
    if not isinstance(content, dict):
        return ""
    for key in ("pubDate", "displayTime"):
        v = content.get(key)
        if not v:
            continue
        try:
            s = str(v).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            continue
    return ""
