"""Price / sales style anchor: intrinsic = k * sales_per_share."""


def price_to_sales_implied_price(sales_per_share: float, target_ps_multiple: float) -> float:
    """Fair price from sales per share and target P/S multiple (modulated by synthesizer)."""
    return sales_per_share * target_ps_multiple
