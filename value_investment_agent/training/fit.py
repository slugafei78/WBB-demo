"""Train Fm to minimize |Fi + Fm - Pt| with L2 on Fm; optional Fi smoothness penalty."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn

from value_investment_agent.models.fm_net import FmNet


@dataclass
class FitConfig:
    epochs: int = 200
    lr: float = 1e-2
    lambda_fm: float = 1e-3  # regularize Fm magnitude (decoupling guardrail)
    lambda_fm_smooth: float = 0.0  # optional: penalize choppy Fm along time index
    device: str = "cpu"


def train_fm(
    features: np.ndarray,
    fi: np.ndarray,
    price: np.ndarray,
    config: FitConfig | None = None,
) -> tuple[FmNet, list[float]]:
    """
    features: (N, D) from FmFeatureBuilder
    fi, price: (N,) intrinsic and observed price (same units per share)
    """
    config = config or FitConfig()
    device = torch.device(config.device)
    x = torch.tensor(features, dtype=torch.float32, device=device)
    fi_t = torch.tensor(fi, dtype=torch.float32, device=device)
    p_t = torch.tensor(price, dtype=torch.float32, device=device)

    model = FmNet(n_features=features.shape[1]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)
    losses: list[float] = []

    for _ in range(config.epochs):
        opt.zero_grad()
        fm = model(x)
        pred = fi_t + fm
        loss_fit = torch.mean((pred - p_t) ** 2)
        loss_fm = config.lambda_fm * torch.mean(fm**2)
        loss = loss_fit + loss_fm
        if config.lambda_fm_smooth > 0 and fm.numel() > 1:
            dfm = fm[1:] - fm[:-1]
            loss = loss + config.lambda_fm_smooth * torch.mean(dfm**2)
        loss.backward()
        opt.step()
        losses.append(float(loss.detach().cpu().item()))

    return model, losses


@torch.no_grad()
def predict_fm(model: FmNet, features: np.ndarray, device: str = "cpu") -> np.ndarray:
    model.eval()
    x = torch.tensor(features, dtype=torch.float32, device=device)
    return model(x).detach().cpu().numpy()
