"""
茅台（可推广到其他标的）季度 **内在价值（简化 PE）** 估计。

**估值 A**：仅宏观存款利率调整 PE（基准 PE 来自配置，默认 20；相对历史存款利率区间映射到约 ±10% 带，默认 PE 18–22），
再乘以 **TTM 归属净利润/股本** 得到每股隐含价值。

**估值 B**：在 A 的 **宏观 PE** 基础上，用 10 个定性因子分数的 **乘积** 映射到 PE 乘子（默认 [0.5, 1.2]），
再裁剪到全局 PE 上下限（默认 10–24），最后同样 × TTM EPS。某季若 10 因子未齐：**沿用上一季完整分**；尚无历史则用配置 **qual_default_score**（或 **qual_default_scores**）。

输入数据：
- 定量：`factors/moutai/quantitative/moutai_fundamental_quant_quarterly.csv`（长表，`net_profit_attributable`）
  **须为单季归属净利润**。不足四季时按 ``×4 / ×2 / ×4/3`` 年化近似 TTM（见 ``ttm_net_profit_proxy``）。
- 定性：`factors/moutai/qualitative/moutai_qual_quarterly_scores.csv`
- 宏观：`factors/macro/series/macro_CHN_FR_INR_DPST.csv`（`period_end`, `value` 为存款利率 %）

  python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly
  python -m value_investment_agent.moutai_experiment.pe_intrinsic_quarterly --config path/to/config.json

配置（默认）：`valuations/{symbol}/pe/config.json`（与 `data/`、`factors/` 并列的估值层）。  
说明：`valuations/moutai/pe/README.md`；总览：`valuations/README.md`。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker
from value_investment_agent.moutai_experiment.net_profit_series import ttm_net_profit_proxy
from value_investment_agent.moutai_experiment.paths import repo_root, valuation_symbol_dir
from value_investment_agent.valuation.pe_macro_qual import (
    apply_pe_global_cap_floor,
    pe_from_deposit_rate_linear,
    qualitative_pe_multiplier_from_scores,
)


def _cfg_path(symbol: str = SYMBOL_MOUTAI, *, override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    return valuation_symbol_dir(symbol) / "pe" / "config.json"


def _load_cfg(symbol: str = SYMBOL_MOUTAI, *, config_path: Path | None = None) -> dict[str, Any]:
    p = _cfg_path(symbol, override=config_path)
    if not p.is_file():
        raise FileNotFoundError(
            f"估值配置不存在: {p}\n"
            f"默认路径为 valuations/{symbol}/pe/config.json；可用 --config 指定。"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_shares(cfg: dict[str, Any], symbol: str) -> float:
    raw = cfg.get("shares_outstanding")
    if raw is not None and str(raw).strip() != "":
        return float(raw)
    try:
        t = yf.Ticker(yahoo_ticker(symbol))
        info = t.info or {}
        sh = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        if sh is not None and float(sh) > 0:
            return float(sh)
    except Exception:
        pass
    return float(cfg.get("shares_outstanding_fallback", 1.25619712e9))


def load_quarterly_net_profit_long(root: Path, cfg: dict[str, Any]) -> pd.Series:
    """长表 → 单季归属净利润序列（索引季度末）。"""
    p = root / str(cfg["quant_quarterly_csv"])
    df = pd.read_csv(p, encoding="utf-8-sig")
    fid = str(cfg["earnings_factor_id"])
    df = df[df["factor_id"] == fid].copy()
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.normalize()
    df = df.sort_values("period_end")
    s = pd.Series(df["value"].values, index=pd.DatetimeIndex(df["period_end"]))
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def load_macro_deposit(root: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    p = root / str(cfg["macro_deposit_csv"])
    df = pd.read_csv(p, encoding="utf-8")
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.normalize()
    return df.sort_values("period_end")


def load_qual_scores_wide(root: Path, cfg: dict[str, Any]) -> pd.DataFrame:
    """季度 × factor_id → 宽表（列名为 factor_id）。"""
    p = root / str(cfg["qual_scores_csv"])
    df = pd.read_csv(p, encoding="utf-8-sig")
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.normalize()
    wide = df.pivot_table(index="period_end", columns="factor_id", values="score", aggfunc="first")
    return wide.sort_index()


def _default_qual_scores(expected_factors: list[str], cfg: dict[str, Any]) -> list[float]:
    """首季及之前无观测时使用的默认定性分（与 expected 顺序一致）。"""
    raw_list = cfg.get("qual_default_scores")
    if raw_list is not None and isinstance(raw_list, list) and len(raw_list) > 0:
        if len(raw_list) != len(expected_factors):
            raise ValueError(
                "qual_default_scores 长度须与 expected_qual_factor_ids 一致，"
                f"现为 {len(raw_list)} vs {len(expected_factors)}"
            )
        return [float(x) for x in raw_list]
    one = float(cfg.get("qual_default_score", 6.0))
    return [one] * len(expected_factors)


def _resolve_qual_scores_row(
    qn: pd.Timestamp,
    qual_wide: pd.DataFrame,
    expected_factors: list[str],
    last_complete: list[float] | None,
    default_scores: list[float],
) -> tuple[list[float], list[float] | None, str]:
    """
    返回 (用于计算的分数, 更新后的 last_complete, 来源标签)。
    本季 10 因子齐全 → observed；否则若有上一季 → carry_forward；否则 → default。
    """
    if qn in qual_wide.index:
        row = qual_wide.loc[qn]
        if all(f in row.index and pd.notna(row[f]) for f in expected_factors):
            scores = [float(row[f]) for f in expected_factors]
            return scores, scores, "observed"
    if last_complete is not None:
        return last_complete, last_complete, "carry_forward"
    return default_scores, default_scores, "default"


def build_pe_intrinsic_table(
    *,
    symbol: str = SYMBOL_MOUTAI,
    root: Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = root or repo_root()
    cfg = cfg or _load_cfg(symbol)

    ni_q = load_quarterly_net_profit_long(root, cfg)
    macro = load_macro_deposit(root, cfg)
    qual_wide = load_qual_scores_wide(root, cfg)

    r_min = float(macro["value"].min())
    r_max = float(macro["value"].max())

    shares = _resolve_shares(cfg, symbol)

    pe_low = float(cfg["pe_macro_when_rates_low"])
    pe_high = float(cfg["pe_macro_when_rates_high"])
    pe_anchor = float(cfg.get("base_pe_reference", 20.0))
    score_floor = float(cfg.get("qual_score_floor", 1.0))
    score_cap = float(cfg.get("qual_score_cap", 10.0))
    mult_min = float(cfg.get("qual_pe_mult_min", 0.5))
    mult_max = float(cfg.get("qual_pe_mult_max", 1.2))
    pe_glob_floor = float(cfg.get("qual_adjusted_pe_floor", 10.0))
    pe_glob_cap = float(cfg.get("qual_adjusted_pe_cap", 24.0))

    expected_factors: list[str] = list(cfg.get("expected_qual_factor_ids", []))
    default_qual = _default_qual_scores(expected_factors, cfg) if expected_factors else []
    last_complete_qual: list[float] | None = None

    rows: list[dict[str, Any]] = []
    macro_sorted = macro.sort_values("period_end")

    for q in ni_q.index:
        qn = q.normalize()
        rate_row = macro_sorted[macro_sorted["period_end"] <= qn]
        if rate_row.empty:
            continue
        rate_pct = float(rate_row.iloc[-1]["value"])

        pe_macro = pe_from_deposit_rate_linear(
            rate_pct,
            rate_hist_min=r_min,
            rate_hist_max=r_max,
            pe_when_rates_low=pe_low,
            pe_when_rates_high=pe_high,
        )

        ttm_ni, ttm_n_used, ttm_method = ttm_net_profit_proxy(qn, ni_q)
        if not (ttm_ni > 0 and shares > 0):
            continue
        ttm_eps = float(ttm_ni / shares)
        iv_simple = float(pe_macro * ttm_eps)

        row: dict[str, Any] = {
            "period_end": qn.strftime("%Y-%m-%d"),
            "deposit_rate_pct": rate_pct,
            "deposit_rate_hist_min": r_min,
            "deposit_rate_hist_max": r_max,
            "pe_macro": round(pe_macro, 4),
            "pe_anchor_reference": round(pe_anchor, 4),
            "macro_pe_vs_anchor": round(pe_macro / pe_anchor, 6) if pe_anchor > 0 else None,
            "ttm_net_profit_proxy": round(ttm_ni, 2),
            "ttm_quarters_used": ttm_n_used,
            "ttm_proxy_method": ttm_method,
            "shares_outstanding": shares,
            "ttm_eps": round(ttm_eps, 4),
            "intrinsic_per_share_pe_simple": round(iv_simple, 4),
        }

        if expected_factors:
            scores, last_complete_qual, fill_src = _resolve_qual_scores_row(
                qn,
                qual_wide,
                expected_factors,
                last_complete_qual,
                default_qual,
            )
            prod = 1.0
            for s in scores:
                prod *= s
            mult = qualitative_pe_multiplier_from_scores(
                scores,
                score_floor=score_floor,
                score_cap=score_cap,
                mult_min=mult_min,
                mult_max=mult_max,
            )
            pe_raw = pe_macro * mult
            pe_adj = apply_pe_global_cap_floor(pe_raw, pe_floor=pe_glob_floor, pe_cap=pe_glob_cap)
            row["qual_scores_fill_source"] = fill_src
            row["qual_score_product"] = prod
            row["qual_pe_multiplier"] = round(mult, 6)
            row["pe_after_qual_pre_clip"] = round(pe_raw, 4)
            row["pe_after_qual"] = round(pe_adj, 4)
            row["intrinsic_per_share_pe_qual_adjusted"] = round(float(pe_adj * ttm_eps), 4)
        else:
            row["qual_scores_fill_source"] = None
            row["qual_score_product"] = None
            row["qual_pe_multiplier"] = None
            row["pe_after_qual_pre_clip"] = None
            row["pe_after_qual"] = None
            row["intrinsic_per_share_pe_qual_adjusted"] = None

        rows.append(row)

    out = pd.DataFrame(rows)
    meta = {
        "symbol": symbol,
        "base_pe_reference": cfg.get("base_pe_reference"),
        "macro_deposit_csv": cfg["macro_deposit_csv"],
        "note": cfg.get("doc", ""),
    }
    return out, meta


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="季度 PE 内在价值（宏观 + 可选定性）")
    ap.add_argument("--symbol", default=SYMBOL_MOUTAI, help="标的 slug，默认 moutai")
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
        help="覆盖默认 valuations/{symbol}/pe/config.json",
    )
    args = ap.parse_args(argv)

    root = repo_root()
    cfg = _load_cfg(args.symbol, config_path=args.config)
    df, meta = build_pe_intrinsic_table(symbol=args.symbol, root=root, cfg=cfg)

    out_rel = str(cfg["output_csv"])
    out_p = root / out_rel
    out_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_p, index=False, encoding="utf-8-sig")

    meta_path = out_p.with_name(out_p.stem + "_meta.json")
    meta.update(
        {
            "rows": int(len(df)),
            "output_csv": out_rel,
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": out_rel, "rows": len(df), "meta": str(meta_path.relative_to(root))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
