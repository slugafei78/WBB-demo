"""v1: transparent elasticity from qualitative scores (1–10) + quantitative baselines."""

from __future__ import annotations

from typing import Any

from value_investment_agent.factors.llm_schemas import KernelName
from value_investment_agent.valuation.runner import run_valuation_kernel


class RulesParameterSynthesizer:
    """
    Maps modulator scores to bounded adjustments of growth, WACC, multiples, etc.
    No price inputs — preserves Fi interpretability.
    """

    def __init__(self, qualitative_weights: dict[str, float] | None = None):
        self.qualitative_weights = qualitative_weights or {}

    def _modulation_index(self, scores: dict[str, float]) -> float:
        """Average weighted deviation from mid score 5.5, clamped."""
        if not scores:
            return 0.0
        num = 0.0
        den = 0.0
        for k, v in scores.items():
            w = self.qualitative_weights.get(k, 1.0)
            num += w * (v - 5.5)
            den += abs(w)
        if den == 0:
            return 0.0
        return max(-1.0, min(1.0, (num / den) / 4.5))

    def build_dcf_params(
        self,
        base: dict[str, Any],
        qualitative: dict[str, float],
    ) -> dict[str, Any]:
        m = self._modulation_index(qualitative)
        growth = float(base["growth_rate"]) + 0.01 * m
        wacc = float(base["wacc"]) - 0.005 * m
        terminal = float(base["terminal_growth"]) + 0.002 * m
        growth = max(-0.05, min(0.25, growth))
        wacc = max(0.04, min(0.20, wacc))
        terminal = max(0.0, min(0.04, terminal))
        if wacc <= terminal:
            wacc = terminal + 0.01
        out = dict(base)
        out["growth_rate"] = growth
        out["wacc"] = wacc
        out["terminal_growth"] = terminal
        return out

    def build_ps_params(
        self,
        base: dict[str, Any],
        qualitative: dict[str, float],
    ) -> dict[str, Any]:
        m = self._modulation_index(qualitative)
        mult = float(base["target_ps_multiple"]) * (1.0 + 0.15 * m)
        mult = max(0.1, min(50.0, mult))
        out = dict(base)
        out["target_ps_multiple"] = mult
        return out

    def build_pb_roe_params(
        self,
        base: dict[str, Any],
        qualitative: dict[str, float],
    ) -> dict[str, Any]:
        m = self._modulation_index(qualitative)
        pers = float(base.get("persistence", 0.6)) + 0.15 * m
        pers = max(0.1, min(0.95, pers))
        out = dict(base)
        out["persistence"] = pers
        return out

    def synthesize_params(
        self,
        kernel: KernelName,
        quantitative_baseline: dict[str, Any],
        qualitative_scores: dict[str, float],
    ) -> dict[str, Any]:
        if kernel == "dcf":
            return self.build_dcf_params(quantitative_baseline, qualitative_scores)
        if kernel == "price_to_sales":
            return self.build_ps_params(quantitative_baseline, qualitative_scores)
        if kernel == "pb_roe":
            return self.build_pb_roe_params(quantitative_baseline, qualitative_scores)
        raise ValueError(kernel)

    def intrinsic_value(
        self,
        kernel: KernelName,
        quantitative_baseline: dict[str, Any],
        qualitative_scores: dict[str, float],
    ) -> float:
        params = self.synthesize_params(kernel, quantitative_baseline, qualitative_scores)
        return run_valuation_kernel(kernel, params)
