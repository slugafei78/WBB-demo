"""
茅台（moutai）简化打穿流程：
  本地/ Yahoo 净利润 → 季度双 Fi（纯 DCF / 定性调制）→ 五年图。

  python -m value_investment_agent.moutai_experiment.run_moutai_flow
  python -m value_investment_agent.moutai_experiment.run_moutai_flow --refresh-yahoo-news
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from value_investment_agent.moutai_experiment.net_profit_series import load_net_profit_quarterly
from value_investment_agent.moutai_experiment.synthetic_data import synthetic_close_daily, synthetic_net_profit_quarterly
from value_investment_agent.moutai_experiment.news_digest import append_yahoo_headlines_to_digest
from value_investment_agent.moutai_experiment.paths import repo_root
from value_investment_agent.moutai_experiment.plot_moutai import fetch_prices_years, plot_moutai_dashboard
from value_investment_agent.moutai_experiment.qual_four import score_moutai_qual_four
from value_investment_agent.moutai_experiment.quarterly_fi import build_quarterly_fi_moutai


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="moutai 五年季度 Fi + 股价看板")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--llm", choices=("auto", "gemini", "openai", "mock"), default="auto")
    p.add_argument("--refresh-yahoo-news", action="store_true", help="把 Yahoo 近期标题追加到 news_digest.csv")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="输出目录，默认 data/moutai_run",
    )
    p.add_argument(
        "--synthetic",
        action="store_true",
        help="强制使用内置合成净利润与股价（无网络可出图）",
    )
    args = p.parse_args(argv)

    root = repo_root()
    out = args.out_dir or (root / "data" / "moutai_run")
    out.mkdir(parents=True, exist_ok=True)

    if args.refresh_yahoo_news:
        append_yahoo_headlines_to_digest()
        print("已更新 news_digest.csv（追加 Yahoo 标题）")

    if args.synthetic:
        ni = synthetic_net_profit_quarterly(years=args.years + 1)
        print("使用 --synthetic：净利润与股价均为可复现演示数据。", flush=True)
    else:
        try:
            ni = load_net_profit_quarterly(years=args.years + 1)
        except Exception as e:
            print(f"加载净利润失败，改用合成序列: {e}", flush=True)
            ni = synthetic_net_profit_quarterly(years=args.years + 1)

    qtxt = "最近季度净利润（元）样本:\n" + ni.tail(8).to_string()

    qual = score_moutai_qual_four(quantitative_summary=qtxt, llm_provider=args.llm)
    (out / "qual_four.json").write_text(qual.model_dump_json(indent=2), encoding="utf-8")

    fq = root / "factors" / "moutai"
    (fq / "quantitative").mkdir(parents=True, exist_ok=True)
    (fq / "qualitative").mkdir(parents=True, exist_ok=True)
    ni.to_csv(fq / "quantitative" / "net_profit_quarterly_used.csv", header=["net_profit"])
    (fq / "qualitative" / "qual_four_last_run.json").write_text(
        qual.model_dump_json(indent=2), encoding="utf-8"
    )

    fi_v, fi_a, ttm_eps = build_quarterly_fi_moutai(years=args.years, qual=qual, ni_quarterly=ni)
    df_fi = pd.DataFrame(
        {"fi_vanilla": fi_v, "fi_adjusted": fi_a, "ttm_net_profit_per_share_proxy": ttm_eps}
    )
    df_fi.to_csv(out / "fi_quarterly.csv")
    print("\n========== 季度 intrinsic value Fi（元/股）==========", flush=True)
    print(df_fi.to_string(), flush=True)
    print("====================================================\n", flush=True)

    if args.synthetic:
        px = synthetic_close_daily(years=args.years)
    else:
        try:
            px = fetch_prices_years("moutai", years=args.years)
        except Exception as e:
            print(f"加载股价失败，改用合成日线: {e}", flush=True)
            px = synthetic_close_daily(years=args.years)
    px.to_csv(out / "prices_daily.csv", header=["close"])

    fig = plot_moutai_dashboard(
        close=px,
        fi_vanilla=fi_v,
        fi_adjusted=fi_a,
        out_path=out / "moutai_dashboard.png",
    )

    meta = {
        "qual_four": json.loads(qual.model_dump_json()),
        "quarters": len(fi_v),
        "figure": str(fig.resolve()),
    }
    (out / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("完成。")
    print(f"  图: {fig}")
    print(f"  季度 Fi: {out / 'fi_quarterly.csv'}")
    print(f"  定性四因子: {out / 'qual_four.json'}")


if __name__ == "__main__":
    main()
