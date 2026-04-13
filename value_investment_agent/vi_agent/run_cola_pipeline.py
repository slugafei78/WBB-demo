"""
cola 示例全流程：ingestion → factor_pipeline（定性+DCF Fi）→ backtest 出图。

  python -m value_investment_agent.vi_agent.run_cola_pipeline --years 10 --freq annual
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from value_investment_agent.backtest.visualize import plot_intrinsic_dashboard
from value_investment_agent.config.symbols import SYMBOL_COLA
from value_investment_agent.factor_pipeline.intrinsic_series import (
    add_ma120,
    forward_fill_fi_to_daily,
    quarterly_fi_series,
)
from value_investment_agent.ingestion.data_fetch import RawDataBundle, fetch_raw_bundle


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="cola 全流程：数据 / LLM 定性 / Fi / 图表")
    p.add_argument("--symbol", type=str, default=SYMBOL_COLA, help="标的 slug（默认 cola）")
    p.add_argument("--years", type=int, default=10, help="回溯年数")
    p.add_argument("--output-dir", type=Path, default=Path("data/cola_run"), help="输出目录")
    p.add_argument("--refresh", action="store_true", help="强制重新抓取")
    p.add_argument("--skip-sec", action="store_true", help="跳过 SEC companyfacts")
    p.add_argument("--freq", choices=("quarterly", "annual"), default="annual")
    p.add_argument("--llm", choices=("auto", "gemini", "openai", "mock"), default=None)
    p.add_argument("--use-openai", action="store_true", help="等价于 --llm openai")
    p.add_argument("--no-openai", action="store_true", help="等价于 --llm mock")
    args = p.parse_args(argv)

    out = Path(args.output_dir)
    bundle_path = out / "bundle"
    fig_path = out / "cola_dashboard.png"

    if args.refresh or not (bundle_path / "prices_daily.csv").exists():
        fetch_raw_bundle(args.symbol, years=args.years, output_dir=bundle_path, skip_sec=args.skip_sec)
        bundle = RawDataBundle.load(args.symbol, bundle_path)
    else:
        bundle = RawDataBundle.load(args.symbol, bundle_path)

    llm_provider = args.llm
    use_openai: bool | None = None
    if args.use_openai:
        llm_provider = "openai"
    if args.no_openai:
        llm_provider = "mock"
    if llm_provider is None:
        llm_provider = "auto"
    if llm_provider == "mock":
        use_openai = False
    elif llm_provider == "openai":
        use_openai = True

    fi_q, _quals = quarterly_fi_series(
        bundle,
        symbol=args.symbol,
        llm_provider=llm_provider,
        use_openai=use_openai,
        freq=args.freq,
    )

    px = bundle.prices["close"].copy()
    px.index = pd.to_datetime(px.index).normalize()
    fi_d = forward_fill_fi_to_daily(fi_q, px.index)
    ma = add_ma120(px)

    plot_intrinsic_dashboard(
        close=px,
        fi_daily=fi_d,
        ma120=ma,
        out_path=fig_path,
        title=f"{args.symbol} ({args.years}y): 收盘价 vs Fi vs MA120",
    )

    pd.DataFrame({"close": px, "fi": fi_d, "ma120": ma}).to_csv(out / "series_aligned.csv")
    fi_q.rename("fi_quarterly").to_csv(out / "fi_quarterly.csv")

    print(f"完成。图表: {fig_path.resolve()}")
    print(f"对齐序列: {(out / 'series_aligned.csv').resolve()}")


if __name__ == "__main__":
    main()
