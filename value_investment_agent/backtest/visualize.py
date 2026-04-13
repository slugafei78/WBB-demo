"""回测/诊断图：内在价值、价格、均线。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def plot_intrinsic_dashboard(
    *,
    close: pd.Series,
    fi_daily: pd.Series,
    ma120: pd.Series,
    out_path: Path,
    title: str = "cola: 股价 vs 内在价值 vs 120 日均线",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({"close": close, "fi": fi_daily, "ma120": ma120}).sort_index()
    df = df.dropna(how="all")

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(df.index, df["close"], label="收盘价", color="#1f77b4", linewidth=1.2, alpha=0.9)
    ax.plot(df.index, df["ma120"], label="120 日均线", color="#ff7f0e", linewidth=1.2, alpha=0.85)
    ax.plot(df.index, df["fi"], label="内在价值 Fi (季度阶跃)", color="#2ca02c", linewidth=1.8, drawstyle="steps-post", alpha=0.95)
    ax.set_title(title)
    ax.set_xlabel("日期")
    ax.set_ylabel("价格")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
