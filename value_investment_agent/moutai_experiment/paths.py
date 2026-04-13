"""仓库根目录下的 data/moutai 与 factors/moutai 路径。"""

from __future__ import annotations

from pathlib import Path

SYMBOL_MOUTAI = "moutai"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def factor_symbol_dir(symbol: str) -> Path:
    """个股因子根目录：factors/{symbol}/。"""
    return repo_root() / "factors" / symbol


def valuations_root() -> Path:
    """估值产出与按方法划分的配置：与 data/、factors/ 并列。"""
    return repo_root() / "valuations"


def valuation_symbol_dir(symbol: str) -> Path:
    """个股估值根目录：valuations/{symbol}/（其下可有 pe/、dcf/ 等子目录）。"""
    return valuations_root() / symbol


def moutai_quant_extract_config() -> Path:
    return factor_symbol_dir(SYMBOL_MOUTAI) / "config" / "quant_extract.json"


def qualitative_subagent_config(symbol: str) -> Path:
    """该股 qualitative 流水线 JSON：factors/{symbol}/config/qualitative_subagent.json。"""
    return factor_symbol_dir(symbol) / "config" / "qualitative_subagent.json"


def shared_qualitative_subagent_prompts_dir() -> Path:
    """全个股共享的五步提示词：prompts/qualitative_subagent/。"""
    return repo_root() / "prompts" / "qualitative_subagent"


def moutai_qualitative_subagent_config() -> Path:
    return qualitative_subagent_config(SYMBOL_MOUTAI)


def moutai_raw() -> Path:
    return repo_root() / "data" / "moutai" / "raw"


def news_digest_path() -> Path:
    return moutai_raw() / "news" / "news_digest.csv"


def net_profit_csv_path() -> Path:
    return moutai_raw() / "financials" / "net_profit_quarterly.csv"


def moutai_em_quantitative_raw_dir() -> Path:
    """东财等下载的原始 quantitative 宽表（CSV），放在 data 下，不进 factors。"""
    return moutai_raw() / "financials" / "em"


def moutai_sina_financials_raw_dir() -> Path:
    """新浪财经财报原始表（可选下载）。"""
    return moutai_raw() / "financials" / "sina"
