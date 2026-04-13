import numpy as np
import torch

from value_investment_agent.models.fm_net import FmFeatureBuilder
from value_investment_agent.training.fit import FitConfig, train_fm
from value_investment_agent.valuation.dcf import dcf_intrinsic_per_share
from value_investment_agent.valuation.pb_roe import pb_roe_intrinsic_per_share
from value_investment_agent.valuation.ps import price_to_sales_implied_price
from value_investment_agent.valuation.runner import run_valuation_kernel


def test_dcf_positive():
    v = dcf_intrinsic_per_share(
        fcf_per_share=1.0,
        shares_outstanding=1_000_000_000,
        net_debt=0.0,
        growth_rate=0.02,
        terminal_growth=0.01,
        wacc=0.08,
        forecast_years=5,
    )
    assert v > 0


def test_ps_pb():
    assert price_to_sales_implied_price(5.0, 2.0) == 10.0
    x = pb_roe_intrinsic_per_share(10.0, 0.12, 0.09, persistence=0.5)
    assert x > 10.0


def test_runner_dispatch():
    run_valuation_kernel("dcf", {
        "fcf_per_share": 1.0,
        "shares_outstanding": 1e9,
        "net_debt": 0.0,
        "growth_rate": 0.02,
        "terminal_growth": 0.01,
        "wacc": 0.08,
    })


def test_fm_train_shapes():
    n, d = 32, len(FmFeatureBuilder.FEATURE_NAMES)
    x = np.random.randn(n, d).astype(np.float32)
    fi = np.linspace(40, 45, n).astype(np.float32)
    price = fi + np.random.randn(n).astype(np.float32) * 0.5
    model, losses = train_fm(x, fi, price, FitConfig(epochs=30, lr=0.05))
    assert losses[-1] < losses[0]
    xt = torch.tensor(x, dtype=torch.float32)
    out = model(xt)
    assert out.shape == (n,)
