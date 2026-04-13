"""Train MLParameterSynthesizer head with a differentiable surrogate around rules-Fi (no grad through kernel)."""

from __future__ import annotations

import torch

from value_investment_agent.synthesis.mlp_synthesizer import MLParameterSynthesizer


def train_mlp_synthesizer_surrogate(
    model: MLParameterSynthesizer,
    quant_vec: torch.Tensor,
    qual_vec: torch.Tensor,
    rules_fi_anchor: float,
    target_fi: float,
    epochs: int = 200,
    lr: float = 1e-2,
    scale: float = 0.05,
) -> list[float]:
    """
    Minimize (rules_fi_anchor + scale * sum(delta) - target_fi)^2 so the MLP learns a
    bounded correction direction; full analytic kernel remains used at inference via apply_delta_dcf.
    """
    device = quant_vec.device
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    anchor = torch.tensor(rules_fi_anchor, dtype=torch.float32, device=device)
    target = torch.tensor(target_fi, dtype=torch.float32, device=device)
    losses: list[float] = []
    for _ in range(epochs):
        opt.zero_grad()
        delta = model.forward(quant_vec, qual_vec)
        pred = anchor + scale * delta.sum()
        loss = (pred - target).pow(2)
        loss.backward()
        opt.step()
        losses.append(float(loss.detach().cpu().item()))
    return losses
