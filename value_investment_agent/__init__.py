"""Neuro-symbolic value investment agent: Fi (symbolic) + Fm (neural) + LLM modulators."""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["ViAgent"]


def __getattr__(name: str):
    """避免 `import value_investment_agent` 时拉满 ViAgent → pydantic 等重依赖。"""
    if name == "ViAgent":
        from value_investment_agent.vi_agent import ViAgent

        return ViAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
