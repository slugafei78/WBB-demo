"""Vanilla DCF path, simple FF-style linear factor model proxy, LSTM sequence baseline."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from value_investment_agent.valuation.dcf import dcf_intrinsic_per_share


def vanilla_dcf_series(
    fcf_per_share: np.ndarray,
    shares_outstanding: float,
    net_debt: float,
    growth_rate: float,
    terminal_growth: float,
    wacc: float,
) -> np.ndarray:
    """Constant-parameter DCF each row (no LLM modulation)."""
    out = np.empty_like(fcf_per_share, dtype=float)
    for i, fcf in enumerate(fcf_per_share):
        out[i] = dcf_intrinsic_per_share(
            fcf_per_share=float(fcf),
            shares_outstanding=shares_outstanding,
            net_debt=net_debt,
            growth_rate=growth_rate,
            terminal_growth=terminal_growth,
            wacc=wacc,
        )
    return out


class TinyLSTM(nn.Module):
    def __init__(self, n_in: int, hidden: int = 16):
        super().__init__()
        self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y, _ = self.lstm(x)
        return self.head(y[:, -1, :]).squeeze(-1)


def lstm_baseline(
    seq_features: np.ndarray,
    target: np.ndarray,
    epochs: int = 100,
    lr: float = 1e-2,
) -> tuple[TinyLSTM, list[float]]:
    """
    seq_features: (N, T, F) windows
    target: (N,) e.g. next-month return or price level
    """
    device = torch.device("cpu")
    x = torch.tensor(seq_features, dtype=torch.float32, device=device)
    y = torch.tensor(target, dtype=torch.float32, device=device)
    n_in = seq_features.shape[2]
    model = TinyLSTM(n_in).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    losses: list[float] = []
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(x)
        loss = torch.mean((pred - y) ** 2)
        loss.backward()
        opt.step()
        losses.append(float(loss.detach().cpu().item()))
    return model, losses


def ff_style_linear_proxy(
    factors: np.ndarray,
    ret_forward: np.ndarray,
) -> tuple[np.ndarray, float]:
    """
    OLS-style baseline: predict forward return from factor matrix (Fama-French proxy).
    factors: (N, K), ret_forward: (N,)
    Returns (predicted, in_sample_r2_proxy).
    """
    X = np.column_stack([np.ones(len(factors)), factors])
    beta, *_ = np.linalg.lstsq(X, ret_forward, rcond=None)
    pred = X @ beta
    ss_res = np.sum((ret_forward - pred) ** 2)
    ss_tot = np.sum((ret_forward - np.mean(ret_forward)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return pred, float(r2)
