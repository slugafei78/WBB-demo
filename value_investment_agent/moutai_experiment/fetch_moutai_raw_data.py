"""
贵州茅台（moutai）原始数据抓取 — 固定脚本，可重复执行。

  python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data

默认：下载约 5 年日线 + 将内置「提价 / i茅台」补充行合并进 news_digest.csv（同日期不覆盖已有行）。

  python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data --years 5 --no-news
  python -m value_investment_agent.moutai_experiment.fetch_moutai_raw_data --no-trading

依赖：yfinance（项目已声明）。行情源为 Yahoo Finance，代码 600519.SS。

说明：
- 财报 PDF：由用户自行放入 data/moutai/raw/financials/，本脚本不下载。
- 新闻：data/moutai/raw/news/news_digest.csv。
- 日线：data/moutai/raw/trading/daily_600519_ss_yahoo.csv。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from value_investment_agent.config.symbols import yahoo_ticker
from value_investment_agent.moutai_experiment.paths import moutai_raw, repo_root


def trading_out_path() -> Path:
    return moutai_raw() / "trading" / "daily_600519_ss_yahoo.csv"


def fetch_trading_daily(*, years: int, out_path: Path | None = None) -> Path:
    """拉取过去约 N 年日线（未复权列，便于与「原始抓取」语义一致）。"""
    out_path = out_path or trading_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    symbol = yahoo_ticker("moutai")
    t = yf.Ticker(symbol)
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    # auto_adjust=False：保留交易所原始 OHLCV，便于归档；A 股拆股极少。
    df = t.history(start=start, end=end, auto_adjust=False, actions=True)
    if df is None or df.empty:
        raise RuntimeError(f"未获取到行情: {symbol} {start.date()} ~ {end.date()}")
    df = df.sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    df.to_csv(out_path, encoding="utf-8-sig")
    return out_path


# 过往几年提价与 i茅台 战略相关摘要（公开信息整理；URL 可后续替换为公告原文链接）
NEWS_SUPPLEMENT_ROWS: list[dict[str, str]] = [
    {
        "date": "2018-01-01",
        "summary": (
            "贵州茅台上调茅台酒出厂价：飞天53度500ml出厂价由819元/瓶上调至969元/瓶，"
            "为多年来首次大幅上调出厂价，体现提价权与利润弹性（次年渠道批发价亦跟进）。"
        ),
        "url": "",
    },
    {
        "date": "2022-05-19",
        "summary": (
            "「i茅台」数字营销APP正式上线，公司推进直销与数字化渠道、强化消费者触达，"
            "为渠道与品牌战略重要节点。"
        ),
        "url": "https://www.moutai.com.cn/",
    },
    {
        "date": "2023-11-01",
        "summary": (
            "公司公告自11月1日起上调53度飞天茅台出厂价与渠道体系，为近年重要提价动作，"
            "有利于增厚营收与利润、体现定价权。"
        ),
        "url": "",
    },
]


def merge_news_digest(*, news_path: Path) -> int:
    """将补充行并入 news_digest.csv：按 date 去重，已有日期不覆盖。"""
    news_path.parent.mkdir(parents=True, exist_ok=True)
    if news_path.exists():
        old = pd.read_csv(news_path, encoding="utf-8")
    else:
        old = pd.DataFrame(columns=["date", "summary", "url"])
    add = pd.DataFrame(NEWS_SUPPLEMENT_ROWS)
    merged = pd.concat([old, add], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = merged.dropna(subset=["date"])
    merged = merged.drop_duplicates(subset=["date"], keep="first")
    merged = merged.sort_values("date").reset_index(drop=True)
    merged.to_csv(news_path, index=False, encoding="utf-8-sig")
    return len(add)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="moutai 原始数据：日线抓取 + 新闻 digest 合并")
    p.add_argument("--years", type=int, default=5, help="日线回溯年数，默认 5")
    p.add_argument("--no-trading", action="store_true", help="不拉行情，仅合并新闻（若未 --no-news）")
    p.add_argument("--no-news", action="store_true", help="不合并新闻，仅拉行情")
    args = p.parse_args(argv)

    root = repo_root()
    news_path = moutai_raw() / "news" / "news_digest.csv"

    if not args.no_trading:
        out = fetch_trading_daily(years=args.years)
        print(f"[trading] 已写入: {out.relative_to(root)}  rows={pd.read_csv(out).shape[0]}")
    if not args.no_news:
        n = merge_news_digest(news_path=news_path)
        print(
            f"[news] 已合并（同 date 保留原文件首条）: {news_path.relative_to(root)}  "
            f"补充模板行数={n}"
        )


if __name__ == "__main__":
    main()
