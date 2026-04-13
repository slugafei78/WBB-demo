from datetime import date

from value_investment_agent.vi_agent import ViAgent
from value_investment_agent.factors.schemas import PITKey
from value_investment_agent.synthesis.rules_synthesizer import RulesParameterSynthesizer
from value_investment_agent.synthesis.mlp_synthesizer import MLParameterSynthesizer
import torch


def test_agent_two_turns():
    key = PITKey(symbol="TST", asof_date=date(2019, 1, 1))
    pipe = ViAgent()
    r, a1 = pipe.turn1_router(key, "Test company.")
    q, audits = pipe.turn2_qualitative(key, r)
    assert r.kernel in ("dcf", "price_to_sales", "pb_roe")
    assert len(q.factors) >= 1
    assert a1.event == "turn1_router"
    m = pipe.qualitative_to_map(q)
    assert all(1 <= v <= 10 for v in m.values())


def test_rules_synth_monotone():
    s = RulesParameterSynthesizer()
    base = {
        "fcf_per_share": 1.0,
        "shares_outstanding": 1e9,
        "net_debt": 0.0,
        "growth_rate": 0.02,
        "terminal_growth": 0.01,
        "wacc": 0.09,
    }
    low = {k: 3.0 for k in ["competitive_moat", "management_quality"]}
    high = {k: 9.0 for k in ["competitive_moat", "management_quality"]}
    fi_low = s.intrinsic_value("dcf", base, low)
    fi_high = s.intrinsic_value("dcf", base, high)
    assert fi_high != fi_low


def test_mlp_synth_forward():
    m = MLParameterSynthesizer(n_quant_features=4, n_qual=5, hidden=16, delta_dim=4)
    q = torch.randn(1, 4)
    qual = torch.ones(1, 5) * 0.6
    d = m.forward(q, qual)
    assert d.shape == (1, 4)
