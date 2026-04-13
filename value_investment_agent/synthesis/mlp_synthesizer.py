"""v2: small MLP maps normalized [quant series features | qual scores] → kernel scalar adjustments."""

from __future__ import annotations

import math

import torch
import torch.nn as nn

from value_investment_agent.factors.llm_schemas import KernelName
from value_investment_agent.synthesis.rules_synthesizer import RulesParameterSynthesizer
from value_investment_agent.valuation.runner import run_valuation_kernel


class MLParameterSynthesizer(nn.Module):
    """
    Outputs a low-dimensional delta vector applied on top of rules-based params.
    Keeps physical bounds via clamping before calling the symbolic kernel.
    """

    def __init__(
        self,
        n_quant_features: int,
        n_qual: int,
        hidden: int = 32,
        delta_dim: int = 4,
    ):
        super().__init__()
        self.n_qual = n_qual
        in_dim = n_quant_features + n_qual
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, delta_dim),
            nn.Tanh(),
        )
        self.delta_dim = delta_dim
        self.rules = RulesParameterSynthesizer()

    def forward(
        self,
        quant_vec: torch.Tensor,
        qual_vec: torch.Tensor,
    ) -> torch.Tensor:
        x = torch.cat([quant_vec, qual_vec], dim=-1)
        return self.net(x)

    def apply_delta_dcf(self, base_params: dict, delta: torch.Tensor) -> dict:
        d = delta.detach().cpu().numpy().ravel()
        p = dict(base_params)
        scale = 0.02
        p["growth_rate"] = float(p["growth_rate"]) + scale * float(d[0])
        p["wacc"] = float(p["wacc"]) - scale * float(d[1])
        p["terminal_growth"] = float(p["terminal_growth"]) + 0.01 * float(d[2])
        p["fcf_per_share"] = float(p["fcf_per_share"]) * (1.0 + 0.05 * float(d[3]))
        p["growth_rate"] = max(-0.05, min(0.25, p["growth_rate"]))
        p["wacc"] = max(0.04, min(0.20, p["wacc"]))
        p["terminal_growth"] = max(0.0, min(0.04, p["terminal_growth"]))
        if p["wacc"] <= p["terminal_growth"]:
            p["wacc"] = p["terminal_growth"] + 0.01
        return p

    def intrinsic_from_vectors(
        self,
        kernel: KernelName,
        quantitative_baseline: dict,
        qualitative_scores: dict[str, float],
        qual_order: list[str],
        quant_vec: torch.Tensor,
        delta_override: torch.Tensor | None = None,
    ) -> tuple[float, dict]:
        qual = [float(qualitative_scores.get(name, 5.5)) for name in qual_order]
        while len(qual) < self.n_qual:
            qual.append(5.5)
        qual = qual[: self.n_qual]
        qv = torch.tensor(qual, dtype=torch.float32).view(1, -1) / 10.0
        qv = qv.to(quant_vec.device)
        base = self.rules.synthesize_params(kernel, quantitative_baseline, qualitative_scores)
        delta = self.forward(quant_vec, qv) if delta_override is None else delta_override
        if kernel != "dcf":
            # For non-DCF kernels in v2, fall back to rules-only intrinsic
            return run_valuation_kernel(kernel, base), base
        params = self.apply_delta_dcf(base, delta[0])
        return run_valuation_kernel("dcf", params), params


def stack_qualitative(scores: dict[str, float], order: list[str], n_qual: int) -> list[float]:
    out = [float(scores.get(k, 5.5)) for k in order[:n_qual]]
    while len(out) < n_qual:
        out.append(5.5)
    return out


def quant_feature_vector_from_series(
    revenue_yoy: float,
    margin: float,
    fcf_margin: float,
    leverage: float,
) -> list[float]:
    """Minimal temporal-to-scalar features (extend with rolling stats in production)."""
    return [math.tanh(revenue_yoy), math.tanh(margin), math.tanh(fcf_margin), math.tanh(leverage)]
