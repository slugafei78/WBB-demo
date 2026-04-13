"""Fitting and research-style diagnostics."""

from __future__ import annotations

import numpy as np


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def information_coefficient(signal: np.ndarray, forward_ret: np.ndarray) -> float:
    """Spearman rank IC proxy via Pearson on ranks (sufficient for smoke tests)."""
    if len(signal) < 3:
        return 0.0
    s = signal.astype(float)
    r = forward_ret.astype(float)
    mask = np.isfinite(s) & np.isfinite(r)
    s, r = s[mask], r[mask]
    if len(s) < 3:
        return 0.0
    rank_s = np.argsort(np.argsort(s))
    rank_r = np.argsort(np.argsort(r))
    if np.std(rank_s) == 0 or np.std(rank_r) == 0:
        return 0.0
    return float(np.corrcoef(rank_s, rank_r)[0, 1])


def stability_vs_long_ma(fi: np.ndarray, price: np.ndarray, window: int = 250) -> float:
    """
    Mean absolute z-score of Fi vs rolling MA of price (qualitative stability check).
    Lower is smoother relative to long-horizon price path.
    """
    if len(price) < window or len(fi) != len(price):
        return float("nan")
    ma = np.convolve(price, np.ones(window) / window, mode="valid")
    fi_al = fi[window - 1 :]
    rel = fi_al - ma
    return float(np.mean(np.abs(rel)) / (np.std(price) + 1e-9))
