"""Structured JSON contracts for router, qualitative scoring, and rationale (human gate)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

KernelName = Literal["dcf", "price_to_sales", "pb_roe"]


class KernelRouterOutput(BaseModel):
    """Turn 1: business model → valuation kernel + driver emphasis."""

    business_model_summary: str = Field(..., max_length=2000)
    kernel: KernelName
    primary_quantitative_drivers: list[str] = Field(
        default_factory=list,
        description="e.g. fcf_margin, revenue_growth, dividend_yield",
    )
    peer_tickers_suggested: list[str] = Field(default_factory=list, max_length=20)


class QualitativeCitation(BaseModel):
    source_type: Literal["edgar_10k", "edgar_10q", "news", "other"] = "other"
    reference: str = Field(..., description="Section, URL, or filing accession")
    excerpt: str | None = Field(default=None, max_length=2000)


class QualitativeFactorScore(BaseModel):
    name: str = Field(..., description="e.g. competitive_moat, management_quality")
    score_1_to_10: int = Field(..., ge=1, le=10)
    citations: list[QualitativeCitation] = Field(default_factory=list)


class QualitativeScoringOutput(BaseModel):
    """Turn 2: ~20 qualitative indicators with citations."""

    factors: list[QualitativeFactorScore] = Field(default_factory=list, max_length=30)
    narrative: str | None = Field(default=None, max_length=4000)


class FiChangeRationale(BaseModel):
    """Required when Fi inputs change outside regular quarterly rhythm."""

    trigger_event: str = Field(..., description="e.g. CEO_succession, M&A_close")
    explanation: str = Field(..., max_length=4000)
    approved: bool = Field(default=False, description="Human gate")


def default_qualitative_factor_names() -> list[str]:
    """Starter pool (~20) aligned with proposal; extend per universe."""
    return [
        "competitive_moat",
        "management_quality",
        "capital_allocation",
        "pricing_power",
        "brand_equity",
        "industry_position",
        "product_differentiation",
        "balance_sheet_strength",
        "cash_conversion",
        "capex_discipline",
        "innovation_pipeline",
        "regulatory_risk",
        "customer_concentration",
        "supplier_power",
        "esg_governance",
        "strategic_clarity",
        "execution_track_record",
        "transparency_disclosure",
        "cycle_resilience",
        "long_term_growth_optionality",
    ]
