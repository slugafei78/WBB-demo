"""Dispatch to DCF / P/S / PB-ROE from a single structured input bag."""

from __future__ import annotations

from typing import Literal

from value_investment_agent.valuation.dcf import dcf_intrinsic_per_share
from value_investment_agent.valuation.pb_roe import pb_roe_intrinsic_per_share
from value_investment_agent.valuation.ps import price_to_sales_implied_price

KernelName = Literal["dcf", "price_to_sales", "pb_roe"]


def run_valuation_kernel(kernel: KernelName, params: dict) -> float:
    """Pure dispatch; params keys must match each kernel (filled by synthesizer)."""
    if kernel == "dcf":
        return dcf_intrinsic_per_share(
            fcf_per_share=float(params["fcf_per_share"]),
            shares_outstanding=float(params["shares_outstanding"]),
            net_debt=float(params["net_debt"]),
            growth_rate=float(params["growth_rate"]),
            terminal_growth=float(params["terminal_growth"]),
            wacc=float(params["wacc"]),
            forecast_years=int(params.get("forecast_years", 5)),
        )
    if kernel == "price_to_sales":
        return price_to_sales_implied_price(
            sales_per_share=float(params["sales_per_share"]),
            target_ps_multiple=float(params["target_ps_multiple"]),
        )
    if kernel == "pb_roe":
        return pb_roe_intrinsic_per_share(
            book_value_per_share=float(params["book_value_per_share"]),
            roe=float(params["roe"]),
            cost_of_equity=float(params["cost_of_equity"]),
            persistence=float(params.get("persistence", 0.6)),
        )
    raise ValueError(f"unknown kernel {kernel}")
