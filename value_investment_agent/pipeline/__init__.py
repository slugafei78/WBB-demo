"""已迁移至 `ingestion`、`factor_pipeline`、`vi_agent`、`backtest`；此处仅兼容旧 import。"""

from __future__ import annotations

from value_investment_agent.vi_agent.run_cola_pipeline import main as run_cola_main

run_ko_main = run_cola_main

__all__ = ["run_cola_main", "run_ko_main"]
