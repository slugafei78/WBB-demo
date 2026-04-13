"""
茅台简化定性：仅 4 项，0–20 分。优先 Gemini/OpenAI，否则根据 news_digest 关键词启发式。
"""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, Field

from value_investment_agent.llm.llm_provider import gemini_api_key, resolve_llm_provider
from value_investment_agent.moutai_experiment.news_digest import load_news_digest

QUAL_NAMES = (
    "competitive_moat",
    "pricing_power",
    "brand_mindshare",
    "management_quality",
)


class MoutaiQualFour(BaseModel):
    competitive_moat: int = Field(..., ge=0, le=20)
    pricing_power: int = Field(..., ge=0, le=20)
    brand_mindshare: int = Field(..., ge=0, le=20)
    management_quality: int = Field(..., ge=0, le=20)
    rationale: str | None = None


def _heuristic_from_digest(digest_text: str) -> MoutaiQualFour:
    bump = 0
    if "提价" in digest_text or "涨价" in digest_text or "上调" in digest_text:
        bump = 3
    base_moat = 14 + min(bump, 4)
    base_price = 13 + min(bump, 5)
    base_brand = 16
    base_mgmt = 14
    return MoutaiQualFour(
        competitive_moat=min(20, base_moat),
        pricing_power=min(20, base_price),
        brand_mindshare=base_brand,
        management_quality=base_mgmt,
        rationale="heuristic: 关键词/无 API",
    )


def score_moutai_qual_four(
    *,
    quantitative_summary: str,
    llm_provider: Literal["auto", "gemini", "openai", "mock"] = "auto",
) -> MoutaiQualFour:
    digest = load_news_digest()
    if llm_provider == "mock":
        return _heuristic_from_digest(digest)
    if llm_provider == "auto" and not gemini_api_key() and not os.environ.get("OPENAI_API_KEY"):
        return _heuristic_from_digest(digest)

    from value_investment_agent.factor_pipeline.llm_qualitative import (
        _complete_json_gemini,
        _complete_json_openai,
    )

    system = (
        "You are a China A-share consumer analyst. Output ONE JSON object only with keys: "
        "competitive_moat, pricing_power, brand_mindshare, management_quality (each integer 0-20), "
        "rationale (short Chinese). "
        "competitive_moat=竞争护城河, pricing_power=提价权, brand_mindshare=消费者品牌心智, management_quality=管理层能力. "
        "Use only the provided text; neutral is ~10."
    )
    user = f"新闻与事件摘要:\n{digest[:8000]}\n\n定量上下文:\n{quantitative_summary[:4000]}\n"
    raw = "{}"
    try:
        if llm_provider == "openai":
            raw = _complete_json_openai(system, user)
        elif llm_provider == "gemini":
            raw = _complete_json_gemini(system, user)
        else:
            r = resolve_llm_provider("auto")
            if r == "gemini":
                raw = _complete_json_gemini(system, user)
            elif r == "openai":
                raw = _complete_json_openai(system, user)
    except Exception:
        raw = "{}"
    try:
        data = json.loads(raw)
        return MoutaiQualFour.model_validate(data)
    except Exception:
        return _heuristic_from_digest(digest)


def modulation_index(q: MoutaiQualFour) -> float:
    vals = [
        q.competitive_moat,
        q.pricing_power,
        q.brand_mindshare,
        q.management_quality,
    ]
    m = sum((v - 10.0) / 10.0 for v in vals) / len(vals)
    return max(-1.0, min(1.0, m))
