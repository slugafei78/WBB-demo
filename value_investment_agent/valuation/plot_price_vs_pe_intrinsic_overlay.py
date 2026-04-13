"""
Overlay daily close, 120-day MA, and quarterly PE-based intrinsic value (per share).

Default paths target Moutai; override with --daily-csv / --intrinsic-csv / --out.

When macro PE, qualitative PE multiplier, or the **current quarter top factor's score**
(vs the same factor in the prior quarter) changes, draws a compact **3-line** English
note (Macro PE old→new, Qual mult old→new, top factor id old→new). Uses **data coords**
with vertical stacking plus y-axis headroom to reduce overlap.

Usage:

  python -m value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay
  python -m value_investment_agent.valuation.plot_price_vs_pe_intrinsic_overlay --out valuations/moutai/pe/custom.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from value_investment_agent.moutai_experiment.paths import repo_root


def _default_paths_moutai(root: Path) -> tuple[Path, Path, Path, Path]:
    return (
        root / "data" / "moutai" / "raw" / "trading" / "daily_600519_ss_yahoo.csv",
        root / "valuations" / "moutai" / "pe" / "intrinsic_quarterly.csv",
        root / "valuations" / "moutai" / "pe" / "moutai_price_vs_pe_intrinsic_overlay.png",
        root / "factors" / "moutai" / "qualitative" / "moutai_qual_quarterly_scores.csv",
    )


def load_daily_close_and_ma120(daily_csv: Path, *, ma_window: int = 120) -> tuple[pd.Series, pd.Series]:
    df = pd.read_csv(daily_csv, encoding="utf-8-sig")
    if "date" not in df.columns:
        raise ValueError(f"daily CSV must have date column: {daily_csv}")
    close_col = "Close" if "Close" in df.columns else "close"
    if close_col not in df.columns:
        raise ValueError(f"daily CSV must have Close column: {daily_csv}")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").drop_duplicates("date", keep="last")
    close = df.set_index("date")[close_col].astype(float)
    ma = close.rolling(window=ma_window, min_periods=ma_window).mean()
    return close, ma


def load_intrinsic_csv(intrinsic_csv: Path) -> pd.DataFrame:
    """Full intrinsic quarterly table (all columns preserved for annotations)."""
    df = pd.read_csv(intrinsic_csv, encoding="utf-8-sig")
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.normalize()
    return df.sort_values("period_end")


def intrinsic_to_merge_frame(iv_full: pd.DataFrame) -> pd.DataFrame:
    """Narrow frame for merge_asof onto daily index."""
    need = ["period_end", "intrinsic_per_share_pe_simple"]
    for c in need:
        if c not in iv_full.columns:
            raise ValueError(f"intrinsic CSV missing column {c}")
    out = iv_full[["period_end", "intrinsic_per_share_pe_simple"]].copy()
    if "intrinsic_per_share_pe_qual_adjusted" in iv_full.columns:
        out["intrinsic_per_share_pe_qual_adjusted"] = iv_full["intrinsic_per_share_pe_qual_adjusted"]
    else:
        out["intrinsic_per_share_pe_qual_adjusted"] = np.nan
    out = out.rename(
        columns={
            "intrinsic_per_share_pe_simple": "iv_simple",
            "intrinsic_per_share_pe_qual_adjusted": "iv_qual",
        }
    )
    return out


def merge_intrinsic_onto_daily(
    daily_index: pd.DatetimeIndex,
    intrinsic: pd.DataFrame,
) -> pd.DataFrame:
    """Backward asof: each session uses latest quarter-end intrinsic."""
    left = pd.DataFrame({"date": daily_index}).sort_values("date")
    right = intrinsic.rename(columns={"period_end": "pe_date"}).sort_values("pe_date")
    m = pd.merge_asof(left, right, left_on="date", right_on="pe_date", direction="backward")
    return m.set_index("date")


def load_qual_scores_long(qual_csv: Path) -> pd.DataFrame:
    if not qual_csv.is_file():
        return pd.DataFrame()
    df = pd.read_csv(qual_csv, encoding="utf-8-sig")
    if "period_end" not in df.columns:
        return pd.DataFrame()
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.normalize()
    return df


def _top_factor_id_this_quarter(qual_df: pd.DataFrame, period: pd.Timestamp) -> str | None:
    """Highest score factor_id this quarter; tie-break by factor_id."""
    sub = qual_df[qual_df["period_end"] == period.normalize()]
    if sub.empty:
        return None
    sub = sub.copy()
    sub["score"] = pd.to_numeric(sub["score"], errors="coerce")
    sub = sub.dropna(subset=["score"])
    if sub.empty:
        return None
    sub = sub.sort_values(["score", "factor_id"], ascending=[False, True])
    return str(sub.iloc[0]["factor_id"])


def _score_for_factor(
    qual_df: pd.DataFrame, period: pd.Timestamp, factor_id: str
) -> float | None:
    sub = qual_df[
        (qual_df["period_end"] == period.normalize()) & (qual_df["factor_id"] == factor_id)
    ]
    if sub.empty:
        return None
    v = pd.to_numeric(sub["score"], errors="coerce").dropna()
    if v.empty:
        return None
    return float(v.iloc[0])


def _fmt_arrow(old: float | None, new: float | None, *, nd: int) -> str:
    if old is None and new is None:
        return "n/a"
    if old is None:
        return f"->{new:.{nd}f}" if new is not None else "n/a"
    if new is None:
        return f"{old:.{nd}f}->"
    return f"{old:.{nd}f}->{new:.{nd}f}"


def _annotation_triggers_change(
    cur: pd.Series,
    prev: pd.Series,
    qual_df: pd.DataFrame,
    *,
    pe_dt_prev: pd.Timestamp,
    pe_dt_cur: pd.Timestamp,
) -> bool:
    """True iff prev exists and macro PE, qual mult, or top-factor (this quarter) score vs prev quarter moved."""
    if abs(float(cur["pe_macro"]) - float(prev["pe_macro"])) > 1e-4:
        return True
    cq, pq = cur.get("qual_pe_multiplier"), prev.get("qual_pe_multiplier")
    if pd.isna(cq) and pd.isna(pq):
        pass
    elif pd.isna(cq) or pd.isna(pq):
        return True
    elif abs(float(cq) - float(pq)) > 1e-5:
        return True

    top_id = _top_factor_id_this_quarter(qual_df, pe_dt_cur)
    if not top_id:
        return False
    s_prev = _score_for_factor(qual_df, pe_dt_prev, top_id)
    s_cur = _score_for_factor(qual_df, pe_dt_cur, top_id)
    if s_prev is None and s_cur is None:
        return False
    if s_prev is None or s_cur is None:
        return True
    return abs(s_cur - s_prev) > 1e-4


def _annotation_y_level(merged: pd.DataFrame, quarter_end: pd.Timestamp) -> float:
    """IV level at last trading day on or before quarter_end (step series)."""
    sub = merged.loc[merged.index <= quarter_end.normalize()]
    if sub.empty:
        return float(np.nanmax([merged["iv_simple"].max(), merged["iv_qual"].max()]))
    last = sub.iloc[-1]
    a = float(last["iv_simple"])
    b = float(last["iv_qual"]) if pd.notna(last.get("iv_qual")) else a
    return max(a, b)


def add_premium_change_annotations(
    ax: plt.Axes,
    merged: pd.DataFrame,
    iv_full: pd.DataFrame,
    qual_df: pd.DataFrame,
) -> float | None:
    """
    For consecutive quarters where macro PE, qual PE multiplier, or the **current** top
    factor's score (same factor_id vs prior quarter) changes: draw a 3-line English box:
    Macro PE old->new, Qual mult old->new, top_factor_id old->new.

    Positions use **data coordinates** with horizontal date nudge + vertical stack so
    boxes stay separated; caller should extend y-axis top using the return value.
    """
    cols = {"pe_macro", "period_end"}
    if not cols.issubset(iv_full.columns):
        return None

    ylo, yhi = ax.get_ylim()
    span = max(float(yhi - ylo), 1.0)
    y_step = max(span * 0.048, 40.0)
    y_pad = span * 0.035

    prev_row: pd.Series | None = None
    ann_idx = 0
    max_y_text: float | None = None

    for _, row in iv_full.sort_values("period_end").iterrows():
        if prev_row is None:
            prev_row = row
            continue

        pe_prev = pd.Timestamp(prev_row["period_end"])
        pe_cur = pd.Timestamp(row["period_end"])
        if not _annotation_triggers_change(row, prev_row, qual_df, pe_dt_prev=pe_prev, pe_dt_cur=pe_cur):
            prev_row = row
            continue

        line1 = "Macro PE: " + _fmt_arrow(
            float(prev_row["pe_macro"]),
            float(row["pe_macro"]),
            nd=2,
        )
        pq, cq = prev_row.get("qual_pe_multiplier"), row.get("qual_pe_multiplier")
        pq_f = float(pq) if pd.notna(pq) else None
        cq_f = float(cq) if pd.notna(cq) else None
        line2 = "Qual mult: " + _fmt_arrow(pq_f, cq_f, nd=3)

        top_id = _top_factor_id_this_quarter(qual_df, pe_cur) or "n/a"
        s_prev = _score_for_factor(qual_df, pe_prev, top_id) if top_id != "n/a" else None
        s_cur = _score_for_factor(qual_df, pe_cur, top_id) if top_id != "n/a" else None
        line3 = f"{top_id}: " + _fmt_arrow(s_prev, s_cur, nd=1)
        text = f"{line1}\n{line2}\n{line3}"

        y0 = _annotation_y_level(merged, pe_cur)
        if not np.isfinite(y0):
            prev_row = row
            continue
        y_anchor = y0 * 1.02

        x_num = mdates.date2num(pe_cur.to_pydatetime())
        x_slot = (ann_idx % 6) - 2.5
        x_text = mdates.date2num((pe_cur + pd.Timedelta(days=int(x_slot * 26))).to_pydatetime())
        y_text = y_anchor + y_pad + float(ann_idx) * y_step

        ax.annotate(
            text,
            xy=(x_num, y_anchor),
            xytext=(x_text, y_text),
            xycoords=("data", "data"),
            textcoords=("data", "data"),
            fontsize=6.5,
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="wheat", edgecolor="0.5", alpha=0.92),
            arrowprops=dict(arrowstyle="-", color="0.45", lw=0.55, shrinkA=0, shrinkB=0),
        )

        box_top = y_text + span * 0.09
        max_y_text = box_top if max_y_text is None else max(max_y_text, box_top)
        ann_idx += 1
        prev_row = row

    return max_y_text


def plot_overlay(
    close: pd.Series,
    ma120: pd.Series,
    merged: pd.DataFrame,
    *,
    title: str,
    out_png: Path,
    iv_full: pd.DataFrame | None = None,
    qual_scores_csv: Path | None = None,
    figsize: tuple[float, float] = (14, 8),
    dpi: int = 150,
) -> None:
    # English axis labels for portable fonts
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(close.index, close.values, color="#1f77b4", linewidth=0.8, alpha=0.85, label="Daily close")
    ax.plot(ma120.index, ma120.values, color="#ff7f0e", linewidth=1.2, label="120-day MA")

    if "iv_simple" in merged.columns:
        ax.plot(
            merged.index,
            merged["iv_simple"].values,
            color="#2ca02c",
            linewidth=1.4,
            drawstyle="steps-post",
            label="IV (PE × run-rate EPS, macro only)",
        )
    if "iv_qual" in merged.columns and merged["iv_qual"].notna().any():
        ax.plot(
            merged.index,
            merged["iv_qual"].values,
            color="#d62728",
            linewidth=1.4,
            linestyle="--",
            drawstyle="steps-post",
            label="IV (+ qualitative PE adj.)",
        )

    qual_df = load_qual_scores_long(qual_scores_csv) if qual_scores_csv and qual_scores_csv.is_file() else pd.DataFrame()
    if iv_full is not None and not iv_full.empty:
        note_top = add_premium_change_annotations(ax, merged, iv_full, qual_df)
        if note_top is not None:
            lo, hi = ax.get_ylim()
            span = max(float(hi - lo), 1.0)
            ax.set_ylim(lo, max(hi, note_top + 0.05 * span))

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("CNY / share")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    root = repo_root()
    d_daily, d_iv, d_out, d_qual = _default_paths_moutai(root)

    ap = argparse.ArgumentParser(description="Daily close + MA120 + quarterly PE intrinsic overlay")
    ap.add_argument("--daily-csv", type=Path, default=d_daily, help="Daily OHLC CSV (date, Close)")
    ap.add_argument("--intrinsic-csv", type=Path, default=d_iv, help="Quarterly intrinsic CSV")
    ap.add_argument("--qual-scores-csv", type=Path, default=d_qual, help="Long-format qual scores for factor highlight")
    ap.add_argument("--out", type=Path, default=d_out, help="Output PNG path")
    ap.add_argument(
        "--title",
        default="Moutai (600519.SS): close vs simple-PE intrinsic (quarterly, step)",
        help="Figure title",
    )
    ap.add_argument("--ma-window", type=int, default=120, help="MA window (sessions)")
    ap.add_argument(
        "--no-annotations",
        action="store_true",
        help="Skip Macro×/Qual× quarter labels",
    )
    args = ap.parse_args(argv)

    daily_csv = args.daily_csv if args.daily_csv.is_absolute() else root / args.daily_csv
    intrinsic_csv = args.intrinsic_csv if args.intrinsic_csv.is_absolute() else root / args.intrinsic_csv
    qual_csv = args.qual_scores_csv if args.qual_scores_csv.is_absolute() else root / args.qual_scores_csv
    out_png = args.out if args.out.is_absolute() else root / args.out

    close, ma = load_daily_close_and_ma120(daily_csv, ma_window=args.ma_window)

    iv_full = load_intrinsic_csv(intrinsic_csv)
    narrow = intrinsic_to_merge_frame(iv_full)
    merged = merge_intrinsic_onto_daily(close.index, narrow)

    plot_overlay(
        close,
        ma,
        merged,
        title=args.title,
        out_png=out_png,
        iv_full=None if args.no_annotations else iv_full,
        qual_scores_csv=None if args.no_annotations else qual_csv,
    )
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
