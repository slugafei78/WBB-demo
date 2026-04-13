"""茅台五年度图：真实股价、120 日均线、两条季度 Fi（纯 DCF / 定性调制）。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from value_investment_agent.config.symbols import yahoo_ticker
import yfinance as yf

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def fetch_prices_years(symbol: str, years: int) -> pd.Series:
    t = yf.Ticker(yahoo_ticker(symbol))
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    h = t.history(start=start, end=end, auto_adjust=True, actions=False)
    s = h["Close"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s


def plot_moutai_dashboard(
    *,
    close: pd.Series,
    fi_vanilla: pd.Series,
    fi_adjusted: pd.Series,
    out_path: Path,
    title: str = "贵州茅台（moutai）：股价、均线与季度内在价值 Fi",
) -> Path:
    ma120 = close.rolling(120, min_periods=60).mean()

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(close.index, close.values, label="真实收盘价", color="#1f77b4", linewidth=1.2, alpha=0.9)
    ax.plot(ma120.index, ma120.values, label="120 日均线", color="#ff7f0e", linewidth=1.2, alpha=0.85)

    ax.plot(
        fi_vanilla.index,
        fi_vanilla.values,
        marker="o",
        linestyle="-",
        label="Fi 纯 DCF（仅净利润序列）",
        color="#7f7f7f",
        linewidth=1.5,
        markersize=5,
    )
    ax.plot(
        fi_adjusted.index,
        fi_adjusted.values,
        marker="o",
        linestyle="-",
        label="Fi DCF + 四项定性调制",
        color="#2ca02c",
        linewidth=1.8,
        markersize=5,
    )

    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("价格（元）")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
