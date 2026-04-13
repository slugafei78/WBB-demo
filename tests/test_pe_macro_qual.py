"""pe_macro_qual 纯函数边界与单调性。"""
from __future__ import annotations

import math

from value_investment_agent.valuation.pe_macro_qual import (
    apply_pe_global_cap_floor,
    pe_from_deposit_rate_linear,
    qualitative_pe_multiplier_from_scores,
)


def test_pe_from_deposit_monotone() -> None:
    lo = pe_from_deposit_rate_linear(1.5, rate_hist_min=1.5, rate_hist_max=4.14)
    hi = pe_from_deposit_rate_linear(4.14, rate_hist_min=1.5, rate_hist_max=4.14)
    assert hi < lo
    assert abs(lo - 22.0) < 1e-6
    assert abs(hi - 18.0) < 1e-6


def test_qual_mult_extremes() -> None:
    ones = [1.0] * 10
    tens = [10.0] * 10
    m1 = qualitative_pe_multiplier_from_scores(ones)
    m10 = qualitative_pe_multiplier_from_scores(tens)
    assert abs(m1 - 0.5) < 1e-9
    assert abs(m10 - 1.2) < 1e-9


def test_qual_mult_mid() -> None:
    mid = [math.sqrt(10.0)] * 10
    m = qualitative_pe_multiplier_from_scores(mid)
    assert abs(m - 0.85) < 0.02


def test_apply_cap_floor() -> None:
    assert apply_pe_global_cap_floor(30.0, pe_floor=10.0, pe_cap=24.0) == 24.0
    assert apply_pe_global_cap_floor(8.0, pe_floor=10.0, pe_cap=24.0) == 10.0
