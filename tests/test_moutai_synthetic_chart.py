"""离线生成 moutai 四线 PNG（供 CI/无网络验证）。"""

from pathlib import Path

import pandas as pd

from value_investment_agent.moutai_experiment.plot_moutai import plot_moutai_dashboard
from value_investment_agent.moutai_experiment.qual_four import score_moutai_qual_four
from value_investment_agent.moutai_experiment.quarterly_fi import build_quarterly_fi_moutai
from value_investment_agent.moutai_experiment.synthetic_data import synthetic_close_daily, synthetic_net_profit_quarterly


def test_moutai_synthetic_writes_png(tmp_path: Path) -> None:
    ni = synthetic_net_profit_quarterly(years=5)
    qtxt = ni.tail(8).to_string()
    qual = score_moutai_qual_four(quantitative_summary=qtxt, llm_provider="mock")
    fi_v, fi_a, _ = build_quarterly_fi_moutai(years=5, qual=qual, ni_quarterly=ni)
    px = synthetic_close_daily(years=5)
    out = tmp_path / "moutai_dashboard.png"
    plot_moutai_dashboard(close=px, fi_vanilla=fi_v, fi_adjusted=fi_a, out_path=out)
    assert out.exists() and out.stat().st_size > 1000
    df = pd.DataFrame({"fi_vanilla": fi_v, "fi_adjusted": fi_a})
    print("\n", df.to_string(), flush=True)
