"""PB–ROE style residual income shortcut: price = book * f(ROE, COE)."""


def pb_roe_intrinsic_per_share(
    book_value_per_share: float,
    roe: float,
    cost_of_equity: float,
    persistence: float = 0.6,
) -> float:
    """
    Simple justified P/B from ROE spread vs COE.
    persistence: fraction of excess ROE embedded in franchise (0–1).
    """
    if cost_of_equity <= 0:
        raise ValueError("cost_of_equity must be positive")
    spread = roe - cost_of_equity
    justified_pb = 1.0 + persistence * max(spread, -0.99) / cost_of_equity
    return book_value_per_share * justified_pb
