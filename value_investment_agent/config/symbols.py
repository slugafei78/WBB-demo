"""
标的 slug：与仓库根目录 `data/{slug}/`、`factors/{slug}/` 一致。
全市场宏观：原始抓取在 `data/macro/raw/`，因子时间序列在 `factors/macro/series/`（与各 `factors/{slug}/` 并列）。
行情/SEC 等外部 API 使用单独映射（用户无需记忆 Yahoo 代码）。
"""

from __future__ import annotations

SYMBOL_COLA = "cola"
SYMBOL_MOUTAI = "moutai"
SYMBOL_TXRH = "txrh"

# Yahoo Finance（实现细节）
YAHOO_TICKER_BY_SYMBOL: dict[str, str] = {
    SYMBOL_COLA: "KO",
    SYMBOL_MOUTAI: "600519.SS",
    SYMBOL_TXRH: "TXRH",
}

# SEC CIK（10 位），仅适用于在美注册披露的公司
SEC_CIK_BY_SYMBOL: dict[str, str | None] = {
    SYMBOL_COLA: "0000021344",
    SYMBOL_MOUTAI: None,
    SYMBOL_TXRH: "0001289469",
}


def yahoo_ticker(symbol: str) -> str:
    if symbol not in YAHOO_TICKER_BY_SYMBOL:
        raise KeyError(f"Unknown symbol slug {symbol!r}; add it in config.symbols.YAHOO_TICKER_BY_SYMBOL")
    return YAHOO_TICKER_BY_SYMBOL[symbol]


def sec_cik(symbol: str) -> str | None:
    return SEC_CIK_BY_SYMBOL.get(symbol)
