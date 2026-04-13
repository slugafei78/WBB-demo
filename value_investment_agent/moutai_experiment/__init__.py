"""茅台（moutai）简化实验流程（本地 data + 双 Fi DCF）。"""

from __future__ import annotations

__all__ = ["run_moutai_flow_main"]


def __getattr__(name: str):
    """不在包导入时执行 run_moutai_flow（避免拉取 yfinance 以外整棵依赖树）。"""
    if name == "run_moutai_flow_main":
        from value_investment_agent.moutai_experiment.run_moutai_flow import main as run_moutai_flow_main

        return run_moutai_flow_main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
