"""quant_extract_data.merge_rows 优先级与 Yahoo 行扩展。"""

from __future__ import annotations

import pandas as pd

from value_investment_agent.moutai_experiment.quant_extract_data import (
    _rows_from_sina_df_rowwise,
    merge_rows,
)


def test_merge_prefers_manual_over_yahoo() -> None:
    rows = [
        {"period_end": "2024-03-31", "factor_id": "net_income", "value": 1.0, "source": "yahoo_quarterly"},
        {"period_end": "2024-03-31", "factor_id": "net_income", "value": 99.0, "source": "manual_quarterly_csv"},
    ]
    m = merge_rows(rows)
    assert len(m) == 1
    assert m[0]["value"] == 99.0
    assert m[0]["source"] == "manual_quarterly_csv"


def test_akshare_rowwise_profit_columns() -> None:
    """新浪「每行一期、列=科目」格式应能解析出多因子。"""
    cutoff = pd.Timestamp("2020-01-01")
    df = pd.DataFrame(
        {
            "报表日期": ["2024-12-31"],
            "归属于母公司所有者的净利润": [1.0e9],
            "净利润": [1.1e9],
            "营业利润": [2.0e9],
        }
    )
    rows = _rows_from_sina_df_rowwise(df, cutoff, "利润表")
    fids = {r["factor_id"] for r in rows}
    assert "net_profit_attributable" in fids
    assert "net_income" in fids
    assert "operating_profit" in fids


def test_merge_prefers_eastmoney_over_yahoo() -> None:
    rows = [
        {"period_end": "2024-03-31", "factor_id": "net_income", "value": 1.0, "source": "yahoo_quarterly"},
        {"period_end": "2024-03-31", "factor_id": "net_income", "value": 100.0, "source": "eastmoney_quarterly"},
    ]
    m = merge_rows(rows)
    assert len(m) == 1
    assert m[0]["source"] == "eastmoney_quarterly"


def test_merge_prefers_net_profit_csv_over_yahoo() -> None:
    rows = [
        {"period_end": "2024-03-31", "factor_id": "net_profit_attributable", "value": 1.0, "source": "yahoo_quarterly"},
        {"period_end": "2024-03-31", "factor_id": "net_profit_attributable", "value": 2.0, "source": "net_profit_quarterly_csv"},
    ]
    m = merge_rows(rows)
    assert len(m) == 1
    assert m[0]["value"] == 2.0
