"""End-to-end smoke: PIT key → agent (mock) → rules synthesizer → Fi → Fm fit → metrics."""

from __future__ import annotations

from datetime import date

import numpy as np

from value_investment_agent.vi_agent import ViAgent
from value_investment_agent.eval.baselines import ff_style_linear_proxy, vanilla_dcf_series
from value_investment_agent.eval.metrics import information_coefficient, rmse, stability_vs_long_ma
from value_investment_agent.factors.schemas import PITKey
from value_investment_agent.models.fm_net import FmFeatureBuilder
from value_investment_agent.training.fit import FitConfig, predict_fm, train_fm
from value_investment_agent.valuation.runner import run_valuation_kernel


def main() -> None:
    key = PITKey(symbol="DEMO", asof_date=date(2020, 6, 1))
    pipe = ViAgent()
    router, _a1 = pipe.turn1_router(key, "Large cap consumer staple with stable cash flows.")
    qout, _a2 = pipe.turn2_qualitative(key, router)
    qual_map = pipe.qualitative_to_map(qout)

    from value_investment_agent.synthesis.rules_synthesizer import RulesParameterSynthesizer

    synth = RulesParameterSynthesizer()
    base = {
        "fcf_per_share": 2.0,
        "shares_outstanding": 1e9,
        "net_debt": 5e9,
        "growth_rate": 0.03,
        "terminal_growth": 0.02,
        "wacc": 0.08,
    }
    fi0 = synth.intrinsic_value(router.kernel, base, qual_map)
    print("Router kernel:", router.kernel)
    print("Fi (rules):", round(fi0, 4))

    n = 80
    rng = np.random.default_rng(42)
    price = 50.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    fi_series = np.full(n, fi0) + rng.normal(0, 0.2, size=n)

    feats = FmFeatureBuilder.from_arrays(
        ret_1m=rng.normal(0, 0.02, size=n),
        ret_3m=rng.normal(0, 0.04, size=n),
        vol_20d=rng.uniform(0.1, 0.3, size=n),
        volume_z=rng.normal(0, 1, size=n),
        turnover=rng.uniform(0.001, 0.02, size=n),
        pe_ratio=rng.uniform(10, 30, size=n),
        mom_6m=rng.normal(0, 0.1, size=n),
        mom_12m=rng.normal(0, 0.15, size=n),
    )

    model, losses = train_fm(feats, fi_series, price, FitConfig(epochs=150, lambda_fm=1e-2))
    fm_hat = predict_fm(model, feats)
    pred = fi_series + fm_hat
    print("RMSE price fit:", round(rmse(pred, price), 4))
    print("Stability vs 60d MA (short demo):", round(stability_vs_long_ma(fi_series, price, window=20), 4))

    vanilla = vanilla_dcf_series(
        np.full(n, 2.0),
        shares_outstanding=1e9,
        net_debt=5e9,
        growth_rate=0.03,
        terminal_growth=0.02,
        wacc=0.08,
    )
    fwd = np.diff(price, prepend=price[0]) / np.maximum(price, 1e-9)
    ic = information_coefficient(vanilla[:-1], fwd[1:])
    print("Vanilla DCF rank IC vs next-step return (noise demo):", round(ic, 4))

    X = np.column_stack([feats[:, 0], feats[:, 1], feats[:, 6]])
    pred_ff, r2 = ff_style_linear_proxy(X[:-1], fwd[1:][: len(X) - 1])
    print("FF-proxy R2 (toy):", round(r2, 4))

    # Kernel dispatch sanity
    ps = run_valuation_kernel(
        "price_to_sales",
        {"sales_per_share": 10.0, "target_ps_multiple": 2.5},
    )
    print("P/S intrinsic:", round(ps, 4))


if __name__ == "__main__":
    main()
