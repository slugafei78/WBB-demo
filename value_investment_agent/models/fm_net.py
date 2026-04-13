"""Neural branch Fm: absorbs market offset from risk-premium and momentum features."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn


class FmNet(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class FmFeatureBuilder:
    """
    Group II (risk premium / liquidity) + Group III momentum slice.
    Expects aligned arrays by time index.
    """

    FEATURE_NAMES = (
        "ret_1m",
        "ret_3m",
        "vol_20d",
        "volume_z",
        "turnover",
        "pe_ratio",
        "mom_6m",
        "mom_12m",
    )

    @staticmethod
    def build_row(
        ret_1m: float,
        ret_3m: float,
        vol_20d: float,
        volume_z: float,
        turnover: float,
        pe_ratio: float,
        mom_6m: float,
        mom_12m: float,
    ) -> np.ndarray:
        v = np.array(
            [
                np.tanh(ret_1m),
                np.tanh(ret_3m),
                np.tanh(vol_20d),
                np.tanh(volume_z),
                np.tanh(turnover),
                np.tanh(pe_ratio / 50.0),
                np.tanh(mom_6m),
                np.tanh(mom_12m),
            ],
            dtype=np.float32,
        )
        return v

    @staticmethod
    def from_arrays(
        ret_1m: np.ndarray,
        ret_3m: np.ndarray,
        vol_20d: np.ndarray,
        volume_z: np.ndarray,
        turnover: np.ndarray,
        pe_ratio: np.ndarray,
        mom_6m: np.ndarray,
        mom_12m: np.ndarray,
    ) -> np.ndarray:
        n = len(ret_1m)
        rows = []
        for i in range(n):
            rows.append(
                FmFeatureBuilder.build_row(
                    float(ret_1m[i]),
                    float(ret_3m[i]),
                    float(vol_20d[i]),
                    float(volume_z[i]),
                    float(turnover[i]),
                    float(pe_ratio[i]),
                    float(mom_6m[i]),
                    float(mom_12m[i]),
                )
            )
        return np.stack(rows, axis=0)
