"""无 Yahoo 时的确定性演示数据（可复现图表）。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_net_profit_quarterly(years: int = 5) -> pd.Series:
    rng = np.random.default_rng(42)
    n = years * 4 + 4
    end = pd.Timestamp.today().normalize() + pd.offsets.QuarterEnd(0)
    idx = pd.date_range(end=end, periods=n, freq="QE")
    base = 16.5e9
    walk = np.cumsum(rng.normal(0.02, 0.015, size=n))
    vals = base * np.exp(walk)
    return pd.Series(vals, index=idx)


def synthetic_close_daily(years: int = 5) -> pd.Series:
    rng = np.random.default_rng(43)
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=years)
    idx = pd.bdate_range(start=start, end=end, freq="C")
    n = len(idx)
    t = np.linspace(0, 4 * np.pi, n)
    base = 1650.0
    y = base + 120 * np.sin(t / 8) + np.cumsum(rng.normal(0, 8, size=n)) + np.linspace(0, 180, n)
    y = np.clip(y, 1200, 2200)
    return pd.Series(y, index=idx)
