"""Two-stage DCF: FCFF or simplified per-share FCF → terminal value → equity per share."""

from __future__ import annotations


def dcf_intrinsic_per_share(
    fcf_per_share: float,
    shares_outstanding: float,
    net_debt: float,
    growth_rate: float,
    terminal_growth: float,
    wacc: float,
    forecast_years: int = 5,
) -> float:
    """
    Gordon-style terminal value after explicit forecast years.
    fcf_per_share: baseline FCF/share for year 1 (already modulated by synthesizer).
    Enterprise value = PV(forecast) + PV(terminal); equity = EV - net_debt.
    """
    if wacc <= terminal_growth:
        raise ValueError("wacc must exceed terminal_growth")
    if forecast_years < 1:
        raise ValueError("forecast_years must be >= 1")

    pv = 0.0
    fcf = fcf_per_share * shares_outstanding
    for t in range(1, forecast_years + 1):
        fcf *= 1.0 + growth_rate
        pv += fcf / (1.0 + wacc) ** t

    tv_fcf = fcf * (1.0 + terminal_growth)
    terminal_value = tv_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1.0 + wacc) ** forecast_years

    ev = pv + pv_terminal
    equity = ev - net_debt
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    return equity / shares_outstanding
