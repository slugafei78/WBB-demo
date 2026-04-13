"""ViAgent：总价值代理编排入口；当前内建定性子流程，后续可挂载采集、因子管道、回测。"""

from __future__ import annotations

from value_investment_agent.agents.qualitative import QualitativeSubAgent


class ViAgent(QualitativeSubAgent):
    """
    顶层 Agent。现阶段与 QualitativeSubAgent 能力相同（turn1_router / turn2_qualitative）。
    后续在此扩展：触发 ingestion、factor_pipeline、synthesis、Fm 训练与 backtest。
    """

    pass
